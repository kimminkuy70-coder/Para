"""Headless tests for the new-Commonality-investigation plan preflight adapter."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from param_manager.desktop_cmsurvey import DesktopCmSurvey

ZONE = "[Zone]\nMinDefectWidth={delta}\n"
OPTIC = "[Scan2d1]\nMag=1.0\nCameraName=TDI\nLight0=5\n"


def _make_wafer(base, machine, device_folder, lot, sm, wafer):
    wdir = Path(base) / machine / "Scanresult" / device_folder / lot / sm / wafer
    (wdir / "Zones").mkdir(parents=True)
    (wdir / "Zones" / "Z.ini").write_text(ZONE.format(delta=25), encoding="utf-8")
    (wdir / "OpticPreset.ini").write_text(OPTIC, encoding="utf-8")
    (wdir / "RTP.txt").write_text("x", encoding="utf-8")
    return wdir


class CmSurveyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rev1-cmsurvey-")
        _make_wafer(self.tmp, "AOI-6", "2D@R2-DEVA-1_0855360PD-0A", "6321", "HPG", "CX01")
        _make_wafer(self.tmp, "AOI-6", "2D@R2-DEVA-1_0855360PD-0A", "6321", "HPG", "CX02")
        self.cfg = os.path.join(self.tmp, "config.json")
        with open(self.cfg, "w", encoding="utf-8") as fh:
            json.dump({"commonality_roots": {"AOI-6": self.tmp}}, fh)
        self.a = DesktopCmSurvey(config_path=self.cfg)

    def test_config_lists_machines_with_roots(self):
        cfg = self.a.config()
        self.assertEqual([m["id"] for m in cfg["machines"]], ["AOI-6"])
        self.assertEqual(cfg["machines"][0]["root"], self.tmp)

    def test_preflight_found_and_missing(self):
        plan = [
            {"디바이스명": "DEVA-1", "공정번호": "6321", "S/M": "HPG", "AOI호기": "AOI-6"},
            {"디바이스명": "DEVA-1", "공정번호": "9999", "S/M": "HPG", "AOI호기": "AOI-6"},
        ]
        out = self.a.preflight({"machine": "AOI-6", "plan": plan})
        self.assertEqual(out["total"], 2)
        self.assertEqual(out["found"], 1)
        self.assertEqual(out["missing"], 1)
        found = [r for r in out["rows"] if r["exists"]][0]
        self.assertEqual(found["wafer"], "CX01")   # 이름순 첫 슬롯
        missing = [r for r in out["rows"] if not r["exists"]][0]
        self.assertIn("공정", missing["reason"])

    def test_preflight_filters_other_machines(self):
        plan = [{"디바이스명": "DEVA-1", "공정번호": "6321", "S/M": "HPG", "AOI호기": "AOI-9"}]
        with self.assertRaises(ValueError):
            self.a.preflight({"machine": "AOI-6", "plan": plan})

    def test_preflight_rejects_unconfigured_machine(self):
        plan = [{"디바이스명": "DEVA-1", "공정번호": "6321", "S/M": "HPG", "AOI호기": "AOI-9"}]
        with self.assertRaises(ValueError):
            self.a.preflight({"machine": "AOI-9", "plan": plan})

    def test_preflight_validates_plan(self):
        with self.assertRaises(ValueError):
            self.a.preflight({"machine": "AOI-6", "plan": []})
        with self.assertRaises(ValueError):
            self.a.preflight({"machine": "AOI-6", "plan": [{"디바이스명": "", "공정번호": "6321", "S/M": "HPG"}]})

    def test_no_roots_configured(self):
        empty = os.path.join(self.tmp, "empty.json")
        with open(empty, "w", encoding="utf-8") as fh:
            json.dump({}, fh)
        self.assertEqual(DesktopCmSurvey(config_path=empty).config(), {"machines": []})


if __name__ == "__main__":
    unittest.main()
