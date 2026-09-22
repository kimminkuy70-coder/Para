"""Headless tests for the desktop config (save-folder / folder registration) adapter."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from param_manager import refdata
from param_manager.desktop_config import DesktopConfig


class DesktopConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rev1-cfg-")
        self.cfg = os.path.join(self.tmp, "config.json")
        with open(self.cfg, "w", encoding="utf-8") as fh:
            json.dump({"unrelated": "keep"}, fh)
        self.save = os.path.join(self.tmp, "저장폴더")
        os.makedirs(self.save)
        self.reports = os.path.join(self.tmp, "reports")
        os.makedirs(self.reports)
        self.a = DesktopConfig(config_path=self.cfg)

    def _cfg(self):
        with open(self.cfg, encoding="utf-8") as fh:
            return json.load(fh)

    def test_local_dir_about_and_purge(self):
        local = os.path.join(self.tmp, "pc")
        os.makedirs(local)
        state = self.a.set_local_dir({"path": local})
        self.assertEqual(state["root"], str(Path(local, "CamtekAOI").resolve()))
        self.assertTrue(os.path.isdir(os.path.join(local, "CamtekAOI", "logs")) or os.path.isdir(os.path.join(local, "CamtekAOI")))
        self.assertEqual(self._cfg()["local_dir"], os.path.join(str(Path(local).absolute()), "CamtekAOI"))
        onedrive = os.path.join(self.tmp, "OneDrive - Corp")
        os.makedirs(onedrive)
        with self.assertRaises(ValueError):
            self.a.set_local_dir({"path": onedrive})
        self.a.set_report_path({"machine": "AOI-01", "path": self.reports})
        with self.assertRaises(ValueError):                       # inside an equipment source
            self.a.set_local_dir({"path": self.reports})
        self.assertIn("removed", self.a.purge_temp({}))
        about = self.a.about({})
        self.assertTrue(about["version"] and about["logs"].startswith(state["root"]))

    def test_batch_auto_and_extra_paths(self):
        self.assertFalse(self.a.state()["batch_auto"])
        self.assertTrue(self.a.set_batch_auto({"enabled": True})["batch_auto"])
        with self.assertRaises(ValueError):
            self.a.set_batch_auto({"enabled": 1})
        archive = os.path.join(self.tmp, "archive")
        os.makedirs(archive)
        with self.assertRaises(ValueError):          # main folder must be registered first
            self.a.set_extra_paths({"machine": "AOI-01", "paths": [archive]})
        self.a.set_report_path({"machine": "AOI-01", "path": self.reports})
        for bad in ([self.reports], [os.path.join(self.tmp, "missing")], "x"):
            with self.assertRaises(ValueError):
                self.a.set_extra_paths({"machine": "AOI-01", "paths": bad})
        state = self.a.set_extra_paths({"machine": "AOI-01", "paths": [archive, archive]})
        self.assertEqual(state["extra_paths"], {"AOI-01": [str(Path(archive).absolute())]})
        self.assertEqual(self._cfg()["unrelated"], "keep")
        self.assertEqual(self.a.set_extra_paths({"machine": "AOI-01", "paths": []})["extra_paths"], {})

    def test_set_save_dir_creates_initial_files_and_persists(self):
        out = self.a.set_save_dir({"path": self.save})
        self.assertEqual(out["save_dir"], str(Path(self.save).absolute()))
        # three initial reference files created
        self.assertEqual(set(out["created"]),
                         {refdata.IP_FILENAME, refdata.REF_FILENAME, refdata.SPECIAL_FILENAME})
        for name in (refdata.IP_FILENAME, refdata.REF_FILENAME, refdata.SPECIAL_FILENAME):
            self.assertTrue(os.path.exists(os.path.join(self.save, name)))
        # persisted + unrelated keys preserved
        cfg = self._cfg()
        self.assertEqual(cfg["save_dir"], str(Path(self.save).absolute()))
        self.assertEqual(cfg["unrelated"], "keep")
        # second call does not recreate
        again = self.a.set_save_dir({"path": self.save})
        self.assertEqual(again["created"], [])

    def test_set_save_dir_rejects_missing_or_bad(self):
        with self.assertRaises(ValueError):
            self.a.set_save_dir({"path": os.path.join(self.tmp, "does-not-exist")})
        with self.assertRaises(ValueError):
            self.a.set_save_dir({"path": ""})
        with self.assertRaises(ValueError):
            self.a.set_save_dir({"path": self.save, "extra": 1})

    def test_report_and_scanresult_registration(self):
        r = self.a.set_report_path({"machine": "AOI-21", "path": self.reports})
        self.assertEqual(r["report_paths"]["AOI-21"], str(Path(self.reports).absolute()))
        s = self.a.set_scanresult_root({"machine": "AOI-9", "path": self.reports})
        self.assertEqual(s["scanresult_roots"]["AOI-9"], str(Path(self.reports).absolute()))
        state = self.a.state()
        self.assertIn("AOI-21", state["report_paths"])
        self.assertIn("AOI-9", state["scanresult_roots"])
        # remove
        after = self.a.remove({"kind": "report", "machine": "AOI-21"})
        self.assertNotIn("AOI-21", after["report_paths"])
        self.assertIn("AOI-9", after["scanresult_roots"])

    def test_registration_rejects_bad(self):
        with self.assertRaises(ValueError):
            self.a.set_report_path({"machine": "", "path": self.reports})
        with self.assertRaises(ValueError):
            self.a.set_report_path({"machine": "AOI-1", "path": os.path.join(self.tmp, "nope")})

    def test_state_defaults(self):
        st = self.a.state()
        self.assertEqual(st["save_dir"], "")
        self.assertEqual(st["report_paths"], {})
        self.assertEqual(st["scanresult_roots"], {})


if __name__ == "__main__":
    unittest.main()
