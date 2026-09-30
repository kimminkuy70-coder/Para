"""상세 진단 로그: 시작 전 기록 버퍼→파일 연결, import 시간, 화면 타임라인, zip 묶기, 회전."""
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from param_manager import desktop_diag as diag  # noqa: E402


class DiagTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        diag._path = ""
        diag._buffer.clear()

    def tearDown(self):
        diag._path = ""
        self.tmp.cleanup()

    def test_buffer_then_attach_and_bundle(self):
        diag.engine_started()
        diag.start_import_timer()
        try:
            old = diag.IMPORT_MS
            diag.IMPORT_MS = 0.0
            sys.modules.pop("colorsys", None)
            import colorsys  # noqa: F401 - any stdlib module not yet imported
        finally:
            diag.IMPORT_MS = old
            diag.stop_import_timer()
        with self.assertRaises(ValueError):
            with diag.timed("설정 읽기"):
                raise ValueError("x")
        logs = os.path.join(self.tmp.name, "Logs")
        path = diag.attach(logs)
        diag.client_events({"events": [{"t": 1759190000000, "text": "화면(웹뷰) 로딩 시작"}, {"bad": 1}]})
        text = Path(path).read_text(encoding="utf-8")
        for needle in ("엔진 시작", "import colorsys", "모듈 로딩 합계", "설정 읽기", "실패 ValueError", "[화면 ", "화면(웹뷰) 로딩 시작"):
            self.assertIn(needle, text)
        self.assertLess(text.index("엔진 시작"), text.index("[화면 "))   # buffered lines come first
        with self.assertRaises(ValueError):
            diag.client_events({"events": "x"})
        z = diag.bundle(logs)
        with zipfile.ZipFile(z) as zf:
            self.assertIn(diag.FILENAME, zf.namelist())

    def test_rotation(self):
        path = diag.attach(os.path.join(self.tmp.name, "L"))
        old = diag.MAX_BYTES
        diag.MAX_BYTES = 100
        try:
            for i in range(10):
                diag.event(f"줄 {i} " + "x" * 50)
        finally:
            diag.MAX_BYTES = old
        self.assertTrue(os.path.exists(path + ".1"))
        self.assertLess(os.path.getsize(path), 400)


if __name__ == "__main__":
    unittest.main()
