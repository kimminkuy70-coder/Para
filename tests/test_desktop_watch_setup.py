"""자동 감시 설정 마법사(2026-09): 장비 연결 확인, 다른 호기에 레시피 폴더 적용(이름이
달라도 실제 Job 폴더를 읽어 맞춤), Commonality 감시 양식의 하위 레시피 선택 단계."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from param_manager import refdata
from param_manager.desktop_watch import CmWatch
import test_desktop_watch
from test_cmwatcher import _mk_scan_sm, _add_recipe2
from test_ini_parser import _mk_recipe


class ParamSetupTests(unittest.TestCase):
    setUp = test_desktop_watch.ParamWatchTests.setUp

    def test_connection_check_and_ips(self):
        st = self.w.state()
        self.assertEqual(st["ips"], {"AOI-01": "10.0.0.1", "AOI-02": "10.0.0.2"})
        r = self.w.connections({"machines": ["AOI-01", "AOI-02"]})
        self.assertEqual([(x["machine"], x["ok"], x["unc"]) for x in r["results"]],
                         [("AOI-01", True, "\\\\10.0.0.1\\c$"), ("AOI-02", True, "\\\\10.0.0.2\\c$")])
        self.jobs["AOI-02"] = self.tmp / "offline" / "Job"          # not reachable
        r = self.w.connections({"machines": ["AOI-02"]})
        self.assertFalse(r["results"][0]["ok"])
        self.assertTrue(r["results"][0]["reason"])
        with self.assertRaises(ValueError):
            self.w.connections({"machines": ["AOI-99"]})

    def test_copy_adapts_to_each_machines_real_job_folder_name(self):
        refdata.save_ip(refdata.ip_path(str(self.save)), [
            {"호기": m, "IP": f"10.0.0.{i}", "장비종류": "Camtek"} for i, m in enumerate(("AOI-01", "AOI-02", "AOI-03", "AOI-04", "AOI-05"), 1)])
        # AOI-02: same name · AOI-03: slightly different name · AOI-04: none · AOI-05: two candidates
        for m, names in (("AOI-03", ["R_PI3 "]), ("AOI-04", ["OTHER"]), ("AOI-05", ["R_PI3_A", "R_PI3_B"])):
            root = self.tmp / "equipment" / m / "Job"
            for n in names:
                _mk_recipe(root / n / "6324" / "Recipes" / "PI")
            self.jobs[m] = root
        self.w.set_path({"machine": "AOI-01", "recipe": "PI3", "rel": "R_PI3"})
        st = self.w.copy_paths({"source": "AOI-01", "targets": ["AOI-02", "AOI-03", "AOI-04", "AOI-05"]})
        rep = {x["machine"]: x for x in st["copy_report"]}
        self.assertEqual((rep["AOI-02"]["status"], rep["AOI-02"]["rel"]), ("same", "R_PI3"))
        self.assertEqual((rep["AOI-03"]["status"], rep["AOI-03"]["rel"]), ("matched", "R_PI3 "))
        self.assertEqual((rep["AOI-04"]["status"], rep["AOI-04"]["rel"]), ("missing", ""))
        self.assertEqual((rep["AOI-05"]["status"], rep["AOI-05"]["rel"]), ("ambiguous", ""))
        paths = {t["machine"]: t["path"] for t in st["targets"]}
        self.assertEqual(paths, {"AOI-01": "R_PI3", "AOI-02": "R_PI3", "AOI-03": "R_PI3 "})   # unmatched machines not assigned
        self.assertEqual(self.sleeps, [2.0, 2.0, 2.0])                       # one machine at a time


class CmRecipePickTests(unittest.TestCase):
    def test_representative_sm_with_two_recipes_lets_you_pick(self):
        tmp = Path(tempfile.mkdtemp(prefix="rev1-cmpick-"))
        base = tmp / "scan"
        slot = _mk_scan_sm(base, "AOI-9", "DEV1-0001", "6412", "ASD", 25)
        _add_recipe2(Path(slot) / "CX01", 40)
        cfg = tmp / "c.json"
        cfg.write_text(json.dumps({"local_dir": str(tmp / "local"), "commonality_roots": {"AOI-9": str(base)}}), encoding="utf-8")
        w = CmWatch(cfg)
        w.save({"enabled": False, "machines": ["AOI-9"], "settle_minutes": 0,
                "plan": [{"device": "DEV1-0001", "lot": "6412", "machines": "AOI-9", "note": ""}]})
        w.candidates({"machine": "AOI-9", "device": "DEV1-0001", "lot": "6412"})
        step = w.begin({"sm": "ASD", "title": "감시"})
        self.assertEqual(step["stage"], "recipes")
        self.assertEqual([r["name"] for r in step["recipes"]], ["PI", "PI_Bubble"])
        with self.assertRaises(ValueError):
            w.pick_recipes({"indexes": []})
        opened = w.pick_recipes({"indexes": [1]})                 # only PI_Bubble
        self.assertEqual((opened["stage"], opened["recipe"], opened["total"]), ("edit", "감시_PI_Bubble", 1))
        w.form.edit({"snapshot": w.form.version, "row": 0, "kind": "use", "value": True})
        done = w.confirm({"snapshot": w.form.version})
        self.assertEqual(done["forms"], ["감시_PI_Bubble"])


if __name__ == "__main__":
    unittest.main()
