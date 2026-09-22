"""양식 만들기 — new form from a fake equipment tree: question → scales → edit → confirm."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from param_manager import locking, refdata, workdirs
from param_manager.desktop_form import DesktopForm
from param_manager.desktop_formnew import DesktopFormNew
from test_ini_parser import _mk_recipe


class FormNewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rev1-formnew-"))
        self.save = self.tmp / "save"
        self.save.mkdir()
        refdata.save_ip(refdata.ip_path(str(self.save)), [{"호기": "AOI-01", "IP": "10.0.0.1", "장비종류": "Camtek"}])
        job_root = self.tmp / "eq" / "Job"
        _mk_recipe(job_root / "R_TB500_LIVE_PI9 - Enhanced" / "6324" / "Recipes" / "PI")
        self.cfg = self.tmp / "c.json"
        self.cfg.write_text(json.dumps({"save_dir": str(self.save), "local_dir": str(self.tmp / "local")}), encoding="utf-8")
        self.form = DesktopForm(self.cfg)
        self.new = DesktopFormNew(self.form, self.cfg)
        self.new.collector.job_root_override = lambda m: job_root
        p = patch.object(locking, "VERIFY_DELAY_SEC", 0)
        p.start()
        self.addCleanup(p.stop)

    def test_new_form_from_equipment(self):
        for bad in ("", "a/b", "x" * 65):
            with self.assertRaises(ValueError):
                self.new.collect({"recipe": bad, "machines": ["AOI-01"], "source": "equipment"})
        req = {"recipe": "PI9", "machines": ["AOI-01"], "source": "equipment"}
        q = self.new.collect(req)
        self.assertEqual(q["question"]["kind"], "match")
        out = self.new.collect(dict(req, answers={"match": {"AOI-01": {"PI9": q["question"]["suggested"]["PI9"]}}}))
        self.assertEqual(out["stage"], "scales")
        self.assertIsNone(self.new.collector.lock_root)          # 양식 만들기 does not take the collate lock
        parsed = self.new.parse({"scales": {s["variant"]: s["coef"] for s in out["scales"]}, "base_form": ""})
        snap = parsed["form"]["version"]
        page = self.form.page({"snapshot": snap, "limit": 100})
        self.assertGreater(page["total"], 0)
        used = self.form.edit({"snapshot": snap, "row": page["rows"][0]["id"], "kind": "use", "value": True})["used"]
        done = self.form.confirm({"snapshot": snap, "machine": "AOI-01"})
        self.assertTrue(os.path.isfile(done["final"]) and os.path.isfile(done["original"]))
        self.assertEqual(done["kept"], used)
        self.assertEqual(workdirs.list_recipes(str(self.save)), ["PI9"])
        self.assertIsNone(done["merge"])                         # brand-new recipe: nothing to inherit
        self.new.cancel({})


if __name__ == "__main__":
    unittest.main()
