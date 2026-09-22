"""New Commonality investigation (web): plan → slots → copy → form → Lot values → result."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from param_manager import commonality
from param_manager.desktop_cmrun import DesktopCmRun
from param_manager.desktop_commonality import DesktopCommonality
from test_commonality import _make_wafer


class CmRunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rev1-cmrun-"))
        dev = "2D@R2-DEVA-1_0855360PD-0A"
        self.src = _make_wafer(self.tmp / "eq", "AOI-6", dev, "6321", "HPG", "CX01", delta=25)
        _make_wafer(self.tmp / "eq", "AOI-6", dev, "6321", "HPG", "CX02", delta=30)
        _make_wafer(self.tmp / "eq", "AOI-6", dev, "6322", "TVS", "CX01", delta=25)
        self.before = (self.src / "Zones" / "Z.ini").read_text(encoding="utf-8")
        self.save = self.tmp / "save"
        self.save.mkdir()
        self.cfg = self.tmp / "c.json"
        self.cfg.write_text(json.dumps({"save_dir": str(self.save), "local_dir": str(self.tmp / "local"),
                                        "commonality_roots": {"AOI-6": str(self.tmp / "eq")}}), encoding="utf-8")
        self.run = DesktopCmRun(self.cfg)

    def test_full_run(self):
        plan = [{"디바이스명": "DEVA-1", "공정번호": "6321", "S/M": "HPG", "AOI호기": "AOI-6"},
                {"디바이스명": "DEVA-1", "공정번호": "6322", "S/M": "TVS", "AOI호기": "AOI-6"},
                {"디바이스명": "DEVA-1", "공정번호": "9999", "S/M": "X", "AOI호기": "AOI-6", "fail여부": "Y"}]
        out = self.run.plan({"machine": "AOI-6", "plan": plan})
        lots = {l["label"]: l for l in out["lots"]}
        self.assertEqual(lots["HPG"]["wafers"], ["CX01", "CX02"])
        missing = [l for l in out["lots"] if not l["exists"]]
        self.assertEqual(len(missing), 1)
        with self.assertRaises(ValueError):                         # missing folder cannot be copied
            self.run.copy({"picks": [{"id": missing[0]["id"]}]})
        copied = self.run.copy({"picks": [{"id": lots["HPG"]["id"], "wafers": ["CX01", "CX02"]},
                                          {"id": lots["TVS"]["id"]}]})
        self.assertEqual(copied["copied"], 3)                      # two slots of HPG → two columns
        self.assertTrue(copied["staging"].startswith(str(self.tmp / "local")))
        self.assertEqual(len(copied["units"]), 1)
        with self.assertRaises(ValueError):
            self.run.detect({"unit": 0, "base": "a/b"})
        det = self.run.detect({"unit": 0, "base": "PI3"})
        self.assertEqual(det["title"], "PI3")
        scales = {s["variant"]: s["coef"] for s in det["scales"]}
        parsed = self.run.parse({"unit": 0, "scales": scales, "base_form": ""})
        self.assertEqual(sorted(parsed["labels"]), ["HPG·CX01", "HPG·CX02", "TVS"])
        snap = parsed["form"]["version"]
        page = self.run.form.page({"snapshot": snap, "used_only": False, "limit": 100})
        self.assertGreater(page["total"], 0)
        conf = self.run.confirm({"unit": 0, "snapshot": snap})
        self.assertTrue(os.path.isfile(conf["form"]))
        mapping = {r[1]: r[0] for r in (conf["variants"] or {}).get("rows", []) if r[1]}
        res = self.run.collate({"unit": 0, "mapping": mapping})
        self.assertTrue(os.path.isfile(res["result"]))
        self.assertEqual(res["units"][0]["result"], res["result"])
        info = commonality.read_lot_result(res["result"])
        self.assertTrue(info)
        # The existing compare screen lists the new result right away.
        catalog = DesktopCommonality(self.cfg).catalog()
        self.assertIn(Path(res["result"]).name, [f["name"] for f in catalog["files"]])
        # Equipment source untouched.
        self.assertEqual((self.src / "Zones" / "Z.ini").read_text(encoding="utf-8"), self.before)

    def test_requires_order(self):
        with self.assertRaises(ValueError):
            self.run.copy({"picks": [{"id": 0}]})
        with self.assertRaises(ValueError):
            self.run.detect({"unit": 0, "base": "PI3"})


if __name__ == "__main__":
    unittest.main()
