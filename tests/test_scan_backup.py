"""Scanresult 백업본 포함 조사 설정(이슈 #8) — 원본 / 백업본 구분, 설정 저장, 조사 기능이 설정을 따르는지."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from param_manager import commonality as cm
from param_manager import cmwatcher as cw
from param_manager.desktop_cmsurvey import DesktopCmSurvey
from param_manager.desktop_config import DesktopConfig, scan_backup, scanresult_roots_for, scanresult_roots_info


class ScanBackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="scan-backup-")
        self.machine_dir = Path(self.tmp, "AOI-9")
        for name in ("Scanresult", "Scanresult_260402", "SCANRESULT_BACKUP_260805"):
            (self.machine_dir / name / "2D@R3-DEV1-0001" / "6412" / "ASD" / "CX01").mkdir(parents=True)
        self.extra = Path(self.tmp, "보관", "Scanresult_2025")
        (self.extra / "2D@R3-DEV1-0001" / "6412" / "BQC" / "CX01").mkdir(parents=True)
        self.cfg_path = os.path.join(self.tmp, "config.json")
        self._write({"commonality_roots": {"AOI-9": str(self.machine_dir)},
                     "aoi_extra": {"AOI-9": {"scanresult": [str(self.extra)]}}})

    def _write(self, cfg):
        with open(self.cfg_path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, ensure_ascii=False)

    def _cfg(self):
        with open(self.cfg_path, encoding="utf-8") as fh:
            return json.load(fh)

    def test_backup_names_and_main_only(self):
        self.assertFalse(cm.is_backup_scanresult(self.machine_dir / "ScanResult"))
        self.assertTrue(cm.is_backup_scanresult(self.machine_dir / "Scanresult_260402"))
        every = cm.scanresult_roots(str(self.machine_dir), "AOI-9")
        self.assertEqual(len(every), 3)
        self.assertEqual([p.name for p in cm.scanresult_roots(str(self.machine_dir), "AOI-9", backup=False)], ["Scanresult"])
        # 상위 폴더를 등록해도 같은 규칙(호기 폴더 아래)
        self.assertEqual([p.name for p in cm.scanresult_roots(self.tmp, "AOI-09", backup=False)], ["Scanresult"])

    def test_no_plain_scanresult_keeps_first(self):
        other = Path(self.tmp, "AOI-3")
        (other / "Scanresult_260401").mkdir(parents=True)
        (other / "Scanresult_260501").mkdir(parents=True)
        self.assertEqual([p.name for p in cm.scanresult_roots(str(other), "AOI-3", backup=False)], ["Scanresult_260401"])

    def test_default_is_backup_included_with_kinds(self):
        cfg = self._cfg()
        self.assertTrue(scan_backup(cfg))
        info = scanresult_roots_info(cfg, "AOI-9")
        kinds = {Path(r["path"]).name: r["kind"] for r in info}
        self.assertEqual(kinds, {"Scanresult": "원본", "Scanresult_260402": "백업본",
                                 "SCANRESULT_BACKUP_260805": "백업본", "Scanresult_2025": "추가 폴더"})

    def test_setting_off_limits_every_root_list(self):
        state = DesktopConfig(config_path=self.cfg_path).set_scan_backup({"enabled": False})
        self.assertFalse(state["scan_backup"])
        self.assertIs(self._cfg()["scanresult_backup"], False)
        cfg = self._cfg()
        self.assertEqual([p.name for p in scanresult_roots_for(cfg, "AOI-9")], ["Scanresult"])
        self.assertEqual([r["kind"] for r in scanresult_roots_info(cfg, "AOI-9")], ["원본"])
        with self.assertRaises(ValueError):
            DesktopConfig(config_path=self.cfg_path).set_scan_backup({"enabled": "no"})
        self.assertTrue(DesktopConfig(config_path=self.cfg_path).set_scan_backup({"enabled": True})["scan_backup"])

    def test_survey_preflight_follows_setting(self):
        plan = [{"디바이스명": "DEV1-0001", "공정번호": "6412", "S/M": "BQC", "AOI호기": "AOI-9"}]
        survey = DesktopCmSurvey(config_path=self.cfg_path)
        on = survey.preflight({"machine": "AOI-9", "plan": plan})
        self.assertTrue(on["scan_backup"])
        self.assertEqual(on["found"], 1)        # BQC 는 추가 보관 폴더에만 있다
        self.assertIn("추가 폴더", [r["kind"] for r in on["root_info"]])
        DesktopConfig(config_path=self.cfg_path).set_scan_backup({"enabled": False})
        off = survey.preflight({"machine": "AOI-9", "plan": plan})
        self.assertFalse(off["scan_backup"])
        self.assertEqual(off["found"], 0)
        self.assertEqual([r["kind"] for r in off["root_info"]], ["원본"])

    def test_watch_cycle_roots_follow_backup_flag(self):
        seen = []
        orig = cw.scan_new

        def spy(roots, *a, **k):
            seen.append([Path(r).name for r in roots])
            return orig(roots, *a, **k)
        local = os.path.join(self.tmp, "local")
        os.makedirs(local)
        plan = os.path.join(local, "plan.xlsx")
        cw.create_watch_plan_template(plan, [{"디바이스명": "DEV1-0001", "공정번호": "6412", "AOI호기": "AOI-9", "비고": ""}])
        s = cw.CmWatchSettings(enabled=True, machines=["AOI-9"], watch_plan=plan,
                               roots={"AOI-9": [str(self.machine_dir), str(self.extra)]})
        cw.scan_new = spy
        try:
            cw.run_cycle(s, cw.CmWatchState(), local_root=local, backup=False)
            cw.run_cycle(s, cw.CmWatchState(), local_root=local, backup=True)
        finally:
            cw.scan_new = orig
        self.assertEqual(seen[0], ["Scanresult"])
        self.assertEqual(len(seen[1]), 4)


if __name__ == "__main__":
    unittest.main()
