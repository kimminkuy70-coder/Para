"""v13 install zip: layout + the one-line starter .bat (Para #64)."""
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
    def test_zip_layout_and_starter(self):
        with tempfile.TemporaryDirectory() as d:
            py = Path(d) / "pyembed"
            py.mkdir()
            for name in ("python.exe", "pythonw.exe", "python311.dll"):
                (py / name).write_bytes(b"x")
            path = build_install.build(py, Path(d) / "out")
            self.assertEqual(path.name, f"Camtek_AOI_manager_v{__version__}_install.zip")
            with zipfile.ZipFile(path) as z:
                names = set(z.namelist())
                bat = z.read("Camtek_AOI_manager.bat")
                guide = z.read("설치_안내.txt").decode("utf-8-sig")
        self.assertIn("python/pythonw.exe", names)
        self.assertIn("Camtek_AOI_manager.pyw", names)
        for rel in deploy.files(ROOT):
            self.assertIn("app/" + rel, names)
        # The .bat is the only script, at the root; nothing else of ours is a script/executable.
        ours = [n for n in names if not n.startswith("python/")]
        self.assertEqual(deploy.forbidden(ours), ["Camtek_AOI_manager.bat"])
        # One command, ASCII, CRLF, relative to its own folder (works in any install folder).
        text = bat.decode("ascii")
        self.assertTrue(text.endswith("\r\n"))
        lines = [ln for ln in text.split("\r\n") if ln]
        self.assertEqual(lines, ["@echo off", 'start "" "%~dp0python\\pythonw.exe" "%~dp0Camtek_AOI_manager.pyw"'])
        self.assertIn("Camtek_AOI_manager.bat 을 더블클릭", guide)
        self.assertNotIn("Win + R", guide)

    def test_bat_not_in_repository(self):
        # The starter is generated into the zip only; the repository and updates carry no .bat.
        bats = [os.path.join(dp, f) for dp, _, fs in os.walk(ROOT) if ".git" not in dp
                and "node_modules" not in dp for f in fs if f.lower().endswith((".bat", ".cmd"))]
        self.assertEqual(bats, [])


if __name__ == "__main__":
    unittest.main()
