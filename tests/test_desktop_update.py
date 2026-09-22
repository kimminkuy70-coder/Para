"""값 업데이트 (web): collect from a fake equipment tree / local folder → questions →
variant preview → collation write. No network; the equipment Job root is a temp tree."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from param_manager import collate, formbuilder, ini_parser, locking, refdata, workdirs
from param_manager.desktop_update import DesktopUpdate
from test_ini_parser import _mk_recipe


class DesktopUpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rev1-update-"))
        self.save = self.tmp / "save"
        self.save.mkdir()
        refdata.save_ip(refdata.ip_path(str(self.save)), [
            {"호기": "AOI-01", "IP": "10.0.0.1", "장비종류": "Camtek"},
            {"호기": "AOI-02", "IP": "10.0.0.2", "장비종류": "Camtek"}])
        # Form for PI3 built from the same recipe layout the equipment has.
        sample = self.tmp / "sample" / "PI"
        _mk_recipe(sample)
        rows, _ = ini_parser.build_pivot(ini_parser.scan_tree(sample.parent, default_level="PI3", default_equipment="AOI-01"))
        init = self.tmp / "init.xlsx"
        formbuilder.build_initial_workbook(rows, str(init), level="PI3")
        st = workdirs.stamp()
        run = workdirs.form_run_dir(str(self.save), "PI3", st)
        formbuilder.build_final_from_initial(str(init), workdirs.form_final_path(run, "PI3", "AOI-01", st), level="PI3")
        # Fake equipment: AOI-01 one Setup, AOI-02 two Setups in the matching Job.
        self.equipment = {}
        for machine, setups in (("AOI-01", ["6324"]), ("AOI-02", ["6324", "7000"])):
            job_root = self.tmp / "equipment" / machine / "Job"
            for setup in setups:
                _mk_recipe(job_root / "R_TB500_LIVE_PI3 - Enhanced" / setup / "Recipes" / "PI")
            (job_root / "Other job").mkdir(parents=True)
            self.equipment[machine] = job_root
        self.cfg = self.tmp / "c.json"
        self.cfg.write_text(json.dumps({"save_dir": str(self.save), "local_dir": str(self.tmp / "local")}), encoding="utf-8")
        self.update = DesktopUpdate(self.cfg)
        self.update.job_root_override = lambda m: self.equipment[m]
        self.patch = patch.object(locking, "VERIFY_DELAY_SEC", 0)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_equipment_questions_preview_commit(self):
        prep = self.update.prepare({})
        self.assertEqual(prep["recipes"], ["PI3"])
        self.assertEqual([m["id"] for m in prep["machines"]], ["AOI-01", "AOI-02"])
        req = {"recipes": ["PI3"], "machines": ["AOI-01", "AOI-02"], "source": "equipment"}
        q = self.update.collect(dict(req, answers={}))
        self.assertEqual((q["stage"], q["question"]["kind"], q["question"]["machine"]), ("question", "match", "AOI-01"))
        self.assertEqual(q["question"]["suggested"]["PI3"], ["R_TB500_LIVE_PI3 - Enhanced"])
        self.assertIsNotNone(self.update.lock_root)            # global collate lock held during the flow
        answers = {"match": {"AOI-01": {"PI3": ["R_TB500_LIVE_PI3 - Enhanced"]}}}
        q = self.update.collect(dict(req, answers=answers))
        self.assertEqual((q["question"]["kind"], q["question"]["machine"]), ("setup", "AOI-02"))
        self.assertEqual(sorted(q["question"]["options"]), ["6324", "7000"])
        self.assertEqual(q["collected"], ["AOI-01"])            # AOI-02 reused AOI-01's Job match
        answers["setup"] = {"AOI-02": {q["question"]["job"]: "7000"}}
        out = self.update.collect(dict(req, answers=answers))
        self.assertEqual(out["stage"], "variants")
        self.assertEqual(out["collected"], ["AOI-01", "AOI-02"])
        self.assertGreater(out["rows"], 0)
        prev = self.update.preview({"mapping": {}})
        self.assertEqual([r["recipe"] for r in prev["recipes"]], ["PI3"])
        self.assertGreater(prev["recipes"][0]["filled_cells"], 0)
        done = self.update.commit({"include": []})
        self.assertTrue(os.path.isfile(done["path"]))
        sheets, machines = collate.load_collation(done["path"])
        self.assertEqual(machines, ["AOI-01", "AOI-02"])
        self.assertTrue(any(r.get("AOI-02") not in (None, "") for rows in sheets.values() for r in rows))
        self.assertIsNone(self.update.lock_root)                # released after commit
        for bad in ({"recipes": ["NOPE"], "machines": ["AOI-01"], "source": "equipment"},
                    {"recipes": ["PI3"], "machines": ["AOI-99"], "source": "equipment"},
                    {"recipes": ["PI3"], "machines": ["AOI-01"], "source": "ftp"}):
            with self.assertRaises(ValueError):
                self.update.collect(bad)

    def test_local_source_and_cancel(self):
        with self.assertRaises(ValueError):
            self.update.collect({"recipes": ["PI3"], "machines": ["AOI-01"], "source": "local"})
        self.assertIsNone(self.update.lock_root)                # failure releases the lock
        local = self.tmp / "copies"
        _mk_recipe(local / "AOI-01" / "PI")
        prep = self.update.set_local_source({"path": str(local)})
        self.assertEqual([m["local"] != "" for m in prep["machines"]], [True, False])
        out = self.update.collect({"recipes": ["PI3"], "machines": ["AOI-01", "AOI-02"], "source": "local"})
        self.assertEqual(out["collected"], ["AOI-01"])
        self.assertEqual(out["errors"][0]["machine"], "AOI-02")
        self.update.cancel({})
        self.assertIsNone(self.update.lock_root)
        with self.assertRaises(ValueError):
            self.update.preview({"mapping": {}})


if __name__ == "__main__":
    unittest.main()
