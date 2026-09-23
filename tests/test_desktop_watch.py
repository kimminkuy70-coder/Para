"""자동 감시 (web): parameter watch on a fake Job tree + Commonality watch on a fake
Scanresult tree, and the engine scheduler/notice wiring. No network, no sleeps."""
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from param_manager import cmwatcher, desktop_ipc, formbuilder, ini_parser, locking, refdata, watcher, workdirs
from param_manager.desktop_watch import CmWatch, ParamWatch, valid_rel
from test_cmwatcher import _mk_scan_sm
from test_ini_parser import _mk_recipe

REL = "R_PI3\\6324\\Recipes"


class ParamWatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rev1-watch-"))
        self.save = self.tmp / "save"
        self.save.mkdir()
        refdata.save_ip(refdata.ip_path(str(self.save)), [
            {"호기": "AOI-01", "IP": "10.0.0.1", "장비종류": "Camtek"},
            {"호기": "AOI-02", "IP": "10.0.0.2", "장비종류": "Camtek"}])
        sample = self.tmp / "sample" / "PI"
        _mk_recipe(sample)
        rows, _ = ini_parser.build_pivot(ini_parser.scan_tree(sample.parent, default_level="PI3", default_equipment="AOI-01"))
        init = self.tmp / "init.xlsx"
        formbuilder.build_initial_workbook(rows, str(init), level="PI3")
        st = workdirs.stamp()
        run = workdirs.form_run_dir(str(self.save), "PI3", st)
        formbuilder.build_final_from_initial(str(init), workdirs.form_final_path(run, "PI3", "AOI-01", st), level="PI3")
        self.jobs = {}
        for m in ("AOI-01", "AOI-02"):
            root = self.tmp / "equipment" / m / "Job"
            _mk_recipe(root / "R_PI3" / "6324" / "Recipes" / "PI")
            self.jobs[m] = root
        self.cfg = self.tmp / "c.json"
        self.cfg.write_text(json.dumps({"save_dir": str(self.save), "local_dir": str(self.tmp / "local")}), encoding="utf-8")
        self.w = ParamWatch(self.cfg)
        self.w.job_root_override = lambda m: self.jobs[m]
        self.sleeps = []
        self.w.sleep = self.sleeps.append
        p = patch.object(locking, "VERIFY_DELAY_SEC", 0)
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(self.w.release)

    def _collations(self):
        return workdirs.list_collate_files(str(self.save))

    def test_paths_enable_cycle_change_only_and_notice(self):
        self.assertEqual(valid_rel("a/b\\c"), "a\\b\\c")
        for bad in ("..\\x", "a\\..\\b", "a:b"):
            with self.assertRaises(ValueError):
                valid_rel(bad)
        browse = self.w.jobs({"machine": "AOI-01", "sub": ""})
        self.assertEqual(browse["dirs"], ["R_PI3"])
        self.assertTrue(self.w.jobs({"machine": "AOI-01", "sub": "R_PI3\\6324\\Recipes\\PI"})["is_recipe"])
        with self.assertRaises(ValueError):          # cannot enable without targets
            self.w.save({"enabled": True})
        self.w.set_path({"machine": "AOI-01", "recipe": "PI3", "rel": REL})
        st = self.w.copy_paths({"source": "AOI-01", "targets": ["AOI-02"]})
        self.assertEqual(sorted(t["machine"] for t in st["targets"]), ["AOI-01", "AOI-02"])
        with self.assertRaises(ValueError):
            self.w.set_path({"machine": "AOI-99", "recipe": "PI3", "rel": REL})
        st = self.w.save({"enabled": True, "interval_hours": 6.0, "window_start": 0, "window_end": 0})
        self.assertTrue(st["enabled"] and st["owned"])
        # First cycle = baseline: one collation, no report.
        r1 = self.w.run(manual=True)
        self.assertEqual(len(self._collations()), 1)
        self.assertEqual(self.sleeps, [2.0])          # host gap between the two machines
        self.assertFalse(r1["report"])
        # No change: no new shared file at all.
        r2 = self.w.run(manual=True)
        self.assertFalse(r2["has_change"])
        self.assertEqual(len(self._collations()), 1)
        self.assertEqual(watcher.list_reports(str(self.save)), [])
        # Equipment value changes → new collation + change report.
        g = self.jobs["AOI-02"] / "R_PI3" / "6324" / "Recipes" / "PI" / "GlobalRTP.ini"
        text = g.read_text(encoding="utf-8")
        self.assertIn("3000", text)
        g.write_text(text.replace("3000", "4321"), encoding="utf-8")
        r3 = self.w.run(manual=True)
        self.assertTrue(r3["has_change"], r3)
        self.assertTrue(os.path.isfile(r3["report"]))
        self.assertEqual(len(self._collations()), 2)
        # Local staging never piles up.
        temp = self.tmp / "local" / "Temp"
        self.assertEqual([p for p in temp.iterdir()] if temp.is_dir() else [], [])
        # This PC announced its own cycle; another PC's cycle yields a notice.
        self.assertIsNone(self.w.poll_shared())
        s, stt = watcher.load_settings(str(self.save))
        stt.last_run, stt.last_result = "2099-01-01 00:00:00", "PI3: 1건 변경"   # a later cycle on another PC
        watcher.save_settings(str(self.save), s, stt)
        self.w._shared = (0.0, None)
        note = self.w.poll_shared()
        self.assertEqual(note["kind"], "param_watch")
        self.assertIsNone(self.w.poll_shared())       # announced once

    def test_single_pc_lock_and_due(self):
        self.w.set_path({"machine": "AOI-01", "recipe": "PI3", "rel": REL})
        self.w.save({"enabled": True})
        other = ParamWatch(self.cfg)
        with patch("param_manager.engine.current_user", return_value="someone-else"):
            self.assertIsNone(other.due())            # the lock is held by this engine
            with self.assertRaises(ValueError):
                other.run(manual=True)
        self.assertIsNotNone(self.w.due())            # never ran → due now
        self.w.save({"enabled": False})
        self.assertIsNone(self.w.owned)               # disabling hands the watch back


class CmWatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rev1-cmwatch-"))
        self.base = self.tmp / "scan"
        _mk_scan_sm(self.base, "AOI-9", "DEV1-0001", "6412", "ASD", 25)
        self.cfg = self.tmp / "c.json"
        self.cfg.write_text(json.dumps({"local_dir": str(self.tmp / "local"),
                                        "commonality_roots": {"AOI-9": str(self.base)}}), encoding="utf-8")
        self.w = CmWatch(self.cfg)

    def test_plan_form_baseline_then_new_sm(self):
        with self.assertRaises(ValueError):
            self.w.save({"enabled": True, "machines": ["AOI-1"]})
        st = self.w.save({"enabled": True, "machines": ["AOI-9"], "settle_minutes": 0,
                          "plan": [{"device": "DEV1-0001", "lot": "6412", "machines": "AOI-9", "note": ""}]})
        self.assertTrue(st["enabled"])
        self.assertTrue(st["plan_file"].startswith(str(self.tmp / "local")))   # plan stays local
        self.assertEqual([(t["device"], t["forms"]) for t in st["targets"]], [("DEV1-0001", [])])
        # Watch form from the representative S/M (copied locally first).
        cands = self.w.candidates({"machine": "AOI-9", "device": "DEV1-0001", "lot": "6412"})["candidates"]
        self.assertEqual([c["sm"] for c in cands], ["ASD"])
        opened = self.w.begin({"sm": "ASD", "title": "감시PI"})
        self.assertEqual(opened["stage"], "edit")
        self.w.form.edit({"snapshot": self.w.form.version, "row": 0, "kind": "use", "value": True})
        done = self.w.confirm({"snapshot": self.w.form.version})
        self.assertEqual((done["stage"], done["forms"]), ("done", ["감시PI"]))
        st = self.w.state()
        self.assertTrue(st["targets"][0]["forms"][0]["ok"])
        self.assertTrue(self.w.due())                  # never ran
        r1 = self.w.run(manual=True)
        self.assertEqual(r1["found"], [])              # baseline
        _mk_scan_sm(self.base, "AOI-9", "DEV1-0001", "6412", "ASD X20", 30)
        r2 = self.w.run(manual=True)
        self.assertEqual([f["sm"] for f in r2["found"]], ["ASD X20"])
        self.assertTrue(os.path.isfile(cmwatcher.result_path(str(self.tmp / "local"), "AOI-9", "감시PI")))


class SchedulerTests(unittest.TestCase):
    def test_tick_runs_due_watch_and_publishes_notice(self):
        out = io.BytesIO()
        session = desktop_ipc.Session(out)

        class Fake:
            owned = None
            def __init__(self, result, due=True):
                self.result, self.is_due, self.runs = result, due, 0
            def due(self):
                return self.is_due
            def run(self, manual=False):
                self.runs += 1
                return self.result
            def poll_shared(self):
                return None
            def refresh_lock(self):
                pass
            def release(self):
                pass
        session.cmwatch = Fake({"found": [{"sm": "X"}], "summary": "새 S/M 1개"})
        session.pwatch = Fake({"has_change": False, "summary": "변경 없음"}, due=False)
        session.tick(now=0)
        session.watch_thread.join(5)
        session.running = True                          # a user job blocks the scheduler
        session.cmwatch.is_due = True
        session.tick(now=1)
        self.assertEqual(session.cmwatch.runs, 1)
        frames = [json.loads(l) for l in out.getvalue().decode().splitlines()]
        notices = [f for f in frames if f["event"] == "notice"]
        self.assertEqual(len(notices), 1)
        self.assertIsNone(notices[0]["id"])
        self.assertEqual(notices[0]["notice"]["kind"], "cm_watch")
        self.assertEqual(session.notices[-1]["summary"], "새 S/M 1개")
        session.running = False
        session.close()


if __name__ == "__main__":
    unittest.main()
