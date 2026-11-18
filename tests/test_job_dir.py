"""#79 호기별 장비 Job 폴더: 설정 › AOI 장비 호기 루트 › CAMTEK 표의 [Job 폴더] 열.
기본은 \\\\IP\\c$\\Job(종전), D:\\Job 처럼 적으면 \\\\IP\\d$\\Job 을 읽는다."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from param_manager import desktop_config as dc
from param_manager import desktop_watch as dw
from param_manager import watcher


class JobRootUncTests(unittest.TestCase):
    def test_default_is_c_job(self):
        self.assertEqual(watcher.job_root_unc("10.0.0.5"), r"\\10.0.0.5\c$\Job")
        self.assertEqual(watcher.job_path_for("10.0.0.5"), r"\\10.0.0.5\c$\Job")
        self.assertEqual(watcher.machine_recipe_dir("10.0.0.5", r"PI3\Setup1"), r"\\10.0.0.5\c$\Job\PI3\Setup1")

    def test_drive_path_becomes_admin_share(self):
        self.assertEqual(watcher.job_root_unc("10.0.0.5", r"D:\Job"), r"\\10.0.0.5\d$\Job")
        self.assertEqual(watcher.job_root_unc("10.0.0.5", "E:/Data/Job/"), r"\\10.0.0.5\e$\Data\Job")
        self.assertEqual(watcher.machine_recipe_dir("10.0.0.5", "PI3", r"D:\Job"), r"\\10.0.0.5\d$\Job\PI3")

    def test_unc_kept(self):
        self.assertEqual(watcher.job_root_unc("10.0.0.5", r"\\10.0.0.9\d$\Job"), r"\\10.0.0.9\d$\Job")

    def test_bad_spec(self):
        with self.assertRaises(ValueError):
            watcher.job_root_unc("10.0.0.5", "Job")


class ConfigJobDirTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="jobdir-"))
        (self.tmp / "eq" / "AOI-9" / "Reports").mkdir(parents=True)
        self.cfg = self.tmp / "c.json"
        self.cfg.write_text(json.dumps({"local_dir": str(self.tmp / "local")}), encoding="utf-8")
        self.c = dc.DesktopConfig(self.cfg)
        self.c.set_aoi_root({"machine": "AOI-9", "path": str(self.tmp / "eq" / "AOI-9")})

    def raw(self):
        return json.loads(self.cfg.read_text(encoding="utf-8"))

    def view(self, out):
        return next(a for a in out["aoi"] if a["machine"] == "AOI-9")

    def test_set_show_reset(self):
        self.assertEqual(self.view(self.c.state())["job_dir"], "")
        out = self.c.set_aoi_job_dir({"machine": "AOI-9", "path": " d:\\Job\\ "})
        self.assertEqual(self.view(out)["job_dir"], r"D:\Job")
        self.assertIn(r"D:\Job", out["notice"])
        self.assertEqual(self.raw()["aoi_job_dirs"], {"AOI-9": r"D:\Job"})
        out = self.c.set_aoi_job_dir({"machine": "AOI-9", "path": ""})
        self.assertEqual(self.view(out)["job_dir"], "")
        self.assertNotIn("aoi_job_dirs", self.raw())
        self.c.set_aoi_job_dir({"machine": "AOI-9", "path": r"C:\Job"})      # 기본과 같으면 저장 안 함
        self.assertNotIn("aoi_job_dirs", self.raw())

    def test_rejects(self):
        for bad in ("Job", r"D:Job", r"\\only", "D:\\Jo|b"):
            with self.assertRaises(ValueError, msg=bad):
                self.c.set_aoi_job_dir({"machine": "AOI-9", "path": bad})
        with self.assertRaises(ValueError):
            self.c.set_aoi_job_dir({"machine": "AOI-1", "path": r"D:\Job"})   # 등록 안 된 호기

    def test_rename_and_remove_follow(self):
        self.c.set_aoi_job_dir({"machine": "AOI-9", "path": r"D:\Job"})
        self.c.edit_aoi_root({"machine": "AOI-9", "new_machine": "AOI-09", "path": str(self.tmp / "eq" / "AOI-9")})
        self.assertEqual(self.raw()["aoi_job_dirs"], {"AOI-09": r"D:\Job"})
        self.c.remove_aoi({"machine": "AOI-09"})
        self.assertEqual(self.raw().get("aoi_job_dirs"), {})


class ConnectionCheckTests(unittest.TestCase):
    def test_connection_check_uses_job_dir(self):
        rows = [{"호기": "AOI-9", "IP": "10.0.0.5"}, {"호기": "AOI-10", "IP": "10.0.0.6"}]
        seen = []
        with mock.patch.object(dw.refdata, "machines", lambda r: ["AOI-9", "AOI-10"]), \
                mock.patch.object(dw.refdata, "ip_for", lambda r, m: {"AOI-9": "10.0.0.5", "AOI-10": "10.0.0.6"}[m]), \
                mock.patch.object(dw.watcher, "probe_host", lambda ip: True), \
                mock.patch.object(dw.Path, "exists", lambda p: seen.append(str(p)) or False):
            out = dw.check_machine_connections(rows, ["AOI-9", "AOI-10"], sleep=lambda s: None,
                                               job_dirs={"AOI-9": r"D:\Job"})
        self.assertEqual(out[0]["job"], r"\\10.0.0.5\d$\Job")
        self.assertEqual(out[0]["unc"], r"\\10.0.0.5\d$")
        self.assertEqual(out[1]["job"], r"\\10.0.0.6\c$\Job")
        self.assertEqual(out[1]["unc"], r"\\10.0.0.6\c$")
        self.assertIn("Job 폴더", out[0]["reason"])
        self.assertEqual(len(seen), 2)

    def test_param_watch_job_root_reads_setting(self):
        tmp = Path(tempfile.mkdtemp(prefix="jobdir-w-"))
        cfg = tmp / "c.json"
        cfg.write_text(json.dumps({"aoi_job_dirs": {"AOI-9": r"D:\Job"}}), encoding="utf-8")
        w = dw.ParamWatch(cfg)
        self.assertEqual(str(w._job_root("AOI-9", "10.0.0.5")).replace("/", "\\"), r"\\10.0.0.5\d$\Job")
        self.assertEqual(str(w._job_root("AOI-10", "10.0.0.6")).replace("/", "\\"), r"\\10.0.0.6\c$\Job")


if __name__ == "__main__":
    unittest.main()
