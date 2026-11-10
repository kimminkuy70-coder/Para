"""v13: nothing shipped may look like a script or be an executable (Para #31 · #58).

v12.9.30~32 zips were blocked by Windows Defender (`Trojan:Script/Wacatac.F!ml`, `Wacatac!ml`):
batch-file text (`@echo off` · `ping -n` · `start ""` · `del "%~f0"`) sat inside the engine, and our
own unsigned exe files had no reputation. v13 ships source text only, so every shipped file —
the exact list in `param_manager.deploy` — is checked here.
"""
from __future__ import annotations

import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from param_manager import deploy  # noqa: E402

MARKERS = re.compile(
    r'%~f0|@echo off|rmdir /s|ping -n|ping 127\.0\.0\.1|start ""|del /q|'
    r'powershell|-EncodedCommand|ExecutionPolicy|schtasks|wscript|cscript|reg add|remote-debugging',
    re.IGNORECASE)
TEXT = {".py", ".pyw", ".js", ".css", ".html", ".json", ".txt", ".md", ".svg", ".map", ""}


class DeployFilesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = deploy.files(ROOT)

    def test_list_has_the_program(self):
        for need in ("Camtek_AOI_manager.pyw", "param_manager/launcher.py", "param_manager/desktop_ipc.py",
                     "param_manager/webserver.py", "param_manager/data/para_icon.ico"):
            self.assertIn(need, self.files)
        self.assertFalse([f for f in self.files if f.startswith(("tests/", "tools/", "docs/", ".github/"))])

    def test_no_executables_or_scripts(self):
        self.assertEqual(deploy.forbidden(self.files), [])
        self.assertEqual(deploy.forbidden(["a/b.BAT", "x.py"]), ["a/b.BAT"])

    def test_no_script_text(self):
        hits = {}
        for rel in self.files:
            if os.path.splitext(rel)[1].lower() not in TEXT:
                continue
            with open(os.path.join(ROOT, rel), encoding="utf-8", errors="ignore") as fh:
                found = sorted({m.group(0).lower() for m in MARKERS.finditer(fh.read())})
            if found:
                hits[rel] = found
        self.assertEqual(hits, {}, "배포 파일에 배치 · 스크립트 문구가 있음")


if __name__ == "__main__":
    unittest.main()
