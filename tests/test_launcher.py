"""Start file + launcher: update swap, OneDrive refusal, Edge command, second start, editions (v14.4)."""
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

    def test_shortcut_runs_signed_pythonw_with_start_file(self):
        spec = winnative.shortcut_spec(Path("H"))
        self.assertEqual(Path(spec["target"]).parts[-2:], ("python", "pythonw.exe"))
        self.assertTrue(spec["args"].strip('"').endswith("AOI_Manager.pyw"))
        self.assertEqual(spec["description"], "AOI Manager")
        self.assertFalse(winnative.ensure_desktop_shortcut(None))     # source copy: never

    def test_mini_shortcut_adds_flag_and_keeps_old_start_file(self):
        # An install from before v14.4 has only Camtek_AOI_manager.pyw at its root.
        spec = winnative.shortcut_spec(Path("H"), "mini", Path("H") / "Camtek_AOI_manager.pyw")
        self.assertTrue(spec["args"].endswith('Camtek_AOI_manager.pyw" --mini'))
        self.assertEqual(spec["description"], "AOI Manager Mini")

    def test_start_file_prefers_the_running_one(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            (home / "Camtek_AOI_manager.pyw").write_text("x", encoding="utf-8")
            self.assertEqual(launcher.start_file(home).name, "Camtek_AOI_manager.pyw")      # old install
            (home / "AOI_Manager.pyw").write_text("x", encoding="utf-8")
            self.assertEqual(launcher.start_file(home).name, "AOI_Manager.pyw")              # v14.4 install
            self.assertEqual(launcher.start_file(home, str(home / "Camtek_AOI_manager.pyw")).name,
                             "Camtek_AOI_manager.pyw")
            self.assertEqual(launcher.start_file(home, str(home / "other.txt")).name, "AOI_Manager.pyw")


class EditionStartTest(unittest.TestCase):
    """v14.4: --mini starts AOI Manager Mini; the two editions never run side by side."""

    def test_flag(self):
        from param_manager import edition
        self.assertEqual(edition.from_argv([]), "full")
        self.assertEqual(edition.from_argv(["--mini"]), "mini")
        self.assertEqual(edition.from_argv(["--MINI "]), "mini")
        self.assertEqual(edition.args("mini"), ["--mini"])
        self.assertEqual(edition.args("full"), [])

    def test_server_url_and_state_carry_the_edition(self):
        from param_manager import webserver
        self.assertTrue(webserver.page_url(1, "t", "mini").endswith("?t=t&e=mini"))
        self.assertTrue(webserver.page_url(1, "t", "full").endswith("?t=t"))
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"LOCALAPPDATA": d}):
            launcher.write_state(mock.Mock(port=1, token="t", edition="mini"))
            self.assertEqual(launcher.read_state()["edition"], "mini")

    def test_second_start(self):
        same = launcher.second_start({"port": 5, "token": "tk", "edition": "mini"}, "mini")
        self.assertEqual(same, ("open", "http://127.0.0.1:5/?t=tk&e=mini"))
        other = launcher.second_start({"port": 5, "token": "tk", "edition": "full"}, "mini")
        self.assertEqual(other[0], "refuse")
        self.assertIn("AOI Manager가 실행 중", other[1])
        old = launcher.second_start({"port": 5, "token": "tk"}, "full")       # state of v14.3 = full
        self.assertEqual(old, ("open", "http://127.0.0.1:5/?t=tk"))
        self.assertEqual(launcher.second_start(None, "full")[0], "refuse")

    def test_mini_runs_no_watch_and_reports_edition(self):
        import io
        from param_manager import desktop_ipc, edition
        with mock.patch.dict(os.environ, {edition.ENV: "mini"}):
            self.assertFalse(edition.watches_on())
            session = desktop_ipc.Session(io.BytesIO())
            with mock.patch.object(session.cmwatch, "due", side_effect=AssertionError("Mini must not check watches")), \
                 mock.patch.object(session.pwatch, "due", side_effect=AssertionError("Mini must not check watches")):
                session.tick(now=0)
            st = session.watch_status()
            self.assertEqual((st["param"], st["commonality"], st["batch"]), (False, False, False))
        with mock.patch.dict(os.environ, {edition.ENV: ""}):
            self.assertTrue(edition.watches_on())


if __name__ == "__main__":
    unittest.main()
