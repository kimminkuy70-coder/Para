"""v14 Defect 분석: 엔진이 고른 폴더를 읽어 주는 다리(param_manager/defect_fs.py · webserver /api/fs/*) — 읽기 전용 · 뿌리 밖 금지 · 토큰."""
import http.client
import json
import os
import re
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from param_manager import defect_fs, webserver  # noqa: E402


def tree(base: Path):
    (base / "RCP" / "SETUP1" / "LOT_A" / "W01" / "Sub").mkdir(parents=True)
    w = base / "RCP" / "SETUP1" / "LOT_A" / "W01"
    (w / "Surface.flt").write_bytes(b"\x00" * 152)
    (w / "ColorImageGrabingInfo.ini").write_text("[a.c.1.jpeg]\nFaultX=1\n", encoding="utf-8")
    (w / "b.t.1.jpeg").write_bytes(b"\xff\xd8\xff" + b"x" * 100)
    (w / "Sub" / "deep.txt").write_text("deep", encoding="utf-8")
    (base / "RCP" / "note.ini").write_text("n", encoding="utf-8")
    (base / "outside.txt").write_text("secret", encoding="utf-8")
    return base / "RCP"


class DefectFsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = tree(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_resolve_stays_below_root(self):
        ok = defect_fs.resolve(self.root, "SETUP1/LOT_A")
        self.assertEqual(ok, self.root / "SETUP1" / "LOT_A")
        self.assertEqual(defect_fs.resolve(self.root, ""), self.root)
        for bad in ["..", "../outside.txt", "SETUP1/../../outside.txt", ".", "a//b", "/abs", "a\\b", "C:", "c:x",
                    "... ", ".. ", "...", "a\x00b", "SETUP1/./x"]:
            with self.assertRaises(ValueError, msg=bad):
                defect_fs.resolve(self.root, bad)

    def test_roots_only_existing_folders_same_id(self):
        r = defect_fs.Roots()
        a = r.add(self.root)
        self.assertEqual(a["name"], "RCP")
        self.assertEqual(a["path"], str(self.root))
        self.assertEqual(r.add(str(self.root))["id"], a["id"])
        self.assertEqual(r.get(a["id"]), self.root)
        with self.assertRaises(ValueError):
            r.add(self.root / "nope")
        with self.assertRaises(KeyError):
            r.get("nope")

    def test_list_stat_walk(self):
        d = defect_fs.list_dir(self.root / "SETUP1" / "LOT_A" / "W01")
        self.assertEqual(d["dirs"], ["Sub"])
        self.assertEqual([f[0] for f in d["files"]], ["b.t.1.jpeg", "ColorImageGrabingInfo.ini", "Surface.flt"])
        self.assertEqual(d["files"][2][1], 152)
        s = defect_fs.stat(self.root / "SETUP1" / "LOT_A" / "W01" / "Surface.flt")
        self.assertEqual((s["kind"], s["size"], s["name"]), ("file", 152, "Surface.flt"))
        self.assertEqual(defect_fs.stat(self.root / "SETUP1")["kind"], "dir")
        w = defect_fs.walk(self.root)
        self.assertFalse(w["truncated"])
        self.assertEqual(sorted(f[0] for f in w["files"]), sorted([
            "note.ini", "SETUP1/LOT_A/W01/Surface.flt", "SETUP1/LOT_A/W01/ColorImageGrabingInfo.ini",
            "SETUP1/LOT_A/W01/b.t.1.jpeg", "SETUP1/LOT_A/W01/Sub/deep.txt"]))
        self.assertTrue(defect_fs.walk(self.root, limit=2)["truncated"])

    def test_module_has_no_write_paths(self):
        src = Path(defect_fs.__file__).read_text(encoding="utf-8")
        code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
        body = code.split('"""', 2)[2]          # docstring 밖
        for pat in [r"\.write\(", r"os\.remove", r"os\.unlink", r"shutil", r"\.rename\(", r"rmdir", r"mkdir", r"replace\(",
                    r"open\([^)]*['\"][wax+]"]:
            self.assertIsNone(re.search(pat, body), pat)


class Picker(webserver.Natives):
    target = None

    def pick_folder(self, args):
        return str(Picker.target) if Picker.target else None


class WebFsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.root = tree(base)
        dist = base / "dist"
        dist.mkdir()
        (dist / "index.html").write_text("ok", encoding="utf-8")
        Picker.target = self.root
        self.srv = webserver.WebServer(dist=dist, natives_factory=Picker).start()
        threading.Thread(target=self._drain, daemon=True).start()

    def _drain(self):
        while self.srv.bridge.readline():
            pass
        self.srv.shutdown()

    def tearDown(self):
        self.srv.request_exit()
        self.srv.bridge.closed.wait(3)
        self.tmp.cleanup()

    def req(self, method, path, body=None, token=True, ctype="application/json"):
        c = http.client.HTTPConnection("127.0.0.1", self.srv.port, timeout=5)
        h = {"Host": f"127.0.0.1:{self.srv.port}"}
        if token:
            h["X-Para-Token"] = self.srv.token
        if body is not None:
            h["Content-Type"] = ctype
        c.request(method, path, body=json.dumps(body).encode() if body is not None else None, headers=h)
        r = c.getresponse()
        data = r.read()
        c.close()
        return r.status, data

    def pick(self):
        st, data = self.req("POST", "/api/native", {"command": "defect_pick", "args": {}})
        self.assertEqual(st, 200)
        return json.loads(data)["result"]

    def test_pick_then_read_only_below_it(self):
        R = self.pick()
        self.assertEqual((R["name"], R["path"]), ("RCP", str(self.root)))
        q = lambda kind, p: f"/api/fs/{kind}?r={R['id']}&p={p}"   # noqa: E731
        st, d = self.req("GET", q("list", "SETUP1/LOT_A/W01"))
        self.assertEqual(st, 200)
        self.assertEqual(json.loads(d)["dirs"], ["Sub"])
        st, d = self.req("GET", q("stat", "SETUP1/LOT_A/W01/ColorImageGrabingInfo.ini"))   # .ini 도 그대로(브라우저 핸들과 다름)
        self.assertEqual((st, json.loads(d)["kind"]), (200, "file"))
        st, d = self.req("GET", q("file", "SETUP1/LOT_A/W01/b.t.1.jpeg"))
        self.assertEqual((st, d[:3]), (200, b"\xff\xd8\xff"))
        st, d = self.req("GET", q("walk", ""))
        self.assertEqual(len(json.loads(d)["files"]), 5)
        self.assertEqual(self.req("GET", q("stat", "SETUP1/none.ini"))[0], 404)
        self.assertEqual(self.req("GET", q("file", "SETUP1"))[0], 404)                       # 폴더는 파일로 못 읽음
        for bad in ["..%2Foutside.txt", "../outside.txt", "SETUP1/..%2F..%2Foutside.txt", "%2E%2E"]:
            self.assertEqual(self.req("GET", q("file", bad))[0], 400, bad)
        self.assertEqual(self.req("GET", f"/api/fs/list?r=nope&p=")[0], 404)                    # 고르지 않은 뿌리
        self.assertEqual(self.req("GET", q("list", ""), token=False)[0], 403)                # 토큰 없음
        self.assertEqual(self.req("GET", q("remove", "note.ini"))[0], 404)                   # 쓰기 · 지우기 요청 없음
        self.assertEqual(self.req("POST", q("file", "note.ini"), {"x": 1})[0], 404)
        self.assertTrue((self.root / "note.ini").exists())

    def test_too_large_and_cancel(self):
        R = self.pick()
        old = defect_fs.FILE_MAX
        defect_fs.FILE_MAX = 10
        try:
            self.assertEqual(self.req("GET", f"/api/fs/file?r={R['id']}&p=SETUP1/LOT_A/W01/Surface.flt")[0], 413)
        finally:
            defect_fs.FILE_MAX = old
        Picker.target = None
        self.assertIsNone(self.pick())                                                       # 고르기 취소


if __name__ == "__main__":
    unittest.main(verbosity=1)
