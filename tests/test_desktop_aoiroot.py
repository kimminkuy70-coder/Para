"""설정 'AOI 장비 호기 루트'(2026-09): 호기 폴더 하나로 Batch Report(Reports)와
Commonality(Scanresult*)를 함께 등록하고, 호기별 추가 백업·보관 폴더를 두 기능이 함께 읽는다."""
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from param_manager import desktop_config as dc, desktop_appupdate as au, updater
from param_manager.desktop_batch import DesktopBatch
from param_manager.desktop_cmrun import DesktopCmRun
from test_commonality import _make_wafer
from test_desktop_appupdate import make_package

DEV = "2D@R2-DEVA-1_0855360PD-0A"


class AoiRootTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rev1-aoi-"))
        self.eq = self.tmp / "eq"
        for m in ("AOI-9", "AOI-10"):
            (self.eq / m / "Reports").mkdir(parents=True)
        _make_wafer(self.eq, "AOI-9", DEV, "6321", "HPG", "CX01", delta=25)
        self.cfg = self.tmp / "c.json"
        self.cfg.write_text(json.dumps({"local_dir": str(self.tmp / "local")}), encoding="utf-8")
        self.c = dc.DesktopConfig(self.cfg)

    def raw(self):
        return json.loads(self.cfg.read_text(encoding="utf-8"))

    def test_one_root_feeds_reports_and_scanresult_sorted(self):
        out = self.c.set_aoi_root({"machine": "AOI-10", "path": str(self.eq / "AOI-10")})
        self.assertIn("Reports", out["notice"])
        self.assertIn("Scanresult 폴더를 찾지 못했습니다", out["notice"])
        out = self.c.set_aoi_root({"machine": "AOI-9", "path": str(self.eq / "AOI-9")})
        self.assertIn("Scanresult: Scanresult", out["notice"])
        self.assertEqual([a["machine"] for a in out["aoi"]], ["AOI-9", "AOI-10"])        # 이름(숫자) 순
        cfg = self.raw()
        # 기존 프로그램과 공유하는 구 키도 같은 값으로 맞춰 둔다.
        self.assertEqual(cfg["wph_report_paths"]["AOI-9"], str(self.eq / "AOI-9" / "Reports"))
        self.assertEqual(cfg["commonality_roots"]["AOI-9"], str(self.eq / "AOI-9"))
        # 배치 리포트 분석은 등록 즉시 Reports 폴더를 쓴다(이름 순).
        desc = DesktopBatch(self.cfg).describe()
        self.assertEqual([(m["id"], m["folder"]) for m in desc["machines"]],
                         [("AOI-9", str(self.eq / "AOI-9" / "Reports")), ("AOI-10", str(self.eq / "AOI-10" / "Reports"))])
        with self.assertRaises(ValueError):
            self.c.set_aoi_root({"machine": "AOI-9", "path": str(self.eq / "AOI-9")})   # 중복 등록

    def test_extras_are_read_by_batch_and_commonality(self):
        self.c.set_aoi_root({"machine": "AOI-9", "path": str(self.eq / "AOI-9")})
        backup = self.tmp / "보관" / "Reports_2025"
        backup.mkdir(parents=True)
        (self.eq / "AOI-9" / "Reports" / "2D@X_26-Sep-01_(10.00.00)_BatchReport.htm").write_text("x")
        (backup / "2D@X_25-Jan-01_(10.00.00)_BatchReport.htm").write_text("x")
        # 보관 Scanresult: 호기 루트 밖의 다른 S/M
        _make_wafer(self.tmp / "arch", "AOI-9", DEV, "6321", "TVS", "CX01", delta=25)
        arch = self.tmp / "arch" / "AOI-9"
        st = self.c.set_aoi_extra({"machine": "AOI-9", "kind": "report", "paths": [str(backup)]})
        st = self.c.set_aoi_extra({"machine": "AOI-9", "kind": "scanresult", "paths": [str(arch)]})
        a = st["aoi"][0]
        self.assertEqual(a["extra"], {"report": [str(backup)], "scanresult": [str(arch)]})
        self.assertEqual(self.raw()["batch_extra_paths"]["AOI-9"], [str(backup)])
        found = DesktopBatch(self.cfg).reports({"machine": "AOI-9", "query": "", "start": "", "end": ""})
        self.assertEqual(found["total"], 2)                                  # 기본 + 추가 Reports
        roots = dc.scanresult_roots_for(self.raw(), "AOI-9")
        self.assertEqual(len(roots), 2)                                      # 호기 루트 + 보관 폴더
        run = DesktopCmRun(self.cfg)
        out = run.plan({"machine": "AOI-9", "plan": [
            {"디바이스명": "DEVA-1", "공정번호": "6321", "S/M": sm, "AOI호기": "AOI-9"} for sm in ("HPG", "TVS")]})
        self.assertEqual(sorted(l["label"] for l in out["lots"] if l["exists"]), ["HPG", "TVS"])
        with self.assertRaises(ValueError):
            self.c.set_aoi_extra({"machine": "AOI-9", "kind": "other", "paths": []})
        with self.assertRaises(ValueError):
            self.c.set_aoi_extra({"machine": "AOI-99", "kind": "report", "paths": []})

    def test_rename_remove_and_legacy_view(self):
        # 구 설정: Report 폴더와 Scanresult 루트를 따로 등록했던 파일.
        self.cfg.write_text(json.dumps({
            "local_dir": str(self.tmp / "local"),
            "wph_report_paths": {"AOI-10": str(self.eq / "AOI-10" / "Reports")},
            "commonality_roots": {"AOI-9": str(self.eq / "AOI-9")},
            "batch_extra_paths": {"AOI-10": [str(self.tmp)]}}), encoding="utf-8")
        view = self.c.state()["aoi"]
        self.assertEqual([(v["machine"], v["root"], v["legacy"]) for v in view],
                         [("AOI-9", str(self.eq / "AOI-9"), True), ("AOI-10", str(self.eq / "AOI-10"), True)])
        st = self.c.edit_aoi_root({"machine": "AOI-10", "new_machine": "AOI-11", "path": str(self.eq / "AOI-10")})
        cfg = self.raw()
        self.assertNotIn("AOI-10", cfg["wph_report_paths"])
        self.assertEqual(cfg["batch_extra_paths"], {"AOI-11": [str(self.tmp)]})       # 추가 폴더도 따라감
        self.assertFalse(next(v for v in st["aoi"] if v["machine"] == "AOI-11")["legacy"])
        st = self.c.remove_aoi({"machine": "AOI-11"})
        self.assertEqual([v["machine"] for v in st["aoi"]], ["AOI-9"])
        cfg = self.raw()
        self.assertTrue(all("AOI-11" not in (cfg.get(k) or {}) for k in
                            ("aoi_roots", "commonality_roots", "wph_report_paths", "batch_extra_paths")))

    def test_config_read_never_opens_equipment_folders(self):
        """호기 목록 표시(state)는 경로 문자열만 본다 — 느린 장비 공유를 열지 않는다."""
        self.cfg.write_text(json.dumps({"aoi_roots": {"AOI-1": "\\\\10.0.0.1\\c$\\AOI-1"},
                                        "commonality_roots": {"AOI-1": "\\\\10.0.0.1\\c$\\AOI-1"}}), encoding="utf-8")
        import unittest.mock as um
        with um.patch("os.scandir", side_effect=AssertionError("listed")):
            view = dc.aoi_view(self.raw())
        self.assertEqual(view[0]["root"], "\\\\10.0.0.1\\c$\\AOI-1")


class ZipPublishTests(unittest.TestCase):
    def test_actions_artifact_zip_is_published_and_extracted_only_locally(self):
        tmp = Path(tempfile.mkdtemp(prefix="rev1-zippub-"))
        save = tmp / "OneDrive" / "docs"
        save.mkdir(parents=True)
        cfg = tmp / "c.json"
        cfg.write_text(json.dumps({"save_dir": str(save), "local_dir": str(tmp / "local")}), encoding="utf-8")
        pkg = make_package(tmp, "8.4.0")
        artifact = tmp / "Downloads" / "Camtek_AOI_manager_v8.4.0.zip"
        artifact.parent.mkdir()
        with zipfile.ZipFile(artifact, "w") as zf:          # upload-artifact: 패키지 내용이 zip 최상위
            for f in pkg.rglob("*"):
                if f.is_file():
                    zf.write(f, f.relative_to(pkg).as_posix())
        adapter = au.DesktopAppUpdate(cfg)
        r = adapter.publish({"path": str(artifact), "notes": "zip"})
        self.assertEqual(r["version"], "8.4.0")
        self.assertTrue(os.path.isfile(os.path.join(updater.program_dir(str(save)), au.zip_name("8.4.0"))))
        # 압축 해제는 로컬 Temp 에서만, 끝나면 지운다(OneDrive 에 풀지 않음).
        temp = tmp / "local" / "CamtekAOI" / "Temp"
        self.assertFalse(any(temp.glob("*webpackage*")) if temp.exists() else False)
        self.assertEqual(sorted(p.name for p in Path(updater.program_dir(str(save))).iterdir()),
                         sorted([au.zip_name("8.4.0"), au.WEB_MANIFEST]))
        # 한 단계 폴더로 감싼 zip 도 받는다.
        nested = tmp / "nested.zip"
        with zipfile.ZipFile(nested, "w") as zf:
            inner = make_package(tmp, "8.5.0")
            for f in inner.rglob("*"):
                if f.is_file():
                    zf.write(f, "pkg/" + f.relative_to(inner).as_posix())
        self.assertEqual(adapter.publish({"path": str(nested), "notes": ""})["version"], "8.5.0")
        bad = tmp / "bad.zip"
        with zipfile.ZipFile(bad, "w") as zf:
            zf.writestr("readme.txt", "no manifest")
        with self.assertRaises(ValueError):
            adapter.publish({"path": str(bad), "notes": ""})
        broken = tmp / "broken.zip"
        broken.write_bytes(b"PK\x03\x04 not really")
        with self.assertRaises(ValueError):
            adapter.publish({"path": str(broken), "notes": ""})


if __name__ == "__main__":
    unittest.main()
