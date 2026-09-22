"""Open-path allowlist: only existing documents/folders under save_dir or the local result root."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from param_manager.desktop_open import DesktopOpen


class DesktopOpenTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rev1-open-"))
        self.save, self.local, self.other = self.tmp / "save", self.tmp / "local", self.tmp / "other"
        for d in (self.save, self.local, self.other):
            d.mkdir()
        self.cfg = self.tmp / "c.json"
        self.cfg.write_text(json.dumps({"save_dir": str(self.save), "local_dir": str(self.local)}), encoding="utf-8")
        self.opener = DesktopOpen(self.cfg)
        (self.local / "result.xlsx").write_bytes(b"x")
        (self.save / "doc.html").write_text("x", encoding="utf-8")
        (self.save / "tool.exe").write_bytes(b"x")
        (self.other / "outside.xlsx").write_bytes(b"x")

    def test_allowlist(self):
        self.assertEqual(self.opener.resolve(str(self.local / "result.xlsx")).name, "result.xlsx")
        self.assertTrue(self.opener.resolve(str(self.save)).is_dir())
        for bad in (str(self.other / "outside.xlsx"), str(self.save / "tool.exe"), str(self.save / "missing.xlsx"),
                    str(self.save / ".." / "other" / "outside.xlsx"), "", 5, "a\0b"):
            with self.assertRaises(ValueError):
                self.opener.resolve(bad)

    def test_symlink_rejected(self):
        link = self.save / "link.xlsx"
        try:
            link.symlink_to(self.other / "outside.xlsx")
        except OSError:
            self.skipTest("symlinks unavailable")
        with self.assertRaises(ValueError):
            self.opener.resolve(str(link))

    def test_open_uses_default_handler_only(self):
        with patch("param_manager.desktop_open.os.name", "posix"), \
             patch("param_manager.desktop_open.shutil.which", return_value="/usr/bin/xdg-open"), \
             patch("param_manager.desktop_open.subprocess.Popen") as popen:
            self.opener.open({"path": str(self.local / "result.xlsx")})
            self.opener.open({"path": str(self.local / "result.xlsx"), "reveal": True})
        self.assertEqual(popen.call_args_list[0].args[0], ["/usr/bin/xdg-open", str(self.local / "result.xlsx")])
        self.assertEqual(popen.call_args_list[1].args[0], ["/usr/bin/xdg-open", str(self.local)])
        with self.assertRaises(ValueError):
            self.opener.open({"path": str(self.local / "result.xlsx"), "shell": True})


if __name__ == "__main__":
    unittest.main()
