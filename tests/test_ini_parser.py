"""ini_parser / workdirs / refresh / extract_io / collector 헤드리스 테스트."""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from param_manager import collector, engine, extract_io, ini_parser, refresh, workdirs  # noqa: E402
from param_manager import rtp_parser  # noqa: E402

GLOBAL_RTP = """[GLOBAL_RTP]
MaxFaultsPerWafer = 3000 ; comment
ApplyDieCalib = 1
DuplicateRange_um = 10.5
"""

ZONE_INI = """[General]
ZoneName = PI Opening / Mask Zone
[Surface]
High_Delta = 25 ; bright delta
BrightLength = 5
[Genesis]
BrightSeedTh = 7
"""

OPTIC = """[General]
Name = preset
[Scan2d]
Mag = 5
CameraName = TDI
ScanSpeed = 80
"""


def _mk_recipe(d: Path, with_zones_subdir=True):
    d.mkdir(parents=True, exist_ok=True)
    (d / "GlobalRTP.ini").write_text(GLOBAL_RTP, encoding="utf-8")
    (d / "OpticPreset.ini").write_text(OPTIC, encoding="utf-8")
    if with_zones_subdir:
        (d / "Zones").mkdir(exist_ok=True)
        (d / "Zones" / "Zone1.ini").write_text(ZONE_INI, encoding="utf-8")
    else:
        (d / "Zone1.ini").write_text(ZONE_INI, encoding="utf-8")


def test_parse_ini_file():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "GlobalRTP.ini"
        p.write_text(GLOBAL_RTP, encoding="utf-8")
        rows = ini_parser.parse_ini_file(p)
        assert len(rows) == 3, rows
        by_key = {r.key: r for r in rows}
        r = by_key["MaxFaultsPerWafer"]
        assert r.zone == "GlobalRTP" and r.param == "Max Defects Per Wafer"
        assert r.raw == 3000 and r.value == 3000
        assert by_key["ApplyDieCalib"].value == "Checked"       # BOOL 변환
        z = Path(tmp) / "Zone1.ini"
        z.write_text(ZONE_INI, encoding="utf-8")
        zr = ini_parser.parse_ini_file(z)
        bz = {r.key: r for r in zr}
        assert bz["High_Delta"].zone == "PI Opening / Mask Zone"
        assert bz["High_Delta"].alg == "Surface"
        assert bz["High_Delta"].param == "Contrast Delta - Bright"
        assert bz["BrightLength"].value == round(5 * ini_parser.SCALE, 6)  # LINEAR
        assert bz["BrightSeedTh"].param == "Bright Sensitivity"
    print("  parse_ini_file OK: 표시매핑/BOOL/LINEAR 변환")


def test_scan_tree_and_meta():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _mk_recipe(root / "AOI-13" / "R_TB500_LIVE_PI3" / "PI")           # 장비형 구조
        _mk_recipe(root / "AOI-13" / "R_TB500_LIVE_PI3" / "PI_BUBBLE",
                   with_zones_subdir=False)                                # staging 평탄 구조
        _mk_recipe(root / "AOI-20" / "TB500_RDL4 - Multi" / "x5")
        cfgs = ini_parser.scan_tree(root)
        assert len(cfgs) == 3, [c.config_dir for c in cfgs]
        by_mag = {(c.recipe, c.mag): c for c in cfgs}
        assert ("PI3", "PI") in by_mag and ("PI3", "PI-bubble") in by_mag
        assert ("RDL4", "x5") in by_mag
        c = by_mag[("PI3", "PI")]
        assert c.equipment == "AOI-13" and c.layer == "PI"
        assert all(rtp_parser.config_valid(c) for c in cfgs)
        # default 오버라이드(수집 단계에서 이미 아는 값)
        one = ini_parser.scan_tree(root / "AOI-20", default_level="RDL4",
                                   default_equipment="AOI-99")
        assert one[0].equipment == "AOI-99" and one[0].recipe == "RDL4"
    print("  scan_tree OK: PI/PI-bubble/x5 + 평탄/Zones 구조 + 오버라이드")


def test_pivot_and_refresh_plan():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _mk_recipe(root / "AOI-13" / "PI3" / "PI")
        rows, machines = ini_parser.build_pivot(ini_parser.scan_tree(root))
        assert machines == ["AOI-13"]
        assert any(r["extract"]["key"] == "High_Delta" for r in rows)

        # 공용 파일: 같은 키 1행(값 옛것) + 안 맞는 행 1개
        dest = os.path.join(tmp, "form_PI.xlsx")
        recs = [
            {"PI": "PI3", "Recipe": "PI", "Zone": "PI Opening / Mask Zone",
             "Alg": "Surface", "Parameter": "Contrast Delta - Bright",
             "초기 추천값": "25", "AOI-13": "99"},
            {"PI": "PI3", "Recipe": "PI", "Zone": "없는 Zone", "Alg": "X",
             "Parameter": "그런 파라미터 없음"},
        ]
        repo = engine.create_from_records(dest, recs, ["AOI-13"], sheet_name="PI_ALL")
        plan = refresh.plan_refresh(repo, rows, machines)
        assert plan.matched_rows == 1 and plan.unmatched_rows == 1
        chg = [c for c in plan.changes if c.param == "Contrast Delta - Bright"]
        assert len(chg) == 1 and chg[0].old == "99" and chg[0].new == "25"
        stats = refresh.apply_refresh(repo, plan)
        assert stats["updated_cells"] == len(plan.changes)
        pr = next(p for p in repo.rows if engine._s(p.get("Parameter")) == "Contrast Delta - Bright")
        assert engine._s(pr.get("AOI-13")) == "25"
    print("  pivot+refresh OK: 미리보기 diff → 적용")


def test_workdirs_and_backup():
    with tempfile.TemporaryDirectory() as tmp:
        shared = os.path.join(tmp, "TB500_PI.xlsx")
        Path(shared).write_bytes(b"dummy")
        base = workdirs.base_dir_for(shared)
        ini = workdirs.initial_run_dir(base, "PI3", "AOI-13", "20260706_1430")
        fin = workdirs.final_run_dir(base, "PI3", "AOI-13", "20260706_1430")
        assert ini.endswith(os.path.join("initial", "PI3", "AOI-13", "20260706_1430"))
        assert fin.endswith(os.path.join("final", "PI3", "AOI-13", "20260706_1430"))
        st = workdirs.staging_dir(ini)
        assert os.path.isdir(st) and st.endswith("staging")
        b1 = workdirs.backup_shared_file(shared)
        b2 = workdirs.backup_shared_file(shared)
        assert os.path.isfile(b1) and os.path.isfile(b2) and b1 != b2
        assert os.path.dirname(b1).endswith("백업")
        assert Path(shared).read_bytes() == b"dummy"   # 원본 무변경
    print("  workdirs OK: initial/final/레벨/호기/일시 + 백업 중복회피")


def test_extract_snapshot_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        dest = os.path.join(tmp, "01_초안_AOI-13_PI3.xlsx")
        recs = [{"PI": "PI3", "Recipe": "PI", "Zone": "Z", "Alg": "Surface",
                 "Parameter": "P1", "AOI-13": "1"},
                {"PI": "PI3", "Recipe": "PI", "Zone": "Z", "Alg": "Surface",
                 "Parameter": "P2", "AOI-13": "2"}]
        exts = [{"src_file": "Zone1.ini", "section": "Surface", "key": "K1",
                 "raw": 1, "transform": "RAW", "source_path": "/x/Zone1.ini"},
                None]
        extract_io.write_snapshot(dest, recs, ["AOI-13"], "PI_ALL", exts,
                                  stage="initial", level="PI3", aoi="AOI-13",
                                  source="/src", user="tester")
        # 공용 파일처럼 다시 열림 + 맵 왕복
        repo = engine.ParamRepository(dest)
        repo.load()
        assert len(repo.rows) == 2 and "AOI-13" in repo.aoi_units
        amap = extract_io.read_extract_map(dest)
        assert len(amap) == 2
        r0 = amap[repo.rows[0].row_id]
        assert r0["key"] == "K1" and r0["section"] == "Surface"
    print("  extract_io OK: 스냅샷 생성 → ParamRepository/맵 왕복")


def test_collector_plan_and_copy():
    with tempfile.TemporaryDirectory() as tmp:
        # 가짜 장비 트리: Job/<job>/<setup>/Recipes/<recipe>/{고정2 + Zones}
        job_root = Path(tmp) / "Job"
        rec = job_root / "R_TB500_LIVE_PI3 AOI-13" / "6324" / "Recipes" / "PI3"
        _mk_recipe(rec)
        picks = []

        def chooser(kind, title, items, multi):
            picks.append(kind)
            return list(items) if multi else [items[0]]

        staging = Path(tmp) / "staging"
        planned, plan, used_root = collector.collect_equipment(
            "10.0.0.1", staging, chooser, use_net_use=False,
            job_root_override=job_root)
        assert Path(used_root) == staging
        assert len(planned) == 3          # GlobalRTP + OpticPreset + Zone1
        assert plan.job_keyword == "PI3" and plan.recipe_names == ["PI3"]
        assert (staging / "PI3" / "GlobalRTP.ini").is_file()
        assert (staging / collector.LOG_NAME).is_file()
        # 원본 무변경
        assert (rec / "GlobalRTP.ini").read_text(encoding="utf-8") == GLOBAL_RTP
        # 2대째: plan 재사용 → chooser 호출 없이 자동 매칭
        picks.clear()
        # staging 을 콜러블로 — Job 키워드 확정 후 레벨별 폴더 결정
        got_kw = []

        def staging2(kw):
            got_kw.append(kw)
            return Path(tmp) / "staging2" / kw

        planned2, _, root2 = collector.collect_equipment(
            "10.0.0.2", staging2, chooser, use_net_use=False,
            plan=plan, job_root_override=job_root)
        assert not picks and len(planned2) == 3
        assert got_kw == ["PI3"] and Path(root2).name == "PI3"
        # 키워드/레시피 매칭 단위 확인
        sel, missing = collector.match_recipes_by_names(
            [rec.parent / "PI3", rec.parent / "PI BUBBLE"], ["PI_BUBBLE"])
        assert missing == [] and sel[0].name == "PI BUBBLE"
    print("  collector OK: 계획 수집/자동 재사용/원본 무변경")


def test_scale_param_per_variant():
    # 변환 계수 인자화: LINEAR→×scale, AREA→×scale²
    assert ini_parser.transform_value(1000, "LINEAR_x", scale=0.5) == 500.0
    assert ini_parser.transform_value(1000, "AREA_x", scale=0.5) == 250.0
    assert ini_parser.transform_value(1, "BOOL", scale=0.5) == "Checked"
    with tempfile.TemporaryDirectory() as tmp:
        # 변형 두 개(PI / PI BUBBLE) — 같은 파라미터, 계수만 다르게 적용
        for name in ("PI", "PI BUBBLE"):
            d = Path(tmp) / "R_TB500_PI3" / name
            d.mkdir(parents=True)
            (d / "GlobalRTP.ini").write_text(GLOBAL_RTP, encoding="utf-8")
            (d / "Zones").mkdir()
            (d / "Zones" / "Z.ini").write_text(ZONE_INI, encoding="utf-8")
        scales = {"PI": 0.5, "PI-bubble": 0.25}
        cfgs = ini_parser.scan_tree(Path(tmp) / "R_TB500_PI3", default_level="PI3",
                                    scales=scales)
        by_variant = {c.mag: c for c in cfgs}
        # BrightLength=5 (LINEAR) → PI: 5*0.5=2.5, PI-bubble: 5*0.25=1.25
        def brow(cfg):
            return next(r for r in cfg.rows if r.key == "BrightLength")
        assert brow(by_variant["PI"]).value == 2.5
        assert brow(by_variant["PI-bubble"]).value == 1.25
        # 변환방식 라벨이 실제 계수를 반영(하드코딩 0.8452 아님)
        assert brow(by_variant["PI"]).transform == "LINEAR_0.5"
        assert brow(by_variant["PI-bubble"]).transform == "LINEAR_0.25"
        assert "0.8452" not in brow(by_variant["PI"]).transform
    print("  scale OK: 계수 인자화 + 변형별 적용 + 변환방식 라벨에 실제 계수 반영")


# 실제 구조: [Scan2d] 섹션에 Alg 키(=최신 Scan2d명) + 파라미터들. [Scan2d1]은 잡음/인스턴스.
OPTIC_MULTI = """[General]
Name = preset
[Scan2d]
Alg = Scan2d1
GO = RefOnly
GainOffsetMode = RefOnly
LightSrcDif_ColorFilter = Gray
LightSrcDif2_ColorFilter = Gray
LightSrcRef_ColorFilter = CSI_1
LightSrcDif_NominalGL = 49.6969316003874
LightSrcDif2_NominalGL = 32.0987714085474
LightSrcRef_NominalGL = 632.24986535243
LightSrcDif_NominalGL_On = 0
LightSrcDif2_NominalGL_On = 0
LightSrcRef_NominalGL_On = 1
Mag = 10
Material = ABC
[Scan2d1]
Id = 0f8b1a2c-1111-2222-3333-444455556666
"""


def test_optic_latest_scan2d():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "OpticPreset.ini"
        p.write_text(OPTIC_MULTI, encoding="utf-8")
        rows = ini_parser.parse_ini_file(p)
        by = {(r.section, r.key): r for r in rows}
        # [Scan2d1](잡음 인스턴스)은 제외
        assert not any(r.section == "Scan2d1" for r in rows)
        # KEEP 9개는 alg=Scan2d, 사용=Y (버그: 예전엔 N 이었음)
        for k in ini_parser.OPTIC_SCAN2D_KEEP:
            assert by[("Scan2d", k)].use_default is True, k
            assert by[("Scan2d", k)].alg == "Scan2d"
        # KEEP 밖(GO/Mag/Material)은 사용=N
        assert by[("Scan2d", "GO")].use_default is False
        assert by[("Scan2d", "Mag")].use_default is False
        # 'Alg' 키 자체는 파라미터 행으로 나오지 않음
        assert ("Scan2d", "Alg") not in by
        # 합성 행: 최신 이름 = Alg 값(Scan2d1), alg=Scan2d, 사용=Y
        syn = by[("Scan2d", ini_parser.SCAN2D_LATEST_PARAM)]
        assert syn.value == "Scan2d1" and syn.use_default is True and syn.alg == "Scan2d"
        # 배치: 합성 행이 첫 KEEP 행 바로 위
        keys = [(r.section, r.key) for r in rows]
        first_keep = min(keys.index(("Scan2d", k)) for k in ini_parser.OPTIC_SCAN2D_KEEP)
        assert keys[first_keep - 1] == ("Scan2d", ini_parser.SCAN2D_LATEST_PARAM)
    print("  optic OK: [Scan2d]+Alg키 → KEEP 9개 Y, 합성행(Alg값) 첫 KEEP 위, 나머지 N")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for t in tests:
        print(f"[RUN] {t.__name__}")
        try:
            t()
            passed += 1
            print(f"[PASS] {t.__name__}\n")
        except Exception as e:  # noqa: BLE001
            import traceback
            print(f"[FAIL] {t.__name__}: {e}")
            traceback.print_exc()
            print()
    print(f"==== {passed}/{len(tests)} passed ====")
    sys.exit(0 if passed == len(tests) else 1)
