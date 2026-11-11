"""#65: 화면(Edge 앱 창) 아이콘 = 기존 프로그램 아이콘 para_icon.ico."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from param_manager import deploy  # noqa: E402

ICON = os.path.join(ROOT, "param_manager", "data", "para_icon.ico")


def _read(*parts):
    with open(os.path.join(ROOT, *parts), "rb") as fh:
        return fh.read()


class AppIconTest(unittest.TestCase):
    def test_favicon_is_program_icon(self):
        icon = _read("param_manager", "data", "para_icon.ico")
        self.assertEqual(_read("frontend", "public", "favicon.ico"), icon)
        self.assertEqual(_read("frontend", "dist", "favicon.ico"), icon)

    def test_index_links_favicon(self):
        for parts in (("frontend", "index.html"), ("frontend", "dist", "index.html")):
            self.assertIn(b'rel="icon"', _read(*parts))
            self.assertIn(b'href="/favicon.ico"', _read(*parts))

    def test_icons_are_shipped(self):
        files = deploy.files(ROOT)
        self.assertIn("frontend/dist/favicon.ico", files)
        self.assertIn("param_manager/data/para_icon.ico", files)

    def test_shortcut_and_tray_use_program_icon(self):
        from pathlib import Path
        from param_manager import winnative
        spec = winnative.shortcut_spec(Path("C:/CamtekAOI"))
        self.assertTrue(spec["icon"].replace("\\", "/").endswith("app/param_manager/data/para_icon.ico"))
        self.assertEqual(os.path.normpath(str(winnative.ICON)), os.path.normpath(ICON))


if __name__ == "__main__":
    unittest.main()
