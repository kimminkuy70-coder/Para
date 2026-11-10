"""v13 local web server: the screen (Edge app window) <-> the analysis engine.

Replaces the Tauri shell. Standard library only and imported first, so the page can
be served at once while the heavy engine modules load on a worker thread
(`desktop_boot.load_with_progress`, unchanged from v12).

    browser --POST /api/send (one JSON request)-->  engine input queue  --> desktop_ipc.serve
    browser <--GET /api/events (server-sent events)-- engine output lines <-- Session.emit

Safety (docs/V13_계획.md 11-2 ③):
- bound to 127.0.0.1 only; other PCs cannot connect.
- every API call needs the per-run random token (header ``X-Para-Token``, or ``t`` in the
  query for the event stream, which cannot carry headers).
- Host must be 127.0.0.1/localhost with our port (DNS rebinding), a present Origin must be ours,
  POST bodies must be ``application/json`` (except the file upload, which also needs the token).
- static files only from the built screen folder (no path escape), no directory listing.
"""
from __future__ import annotations

import hmac
import json
import os
import queue
import re
import secrets
import shutil
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

MAX_FRAME = 4 * 1024 * 1024            # same as desktop_ipc.MAX_FRAME
MAX_UPLOAD = 2 * 1024 * 1024 * 1024    # dropped cache zip (written to local Temp only)
PING_SEC = 15.0
FIRST_CONNECT_SEC = 120.0              # Edge may start slowly on a scanned PC
IDLE_EXIT_SEC = 20.0                   # window closed (not a reload) and no tray residency
DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8", ".json": "application/json", ".svg": "image/svg+xml",
         ".png": "image/png", ".ico": "image/x-icon", ".woff2": "font/woff2", ".woff": "font/woff",
         ".otf": "font/otf", ".ttf": "font/ttf", ".map": "application/json"}
CLOSED = {"version": 1, "id": None, "event": "error", "code": "engine_closed"}
_SAFE_NAME = re.compile(r"[^0-9A-Za-z가-힣._ -]")


class Bridge:
    """Engine side of the link: a readline() input and a write()/flush() output."""

    def __init__(self):
        self._in: queue.Queue = queue.Queue()
        self._subs: list[queue.Queue] = []
        self._lock = threading.Lock()
        self._buf = b""
        self.closed = threading.Event()
        self.last_seen = time.monotonic()
        self.ever_connected = False

    # engine input (desktop_boot.FrameQueue reads this like stdin)
    def readline(self, _limit=-1) -> bytes:
        return self._in.get()

    def send(self, frame: bytes):
        self._in.put(frame.rstrip(b"\r\n") + b"\n")

    def end_input(self):
        self._in.put(b"")

    # engine output (Session.emit writes whole JSON lines)
    def write(self, data: bytes):
        with self._lock:
            self._buf += data
            *lines, self._buf = self._buf.split(b"\n")
            subs = list(self._subs)
        for line in lines:
            if line.strip():
                for q in subs:
                    q.put(line)
        return len(data)

    def flush(self):
        pass

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue()
        with self._lock:
            self._subs.append(q)
            self.ever_connected = True
        return q

    def unsubscribe(self, q):
        with self._lock:
            if q in self._subs:
                self._subs.remove(q)
            self.last_seen = time.monotonic()

    def subscribers(self) -> int:
        with self._lock:
            return len(self._subs)

    def close(self):
        """Engine finished: tell every open page, then end their streams."""
        line = json.dumps(CLOSED).encode()
        with self._lock:
            subs = list(self._subs)
        for q in subs:
            q.put(line)
            q.put(None)
        self.closed.set()


def safe_name(name: str) -> str:
    base = _SAFE_NAME.sub("_", os.path.basename(name or ""))[:120].strip(" .")
    return base or "upload.zip"


class Natives:
    """What the Tauri shell did natively. Windows parts are filled in by `winnative` (step 3)."""

    def __init__(self, server: "WebServer"):
        self.server = server
        self.background = {"enabled": False, "tooltip": ""}

    def pick_folder(self, args):
        return None

    def pick_file(self, args):
        return None

    def set_background(self, args):
        self.background = {"enabled": bool(args.get("enabled")), "tooltip": str(args.get("tooltip", ""))[:120]}
        return None

    def app_exit(self, args):
        self.server.request_exit()
        return None

    def call(self, command: str, args: dict):
        fn = {"pick_folder": self.pick_folder, "pick_file": self.pick_file,
              "set_background": self.set_background, "app_exit": self.app_exit}.get(command)
        if fn is None:
            raise KeyError(command)
        return fn(args or {})


class WebServer:
    def __init__(self, dist: Path = DIST, port: int = 0, token: str | None = None,
                 upload_dir: Path | None = None, natives_factory=Natives):
        self.dist = Path(dist).resolve()
        self.token = token or secrets.token_urlsafe(32)
        self.bridge = Bridge()
        self.upload_dir = Path(upload_dir) if upload_dir else Path(tempfile.gettempdir()) / "CamtekAOI_upload"
        self.exit_requested = threading.Event()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", port), _handler(self))
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        self.natives = natives_factory(self)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/?t={self.token}"

    def hosts(self):
        return {f"127.0.0.1:{self.port}", f"localhost:{self.port}"}

    def origins(self):
        return {f"http://{h}" for h in self.hosts()}

    def token_ok(self, value: str | None) -> bool:
        return bool(value) and hmac.compare_digest(str(value), self.token)

    def request_exit(self):
        self.exit_requested.set()
        self.bridge.end_input()          # serve() sees EOF, closes the session (waits for saves)

    def start(self):
        threading.Thread(target=self.httpd.serve_forever, name="http", daemon=True).start()
        threading.Thread(target=self._idle_watch, name="idle", daemon=True).start()
        return self

    def _idle_watch(self):
        started = time.monotonic()
        while not self.bridge.closed.wait(2.0):
            if self.exit_requested.is_set():
                continue
            b = self.bridge
            if b.subscribers():
                continue
            if self.natives.background.get("enabled"):
                continue                   # window closed but a watch keeps the app in the tray
            if not b.ever_connected:
                if time.monotonic() - started > FIRST_CONNECT_SEC:
                    self.request_exit()
            elif time.monotonic() - b.last_seen > IDLE_EXIT_SEC:
                self.request_exit()

    def shutdown(self):
        self.bridge.close()
        time.sleep(0.2)                    # let open pages receive engine_closed
        self.httpd.shutdown()
        self.httpd.server_close()


def _handler(server: WebServer):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "Para"
        sys_version = ""

        def log_message(self, *args):    # no console (pythonw) and no access log
            pass

        # ---- helpers
        def _guard(self) -> bool:
            if self.headers.get("Host", "") not in server.hosts():
                self._reply(421, b"")
                return False
            origin = self.headers.get("Origin")
            if origin is not None and origin not in server.origins():
                self._reply(403, b"")
                return False
            return True

        def _reply(self, code, body: bytes, ctype="application/json", extra=None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, code, data):
            self._reply(code, json.dumps(data, ensure_ascii=False).encode("utf-8"))

        def _body(self, limit) -> bytes | None:
            try:
                n = int(self.headers.get("Content-Length", "-1"))
            except ValueError:
                n = -1
            if n < 0 or n > limit:
                self._json(413, {"error": "too_large"})
                return None
            return self.rfile.read(n)

        # ---- GET: static files + event stream
        def do_GET(self):
            if not self._guard():
                return
            parts = urlsplit(self.path)
            if parts.path == "/api/events":
                return self._events(parse_qs(parts.query).get("t", [""])[0])
            if parts.path.startswith("/api/"):
                return self._json(404, {"error": "not_found"})
            rel = "index.html" if parts.path in ("", "/") else parts.path.lstrip("/")
            target = (server.dist / rel).resolve()
            if server.dist not in target.parents or not target.is_file():
                return self._reply(404, b"", "text/plain")
            body = target.read_bytes()
            self._reply(200, body, TYPES.get(target.suffix.lower(), "application/octet-stream"))

        do_HEAD = do_GET

        def _events(self, token):
            if not server.token_ok(token):
                return self._json(403, {"error": "token"})
            q = server.bridge.subscribe()
            try:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(b": ok\n\n")
                self.wfile.flush()
                self.close_connection = True
                while True:
                    try:
                        line = q.get(timeout=PING_SEC)
                    except queue.Empty:
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
                        continue
                    if line is None:
                        break
                    self.wfile.write(b"data: " + line + b"\n\n")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                server.bridge.unsubscribe(q)

        # ---- POST: requests, native commands, file upload
        def do_POST(self):
            if not self._guard():
                return
            if not server.token_ok(self.headers.get("X-Para-Token")):
                return self._json(403, {"error": "token"})
            parts = urlsplit(self.path)
            if parts.path == "/api/upload":
                return self._upload(parse_qs(parts.query).get("name", [""])[0])
            if not self.headers.get("Content-Type", "").startswith("application/json"):
                return self._json(415, {"error": "json_only"})
            body = self._body(MAX_FRAME)
            if body is None:
                return
            if parts.path == "/api/send":
                if server.bridge.closed.is_set() or server.exit_requested.is_set():
                    return self._json(503, {"error": "engine_busy_or_closed"})
                try:
                    json.loads(body.decode("utf-8"))
                except (ValueError, UnicodeError):
                    return self._json(400, {"error": "invalid_json"})
                server.bridge.send(body)
                return self._json(200, {"ok": True})
            if parts.path == "/api/native":
                try:
                    req = json.loads(body.decode("utf-8"))
                    result = server.natives.call(str(req.get("command", "")), req.get("args") or {})
                except KeyError:
                    return self._json(404, {"error": "unknown_command"})
                except (ValueError, UnicodeError, AttributeError):
                    return self._json(400, {"error": "invalid_json"})
                return self._json(200, {"result": result})
            return self._json(404, {"error": "not_found"})

        def _upload(self, name):
            """A file dropped on the window (browsers give contents, not paths): local Temp only."""
            name = safe_name(name)
            if not name.lower().endswith(".zip"):
                return self._json(415, {"error": "zip_only"})
            try:
                n = int(self.headers.get("Content-Length", "-1"))
            except ValueError:
                n = -1
            if n < 0 or n > MAX_UPLOAD:
                return self._json(413, {"error": "too_large"})
            folder = Path(tempfile.mkdtemp(prefix="drop_", dir=_ensure(server.upload_dir)))
            path = folder / name
            with open(path, "wb") as fh:
                left = n
                while left > 0:
                    chunk = self.rfile.read(min(left, 1 << 20))
                    if not chunk:
                        break
                    fh.write(chunk)
                    left -= len(chunk)
            if left:
                shutil.rmtree(folder, ignore_errors=True)
                return self._json(400, {"error": "incomplete"})
            return self._json(200, {"path": str(path)})

    return Handler


def _ensure(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


def run_engine(server: WebServer, loader, diag=None, startup_prefix="엔진 시작"):
    """Load the engine on a worker (progress events to waiting requests) and serve until exit."""
    from .desktop_boot import FrameQueue, load_with_progress
    started = time.perf_counter()
    frames = FrameQueue(server.bridge, MAX_FRAME)
    try:
        ipc = load_with_progress(loader, frames, server.bridge, diag)
        if diag is not None:
            diag.stop_import_timer()
        ipc.serve(frames, server.bridge, startup=f"{startup_prefix} — 모듈 로딩 {time.perf_counter() - started:.1f}s")
    finally:
        server.shutdown()
