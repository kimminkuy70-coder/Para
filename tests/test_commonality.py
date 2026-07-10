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
            {"디바이스명": "S6WH11001-00001", "LOT번호": "6321", "S/M": "HPG", "AOI호기": "AOI-6"},
            {"디바이스명": "S6WH11001-00001", "LOT번호": "6323", "S/M": "TVS", "AOI호기": "AOI-9"},
        ])
        rows = commonality.read_plan(p)
        assert len(rows) == 2
        assert rows[0]["LOT번호"] == "6321"
        only6 = commonality.filter_plan_for_machine(rows, "aoi_6")   # 정규화 매칭
        assert len(only6) == 1 and only6[0]["S/M"] == "HPG"
    print("  commonality OK: 계획 엑셀 왕복 + 호기 필터(정규화)")


def test_resolve_plan_found_and_missing():
    with tempfile.TemporaryDirectory() as tmp:
        _make_wafer(tmp, "AOI-6", "2D@R2-DEVA-1_0855360PD-0A", "6321", "HPG", "CX02")
        _make_wafer(tmp, "AOI-6", "2D@R2-DEVA-1_0855360PD-0A", "6321", "HPG", "CX01")
        root = commonality.scanresult_root(tmp, "AOI-6")
        plan = [
            {"디바이스명": "DEVA-1", "LOT번호": "6321", "S/M": "HPG", "AOI호기": "AOI-6"},
            {"디바이스명": "DEVA-1", "LOT번호": "9999", "S/M": "HPG", "AOI호기": "AOI-6"},
        ]
        lots = commonality.resolve_plan(root, plan)
        found = [l for l in lots if l.exists]
        missing = [l for l in lots if not l.exists]
        assert len(found) == 1 and len(missing) == 1
        # 이름순 첫 웨이퍼 = CX01
        assert found[0].wafer_dir.name == "CX01"
        assert found[0].has_zones and found[0].has_rtp and found[0].has_optic
        assert "LOT" in missing[0].reason
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
        plan = [{"디바이스명": "L6WZ30001-00001", "LOT번호": "6412", "S/M": "HCH",
                 "AOI호기": "AOI-09"}]
        assert len(commonality.filter_plan_for_machine(plan, "AOI-9")) == 1
        # 폴더 해석 성공(디바이스명 포함 매칭)
        lot = commonality.resolve_lot(root, "L6WZ30001-00001", "6412", "HCH", "AOI-9")
        assert lot.exists and lot.wafer_dir.name == "65349540001"
        # LOT 오타(6421)면 실패 + 사유
        bad = commonality.resolve_lot(root, "L6WZ30001-00001", "6421", "HCH", "AOI-9")
        assert not bad.exists and "LOT" in bad.reason
    print("  commonality OK: Scanresult_260401 폴더명 + AOI-9/AOI-09 + LOT 오타 사유")


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
        assert (Path(dest) / "6400_HPG" / "Zones" / "Z.ini").is_file()
        assert (Path(dest) / "6400_HPG" / "RTP.txt").is_file()
    print("  commonality OK: 안전복사(원본 read-only) + 대상만 복사")


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
        assert comp["columns"][:2] == ["LOT", "호기"]
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
        assert ws.cell(row=1, column=1).value == "LOT"
    print("  commonality OK: 호기 비교(행=Lot/호기) + 과반수 이탈 색칠")


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
