"""collate 테스트 — 양식(이름변경 포함) + 파싱 → 호기별 취합 + 불일치."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import openpyxl  # noqa: E402

from param_manager import collate, engine, formbuilder, ini_parser  # noqa: E402

GLOBAL_RTP = """[GLOBAL_RTP]
MaxFaultsPerWafer = 3000
ApplyDieCalib = 1
"""
ZONE_INI = """[General]
ZoneName = PI Opening
[Surface]
High_Delta = 25
"""
GLOBAL_RTP_B = """[GLOBAL_RTP]
MaxFaultsPerWafer = 5000
ApplyDieCalib = 0
"""


def _pivot(root, equip, with_zone=True, gtext=GLOBAL_RTP):
    rec = Path(root) / "R_TB500_PI3" / "PI"
    rec.mkdir(parents=True, exist_ok=True)
    (rec / "GlobalRTP.ini").write_text(gtext, encoding="utf-8")
    if with_zone:
        (rec / "Zones").mkdir(exist_ok=True)
        (rec / "Zones" / "Zone1.ini").write_text(ZONE_INI, encoding="utf-8")
    cfgs = ini_parser.scan_tree(Path(root) / "R_TB500_PI3", default_equipment=equip)
    return ini_parser.build_pivot(cfgs)[0]


def _make_form(tmp) -> str:
    """장비 A(AOI-13) 파싱으로 양식 생성 + Parameter 하나를 사람이 개명."""
    rows = _pivot(os.path.join(tmp, "A"), "AOI-13")
    init = os.path.join(tmp, "init.xlsx")
    formbuilder.build_initial_workbook(rows, init, level="PI3")
    # 'Max Defects Per Wafer' → '웨이퍼당 최대결함' 으로 개명
    wb = openpyxl.load_workbook(init)
    ws = wb[formbuilder.INIT_SHEET]
    heads = [c.value for c in ws[1]]
    fi = heads.index("최종 Parameter") + 1
    gi = heads.index("추천 Parameter") + 1
    for r in range(2, ws.max_row + 1):
        if ws.cell(r, gi).value == "Max Defects Per Wafer":
            ws.cell(r, fi).value = "웨이퍼당 최대결함"
    wb.save(init); wb.close()
    form = os.path.join(tmp, "TB500_PI.xlsx")
    formbuilder.build_final_from_initial(init, form, level="PI3")
    return form


def test_collate_matches_despite_rename():
    with tempfile.TemporaryDirectory() as tmp:
        form = _make_form(tmp)
        # 장비 B(AOI-14): 값이 다르고, 이름은 원래 표시명으로 파싱됨
        pivot_b = _pivot(os.path.join(tmp, "B"), "AOI-14", gtext=GLOBAL_RTP_B)
        results = collate.collate(form, pivot_b)
        assert len(results) == 1
        res = results[0]
        assert res.level == "PI3" and res.sheet == "PI_ALL"
        # 개명된 행도 원본 설정키(MaxFaultsPerWafer)로 매칭되어 값이 채워져야 함
        assert res.mismatches == [], res.mismatches
        assert "AOI-14" in res.machines
        renamed = [r for r in res.records if r.get("Parameter") == "웨이퍼당 최대결함"]
        assert renamed and engine._s(renamed[0].get("AOI-14")) == "5000"

        # 저장 → 공용 양식 + 값
        dest = os.path.join(tmp, "취합.xlsx")
        collate.write_collated(res, dest, source="AOI-14")
        repo = engine.ParamRepository(dest); repo.load()
        assert "AOI-14" in repo.aoi_units
        got = {engine._s(pr.get("Parameter")): engine._s(pr.get("AOI-14"))
               for pr in repo.rows}
        assert got.get("웨이퍼당 최대결함") == "5000"
    print("  collate OK: 개명된 양식도 설정키로 매칭 + 호기 값 채움")


def test_collate_detects_mismatch():
    with tempfile.TemporaryDirectory() as tmp:
        form = _make_form(tmp)            # GlobalRTP(2) + Zone(1) = 3 항목
        # 장비 C: GlobalRTP 만(Zone 없음) → Zone 파라미터가 불일치로 잡혀야
        pivot_c = _pivot(os.path.join(tmp, "C"), "AOI-15", with_zone=False)
        res = collate.collate(form, pivot_c)[0]
        assert res.mismatches, "Zone 항목 불일치가 안 잡힘"
        params = {m["param"] for m in res.mismatches}
        assert "Contrast Delta - Bright" in params
        # 불일치 행은 저장 시 비고에 [불일치] 표기
        dest = os.path.join(tmp, "취합C.xlsx")
        collate.write_collated(res, dest)
        repo = engine.ParamRepository(dest); repo.load()
        notes = [engine._s(pr.get("비고")) for pr in repo.rows
                 if engine._s(pr.get("Parameter")) == "Contrast Delta - Bright"]
        assert notes and notes[0].startswith("[불일치]")
    print("  collate OK: 불일치 검출 + 비고 [불일치] 표기")


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
