"""Install zip: layout + the one-line starters AOI_Manager.bat · AOI_Manager_Mini.bat (Para #64, v14.4)."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import build_install  # noqa: E402
from param_manager import __version__, deploy  # noqa: E402


class BuildInstallTest(unittest.TestCase):
    def test_zip_layout_and_starters(self):
        with tempfile.TemporaryDirectory() as d:
            py = Path(d) / "pyembed"
            py.mkdir()
            for name in ("python.exe", "pythonw.exe", "python311.dll"):
                (py / name).write_bytes(b"x")
            path = build_install.build(py, Path(d) / "out")
            self.assertEqual(path.name, f"AOI_Manager_v{__version__}_install.zip")
            with zipfile.ZipFile(path) as z:
                names = set(z.namelist())
                bats = {n: z.read(n) for n in ("AOI_Manager.bat", "AOI_Manager_Mini.bat")}
                start = z.read("AOI_Manager.pyw")
                guide = z.read("설치_안내.txt").decode("utf-8-sig")
        self.assertIn("python/pythonw.exe", names)
        # Start file at the root = the repository's start file under its new name (v14.4).
        self.assertEqual(start, (ROOT / "Camtek_AOI_manager.pyw").read_bytes())
        self.assertNotIn("Camtek_AOI_manager.pyw", names)
        self.assertNotIn("Camtek_AOI_manager.bat", names)
        # app/ still holds Camtek_AOI_manager.pyw: installed updaters before v14.4 require it.
        self.assertIn("app/Camtek_AOI_manager.pyw", names)
        for rel in deploy.files(ROOT):
            self.assertIn("app/" + rel, names)
        # The two .bat are the only scripts, at the root; nothing else of ours is a script/executable.
        ours = [n for n in names if not n.startswith("python/")]
        self.assertEqual(sorted(deploy.forbidden(ours)), ["AOI_Manager.bat", "AOI_Manager_Mini.bat"])
        # One command each, ASCII, CRLF, relative to its own folder (works in any install folder).
        expect = {"AOI_Manager.bat": 'start "" "%~dp0python\\pythonw.exe" "%~dp0AOI_Manager.pyw"',
                  "AOI_Manager_Mini.bat": 'start "" "%~dp0python\\pythonw.exe" "%~dp0AOI_Manager.pyw" --mini'}
        for name, raw in bats.items():
            text = raw.decode("ascii")
            self.assertTrue(text.endswith("\r\n"))
            lines = [ln for ln in text.split("\r\n") if ln]
            self.assertEqual(lines, ["@echo off", expect[name]])
        self.assertIn("AOI_Manager.bat 또는 AOI_Manager_Mini.bat", guide)
        self.assertNotIn("Camtek AOI Manager", guide)
        self.assertNotIn("Win + R", guide)

    def test_trial_label(self):
        """소유자 2026-11-27: 디자인 브랜치 zip = 이름 · 설정 > 정보에 시험판 표시, 버전 번호 · 정식 zip 은 그대로."""
        with tempfile.TemporaryDirectory() as d:
            py = Path(d) / "pyembed"
            py.mkdir()
            for name in ("python.exe", "pythonw.exe", "python311.dll"):
                (py / name).write_bytes(b"x")
            plain = build_install.build(py, Path(d) / "a")
            with zipfile.ZipFile(plain) as z:
                self.assertNotIn("app/" + build_install.LABEL_FILE, z.namelist())
            path = build_install.build(py, Path(d) / "b", "디자인시험판_1127")
            self.assertEqual(path.name, f"AOI_Manager_v{__version__}_디자인시험판_1127_install.zip")
            with zipfile.ZipFile(path) as z:
                self.assertEqual(z.read("app/build_label.txt").decode("utf-8").strip(), "디자인 시험판 · 11-27")
                self.assertIn("정식 판이 아닙니다", z.read("설치_안내.txt").decode("utf-8-sig"))
            with self.assertRaises(SystemExit):
                build_install.build(py, Path(d) / "c", "../x")
        self.assertNotIn(build_install.LABEL_FILE, deploy.files(ROOT))          # 저장소 · 업데이트에는 없음
        wf = (ROOT / ".github/workflows/v14.yml").read_text(encoding="utf-8")
        self.assertIn('if ("${{ github.ref_name }}" -ne "version_v14")', wf)
        self.assertIn("if: steps.ver.outputs.label == ''", wf)                  # 시험판으로는 릴리스를 만들지 않음
        cfg = (ROOT / "param_manager/desktop_config.py").read_text(encoding="utf-8")
        self.assertIn('"build_label.txt"', cfg)

    def test_bat_not_in_repository(self):
        # The starter is generated into the zip only; the repository and updates carry no .bat.
        bats = [os.path.join(dp, f) for dp, _, fs in os.walk(ROOT) if ".git" not in dp
                and "node_modules" not in dp for f in fs if f.lower().endswith((".bat", ".cmd"))]
        self.assertEqual(bats, [])


if __name__ == "__main__":
    unittest.main()
