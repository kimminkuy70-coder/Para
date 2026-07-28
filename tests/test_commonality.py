"""Commonality 조사 헤드리스 테스트 — 계획 엑셀·폴더 해석·안전복사·구조 diff·
Lot 취합·호기 비교(과반수 이탈 색칠). 로컬 가짜 Scanresult 트리 사용."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import openpyxl  # noqa: E402

from param_manager import (collate, commonality, engine, formbuilder,  # noqa: E402
                           ini_parser)

ZONE = ("[General]\nZoneName = PI Opening\n"
        "[Surface]\nHigh_Delta = {delta}\nMinDefectWidth_um = 3.5\n")
OPTIC = "[LIGHT]\n[Scan2d1]\nAlg = Scan2d\nLightSrc_Top = 100\n"


def _make_wafer(base, machine, device_folder, lot, sm, wafer, delta=25):
    """가짜 Scanresult 웨이퍼 폴더 생성. 반환: 웨이퍼 config 폴더."""
    wdir = (Path(base) / machine / "Scanresult" / device_folder / lot / sm / wafer)
    (wdir / "Zones").mkdir(parents=True)
    (wdir / "Zones" / "Z.ini").write_text(ZONE.format(delta=delta), encoding="utf-8")
    (wdir / "OpticPreset.ini").write_text(OPTIC, encoding="utf-8")
    (wdir / "RTP.txt").write_text("dummy rtp", encoding="utf-8")
    return wdir


def test_plan_template_roundtrip_and_filter():
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, "plan.xlsx")
        commonality.create_plan_template(p, rows=[
            {"디바이스명": "S6WH11001-00001", "공정번호": "6321", "S/M": "HPG", "AOI호기": "AOI-6"},
            {"디바이스명": "S6WH11001-00001", "공정번호": "6323", "S/M": "TVS", "AOI호기": "AOI-9"},
        ])
        rows = commonality.read_plan(p)
        assert len(rows) == 2
        assert rows[0]["공정번호"] == "6321"
        only6 = commonality.filter_plan_for_machine(rows, "aoi_6")   # 정규화 매칭
        assert len(only6) == 1 and only6[0]["S/M"] == "HPG"
    print("  commonality OK: 계획 엑셀 왕복 + 호기 필터(정규화)")


def test_resolve_plan_found_and_missing():
    with tempfile.TemporaryDirectory() as tmp:
        _make_wafer(tmp, "AOI-6", "2D@R2-DEVA-1_0855360PD-0A", "6321", "HPG", "CX02")
        _make_wafer(tmp, "AOI-6", "2D@R2-DEVA-1_0855360PD-0A", "6321", "HPG", "CX01")
        root = commonality.scanresult_root(tmp, "AOI-6")
        plan = [
            {"디바이스명": "DEVA-1", "공정번호": "6321", "S/M": "HPG", "AOI호기": "AOI-6"},
            {"디바이스명": "DEVA-1", "공정번호": "9999", "S/M": "HPG", "AOI호기": "AOI-6"},
        ]
        lots = commonality.resolve_plan(root, plan)
        found = [l for l in lots if l.exists]
        missing = [l for l in lots if not l.exists]
        assert len(found) == 1 and len(missing) == 1
        # 이름순 첫 웨이퍼 = CX01
        assert found[0].wafer_dir.name == "CX01"
        assert found[0].has_zones and found[0].has_rtp and found[0].has_optic
        assert "공정" in missing[0].reason
    print("  commonality OK: 폴더 해석(디바이스+LOT+S/M) + 이름순 첫 웨이퍼 + 실패사유")


def test_real_world_folder_variants():
    """실제 환경 변형 흡수: Scanresult_260401 폴더명 + AOI-9 vs AOI-09(0패딩)."""
    with tempfile.TemporaryDirectory() as tmp:
        # 실제 경로: W:/AOI-9/Scanresult_260401/2D@RE-DEV..._x/6412/HCH/wafer
        w = (Path(tmp) / "AOI-9" / "Scanresult_260401"
             / "2D@RE-L6WZ30001-00001_0852445PD-0C" / "6412" / "HCH" / "65349540001")
        (w / "Zones").mkdir(parents=True)
        (w / "Zones" / "Z.ini").write_text(ZONE.format(delta=25), encoding="utf-8")
        (w / "OpticPreset.ini").write_text(OPTIC, encoding="utf-8")
        (w / "RTP.txt").write_text("x", encoding="utf-8")

        # base=tmp, 선택 호기="AOI-09"(0패딩 다름) → 루트가 AOI-9/Scanresult_260401 로 해석
        root = commonality.scanresult_root(tmp, "AOI-09")
        assert root.name == "Scanresult_260401"
        # 계획 필터도 AOI-9 == AOI-09
        plan = [{"디바이스명": "L6WZ30001-00001", "공정번호": "6412", "S/M": "HCH",
                 "AOI호기": "AOI-09"}]
        assert len(commonality.filter_plan_for_machine(plan, "AOI-9")) == 1
        # 폴더 해석 성공(디바이스명 포함 매칭)
        lot = commonality.resolve_lot(root, "L6WZ30001-00001", "6412", "HCH", "AOI-9")
        assert lot.exists and lot.wafer_dir.name == "65349540001"
        # LOT 오타(6421)면 실패 + 사유
        bad = commonality.resolve_lot(root, "L6WZ30001-00001", "6421", "HCH", "AOI-9")
        assert not bad.exists and "공정" in bad.reason
    print("  commonality OK: Scanresult_260401 폴더명 + AOI-9/AOI-09 + LOT 오타 사유")


def test_multiple_scanresult_backups():
    """호기 폴더 아래 Scanresult 백업본이 여러 개면 전부 탐색해 Lot 을 찾는다."""
    with tempfile.TemporaryDirectory() as tmp:
        mdir = Path(tmp) / "AOI-9"
        # 현재본엔 6412 없음, 백업본에만 있음
        (mdir / "Scanresult" / "2D@X-DEVZ_0A" / "9999" / "AAA" / "w0" / "Zones").mkdir(parents=True)
        good = (mdir / "SCANRESULT_BACKUP_260805" / "2D@X-DEVZ_0A" / "6412" / "HCH" / "w1")
        (good / "Zones").mkdir(parents=True)
        (good / "Zones" / "Z.ini").write_text(ZONE.format(delta=25), encoding="utf-8")
        (good / "RTP.txt").write_text("x", encoding="utf-8")
        # 또 다른 백업본
        (mdir / "Scanresult_260402").mkdir(parents=True)

        roots = commonality.scanresult_roots(tmp, "AOI-9")
        assert len(roots) == 3, [p.name for p in roots]   # 3개 모두 탐색 대상
        # 호기 폴더만 줘도(=tmp 아래 AOI-9) 백업본의 6412 를 찾음
        lot = commonality.resolve_lot(roots, "DEVZ", "6412", "HCH", "AOI-9")
        assert lot.exists and lot.wafer_dir.name == "w1", lot.reason
        assert "BACKUP" in str(lot.wafer_dir)
    print("  commonality OK: Scanresult 백업본 다중 탐색(호기 폴더만 지정)")


def test_multiple_recipe_folders_and_multimachine_filter():
    """같은 디바이스가 여러 2D@ 레시피 폴더로 나뉘고, 공정 폴더가 두 번째
    폴더에만 있어도 찾아야 한다. 또 'AOI-4,6,9' 한 칸 여러 호기 필터."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "AOI-9" / "Scanresult_260401"
        # 디바이스 L6WZ30001-00001 의 레시피 폴더 2개: _0A(6412 없음), _0C(6412 있음)
        (base / "2D@RE-L6WZ30001-00001_0852445PD-0A" / "9999" / "ZZZ" / "w0"
         / "Zones").mkdir(parents=True)
        good = (base / "2D@RE-L6WZ30001-00001_0852445PD-0C" / "6412" / "HCH"
                / "65349540001")
        (good / "Zones").mkdir(parents=True)
        (good / "Zones" / "Z.ini").write_text(ZONE.format(delta=25), encoding="utf-8")
        (good / "OpticPreset.ini").write_text(OPTIC, encoding="utf-8")
        (good / "RTP.txt").write_text("x", encoding="utf-8")

        root = commonality.scanresult_root(tmp, "AOI-9")
        lot = commonality.resolve_lot(root, "L6WZ30001-00001", "6412", "HCH", "AOI-9")
        assert lot.exists, f"두 번째 레시피 폴더의 6412 를 못 찾음: {lot.reason}"
        assert lot.wafer_dir.name == "65349540001"

        # 여러 호기 한 칸: AOI-4,6,9 → AOI-9 로 필터되어야 함
        plan = [{"디바이스명": "D", "공정번호": "6412", "S/M": "YYH", "AOI호기": "AOI-4,6,9"},
                {"디바이스명": "D", "공정번호": "6412", "S/M": "YYA", "AOI호기": "AOI-05"}]
        got = commonality.filter_plan_for_machine(plan, "AOI-09")
        assert len(got) == 1 and got[0]["S/M"] == "YYH"
    print("  commonality OK: 여러 레시피 폴더 탐색 + 여러 호기 한 칸 필터")


def test_intermediate_level_and_no_numeric_mismatch():
    """공정 폴더가 중간 폴더 아래 있어도 찾고(BFS), 6412 가 64120 에 오매칭 안 됨."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "AOI-9" / "Scanresult"
        dev = base / "2D@X-DEVQ-1_0A"
        # 헷갈리게 하는 폴더: 64120(오매칭 유발) + 중간폴더 SUB 아래 진짜 6412
        (dev / "64120" / "AAA" / "w0" / "Zones").mkdir(parents=True)
        good = dev / "SUB" / "6412" / "HCH" / "wafer1"
        (good / "Zones").mkdir(parents=True)
        (good / "Zones" / "Z.ini").write_text(ZONE.format(delta=25), encoding="utf-8")
        (good / "RTP.txt").write_text("x", encoding="utf-8")
        root = commonality.scanresult_root(tmp, "AOI-9")
        lot = commonality.resolve_lot(root, "DEVQ-1", "6412", "HCH", "AOI-9")
        assert lot.exists and lot.wafer_dir.name == "wafer1", lot.reason
        assert "6412" in str(lot.wafer_dir) and "64120" not in str(lot.wafer_dir)
    print("  commonality OK: 중간 폴더 BFS + 숫자 오매칭 방지(6412≠64120)")


def test_read_plan_legacy_header():
    """구 템플릿 헤더(LOT번호)도 공정번호로 읽혀야 한다(하위호환)."""
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, "old.xlsx")
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Lot목록"
        ws.append(["디바이스명", "LOT번호", "S/M", "AOI호기"])   # 구 헤더
        ws.append(["S6WC61001-00001", 6412, "YYA", "AOI-09"])    # 숫자 6412
        wb.save(p)
        rows = commonality.read_plan(p)
        assert rows[0]["공정번호"] == "6412"     # 별칭 + 문자열화
        assert commonality.filter_plan_for_machine(rows, "AOI-9")[0]["S/M"] == "YYA"
    print("  commonality OK: 구 헤더(LOT번호) 하위호환 + 숫자 공정번호")


def test_copy_lot_read_only():
    with tempfile.TemporaryDirectory() as tmp:
        w = _make_wafer(tmp, "AOI-6", "2D@DEVB_x", "6400", "HPG", "CX10")
        root = commonality.scanresult_root(tmp, "AOI-6")
        lot = commonality.resolve_lot(root, "DEVB", "6400", "HPG", "AOI-6")
        assert lot.exists
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns)
                  for p in w.rglob("*") if p.is_file()}
        dest = os.path.join(tmp, "staging")
        res = commonality.copy_lot(lot, dest, verify=True)
        assert res["count"] == 3       # Z.ini + OpticPreset.ini + RTP.txt
        # 원본 불변
        for p, (content, mtime) in before.items():
            assert p.read_bytes() == content and p.stat().st_mtime_ns == mtime
        # 사본은 로컬 staging 에만
        assert lot.label == "HPG"           # 라벨 = S/M 만
        assert (Path(dest) / "HPG" / "Zones" / "Z.ini").is_file()
        assert (Path(dest) / "HPG" / "RTP.txt").is_file()
    print("  commonality OK: 안전복사(원본 read-only) + 대상만 복사")


def test_multi_recipe_copy_preserves_structure():
    """다중 레시피 안전복사: RecipesInfo/ActiveScenarioOptics/Recipe*- 파일 + Recipe*-Zones/
    구조 보존, 사본에서 레시피별 값 분리 파싱까지."""
    with tempfile.TemporaryDirectory() as tmp:
        w = _make_wafer(tmp, "AOI-6", "2D@DEVM_x", "6400", "HPG", "CX20")  # recipe-1 delta=25
        (w / "RecipesInfo.ini").write_text(
            "[Recipe-1]\nName=PI_Bubble\n[Recipe-2]\nName=PI\n[Recipes]\nCount=2\n",
            encoding="utf-8")
        (w / "ActiveScenarioOptics.ini").write_text(
            "[z]\nScenarioName=Scan2d\nOpticsName=Scan2d1\nOpticId=aaa\n", encoding="utf-8")
        (w / "Recipe2-OpticPreset.ini").write_text(
            "[LIGHT]\n[Scan2d1]\nAlg=Scan2d\nLightSrc_Top=100\n", encoding="utf-8")
        (w / "Recipe2-ActiveScenarioOptics.ini").write_text(
            "[z]\nScenarioName=Scan2d\nOpticsName=Scan2d1\nOpticId=aaa\n", encoding="utf-8")
        (w / "Recipe2-Zones").mkdir()
        (w / "Recipe2-Zones" / "Z.ini").write_text(
            "[General]\nZoneName=PI Opening\n[Surface]\nHigh_Delta=99\n", encoding="utf-8")
        root = commonality.scanresult_root(tmp, "AOI-6")
        lot = commonality.resolve_lot(root, "DEVM", "6400", "HPG", "AOI-6")
        dest = os.path.join(tmp, "staging")
        commonality.copy_lot(lot, dest, verify=True)
        base = Path(dest) / "HPG"
        for rel in ("RecipesInfo.ini", "Recipe2-OpticPreset.ini",
                    "Recipe2-ActiveScenarioOptics.ini", "ActiveScenarioOptics.ini",
                    "Recipe2-Zones/Z.ini", "Zones/Z.ini"):
            assert (base / rel).is_file(), f"복사 누락: {rel}"
        recs = commonality.detect_recipes([("HPG", base)])
        assert [r["name"] for r in recs] == ["PI_Bubble", "PI"], recs
        p1, _ = commonality.parse_lots([("HPG", base)], level="PI_Bubble", recipe_prefix="")
        p2, _ = commonality.parse_lots([("HPG", base)], level="PI", recipe_prefix="Recipe2-")

        def hd(pv):
            for r in pv:
                if r["extract"].get("key") == "High_Delta":
                    return str(r["raws"].get("HPG"))
            return None
        assert hd(p1) == "25" and hd(p2) == "99"     # 레시피별 값 분리(사본)
    print("  commonality OK: 다중 레시피 안전복사 구조 보존 + 사본 파싱 분리")


def test_structure_diff():
    with tempfile.TemporaryDirectory() as tmp:
        w1 = _make_wafer(tmp, "AOI-6", "2D@DEVC_x", "1", "HPG", "CXA")
        w2 = _make_wafer(tmp, "AOI-6", "2D@DEVC_x", "2", "HPG", "CXB")
        # w2 는 Zones ini 에 항목 하나 제거(구조 불일치 유발)
        (w2 / "Zones" / "Z.ini").write_text(
            "[General]\nZoneName = PI Opening\n[Surface]\nHigh_Delta = 25\n",
            encoding="utf-8")
        diff = commonality.structure_diff([("L1", w1), ("L2", w2)], level="PI3")
        assert diff["identical"] is False
        # L2 에 MinDefectWidth 관련 항목이 없음
        assert any("MinDefectWidth" in m for m in diff["lots"]["L2"]["missing"])
        assert diff["lots"]["L1"]["missing"] == []
    print("  commonality OK: Lot 간 구조 diff(빠진 항목 검출)")


def _build_form(tmp, pivot_rows, recipe="PI3"):
    init = os.path.join(tmp, f"init_{recipe}.xlsx")
    formbuilder.build_initial_workbook(pivot_rows, init, level=recipe)
    final = os.path.join(tmp, f"form_{recipe}.xlsx")
    formbuilder.build_final_from_initial(init, final, level=recipe)
    return final


def test_collate_lots_and_result_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        w1 = _make_wafer(tmp, "AOI-6", "2D@DEVD_x", "6501", "HPG", "CX1", delta=25)
        w2 = _make_wafer(tmp, "AOI-6", "2D@DEVD_x", "6502", "HPG", "CX2", delta=99)
        lots = [("6501_HPG", w1), ("6502_HPG", w2)]
        pivot, labels = commonality.parse_lots(lots, level="PI3")
        assert set(labels) == {"6501_HPG", "6502_HPG"}
        form = _build_form(tmp, pivot)
        res = commonality.collate_lots("PI3", form, pivot, labels)
        # High_Delta → Contrast Delta - Bright 가 Lot 별로 다른 값
        row = next(r for r in res.records
                   if engine._s(r["Parameter"]) == "Contrast Delta - Bright")
        assert engine._s(row["6501_HPG"]) == "25"
        assert engine._s(row["6502_HPG"]) == "99"
        # 결과 엑셀 왕복
        out = os.path.join(tmp, "조사_AOI-6.xlsx")
        commonality.write_lot_result(out, "PI3", "AOI-6", res, labels)
        data = commonality.read_lot_result(out)
        assert data["machine"] == "AOI-6" and set(data["lots"]) == set(labels)
    print("  commonality OK: Lot 취합(양식 기준) + 호기 결과 엑셀 왕복")


def test_build_comparison_outliers():
    with tempfile.TemporaryDirectory() as tmp:
        # AOI-6: 두 Lot(25/99), AOI-9: 한 Lot(25) → 99 만 과반수(25) 이탈
        w6a = _make_wafer(tmp, "AOI-6", "2D@DEVE_x", "6601", "HPG", "CX1", delta=25)
        w6b = _make_wafer(tmp, "AOI-6", "2D@DEVE_x", "6602", "HPG", "CX2", delta=99)
        w9 = _make_wafer(tmp, "AOI-9", "2D@DEVE_x", "6603", "TVS", "CX3", delta=25)

        piv6, lab6 = commonality.parse_lots([("6601_HPG", w6a), ("6602_HPG", w6b)],
                                            level="PI3")
        form = _build_form(tmp, piv6)
        r6 = commonality.collate_lots("PI3", form, piv6, lab6)
        f6 = os.path.join(tmp, "AOI-6.xlsx")
        commonality.write_lot_result(f6, "PI3", "AOI-6", r6, lab6)

        piv9, lab9 = commonality.parse_lots([("6603_TVS", w9)], level="PI3")
        r9 = commonality.collate_lots("PI3", form, piv9, lab9)
        f9 = os.path.join(tmp, "AOI-9.xlsx")
        commonality.write_lot_result(f9, "PI3", "AOI-9", r9, lab9)

        comp = commonality.build_comparison([f6, f9])
        assert comp["columns"][:2] == ["S/M", "호기"]
        assert len(comp["rows"]) == 3          # 세 (Lot,호기) 행
        # Contrast Delta - Bright 열이 변경 파라미터
        cd = next(c for c in comp["columns"] if "Contrast Delta - Bright" in c)
        assert cd in comp["changed_params"]
        # 99 를 가진 행만 이탈
        out_rows = {i for (i, col) in comp["outliers"] if col == cd}
        vals = [engine._s(r.get(cd)) for r in comp["rows"]]
        assert vals.count("99") == 1
        bad = vals.index("99")
        assert out_rows == {bad}
        # 색칠 엑셀 저장(변경열만) — 파일 생성 확인
        cmp_path = os.path.join(tmp, "취합비교.xlsx")
        commonality.write_comparison(cmp_path, comp, changed_only=True)
        wb = openpyxl.load_workbook(cmp_path)
        ws = wb["취합비교"]
        assert ws.cell(row=1, column=1).value == "S/M"
    print("  commonality OK: 호기 비교(행=Lot/호기) + 과반수 이탈 색칠")


def test_sm_variant_expansion_and_fail_flag():
    """S/M 'CFG' → 변형 폴더(CFG X20 / CFG #14 REWORK / CFG-RW_0517S) 모두 후보로.
    fail여부=Y 는 각 항목에 반영."""
    with tempfile.TemporaryDirectory() as tmp:
        dev6412 = Path(tmp) / "AOI-9" / "Scanresult" / "2D@X-DEVZ_0A" / "6412"
        for sm in ("CFG X20", "CFG #14 REWORK", "CFG-RW_0517S"):
            w = dev6412 / sm / "w1"
            (w / "Zones").mkdir(parents=True)
            (w / "Zones" / "Z.ini").write_text(ZONE.format(delta=25), encoding="utf-8")
            (w / "RTP.txt").write_text("x", encoding="utf-8")
        root = commonality.scanresult_root(tmp, "AOI-9")
        variants = commonality.resolve_lot_variants(root, "DEVZ", "6412", "CFG",
                                                    "AOI-9", fail=True)
        got = sorted(v.label for v in variants if v.exists)
        assert got == sorted(["CFG X20", "CFG #14 REWORK", "CFG-RW_0517S"]), got
        assert all(v.fail for v in variants)
        # resolve_plan 도 변형을 펼치고 fail 을 반영
        plan = [{"디바이스명": "DEVZ", "공정번호": "6412", "S/M": "CFG",
                 "AOI호기": "AOI-9", "fail여부": "Y"}]
        lots = commonality.resolve_plan(root, plan)
        assert len([l for l in lots if l.exists]) == 3
        assert all(l.fail for l in lots)
    print("  commonality OK: S/M 변형 다중 후보 + fail여부 반영")


def test_fail_flag_colors_result_and_comparison():
    """fail S/M 이 결과 엑셀→비교표(fail_rows)→노란색 색칠로 이어진다."""
    with tempfile.TemporaryDirectory() as tmp:
        w1 = _make_wafer(tmp, "AOI-6", "2D@DEVF_x", "6700", "AAA", "CX1", delta=25)
        w2 = _make_wafer(tmp, "AOI-6", "2D@DEVF_x", "6700", "BBB", "CX2", delta=25)
        piv, labels = commonality.parse_lots([("AAA", w1), ("BBB", w2)], level="PI3")
        form = _build_form(tmp, piv)
        res = commonality.collate_lots("PI3", form, piv, labels)
        out = os.path.join(tmp, "AOI-6.xlsx")
        commonality.write_lot_result(out, "PI3", "AOI-6", res, labels,
                                     fail_labels=["BBB"])
        data = commonality.read_lot_result(out)
        assert data["fails"] == {"BBB"}
        comp = commonality.build_comparison([out])
        bbb = next(i for i, r in enumerate(comp["rows"]) if r["S/M"] == "BBB")
        aaa = next(i for i, r in enumerate(comp["rows"]) if r["S/M"] == "AAA")
        assert bbb in comp["fail_rows"] and aaa not in comp["fail_rows"]
        cmp_path = os.path.join(tmp, "cmp.xlsx")
        commonality.write_comparison(cmp_path, comp)
        wb = openpyxl.load_workbook(cmp_path)
        ws = wb["취합비교"]
        got = False
        for r in range(2, ws.max_row + 1):
            if ws.cell(row=r, column=1).value == "BBB":
                rgb = ws.cell(row=r, column=1).fill.fgColor.rgb or ""
                assert str(rgb).endswith(commonality.FAIL_FILL), rgb
                got = True
        assert got
    print("  commonality OK: fail S/M → 결과·비교표 노란색 색칠")


def test_zone_group_sort_adjacent():
    """비슷한 Zone(AL PAD / PAD)이 비교표 열에서 인접하게 정렬돼야 한다."""
    labels = [
        "Surface / Alg / X",
        "PAD / Surface / C",
        "LIGHT / Scan2d / Latest",
        "AL PAD / Surface / M",
    ]
    ordered = sorted(labels, key=commonality._zone_sort_key)
    # AL PAD 와 PAD 는 서로 이웃(둘 다 'pad' 그룹)
    i_alpad = ordered.index("AL PAD / Surface / M")
    i_pad = ordered.index("PAD / Surface / C")
    assert abs(i_alpad - i_pad) == 1, ordered
    print("  commonality OK: Zone 그룹 정렬(AL PAD ↔ PAD 인접)")


def test_multi_recipe_detect_and_parse():
    """다중 레시피 감지 + 레시피별 parse_lots 값 분리."""
    with tempfile.TemporaryDirectory() as tmp:
        cdir = Path(tmp) / "wafer"
        (cdir / "Zones").mkdir(parents=True)
        (cdir / "Zones" / "Z.ini").write_text(
            "[General]\nZoneName=PI Opening\n[Surface]\nHigh_Delta=11\n", encoding="utf-8")
        (cdir / "OpticPreset.ini").write_text(
            "[LIGHT]\n[Scan2d1]\nAlg=Scan2d\nLightSrc_Top=100\n", encoding="utf-8")
        (cdir / "RecipesInfo.ini").write_text(
            "[Recipe-1]\nName=PI_Bubble\n[Recipe-2]\nName=PI\n[Recipes]\nCount=2\n",
            encoding="utf-8")
        (cdir / "Recipe2-Zones").mkdir()
        (cdir / "Recipe2-Zones" / "Z.ini").write_text(
            "[General]\nZoneName=PI Opening\n[Surface]\nHigh_Delta=99\n", encoding="utf-8")
        (cdir / "Recipe2-OpticPreset.ini").write_text(
            "[LIGHT]\n[Scan2d1]\nAlg=Scan2d\nLightSrc_Top=100\n", encoding="utf-8")

        lot_dirs = [("LotA", cdir)]
        recs = commonality.detect_recipes(lot_dirs)
        assert [r["name"] for r in recs] == ["PI_Bubble", "PI"], recs
        assert [r["prefix"] for r in recs] == ["", "Recipe2-"]

        def hd(pivot):
            for row in pivot:
                if row["extract"].get("key") == "High_Delta":
                    return str(row["raws"].get("LotA"))
            return None
        p1, _ = commonality.parse_lots(lot_dirs, level="PI_Bubble",
                                       recipe_prefix=recs[0]["prefix"])
        p2, _ = commonality.parse_lots(lot_dirs, level="PI",
                                       recipe_prefix=recs[1]["prefix"])
        assert hd(p1) == "11" and hd(p2) == "99"       # 레시피별 값 분리(충돌 없음)
        # 단일 레시피면 None
        (cdir / "RecipesInfo.ini").unlink()
        assert commonality.detect_recipes(lot_dirs) is None
    print("  commonality OK: 다중 레시피 감지 + 레시피별 값 분리 파싱")


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
