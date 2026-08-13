"""collate(재설계) 테스트 — 레시피별 시트·전체 호기·직전본 이어받기·불일치."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import openpyxl  # noqa: E402

from param_manager import collate, engine, formbuilder, ini_parser, workdirs  # noqa: E402

GLOBAL = "[GLOBAL_RTP]\nMaxFaultsPerWafer = {v}\nApplyDieCalib = 1\n"
ZONE = "[General]\nZoneName = PI Opening\n[Surface]\nHigh_Delta = 25\n"


def _pivot(root, equip, wafer="3000"):
    rec = Path(root) / "R_TB500_PI3" / "PI"
    rec.mkdir(parents=True, exist_ok=True)
    (rec / "GlobalRTP.ini").write_text(GLOBAL.format(v=wafer), encoding="utf-8")
    (rec / "Zones").mkdir(exist_ok=True)
    (rec / "Zones" / "Z.ini").write_text(ZONE, encoding="utf-8")
    cfgs = ini_parser.scan_tree(Path(root) / "R_TB500_PI3", default_equipment=equip)
    return ini_parser.build_pivot(cfgs)[0]


def _make_form(save_dir, tmp):
    """PI3 양식을 양식/PI3/{stamp}/ 에 배치."""
    rows = _pivot(os.path.join(tmp, "A"), "AOI-24")
    init = os.path.join(tmp, "init.xlsx")
    formbuilder.build_initial_workbook(rows, init, level="PI3")
    st = workdirs.stamp()
    run = workdirs.form_run_dir(save_dir, "PI3", st)
    final = workdirs.form_final_path(run, "PI3", "AOI-24", st)
    formbuilder.build_final_from_initial(init, final, level="PI3")
    return final


def test_form_transform_reapplied_on_update():
    """값 업데이트가 **양식의 변환방식**을 수집 raw 에 재적용해야 한다.
    (사람이 양식에서 AREA 로 고쳤는데 값 업데이트가 raw 그대로 넣던 버그 회귀.)"""
    from param_manager import extract_io
    with tempfile.TemporaryDirectory() as tmp:
        form = os.path.join(tmp, "form.xlsx")
        recs = [{"PI": "PI3", "Recipe": "PI", "Zone": "RDL", "Alg": "Uniform Surface",
                 "Parameter": "Rich Events Min Area (area, µ)", "비고": ""}]
        exts = [{"src_file": "RDL.ini", "section": "Uniform Surface",
                 "key": "RichEventsMinArea", "raw": 2,
                 "transform": "AREA_0.7707763913156815^2", "source_path": ""}]
        extract_io.write_snapshot(form, recs, machines=[], sheet_name="PI_ALL",
                                  extracts=exts, stage="final", level="PI3")
        # 수집 피벗: 같은 설정키, raw=2, 파싱은 RAW(변환 안 됨)로 들어왔다고 가정
        pivot = [{"layer": "RDL", "recipe": "PI3", "mag": "PI", "zone": "RDL",
                  "alg": "Uniform Surface", "param": "RichEventsMinArea",
                  "values": {"AOI-6": 2}, "raws": {"AOI-6": 2},
                  "mags": {"AOI-6": "3.14"}, "use": True,
                  "extract": {"src_file": "RDL.ini", "section": "Uniform Surface",
                              "key": "RichEventsMinArea", "transform": "RAW",
                              "source_path": ""}}]
        # 계수 콜백 없음 → 양식 라벨의 계수(0.7707..) 재적용
        res = collate.collate_recipe("PI3", form, pivot, ["AOI-6"])
        got = float(engine._s(res.records[0].get("AOI-6")))
        assert abs(got - round(2 * 0.7707763913156815 ** 2, 6)) < 1e-6, got
        # coef_lookup(호기별 계수)가 있으면 그게 우선(예: 0.5 → 2*0.25=0.5)
        res2 = collate.collate_recipe("PI3", form, pivot, ["AOI-6"],
                                      coef_lookup=lambda ho, mag: 0.5)
        assert abs(float(engine._s(res2.records[0].get("AOI-6"))) - 0.5) < 1e-9
    print("  collate OK: 양식 변환방식+계수 재적용(라벨/장비별 우선순위)")


def test_micron_name_forces_convert():
    """이름에 µ 있으면 저장된 변환방식이 RAW 여도 항상 변환. µ 없으면 저장값 존중."""
    from param_manager import extract_io
    with tempfile.TemporaryDirectory() as tmp:
        form = os.path.join(tmp, "f.xlsx")
        recs = [{"PI": "PI3", "Recipe": "PI", "Zone": "Scan Area", "Alg": "Surface",
                 "Parameter": "Min Defect Area - Bright (area, µ)", "비고": ""},
                {"PI": "PI3", "Recipe": "PI", "Zone": "Scan Area", "Alg": "Surface",
                 "Parameter": "Min Defect Width - Bright", "비고": ""}]
        exts = [{"src_file": "z.ini", "section": "Surface", "key": "BrightArea",
                 "raw": 10000, "transform": "RAW", "source_path": ""},   # 저장 RAW(불일치)
                {"src_file": "z.ini", "section": "Surface", "key": "BrightDiameter",
                 "raw": 50, "transform": "RAW", "source_path": ""}]
        extract_io.write_snapshot(form, recs, machines=[], sheet_name="PI_ALL",
                                  extracts=exts, stage="final", level="PI3")

        def piv(key, val):
            return {"layer": "PI", "recipe": "PI3", "mag": "PI", "zone": "Scan Area",
                    "alg": "Surface", "param": key, "values": {"AOI-6": val},
                    "raws": {"AOI-6": val}, "mags": {"AOI-6": "3.14"}, "use": True,
                    "extract": {"src_file": "z.ini", "section": "Surface", "key": key,
                                "transform": "RAW", "source_path": ""}}
        rows = [piv("BrightArea", 10000), piv("BrightDiameter", 50)]
        res = collate.collate_recipe("PI3", form, rows, ["AOI-6"],
                                     coef_lookup=lambda h, m: 0.77)
        by = {engine._s(r["Parameter"]): engine._s(r.get("AOI-6")) for r in res.records}
        assert by["Min Defect Area - Bright (area, µ)"] == \
            engine._s(round(10000 * 0.77 ** 2, 6))            # µ → AREA
        assert by["Min Defect Width - Bright"] == "50"        # µ 없음 → RAW
    print("  collate OK: µ 이름은 항상 변환 / µ 없으면 RAW 유지")


def test_build_collation_carryover_and_allmachines():
    with tempfile.TemporaryDirectory() as tmp:
        save = os.path.join(tmp, "저장폴더")
        os.makedirs(save)
        _make_form(save, tmp)
        machines = ["AOI-24", "AOI-25", "AOI-26"]

        # 1) 직전 취합본: AOI-25 값(wafer=5000)
        p25 = _pivot(os.path.join(tmp, "B25"), "AOI-25", wafer="5000")
        prev = collate.build_collation(save, ["PI3"], p25, machines)
        prev_path = workdirs.collate_path(save, workdirs.stamp())
        collate.write_collation(prev_path, prev, machines)

        # 2) 이번 수집: AOI-24 값(wafer=7000) + 직전(AOI-25) 이어받기
        p24 = _pivot(os.path.join(tmp, "B24"), "AOI-24", wafer="7000")
        results = collate.build_collation(save, ["PI3"], p24, machines,
                                          prev_collate_path=prev_path)
        res = results["PI3"]
        assert not res.missing_form and res.mismatches == []
        # 대상 행: Max Defects Per Wafer
        row = next(r for r in res.records
                   if r["Parameter"] == "Max Defects Per Wafer")
        assert engine._s(row["AOI-24"]) == "7000"      # 이번 수집
        assert engine._s(row["AOI-25"]) == "5000"      # 직전 이어받기
        assert engine._s(row.get("AOI-26")) == ""      # 미수집 → 빈칸

        # 3) 저장 → 로드 왕복(멀티시트)
        dest = workdirs.collate_path(save, workdirs.stamp())
        collate.write_collation(dest, results, machines)
        sheets, mac = collate.load_collation(dest)
        assert "PI3" in sheets and set(machines) <= set(mac)

        # 4) 값 확인용 repo 병합
        repo = collate.load_as_repo(dest, machines)
        assert repo.aoi_units == machines
        got = {engine._s(pr.get("Parameter")): engine._s(pr.get("AOI-24"))
               for pr in repo.rows}
        assert got["Max Defects Per Wafer"] == "7000"
    print("  collate OK: 전체 호기 + 직전 이어받기 + 멀티시트 왕복 + repo 병합")


def test_build_collation_keeps_other_recipes():
    """버그 회귀: 한 레시피만 업데이트해도 직전 취합본의 **다른 레시피 시트**는
    사라지지 않고 그대로 누적돼야 한다."""
    with tempfile.TemporaryDirectory() as tmp:
        save = os.path.join(tmp, "저장폴더")
        os.makedirs(save)
        _make_form(save, tmp)                     # PI3 양식만 존재
        machines = ["AOI-24", "AOI-25"]

        # 직전 취합본: PI3 + (양식 없는) 손수 만든 RDL1 시트
        prev = {
            "PI3": collate.CollateRecipe(
                recipe="PI3", machines=list(machines),
                records=[{"PI": "PI3", "Recipe": "PI", "Zone": "RDL",
                          "Alg": "General", "Parameter": "Max Defects Per Wafer",
                          "비고": "", "AOI-24": "111", "AOI-25": "222"}]),
            "RDL1": collate.CollateRecipe(
                recipe="RDL1", machines=list(machines),
                records=[{"PI": "RDL1", "Recipe": "x5", "Zone": "Z",
                          "Alg": "Surface", "Parameter": "High_Delta",
                          "비고": "", "AOI-24": "9", "AOI-25": "8"}]),
        }
        prev_path = workdirs.collate_path(save, workdirs.stamp())
        collate.write_collation(prev_path, prev, machines)

        # 이번엔 PI3 만 다시 취합 — RDL1 은 건드리지 않는다
        p24 = _pivot(os.path.join(tmp, "B24"), "AOI-24", wafer="7000")
        results = collate.build_collation(save, ["PI3"], p24, machines,
                                          prev_collate_path=prev_path)
        assert "PI3" in results and "RDL1" in results, list(results)
        # RDL1 은 직전 값 그대로 이어져야 함
        rdl = results["RDL1"]
        row = rdl.records[0]
        assert engine._s(row["Parameter"]) == "High_Delta"
        assert engine._s(row["AOI-24"]) == "9" and engine._s(row["AOI-25"]) == "8"
        # 저장 왕복 후에도 두 시트 모두 존재
        dest = workdirs.collate_path(save, workdirs.stamp())
        collate.write_collation(dest, results, machines)
        sheets, _ = collate.load_collation(dest)
        assert "PI3" in sheets and "RDL1" in sheets, list(sheets)
    print("  collate OK: 한 레시피 업데이트 시 다른 레시피 시트 누적 유지")


def test_delete_recipe_sheet():
    """레시피 삭제 = 취합 파일에서 그 레벨 시트 제거(실제 엑셀 반영)."""
    with tempfile.TemporaryDirectory() as tmp:
        dest = os.path.join(tmp, "취합.xlsx")
        made = {
            "PI3": collate.CollateRecipe(recipe="PI3", machines=["AOI-1"],
                records=[{"PI": "PI3", "Recipe": "PI", "Zone": "Z", "Alg": "S",
                          "Parameter": "P1", "비고": "", "AOI-1": "1"}]),
            "RDL1": collate.CollateRecipe(recipe="RDL1", machines=["AOI-1"],
                records=[{"PI": "RDL1", "Recipe": "x5", "Zone": "Z", "Alg": "S",
                          "Parameter": "P2", "비고": "", "AOI-1": "2"}]),
        }
        collate.write_collation(dest, made, ["AOI-1"])
        # 삭제 전 두 시트
        sheets, _ = collate.load_collation(dest)
        assert set(sheets) == {"PI3", "RDL1"}
        # PI3 삭제
        n = collate.delete_recipe(dest, "PI3")
        assert n == 1
        sheets2, _ = collate.load_collation(dest)
        assert set(sheets2) == {"RDL1"}
        # 없는 레시피 삭제 → 0
        assert collate.delete_recipe(dest, "PI9") == 0
        # 마지막 하나까지 삭제해도 파일은 유효(취합없음 시트)
        assert collate.delete_recipe(dest, "RDL1") == 1
        import openpyxl
        wb = openpyxl.load_workbook(dest)
        assert wb.sheetnames  # 최소 1개 시트 유지
    print("  collate OK: delete_recipe 시트 삭제(엑셀 반영)")


def test_missing_form_and_mismatch():
    with tempfile.TemporaryDirectory() as tmp:
        save = os.path.join(tmp, "저장폴더")
        os.makedirs(save)
        _make_form(save, tmp)
        machines = ["AOI-24"]
        # 양식 없는 레시피 RDL4 요청 → missing_form
        p = _pivot(os.path.join(tmp, "C"), "AOI-24")
        results = collate.build_collation(save, ["PI3", "RDL4"], p, machines)
        assert results["RDL4"].missing_form is True
        assert results["PI3"].missing_form is False

        # 불일치: Zone 항목 없는 장비(GlobalRTP만)
        recD = Path(tmp) / "D" / "R_TB500_PI3" / "PI"
        recD.mkdir(parents=True)
        (recD / "GlobalRTP.ini").write_text(GLOBAL.format(v="1"), encoding="utf-8")
        cfgs = ini_parser.scan_tree(Path(tmp) / "D" / "R_TB500_PI3",
                                    default_equipment="AOI-24")
        pD = ini_parser.build_pivot(cfgs)[0]
        res = collate.build_collation(save, ["PI3"], pD, machines)["PI3"]
        params = {m["param"] for m in res.mismatches}
        assert "Contrast Delta - Bright" in params
    print("  collate OK: 양식 없음(missing_form) + 불일치 검출")


def test_load_form_no_duplicate_rows():
    """버그1 회귀: 양식 파일(요약/스냅샷 부가시트 포함)을 값확인용으로 로드해도
    파라미터가 중복 복제되지 않아야 한다."""
    with tempfile.TemporaryDirectory() as tmp:
        save = os.path.join(tmp, "저장폴더")
        os.makedirs(save)
        form = _make_form(save, tmp)         # engine.create_from_records → 부가시트 다수
        # 양식의 실제 파라미터 수
        repo0 = engine.ParamRepository(form)
        repo0.load()
        n = len(repo0.rows)
        assert n > 0
        # load_collation/load_as_repo 는 PI_ALL 데이터만(부가시트 제외)
        sheets, _ = collate.load_collation(form)
        total = sum(len(rows) for rows in sheets.values())
        assert total == n, f"중복 로드: {total} != {n}"
        repo = collate.load_as_repo(form, ["AOI-24"])
        assert len(repo.rows) == n, f"repo 중복: {len(repo.rows)} != {n}"
    print("  collate OK: 양식 부가시트 제외 — 값확인 로드 시 중복 없음")


def _pivot_variant(root, equip, variant, wafer="3000"):
    """하위 레시피(변형) 폴더 이름을 지정해 피벗을 만든다."""
    rec = Path(root) / "R_TB500_PI3" / variant
    rec.mkdir(parents=True, exist_ok=True)
    (rec / "GlobalRTP.ini").write_text(GLOBAL.format(v=wafer), encoding="utf-8")
    (rec / "Zones").mkdir(exist_ok=True)
    (rec / "Zones" / "Z.ini").write_text(ZONE, encoding="utf-8")
    cfgs = ini_parser.scan_tree(Path(root) / "R_TB500_PI3", default_level="PI3",
                                default_equipment=equip)
    return ini_parser.build_pivot(cfgs)[0]


def test_unmatched_variant_detection_and_remap():
    """장비마다 **하위 레시피 폴더 이름이 다르면** 값이 채워지지 않는다.
    값 업데이트 전에 그런 변형을 찾아내고, 사람이 매칭한 대로 이름을 바꿔
    양식 행에 값이 들어가야 한다."""
    with tempfile.TemporaryDirectory() as tmp:
        save_dir = os.path.join(tmp, "저장")
        os.makedirs(save_dir)
        # 양식은 '2D+3D_CAMTEK' 이름으로 만들어 둔다
        rows = _pivot_variant(os.path.join(tmp, "form"), "AOI-24", "2D+3D_CAMTEK")
        init = os.path.join(tmp, "init.xlsx")
        formbuilder.build_initial_workbook(rows, init, level="PI3")
        st = workdirs.stamp()
        run = workdirs.form_run_dir(save_dir, "PI3", st)
        form = workdirs.form_final_path(run, "PI3", "AOI-24", st)
        formbuilder.build_final_from_initial(init, form, level="PI3")
        assert "2D+3D_CAMTEK" in collate.form_variants(form), \
            collate.form_variants(form)

        # 다른 호기는 폴더 이름이 조금 다르다
        other = _pivot_variant(os.path.join(tmp, "b"), "AOI-25",
                               "2D+3D CAMTEK BUMP", wafer="7777")
        miss = collate.unmatched_variants(other, form)
        assert miss == ["2D+3D CAMTEK BUMP"], miss

        # 매칭 없이 취합하면 그 호기 값이 안 채워진다
        res = collate.collate_recipe("PI3", form, other, ["AOI-24", "AOI-25"])
        assert res.filled_cells == 0, res.filled_cells

        # 사람이 매칭해 주면 값이 들어간다
        mapped = collate.apply_variant_map(other, {"2D+3D CAMTEK BUMP":
                                                   "2D+3D_CAMTEK"})
        assert collate.unmatched_variants(mapped, form) == []
        res2 = collate.collate_recipe("PI3", form, mapped, ["AOI-24", "AOI-25"])
        assert res2.filled_cells > 0
        got = next(r for r in res2.records
                   if engine._s(r["Parameter"]).startswith("Max Defects Per Wafer"))
        assert engine._s(got["AOI-25"]) == "7777", got

        # '제외'(빈 값)로 매칭하면 그 변형 행이 아예 빠진다
        dropped = collate.apply_variant_map(other, {"2D+3D CAMTEK BUMP": ""})
        assert dropped == []
        # 대소문자·구분자만 다른 이름은 애초에 불일치로 보지 않는다
        same = collate.apply_variant_map(other, {})
        assert collate.unmatched_variants(
            [dict(r, mag="2d+3d camtek") for r in same], form) == []
    print("  collate OK: 하위 레시피 이름 불일치 검출 + 매칭 재적용")

def test_variant_match_table_and_auto_map():
    """하위 레시피 이름 매칭: 자동매칭(norm_key)·확인창 표·이름 교체."""
    form_vars = ["2D+3D_CAMTEK", "DUMMY"]
    parsed = ["2d+3d camtek", "DUMMY", "SPECIAL X20"]   # 대소문자·구분자·양식에 없는 것
    # 자동 매핑: 정규화로 같은데 문자열만 다른 것만(같은 이름은 제외)
    amap = collate.auto_variant_map(form_vars, parsed)
    assert amap == {"2d+3d camtek": "2D+3D_CAMTEK"}, amap   # DUMMY 는 이미 같음
    # 확인창용 표: 왼쪽=양식, 오른쪽 기본선택=자동매칭된 수집 이름
    tbl = collate.variant_match_table(form_vars, parsed)
    assert tbl["rows"] == [("2D+3D_CAMTEK", "2d+3d camtek"), ("DUMMY", "DUMMY")], tbl["rows"]
    assert tbl["unmatched_parsed"] == ["SPECIAL X20"], tbl   # 양식에 없는 수집 변형
    assert tbl["parsed"] == parsed
    # 매핑 적용 → 피벗의 mag(변형)가 양식 이름으로 바뀐다
    rows = [{"mag": "2d+3d camtek", "x": 1}, {"mag": "DUMMY", "x": 2},
            {"mag": "SPECIAL X20", "x": 3}]
    out = collate.apply_variant_map(rows, amap)
    assert [r["mag"] for r in out] == ["2D+3D_CAMTEK", "DUMMY", "SPECIAL X20"], out
    assert rows[0]["mag"] == "2d+3d camtek", "원본 리스트는 안 바뀐다"
    print("  collate OK: 하위 레시피 자동매칭·확인창 표·이름 교체")


def test_update_flow_asks_before_collating():
    """값 업데이트는 **취합 전에** 이름 매칭을 물어봐야 한다(취합 후면 늦다).
    (GUI 는 이 환경에서 못 띄우므로 호출 순서를 소스로 고정한다.)"""
    import re
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "param_manager", "equip_app.py"),
              encoding="utf-8") as fh:
        src = fh.read()
    m = re.search(r"def _update_collate_flow.*?(?=\n    def )", src, re.S)
    assert m, "_update_collate_flow 를 찾지 못함"
    body = m.group(0)
    assert "_match_variants(forms, pivot_rows)" in body, "매칭 단계가 없음"
    assert body.index("_match_variants") < body.index("build_collation"), \
        "취합보다 먼저 매칭을 물어야 한다"
    # 확인창(항상 표시)과 매칭 적용
    assert "_confirm_variant_match" in src and "apply_variant_map" in src
    assert "variant_match_table" in src, "확인창용 매칭표를 쓰지 않음"
    # commonality 조사(_cm_collate)도 취합(collate_lots) 전에 매칭을 확인해야 한다
    cm = re.search(r"def _cm_collate.*?(?=\n    def )", src, re.S)
    assert cm and "_confirm_variant_match" in cm.group(0), \
        "commonality 조사에 하위 레시피 매칭 확인이 없음"
    assert cm.group(0).index("_confirm_variant_match") < cm.group(0).index("collate_lots"), \
        "commonality 도 취합보다 먼저 매칭을 물어야 한다"
    print("  collate OK: 값 업데이트·commonality 가 취합 전에 이름 매칭을 확인한다")

if __name__ == "__main__":
    fails = 0
    tests = [(n, f) for n, f in list(globals().items())
             if n.startswith("test_") and callable(f)]
    for name, fn in tests:
        print(f"[RUN] {name}")
        try:
            fn()
            print(f"[PASS] {name}\n")
        except Exception as e:  # noqa: BLE001
            fails += 1
            import traceback
            traceback.print_exc()
            print(f"[FAIL] {name}: {e}\n")
    print(f"==== {len(tests) - fails}/{len(tests)} passed ====")
    sys.exit(1 if fails else 0)
