"""Wafer Map 전용판(특수 버전) 엔진 — `Wafer Map 수정하기` 하나만 있는 stdio 프로토콜.

본 앱 엔진(`desktop_ipc`)과 같은 프로토콜(version 1 · 늘어나는 id · accepted/progress/completed/error)을
쓰지만 Wafer Map 변환에 필요한 요청만 받는다. 이 모듈이 import 하는 프로그램 모듈은
`wafermap` · `desktop_wafermap` · `desktop_progress` · `desktop_diag` 뿐이라, PyInstaller 로 묶으면
다른 기능(장비 수집 · Recipe · Batch Report · Commonality · 자동 감시 · 자동 업데이트)의 코드는 패키지에
들어가지 않는다(`tools/wafermap_edition.py` 가 빌드 때 나머지를 명시적으로 뺀다 — 테스트가 고정).

보안 원칙(본 앱과 같음): 원본은 읽기만(변환은 늘 새 파일), 네트워크 포트를 열지 않음(stdin/stdout 만),
인터넷 접속 없음, 자동 업데이트(배치 스크립트로 폴더 교체) 없음, 연 파일은 이번 변환의 결과 폴더 안만.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path

from . import __version__, desktop_diag, desktop_progress
from .desktop_wafermap import DesktopWaferMap

VERSION = 1
MAX_FRAME = 4 * 1024 * 1024
PRODUCT = "Camtek AOI Wafer Map"
APP_DIR = "CamtekAOI_WaferMap"           # %LOCALAPPDATA%\CamtekAOI_WaferMap\Logs (본 앱 폴더와 섞지 않음)
ALLOWED = {
    "contract": set(), "configuration": set(), "open_path": {"path", "reveal"}, "diag_client": {"events"},
    "wm_scan": {"root", "mode"}, "wm_start": {"ids", "output"}, "wm_state": set(),
    "wm_convert": {"index"}, "wm_image": {"index", "kind", "data"}, "wm_reset": set(),
}
METHODS = set(ALLOWED)
OPENABLE = {".xlsx", ".xlsm", ".txt", ".png"}
MAX_PATH = 4096


def local_root() -> str:
    """로그 폴더의 부모 — 설치 폴더 · OneDrive 가 아닌 사용자 로컬 앱 데이터."""
    base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, APP_DIR)


def logs_dir() -> str:
    return os.path.join(local_root(), "Logs")


def log_failure(method: str, exc: BaseException) -> None:
    """오류 traceback 을 로컬 Logs 에만 남긴다(경로 · 원문 내용은 화면에 보내지 않음). 실패해도 조용히."""
    try:
        os.makedirs(logs_dir(), exist_ok=True)
        with open(os.path.join(logs_dir(), "오류_로그.txt"), "a", encoding="utf-8") as fh:
            fh.write(f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}] {method} 실패 (v{__version__})\n")
            fh.write("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
    except Exception:  # noqa: BLE001 - logging must never break the protocol
        pass


def failure_code(exc: BaseException) -> str:
    if isinstance(exc, PermissionError):
        return "access_denied"
    if isinstance(exc, FileNotFoundError):
        return "file_missing"
    if isinstance(exc, OSError):
        return "io_failed"
    return "engine_failed"


def encoded(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


class Session:
    def __init__(self, output):
        self.output = output
        self.lock = threading.RLock()
        self.wafermap = DesktopWaferMap()
        self.busy = None                    # request id of the running worker (one job at a time)
        self.workers = set()
        self.closed = False
        self.last_id = 0

    # ------------------------------------------------------------ protocol
    def emit(self, request_id, event, **data):
        with self.lock:
            payload = encoded(dict(version=VERSION, id=request_id, event=event, **data))
            if len(payload) > MAX_FRAME:
                payload = encoded(dict(version=VERSION, id=request_id, event="error", code="response_too_large"))
            self.output.write(payload)
            self.output.flush()

    def handle(self, request):
        request_id = None
        try:
            if not isinstance(request, dict) or set(request) != {"version", "id", "method", "params"}:
                raise ValueError("Invalid request envelope")
            request_id = request["id"]
            if type(request_id) is not int or not 1 <= request_id <= 2**53 - 1 or request_id <= self.last_id:
                request_id = None
                raise ValueError("Request ids must be increasing safe integers")
            self.last_id = request_id
            if type(request["version"]) is not int or request["version"] != VERSION:
                raise ValueError("Unsupported protocol version")
            method, params = request["method"], request["params"]
            # 이 판에 없는 기능의 요청은 이름부터 거절한다(본 앱 요청을 보내도 아무것도 하지 않음).
            if not isinstance(method, str) or method not in METHODS or not isinstance(params, dict):
                raise ValueError("Unsupported method or params")
            if set(params) - ALLOWED[method]:
                raise ValueError("Unexpected parameters")
            with self.lock:
                if self.closed:
                    raise ValueError("Session closed")
                self.route(request_id, method, params)
        except (ValueError, TypeError, KeyError) as exc:
            self.emit(request_id, "error", code="invalid_request", message=str(exc))
        except Exception as exc:  # noqa: BLE001 - classified, never exposes paths
            log_failure(request.get("method") if isinstance(request, dict) else "?", exc)
            self.emit(request_id, "error", code=failure_code(exc))

    def route(self, rid, method, params):
        wm = self.wafermap
        if method == "contract":
            self.emit(rid, "completed", methods=sorted(METHODS), max_frame=MAX_FRAME, product=PRODUCT)
        elif method == "configuration":
            self.emit(rid, "completed", product=PRODUCT, app_version=__version__, local_root=local_root(),
                      logs=logs_dir(), machines=[])
        elif method == "diag_client":
            self.emit(rid, "completed", diag=desktop_diag.client_events(params))
        elif method == "open_path":
            self.emit(rid, "completed", opened=open_result(params))
        elif method in ("wm_scan", "wm_convert"):
            # 폴더 탐색(장비 공유일 수 있음) · 파일 하나 변환 = worker. 입력 스레드는 막지 않는다.
            action = wm.scan if method == "wm_scan" else wm.convert
            self.background(rid, lambda: action(params), read_only=method == "wm_scan")
        elif method == "wm_reset" and self.busy is not None:
            wm.cancel.set()              # 폴더 탐색을 멈춘다 — 진행 중 단계는 스스로 끝난다
            self.emit(rid, "completed", wafermap=dict(cancelling=True))
        else:
            if self.busy is not None and method == "wm_start":
                raise ValueError("Wafer Map 작업이 아직 진행 중입니다. 끝난 뒤 다시 시도하세요.")
            quick = {"wm_state": wm.view, "wm_start": lambda: wm.start(params),
                     "wm_image": lambda: wm.image(params), "wm_reset": lambda: wm.reset(params)}
            self.emit(rid, "completed", wafermap=quick[method]())

    def background(self, rid, action, read_only=False):
        if self.busy is not None:
            raise ValueError("Wafer Map 작업이 아직 진행 중입니다. 끝난 뒤 다시 시도하세요.")
        self.busy = rid
        self.emit(rid, "accepted")

        def step(message):
            self.emit(rid, "progress", message=message)

        def work():
            desktop_progress.set_reporter(step)
            try:
                value = action()
                with self.lock:
                    self.busy = None
                    self.emit(rid, "completed", wafermap=value)
            except Exception as exc:  # noqa: BLE001 - reported to the screen below
                if not isinstance(exc, ValueError):
                    log_failure("wafermap", exc)
                with self.lock:
                    self.busy = None
                    self.emit(rid, "error", code="wafermap_failed",
                              message=str(exc) if isinstance(exc, ValueError)
                              else "Wafer Map 변환을 완료하지 못했습니다. 폴더 연결과 저장 공간을 확인하세요.")
            finally:
                desktop_progress.set_reporter(None)
                self.workers.discard(threading.current_thread())

        thread = threading.Thread(target=work, daemon=True)
        thread.read_only = read_only
        self.workers.add(thread)
        thread.start()

    def close(self):
        with self.lock:
            self.closed = True
            self.wafermap.cancel.set()
        for worker in list(self.workers):
            if not getattr(worker, "read_only", False):
                worker.join()            # 쓰던 결과 파일은 끝까지 쓴다(중간에 끊지 않음)


# ---------------------------------------------------------------- 결과 열기
def _roots():
    """열어도 되는 폴더 = 이번 변환의 결과 위치(원본과 같은 폴더 또는 사용자가 고른 폴더)."""
    return [Path(p) for p in DesktopWaferMap.extra_roots]


def resolve_openable(raw) -> Path:
    if not isinstance(raw, str) or not raw.strip() or len(raw) > MAX_PATH or "\0" in raw:
        raise ValueError("열 파일 경로를 확인하세요")
    path = Path(raw).absolute()
    if not path.exists():
        raise ValueError("파일이 없습니다. 이동되었거나 삭제되었을 수 있습니다.")
    if any(p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction()) for p in (path, *path.parents)):
        raise ValueError("연결 경로는 열 수 없습니다")
    if path.is_file() and path.suffix.lower() not in OPENABLE:
        raise ValueError("이 종류의 파일은 열 수 없습니다")
    if not path.is_file() and not path.is_dir():
        raise ValueError("파일 또는 폴더만 열 수 있습니다")
    real = path.resolve()
    if not any(real == root.resolve() or real.is_relative_to(root.resolve()) for root in _roots()):
        raise ValueError("이번에 변환한 결과 폴더 안의 파일만 열 수 있습니다")
    return path


def open_result(params) -> dict:
    if type(params.get("reveal", False)) is not bool:
        raise ValueError("열기 요청을 확인하세요")
    path = resolve_openable(params.get("path"))
    reveal = params.get("reveal", False)
    if os.name == "nt":
        if reveal and path.is_file():
            subprocess.Popen(["explorer.exe", "/select,", str(path)])   # 고정 프로그램 + 경로 인자 하나, shell 없음
        else:
            os.startfile(str(path.parent if reveal else path))         # noqa: S606 - Windows only
    else:
        opener = shutil.which("xdg-open") or shutil.which("open")
        if not opener:
            raise ValueError("이 환경에서는 파일을 열 수 없습니다")
        subprocess.Popen([opener, str(path.parent if reveal and path.is_file() else path)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return dict(opened=str(path))


# ---------------------------------------------------------------- 입력 루프
def serve(source, output, startup=""):
    session = Session(output)
    try:
        desktop_diag.attach(logs_dir())
    except Exception:  # noqa: BLE001 - diagnostics are best effort
        pass
    if startup:
        desktop_diag.event(startup)
    try:
        while not session.closed:
            frame = source.readline(MAX_FRAME + 1)
            if not frame:
                break
            if len(frame) > MAX_FRAME:
                session.emit(None, "error", code="frame_too_large")
                break                    # fail closed
            try:
                request = json.loads(frame.decode("utf-8"), parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            except (ValueError, UnicodeError, RecursionError):
                session.emit(None, "error", code="invalid_json")
                continue
            started = time.monotonic()
            session.handle(request)
            if time.monotonic() - started >= 0.5:
                desktop_diag.event(f"요청 처리 {request.get('method') if isinstance(request, dict) else '?'} "
                                   f"{(time.monotonic() - started) * 1000:.0f}ms")
    finally:
        session.close()


if __name__ == "__main__":
    serve(sys.stdin.buffer, sys.stdout.buffer)
