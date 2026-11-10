"""v13 start file + launcher: update swap, OneDrive refusal, Edge command, second start."""
import json
import os
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from param_manager import launcher, winnative  # noqa: E402

START = runpy.run_path(str(ROOT / "Camtek_AOI_manager.pyw"), run_name="para_start_test")


def tree(base: Path, name: str, marker: str):
    (base / name / "param_manager").mkdir(parents=True)
    (base / name / "param_manager" / "launcher.py").write_text(marker, encoding="utf-8")


class SwapTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def read(self, name):
        return (self.home / name / "param_manager" / "launcher.py").read_text(encoding="utf-8")

    def test_ready_update_replaces_app_and_keeps_old_until_next_start(self):
        tree(self.home, "app", "old"); tree(self.home, "app.new", "new")
        START["_swap"](str(self.home))
        self.assertEqual(self.read("app"), "new")
        self.assertEqual(self.read("app.old"), "old")
        self.assertFalse((self.home / "app.new").exists())
        START["_swap"](str(self.home))                     # next start: old copy removed
        self.assertFalse((self.home / "app.old").exists())
        self.assertEqual(self.read("app"), "new")

    def test_incomplete_update_is_ignored(self):
        tree(self.home, "app", "old")
        (self.home / "app.new").mkdir()                     # no launcher.py = not finished
        START["_swap"](str(self.home))
        self.assertEqual(self.read("app"), "old")

    def test_cut_off_swap_is_restored(self):
        tree(self.home, "app.old", "old")                  # app renamed away, then power loss
        START["_swap"](str(self.home))
        self.assertEqual(self.read("app"), "old")

    def test_source_copy_runs_in_place(self):
        self.assertEqual(START["APP"], str(ROOT))
        self.assertIsNone(START["INSTALLED"])


class LauncherTest(unittest.TestCase):
    def test_onedrive_install_is_refused(self):
        with mock.patch("param_manager.localdirs.is_under_onedrive", return_value=True):
            self.assertIn("OneDrive", launcher.onedrive_refusal(r"C:\Users\u\OneDrive\app"))
        self.assertIsNone(launcher.onedrive_refusal(None))

    def test_state_file_roundtrip_and_only_own_is_cleared(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"LOCALAPPDATA": d}):
            srv = mock.Mock(port=4321, token="tok")
            launcher.write_state(srv)
            self.assertEqual(launcher.read_state()["port"], 4321)
            launcher.clear_state(mock.Mock(token="other"))
            self.assertIsNotNone(launcher.read_state())
            launcher.clear_state(srv)
            self.assertIsNone(launcher.read_state())
            self.assertTrue(str(launcher.state_file()).startswith(d))

    def test_edge_command_is_app_mode_without_debug_port(self):
        cmd = winnative.app_window_cmd(Path("msedge.exe"), "http://127.0.0.1:1/?t=x", Path("prof"))
        self.assertIn("--app=http://127.0.0.1:1/?t=x", cmd)
        self.assertTrue(any(c.startswith("--user-data-dir=") for c in cmd))
        self.assertFalse([c for c in cmd if "debug" in c.lower()])

    def test_edge_candidates_and_dialog_options(self):
        c = winnative.edge_candidates({"ProgramFiles(x86)": "X", "LOCALAPPDATA": "L"})
        self.assertEqual([p.parts[0] for p in c], ["X", "L"])
        self.assertTrue(winnative.dialog_options("folder") & winnative.FOS_PICKFOLDERS)
        self.assertFalse(winnative.dialog_options("excel") & winnative.FOS_PICKFOLDERS)
        if os.name != "nt":
            self.assertIsNone(winnative.pick("folder"))   # quiet no-op off Windows


if __name__ == "__main__":
    unittest.main()
