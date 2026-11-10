"""v13 local web server safety (docs/V13_계획.md 11-2 ③): 127.0.0.1 only, token, Host/Origin, json-only."""
import http.client
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from param_manager import webserver  # noqa: E402


class Echo:
    """Stand-in engine: answers each request line with a completed event."""

    def __init__(self, server):
        self.server = server
        threading.Thread(target=self.loop, daemon=True).start()

    def loop(self):
        while True:
            line = self.server.bridge.readline()
            if not line:
                self.server.shutdown()
                return
            req = json.loads(line)
            self.server.bridge.write(json.dumps({"version": 1, "id": req["id"], "event": "completed"}).encode() + b"\n")


class WebServerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        dist = Path(self.tmp.name) / "dist"
        dist.mkdir()
        (dist / "index.html").write_text("<html>ok</html>", encoding="utf-8")
        (Path(self.tmp.name) / "secret.txt").write_text("no", encoding="utf-8")
        self.srv = webserver.WebServer(dist=dist, upload_dir=Path(self.tmp.name) / "up").start()
        Echo(self.srv)

    def tearDown(self):
        if not self.srv.bridge.closed.is_set():
            self.srv.request_exit()
            self.srv.bridge.closed.wait(3)
        self.tmp.cleanup()

    def call(self, method, path, body=None, headers=None, host=None):
        c = http.client.HTTPConnection("127.0.0.1", self.srv.port, timeout=5)
        h = {"Host": host or f"127.0.0.1:{self.srv.port}"}
        h.update(headers or {})
        c.request(method, path, body=body, headers=h)
        r = c.getresponse()
        data = r.read()
        c.close()
        return r.status, data

    def auth(self, extra=None):
        h = {"X-Para-Token": self.srv.token, "Content-Type": "application/json"}
        h.update(extra or {})
        return h

    def test_binds_loopback_only_and_url_has_token(self):
        self.assertEqual(self.srv.httpd.server_address[0], "127.0.0.1")
        self.assertTrue(self.srv.url.startswith(f"http://127.0.0.1:{self.srv.port}/?t="))
        self.assertGreaterEqual(len(self.srv.token), 32)

    def test_static_index_and_no_escape(self):
        self.assertEqual(self.call("GET", "/")[0], 200)
        self.assertEqual(self.call("GET", "/../secret.txt")[0], 404)
        self.assertEqual(self.call("GET", "/%2e%2e/secret.txt")[0], 404)

    def test_host_header_must_be_ours(self):          # DNS rebinding
        self.assertEqual(self.call("GET", "/", host="evil.example:80")[0], 421)
        self.assertEqual(self.call("POST", "/api/send", b"{}", self.auth(), host="evil.example")[0], 421)

    def test_token_required(self):
        body = json.dumps({"version": 1, "id": 1, "method": "x", "params": {}}).encode()
        self.assertEqual(self.call("POST", "/api/send", body, {"Content-Type": "application/json"})[0], 403)
        self.assertEqual(self.call("POST", "/api/send", body, self.auth({"X-Para-Token": "wrong"}))[0], 403)
        self.assertEqual(self.call("GET", "/api/events?t=wrong")[0], 403)
        self.assertEqual(self.call("POST", "/api/send", body, self.auth())[0], 200)

    def test_foreign_origin_and_non_json_refused(self):
        body = b'{"version":1,"id":2,"method":"x","params":{}}'
        self.assertEqual(self.call("POST", "/api/send", body, self.auth({"Origin": "https://evil.example"}))[0], 403)
        self.assertEqual(self.call("POST", "/api/send", body, self.auth({"Content-Type": "text/plain"}))[0], 415)
        ok = self.call("POST", "/api/send", body, self.auth({"Origin": f"http://127.0.0.1:{self.srv.port}"}))
        self.assertEqual(ok[0], 200)

    def test_event_stream_carries_engine_reply(self):
        c = http.client.HTTPConnection("127.0.0.1", self.srv.port, timeout=5)
        c.request("GET", f"/api/events?t={self.srv.token}", headers={"Host": f"127.0.0.1:{self.srv.port}"})
        r = c.getresponse()
        self.assertEqual(r.status, 200)
        self.assertEqual(r.fp.readline(), b": ok\n")
        for _ in range(50):
            if self.srv.bridge.subscribers():
                break
            time.sleep(0.02)
        self.call("POST", "/api/send", b'{"version":1,"id":7,"method":"x","params":{}}', self.auth())
        r.fp.readline()
        line = r.fp.readline()
        self.assertEqual(json.loads(line[len(b"data: "):]), {"version": 1, "id": 7, "event": "completed"})
        c.close()

    def test_upload_zip_only_into_upload_dir(self):
        st, data = self.call("POST", "/api/upload?name=..%2F..%2Fx.zip", b"PK\x03\x04", {"X-Para-Token": self.srv.token})
        self.assertEqual(st, 200)
        path = Path(json.loads(data)["path"])
        self.assertTrue(path.is_file())
        self.assertIn(Path(self.tmp.name) / "up", path.parents)
        self.assertEqual(self.call("POST", "/api/upload?name=a.exe", b"MZ", {"X-Para-Token": self.srv.token})[0], 415)
        self.assertEqual(self.call("POST", "/api/upload?name=a.zip", b"PK", {})[0], 403)

    def test_native_background_and_exit(self):
        st, _ = self.call("POST", "/api/native", json.dumps({"command": "set_background", "args": {"enabled": True, "tooltip": "t"}}).encode(), self.auth())
        self.assertEqual(st, 200)
        self.assertTrue(self.srv.natives.background["enabled"])
        self.assertEqual(self.call("POST", "/api/native", b'{"command":"rm"}', self.auth())[0], 404)
        self.call("POST", "/api/native", b'{"command":"app_exit"}', self.auth())
        self.assertTrue(self.srv.bridge.closed.wait(3))

    def test_window_closed_without_tray_exits(self):
        old = webserver.IDLE_EXIT_SEC
        webserver.IDLE_EXIT_SEC = 0.1
        try:
            self.srv.bridge.subscribe()
            q = self.srv.bridge._subs[0]
            self.srv.bridge.unsubscribe(q)
            self.assertTrue(self.srv.bridge.closed.wait(6))
        finally:
            webserver.IDLE_EXIT_SEC = old


if __name__ == "__main__":
    unittest.main()
