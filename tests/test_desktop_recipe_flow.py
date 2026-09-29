"""Recipe 업데이트 결과 요약(레시피별 변경 수)과 양식 확정 호기 자동 결정(2026-09)."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from param_manager import collate, workdirs
from param_manager.desktop_update import _changes_by_recipe
from param_manager.desktop_form import DesktopForm, machine_of_form
import test_desktop_form


def _rec(param, values, zone="Z1"):
    return dict(PI="PI3", Recipe="PI", Zone=zone, Alg="Genesis", Parameter=param, **{"비고": ""}, **values)


class UpdateSummaryTests(unittest.TestCase):
    def test_changes_by_recipe_counts_what_is_new(self):
        tmp = tempfile.mkdtemp(prefix="rev1-upd-sum-")
        machines = ["AOI-01", "AOI-02"]
        old = os.path.join(tmp, "old.xlsx")
        new = os.path.join(tmp, "new.xlsx")
        collate.write_collation(old, {
            "PI3": collate.CollateRecipe(recipe="PI3", records=[_rec("A", {"AOI-01": "1", "AOI-02": "5"}),
                                                                _rec("B", {"AOI-01": "", "AOI-02": "7"}),
                                                                _rec("C", {"AOI-01": "3", "AOI-02": "3"})]),
            "RDL1": collate.CollateRecipe(recipe="RDL1", records=[_rec("X", {"AOI-01": "9", "AOI-02": "9"})])}, machines)
        collate.write_collation(new, {
            "PI3": collate.CollateRecipe(recipe="PI3", records=[_rec("A", {"AOI-01": "2", "AOI-02": "5"}),   # 값변경
                                                                _rec("B", {"AOI-01": "4", "AOI-02": ""}),    # 추가 + 삭제
                                                                _rec("D", {"AOI-01": "1", "AOI-02": "1"})]),  # 새 항목 (C 빠짐)
            "RDL1": collate.CollateRecipe(recipe="RDL1", records=[_rec("X", {"AOI-01": "9", "AOI-02": "9"})]),
            "PI4": collate.CollateRecipe(recipe="PI4", records=[_rec("Y", {"AOI-01": "1", "AOI-02": ""})])}, machines)
        out = _changes_by_recipe(old, new)
        pi3 = out["PI3"]
        self.assertEqual((pi3["changed"], pi3["added"], pi3["removed"], pi3["new_rows"], pi3["gone_rows"]), (1, 1, 1, 1, 1))
        self.assertEqual(sorted(pi3["changed_machines"]), ["AOI-01", "AOI-02"])
        self.assertFalse(pi3["new_sheet"])
        self.assertNotIn("RDL1", out)                       # nothing changed → not listed (shown as 0)
        self.assertTrue(out["PI4"]["new_sheet"])
        self.assertEqual(_changes_by_recipe("", new), {})    # first collation: nothing to compare


class ConfirmMachineTests(unittest.TestCase):
    setUp = test_desktop_form.DesktopFormTests.setUp     # same temp save folder + PI3 원본 (AOI-01)

    def test_machine_comes_from_the_form_not_the_user(self):
        self.assertEqual(machine_of_form("PI3_AOI-01호기_참조_20260921.xlsx"), "AOI-01")
        self.assertEqual(machine_of_form(r"x\관련파일\PI3_원본_AOI-12호기_참조_20260921_010101.xlsx"), "AOI-12")
        self.assertEqual(machine_of_form("old_form.xlsx"), "")
        self.form.catalog()
        versions = self.form.versions({"recipe": "PI3"})["versions"]
        self.assertTrue(versions[0]["candidate"].endswith(".xlsx") and "_원본_" in versions[0]["candidate"])
        self.assertEqual(versions[0]["machine"], "AOI-01")
        opened = self.form.open({"recipe": "PI3", "stamp": ""})
        self.assertEqual(opened["machine"], "AOI-01")
        result = self.form.confirm({"snapshot": opened["version"], "machine": opened["machine"]})
        self.assertIn("_AOI-01호기_참조_", os.path.basename(result["final"]))


if __name__ == "__main__":
    unittest.main()
