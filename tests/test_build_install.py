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

    def test_bat_not_in_repository(self):
        # The starter is generated into the zip only; the repository and updates carry no .bat.
        bats = [os.path.join(dp, f) for dp, _, fs in os.walk(ROOT) if ".git" not in dp
                and "node_modules" not in dp for f in fs if f.lower().endswith((".bat", ".cmd"))]
        self.assertEqual(bats, [])


if __name__ == "__main__":
    unittest.main()
