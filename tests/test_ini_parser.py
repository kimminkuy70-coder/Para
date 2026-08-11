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


def _mk_recipe(d: Path, with_zones_subdir=True, extra_ini=None):
    d.mkdir(parents=True, exist_ok=True)
    (d / "GlobalRTP.ini").write_text(GLOBAL_RTP, encoding="utf-8")
    (d / "OpticPreset.ini").write_text(OPTIC, encoding="utf-8")
    if with_zones_subdir:
        (d / "Zones").mkdir(exist_ok=True)
        (d / "Zones" / "Zone1.ini").write_text(ZONE_INI, encoding="utf-8")
    else:
        (d / "Zone1.ini").write_text(ZONE_INI, encoding="utf-8")
    # config 폴더 바로 아래의 '쓸데없는' ini — 파서가 제외해야 한다.
    for name in (extra_ini or []):
        (d / name).write_text("[Junk]\nFoo = 1\n", encoding="utf-8")


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
        _mk_recipe(root / "AOI-13" / "R_TB500_LIVE_PI3" / "PI",
                   extra_ini=["CameraSetup.ini", "Backup.ini"])            # 쓸데없는 ini
        _mk_recipe(root / "AOI-13" / "R_TB500_LIVE_PI3" / "PI_BUBBLE")     # 장비형 구조
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
    print("  scan_tree OK: PI/PI-bubble/x5 + Zones 구조 + 쓸데없는 ini 제외 + 오버라이드")


def test_config_dir_only_fixed_plus_zones():
    """config 폴더 = GlobalRTP.ini/OpticPreset.ini + Zones/*.ini 만 파싱.
    폴더 바로 아래 다른 .ini(카메라/백업 등)는 양식에 끼면 안 된다."""
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp) / "PI"
        _mk_recipe(d, extra_ini=["CameraSetup.ini", "HW_Config.ini"])
        names = {p.name for p in ini_parser.config_ini_files(d)}
        assert names == {"GlobalRTP.ini", "OpticPreset.ini", "Zone1.ini"}, names
        assert "CameraSetup.ini" not in names and "HW_Config.ini" not in names
        # 파싱 결과에도 Junk Zone 이 없어야 함
        rows, _ = ini_parser.build_pivot(
            ini_parser.scan_tree(d, default_level="PI3", default_equipment="AOI-1"))
        zones = {r["zone"] for r in rows}
        assert "CameraSetup" not in zones and "HW Config" not in zones and "Junk" not in zones
        # _N 접미사(복사 중복회피)도 고정명으로 인식
        (d / "GlobalRTP_2.ini").write_text(GLOBAL_RTP, encoding="utf-8")
        names2 = {p.name for p in ini_parser.config_ini_files(d)}
        assert "GlobalRTP_2.ini" in names2
    print("  config_ini_files OK: 고정2 + Zones/* 만(쓸데없는 ini 제외, _N 인식)")


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
        planned, plan, sources = collector.collect_equipment(
            "10.0.0.1", staging, chooser, use_net_use=False,
            job_root_override=job_root)
        # 단일 모드 반환: sources = [(폴더, job키워드)]
        assert sources == [(str(staging), "PI3")]
        assert len(planned) == 3          # GlobalRTP + OpticPreset + Zone1
        assert plan.job_keyword == "PI3" and plan.recipe_names == ["PI3"]
        assert (staging / "PI3" / "GlobalRTP.ini").is_file()
        assert (staging / collector.LOG_NAME).is_file()
        # 원본 무변경
        assert (rec / "GlobalRTP.ini").read_text(encoding="utf-8") == GLOBAL_RTP
        # 2대째: plan 재사용 → chooser 호출 없이 자동 매칭
        picks.clear()
        got_kw = []

        def staging2(kw):
            got_kw.append(kw)
            return Path(tmp) / "staging2" / kw

        planned2, _, sources2 = collector.collect_equipment(
            "10.0.0.2", staging2, chooser, use_net_use=False,
            plan=plan, job_root_override=job_root)
        assert not picks and len(planned2) == 3
        assert got_kw == ["PI3"] and Path(sources2[0][0]).name == "PI3"
        # 키워드/레시피 매칭 단위 확인
        sel, missing = collector.match_recipes_by_names(
            [rec.parent / "PI3", rec.parent / "PI BUBBLE"], ["PI_BUBBLE"])
        assert missing == [] and sel[0].name == "PI BUBBLE"
    print("  collector OK: 계획 수집/자동 재사용/원본 무변경")


def test_optic_target_tdi():
    """OpticPreset target = CameraName=TDI 섹션 중 마지막(이름 무관)."""
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "OpticPreset.ini"
        p.write_text(
            "[optic A]\nCameraName=TDI\nMag=10\n"
            "LightSrcRef_NominalGL=476.28\nLightSrcRef_ColorFilter=CSI3\n"
            "LightSrcRef_NominalGL_On=1\n"
            "[optic B]\nCameraName=AreaScan\nMag=3.14\n"
            "LightSrcRef_NominalGL=999\nLightSrcRef_ColorFilter=CSI5\n"
            "LightSrcRef_NominalGL_On=1\n", encoding="utf-8")
        secs = ini_parser.parse_ini_sections(p)
        assert ini_parser._pick_optic_target(secs) == "optic A"   # TDI 우선
        assert ini_parser.read_optic_mag(Path(tmp)) == "10"
        # TDI 없으면 광원 키 마지막
        p.write_text("[x]\nLightSrcRef_NominalGL=1\n[y]\nLightSrcRef_NominalGL=2\n",
                     encoding="utf-8")
        assert ini_parser._pick_optic_target(ini_parser.parse_ini_sections(p)) == "y"
    print("  ini_parser OK: OpticPreset CameraName=TDI 마지막 섹션 선택")


def test_active_scenario_optics():
    """신 SW: ActiveScenarioOptics.ini 의 ScenarioName=Scan2d optic 으로 target 선택.
    구 SW(파일 없음): 기존 방식 유지."""
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        # [Scan2d] 가 마지막 → 구 방식이면 이걸 고른다.
        (d / "OpticPreset.ini").write_text(
            "[General]\nName=preset\n"
            "[Engineer optic2]\nCameraName=TDI\nMag=3.14\n"
            "LightSrcRef_NominalGL=222\nLightSrcRef_ColorFilter=CSI5\n"
            "LightSrcRef_NominalGL_On=1\nOpticId=e7d7cd83-7e46-4387-9f6e-c6b7c9a62a29\n"
            "[Scan2d]\nCameraName=TDI\nMag=5\n"
            "LightSrcRef_NominalGL=100\nLightSrcRef_ColorFilter=CSI3\n"
            "LightSrcRef_NominalGL_On=1\n", encoding="utf-8")
        secs = ini_parser.parse_ini_sections(d / "OpticPreset.ini")
        # 파일 없음(구 SW) → 마지막 [Scan2d]
        assert ini_parser.read_active_scan2d(d) is None
        assert ini_parser._pick_optic_target(secs, None) == "Scan2d"
        assert ini_parser.read_optic_mag(d) == "5"
        # ActiveScenarioOptics 추가 → ScenarioName=Scan2d 는 'Engineer optic2'
        (d / "ActiveScenarioOptics.ini").write_text(
            "[a]\nScenarioName=ScenarioGrab_x\nOpticsName=x7.5\nOpticId=bc5369a7\n"
            "[b]\nScenarioName=Scan2d\nOpticsName=Engineer optic2\n"
            "OpticId=e7d7cd83-7e46-4387-9f6e-c6b7c9a62a29\n"
            "[c]\nScenarioName=AutoFocus\nOpticsName=AutoFocus0\nOpticId=7e5cb882\n",
            encoding="utf-8")
        active = ini_parser.read_active_scan2d(d)
        assert active == ("Engineer optic2", "e7d7cd83-7e46-4387-9f6e-c6b7c9a62a29")
        assert ini_parser._pick_optic_target(secs, active) == "Engineer optic2"  # 이름 매칭
        assert ini_parser.read_optic_mag(d) == "3.14"                            # 그 optic Mag
        # 섹션명이 OpticsName 과 달라도 OpticId 로 매칭
        (d / "ActiveScenarioOptics.ini").write_text(
            "[b]\nScenarioName=Scan2d\nOpticsName=DiffName\n"
            "OpticId=e7d7cd83-7e46-4387-9f6e-c6b7c9a62a29\n", encoding="utf-8")
        act2 = ini_parser.read_active_scan2d(d)
        assert ini_parser._pick_optic_target(secs, act2) == "Engineer optic2"    # id 매칭
        # 매칭 실패(없는 optic) → 기존 방식 폴백
        (d / "ActiveScenarioOptics.ini").write_text(
            "[b]\nScenarioName=Scan2d\nOpticsName=없는옵틱\nOpticId=zzz\n", encoding="utf-8")
        act3 = ini_parser.read_active_scan2d(d)
        assert ini_parser._pick_optic_target(secs, act3) == "Scan2d"             # 폴백
    print("  ini_parser OK: ActiveScenarioOptics.ini Scan2d optic 매칭(+구SW 폴백)")


def test_multi_recipe_parsing():
    """다중 레시피(RecipesInfo.ini): 무접두=Recipe-1, RecipeN- 접두=Recipe-N.
    레시피별로 자기 OpticPreset/ActiveScenarioOptics/Zones 만 파싱(값 분리)."""
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / "RecipesInfo.ini").write_text(
            "[Recipe-1]\nName=PI_Bubble\n[Recipe-2]\nName=PI\n[Recipes]\nCount=2\n",
            encoding="utf-8")
        (d / "GlobalRTP.ini").write_text(
            "[GLOBAL_RTP]\nMaxFaultsPerWafer=3000\n", encoding="utf-8")  # 공유
        # Recipe-1 (무접두)
        (d / "OpticPreset.ini").write_text(
            "[General]\nName=p\n[Scan2d1]\nId=aaa\nCameraName=TDI\nMag=7.5\n"
            "LightSrcRef_NominalGL=111\nLightSrcRef_ColorFilter=CSI1\n"
            "LightSrcRef_NominalGL_On=1\n", encoding="utf-8")
        (d / "ActiveScenarioOptics.ini").write_text(
            "[z]\nScenarioName=Scan2d\nOpticsName=Scan2d1\nOpticId=aaa\n", encoding="utf-8")
        (d / "Zones").mkdir()
        (d / "Zones" / "PI_Opening.ini").write_text(
            "[General]\nZoneName=PI Opening\n[Surface]\nHigh_Delta=11\n", encoding="utf-8")
        # Recipe-2 (Recipe2- 접두) — 섹션명은 Scan2dX 지만 active 는 OpticId 로 매칭
        (d / "Recipe2-OpticPreset.ini").write_text(
            "[General]\nName=p\n[Scan2d9]\nId=bbb\nCameraName=TDI\nMag=10\n"
            "LightSrcRef_NominalGL=222\nLightSrcRef_ColorFilter=CSI2\n"
            "LightSrcRef_NominalGL_On=1\n", encoding="utf-8")
        (d / "Recipe2-ActiveScenarioOptics.ini").write_text(
            "[z]\nScenarioName=Scan2d\nOpticsName=DiffName\nOpticId=bbb\n", encoding="utf-8")
        (d / "Recipe2-Zones").mkdir()
        (d / "Recipe2-Zones" / "PI_Opening.ini").write_text(
            "[General]\nZoneName=PI Opening\n[Surface]\nHigh_Delta=99\n", encoding="utf-8")
        (d / "Recipe2-Zones" / "PostProcess.ini").write_text(
            "[General]\nZoneName=PostProcess\n[Volume]\nX=1\n", encoding="utf-8")

        recs = ini_parser.read_recipes_info(d)
        assert recs == [
            {"index": 1, "name": "PI_Bubble", "prefix": ""},
            {"index": 2, "name": "PI", "prefix": "Recipe2-"}], recs
        # 레시피별 optic/mag/active 분리
        assert ini_parser.read_optic_mag(d, "") == "7.5"
        assert ini_parser.read_optic_mag(d, "Recipe2-") == "10"       # 접두 OpticPreset
        assert ini_parser.read_active_scan2d(d, "Recipe2-") == ("DiffName", "bbb")
        f1 = [f.name for f in ini_parser.config_ini_files(d, "")]
        f2 = [f.name for f in ini_parser.config_ini_files(d, "Recipe2-")]
        assert "OpticPreset.ini" in f1 and "Recipe2-OpticPreset.ini" in f2
        assert "PostProcess.ini" in f2 and "PostProcess.ini" not in f1   # Zones 분리
        assert "GlobalRTP.ini" in f1 and "GlobalRTP.ini" in f2           # 공유
        # 전체 파싱: 같은 Zone/Alg/param(High_Delta)이라도 레시피별 값이 다르다
        c1 = ini_parser.scan_tree(d, default_level="PI_Bubble",
                                  default_equipment="LotA", recipe_prefix="")
        c2 = ini_parser.scan_tree(d, default_level="PI", default_equipment="LotA",
                                  recipe_prefix="Recipe2-")

        def hd(cfgs):
            for c in cfgs:
                for r in c.rows:
                    if r.key == "High_Delta":
                        return str(r.raw)
            return None
        assert hd(c1) == "11" and hd(c2) == "99"       # 값 충돌 없이 분리
        assert [c.mag_value for c in c1] == ["7.5"]
        assert [c.mag_value for c in c2] == ["10"]
        # 단일 레시피(파일 없음)면 None
        (d / "RecipesInfo.ini").unlink()
        assert ini_parser.read_recipes_info(d) is None
    print("  ini_parser OK: 다중 레시피 RecipesInfo·접두 파일 분리 파싱")


def test_level_folder_match():
    m = collector.level_folder_match
    assert m("R_TB500_LIVE_PI3 - Enhanced", "Enhanced PI3")
    assert not m("R_TB500_LIVE_PI3 - Enhanced", "Enhanced PI2")
    assert not m("R_TB500_LIVE_PI3_Optic Error", "Enhanced PI3")   # enhanced 없음
    assert m("TB500_RDL1 - Multi", "RDL1")
    print("  collector OK: level_folder_match 토큰 매칭")


def test_collector_per_level_matching():
    """복수 레시피 매칭 모드: **레벨마다 Job 폴더**를 골라, 그 Job 안 Recipe 를 전부
    레벨별 하위폴더로 복사(레시피 레벨이 서로 다른 Job 폴더에 있는 실제 구조)."""
    with tempfile.TemporaryDirectory() as tmp:
        job_root = Path(tmp) / "Job"
        # 레벨마다 별도 Job 폴더, 각 Job 안에 Recipes/{변형들}
        for job, variants in [
            ("R_TB500_LIVE_PI3 - Enhanced", ["PI", "PI_BUBBLE"]),
            ("R_TB500_LIVE_PI4 - Enhanced", ["PI"]),
        ]:
            for v in variants:
                _mk_recipe(job_root / job / "6324" / "Recipes" / v)

        def match_recipes(job_dirs, levels):       # 레벨 토큰이 맞는 Job 매칭
            out = {}
            for lvl in levels:
                hits = [p for p in job_dirs
                        if collector.level_folder_match(p.name, lvl)]
                if hits:
                    out[lvl] = hits
            return out

        def chooser(kind, title, items, multi):    # 단일 job/recipe chooser 는 안 불림
            assert kind == "setup", f"예상외 chooser: {kind}"
            return [items[0]]

        staging = Path(tmp) / "staging"
        planned, plan, sources = collector.collect_equipment(
            "10.0.0.9", staging, chooser, use_net_use=False,
            job_root_override=job_root,
            target_levels=["Enhanced PI3", "Enhanced PI4"],
            match_recipes=match_recipes)
        smap = {lvl: d for d, lvl in sources}
        assert set(smap) == {"Enhanced PI3", "Enhanced PI4"}
        # Enhanced PI3 Job 안의 변형(PI, PI_BUBBLE) 전부 복사
        assert (Path(smap["Enhanced PI3"]) / "PI" / "GlobalRTP.ini").is_file()
        assert (Path(smap["Enhanced PI3"]) / "PI_BUBBLE" / "GlobalRTP.ini").is_file()
        assert (Path(smap["Enhanced PI4"]) / "PI" / "GlobalRTP.ini").is_file()
        # 다음 장비 재사용용 recipe_map = 레벨→Job명
        assert plan.recipe_map["Enhanced PI3"] == ["R_TB500_LIVE_PI3 - Enhanced"]
    print("  collector OK: 레시피(레벨)별 Job 폴더 매칭·Job 안 Recipe 전부 복사")


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
        # [Scan2d1](target 아닌 optic)도 **목록에는 남는다** — 단 전부 사용=N
        # (2026-08 변경: 종전에는 이름이 Scan2dN 인 것만 통째로 버렸다)
        other = [r for r in rows if r.section == "Scan2d1"]
        assert other and all(r.use_default is False for r in other)
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


def test_micron_transform_and_globalrtp_keep():
    with tempfile.TemporaryDirectory() as tmp:
        # #2 GlobalRTP: Max Defects Per Die/Wafer 만 기본 Y
        g = Path(tmp) / "GlobalRTP.ini"
        g.write_text("[GLOBAL_RTP]\nMaxFaultsPerWafer=3000\nMaxFaultsPerDie=50\n"
                     "ApplyDieCalib=1\nDuplicateRange_um=10\n", encoding="utf-8")
        gr = {r.param: r for r in ini_parser.parse_ini_file(g)}
        assert gr["Max Defects Per Wafer"].use_default is True
        assert gr["Max Defects Per Die"].use_default is True
        assert gr["Apply Die Calib"].use_default is False
        assert gr["Apply Die Calib"].transform == "BOOL"        # 특수 변환 유지
        assert gr["Duplicate Range um"].use_default is False     # 'um'(µ 아님) → 변환 안 함
        assert gr["Duplicate Range um"].transform == "RAW"

        # #3 µ 규칙: Width(µ 없음)=RAW, Length/Area(µ)=변환
        z = Path(tmp) / "Zone.ini"
        z.write_text("[General]\nZoneName=PI Opening\n[Surface]\n"
                     "BrightDiameter=100\nBrightLength=100\nBrightArea=100\n", encoding="utf-8")
        zr = {r.key: r for r in ini_parser.parse_ini_file(z, scale=0.5)}
        assert zr["BrightDiameter"].transform == "RAW"           # 'Width'(µ 없음)
        assert zr["BrightDiameter"].value == 100                 # 변환 안 함
        assert zr["BrightLength"].transform.startswith("LINEAR") and zr["BrightLength"].value == 50.0
        assert zr["BrightArea"].transform.startswith("AREA") and zr["BrightArea"].value == 25.0
    print("  transform OK: µ 있으면 변환(Length/Area)·없으면 RAW(Width) + GlobalRTP 2개만 Y")


def test_optic_keeps_all_keys_for_manual_pick():
    """OpticPreset 잡키(Id/ZWafer/FocusPos/CreationMeasure*/GUID)도 **버리지 않는다**
    (사용자 확정 2026-08) — 양식에서 체크박스로 고를 수 있어야 하므로.
    대신 기본 '사용'은 N 이고, 광원 KEEP 항목만 Y 다."""
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "OpticPreset.ini"
        p.write_text(
            "[Scan2d1]\n"
            "CameraName = TDI\n"
            "Alg = Scan2d1\n"
            "Id = 3f2504e0-4f89-11d3-9a0c-0305e82c3301\n"
            "ZWafer = 1234\n"
            "FocusPosAboveChuck = 55.5\n"
            "CreationMeasureDistance1 = 10\n"
            "CreationMeasureIntensity2 = 20\n"
            "LightSrcDif_NominalGL = 120\n",
            encoding="utf-8")
        rows = ini_parser.parse_ini_file(p)
        got = {r.key: r for r in rows}
        for k in ("Id", "ZWafer", "FocusPosAboveChuck",
                  "CreationMeasureDistance1", "CreationMeasureIntensity2"):
            assert k in got, f"{k} 가 사라졌다(이제는 남겨야 함)"
            assert got[k].use_default is False, f"{k} 는 기본 사용=N 이어야 함"
        assert got["LightSrcDif_NominalGL"].use_default is True, "광원 KEEP 은 Y"
        # 합성행도 그대로
        assert any(r.param == ini_parser.SCAN2D_LATEST_PARAM for r in rows)
    print("  OpticPreset 잡키 유지(사용=N) + 광원 KEEP 만 Y OK")


def test_unknown_recipe_folder_names_are_loaded():
    """레시피 폴더 이름이 규칙에 안 맞아도(2D+3D_CAMTEK 등) 구조가 맞으면 읽는다.

    구 규칙은 변형 이름이 PI/PI-bubble/x5/x20 이어야 통과시켜서, 이름만 다른
    정상 폴더가 전부 걸러지고 "인식된 설정(config) 폴더가 없습니다" 가 났다
    (2026-08 실사고). 이제 **폴더 이름을 변형 라벨로 그대로 쓰고**, 유효성은
    실제로 파싱된 항목이 있는지로 판단한다.
    """
    import tempfile
    from pathlib import Path
    zone = "[General]\nZoneName = PI Opening\n[Surface]\nHigh_Delta = 25\n"
    optic = "[Scan2d1]\nCameraName = TDI\nAlg = Scan2d1\n" \
            "LightSrcDif_NominalGL = 120\nMag = 3.14\n"
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "AOI-11" / "2D@R2-15966PA0-BW2_0859654PD-0B"
        names = ["2D+3D_CAMTEK", "2D+3D_CAMTEK_BUMP", "DUMMY"]
        for r in names:
            d = base / r
            (d / "Zones").mkdir(parents=True)
            (d / "Zones" / "B.ini").write_text(zone, encoding="utf-8")
            (d / "GlobalRTP.ini").write_text(
                "[General]\nMax Defects Per Wafer = 5000\n", encoding="utf-8")
            (d / "OpticPreset.ini").write_text(optic, encoding="utf-8")
            (d / "RTP.txt").write_text("x", encoding="utf-8")
        (base / "_수집로그.txt").write_text("log", encoding="utf-8")

        cfgs = ini_parser.scan_tree(base, default_level="PI3",
                                    default_equipment="AOI-11")
        assert len(cfgs) == 3, [c.config_dir.name for c in cfgs]
        assert all(ini_parser.config_valid(c) for c in cfgs), \
            "구조가 맞는데 걸러졌다"
        # 변형 라벨 = 폴더 이름(레시피를 구분하는 정보이므로)
        assert sorted(c.mag for c in cfgs) == sorted(names), \
            [c.mag for c in cfgs]
        rows, machines = ini_parser.build_pivot(cfgs)
        assert rows and machines == ["AOI-11"]

    # 익숙한 이름은 종전 라벨을 그대로 유지(회귀 방지)
    from pathlib import Path as _P
    assert ini_parser.detect_variant(_P("PI3"), "PI") == "PI"
    assert ini_parser.detect_variant(_P("PI_BUBBLE"), "PI") == "PI-bubble"
    assert ini_parser.detect_variant(_P("x20"), "RDL") == "x20"
    # 빈 config(파싱 결과 없음)는 여전히 무효
    assert ini_parser.config_valid(type("X", (), {"rows": []})()) is False
    print("  이름 규칙과 다른 레시피 폴더도 로드(변형=폴더명) OK")


def test_never_copy_optics_excluded():
    """이름 끝에 `_@NEVER COPY THIS!!!!!` 가 붙은 optic 은 **target 후보에서 제외**.

    OpticPreset.ini 에는 리뷰·얼라인·clean reference 등 여러 역할의 optic 이 섞여
    있고 순서가 역할과 무관하다. '마지막 광원 섹션' 규칙만 쓰면 복사 금지로 표시된
    리뷰 옵틱이 뽑혀 **엉뚱한 값이 clean reference 값인 척** 취합된다.
    제외 규칙만 앞에 붙이고, 그 뒤 판정은 종전과 완전히 같다.
    """
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / "OpticPreset.ini").write_text(
            "[General]\nName=preset\n"
            "[Align optic]\nCameraName=TDI\nMag=1.00\n"
            "LightSrcRef_NominalGL=10\n"
            "[CleanRef optic]\nCameraName=TDI\nAlg=Scan2d7\nMag=3.14\n"
            "LightSrcRef_NominalGL=222\nLightSrcRef_ColorFilter=CSI5\n"
            "LightSrcRef_NominalGL_On=1\n"
            "[Review optic_@NEVER COPY THIS!!!!!]\nCameraName=TDI\nMag=9.99\n"
            "LightSrcRef_NominalGL=999\nLightSrcRef_ColorFilter=CSI9\n"
            "LightSrcRef_NominalGL_On=1\n", encoding="utf-8")
        secs = ini_parser.parse_ini_sections(d / "OpticPreset.ini")
        # 제외 표시가 없었다면 마지막(Review)이 뽑힌다 → 제외 규칙이 실제로 동작해야
        assert ini_parser._pick_optic_target(secs, None) == "CleanRef optic"
        assert ini_parser.read_optic_mag(d) == "3.14", "MAG(계수 키)도 제외본을 보면 안 됨"

        # ActiveScenarioOptics 가 제외 optic 을 가리켜도 후보가 아니다
        (d / "ActiveScenarioOptics.ini").write_text(
            "[b]\nScenarioName=Scan2d\n"
            "OpticsName=Review optic_@NEVER COPY THIS!!!!!\n", encoding="utf-8")
        act = ini_parser.read_active_scan2d(d)
        assert ini_parser._pick_optic_target(secs, act) == "CleanRef optic"

        # 표시 흔들림 허용: 느낌표 개수·대소문자·뒤 공백
        for name in ("R_@NEVER COPY THIS!!!!!", "R_@never copy this!!!",
                     "R_@NEVER COPY THIS", "R_@NEVER COPY THIS!!!!!   "):
            assert ini_parser.optic_excluded(name, {}), name
        # 이름 키(Alg/OpticsName)에만 붙어 있어도 제외
        assert ini_parser.optic_excluded("X", {"Alg": "S9_@NEVER COPY THIS!!!!!"})
        assert ini_parser.optic_excluded("X", {"OpticsName": "R_@NEVER COPY THIS!!!!!"})
        # **끝**에 있을 때만 — 앞이나 중간에 있으면 정상 optic 이다
        assert not ini_parser.optic_excluded("NEVER COPY THIS optic", {})
        assert not ini_parser.optic_excluded("R_@NEVER COPY THIS!!!!!_v2", {})
        assert not ini_parser.optic_excluded("CleanRef optic", {})
    print("  ini_parser OK: '복사 금지' optic 은 target 후보에서 제외")


def test_all_optics_excluded_is_safe():
    """모든 optic 이 제외 표시면 target 없음 — 예외 없이 조용히 넘어가야 한다."""
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / "OpticPreset.ini").write_text(
            "[A_@NEVER COPY THIS!!!!!]\nCameraName=TDI\nMag=1\n"
            "LightSrcRef_NominalGL=1\n"
            "[B_@NEVER COPY THIS!!!!!]\nCameraName=TDI\nMag=2\n"
            "LightSrcRef_NominalGL=2\n", encoding="utf-8")
        secs = ini_parser.parse_ini_sections(d / "OpticPreset.ini")
        assert ini_parser._pick_optic_target(secs, None) is None
        assert ini_parser.read_optic_mag(d) == "", "제외본 Mag 를 계수 키로 쓰면 안 됨"
        assert ini_parser._pick_optic_target({}, None) is None
        # 파일은 그대로 파싱된다(그냥 일반 ini 취급 — 행이 사라지지 않음)
        rows = ini_parser.parse_ini_file(d / "OpticPreset.ini")
        assert rows
    print("  ini_parser OK: 전부 제외돼도 안전(target 없음·Mag 없음)")


def test_non_target_optics_stay_visible():
    """target 이 아닌 optic 도 **전부 목록에 남는다**(사용=N) — 이름 규칙 무관.

    종전에는 이름이 `Scan2dN` 형인 섹션만 통째로 버려서, 옵틱 이름이 자유로운
    장비에서는 `[Align optic]` 은 보이고 `[Scan2d1]` 만 사라지는 비일관이 있었다.
    이제 보이는 것과 기본 체크(사용=Y)를 분리한다.
    """
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / "OpticPreset.ini").write_text(
            "[Scan2d1]\nCameraName=TDI\nMag=2.0\nLightSrcRef_NominalGL=100\n"
            "[Align optic]\nCameraName=TDI\nMag=1.0\nLightSrcRef_NominalGL=10\n"
            "[Engineer optic2]\nCameraName=TDI\nAlg=Scan2d9\nMag=3.14\n"
            "LightSrcRef_NominalGL=222\nLightSrcRef_ColorFilter=CSI5\n"
            "LightSrcRef_NominalGL_On=1\n"
            "[Scan2d]\nCameraName=TDI\nMag=5.0\nLightSrcRef_NominalGL=500\n",
            encoding="utf-8")
        (d / "ActiveScenarioOptics.ini").write_text(
            "[b]\nScenarioName=Scan2d\nOpticsName=Engineer optic2\n", encoding="utf-8")
        rows = ini_parser.parse_ini_file(d / "OpticPreset.ini")
        secs = {r.section for r in rows}
        assert {"Scan2d1", "Align optic", "Engineer optic2", "Scan2d"} <= secs, secs

        # 사용=Y 는 target(Engineer optic2) 에만
        yes = {(r.section, r.param) for r in rows if r.use_default}
        assert all(sec == "Engineer optic2" for sec, _ in yes), yes
        assert ("Engineer optic2", ini_parser.SCAN2D_LATEST_PARAM) in yes

        # target 은 alg 가 'Scan2d' 로 통일, 나머지는 섹션 이름 그대로
        alg = {r.section: r.alg for r in rows}
        assert alg["Engineer optic2"] == ini_parser.OPTIC_ALG
        assert alg["Scan2d1"] == "Scan2d1" and alg["Align optic"] == "Align optic"
        # 하필 이름이 'Scan2d' 인 비선택 섹션은 target 과 Alg 가 겹쳐 한 줄로
        # 합쳐지므로(값 덮어씀) 꼬리표로 갈라 놓는다
        assert alg["Scan2d"] == "Scan2d" + ini_parser.OPTIC_OTHER_SUFFIX
        assert alg["Scan2d"] != ini_parser.OPTIC_ALG

        # 피벗에서도 두 줄이 살아 있어야 한다(합쳐지면 값이 하나만 남는다)
        cfgs = ini_parser.scan_tree(d, default_equipment="AOI-13")
        pivot, _m = ini_parser.build_pivot(cfgs)
        gl = [r for r in pivot if r["param"] == "LightSrcRef_NominalGL"]
        assert len(gl) == 4, [(r["alg"], r["raws"]) for r in gl]
        raws = {r["alg"]: engine._s(list(r["raws"].values())[0]) for r in gl}
        assert raws[ini_parser.OPTIC_ALG] == "222", raws          # target 값
        assert raws["Scan2d" + ini_parser.OPTIC_OTHER_SUFFIX] == "500", raws
    print("  ini_parser OK: 비선택 optic 도 목록 유지(사용=N)·Alg 충돌 회피")


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
