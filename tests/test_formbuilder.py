"""formbuilder 테스트 — 편집용 initial 생성 + 편집된 initial→final 양식."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import openpyxl  # noqa: E402

from param_manager import engine, extract_io, formbuilder, ini_parser  # noqa: E402

GLOBAL_RTP = """[GLOBAL_RTP]
MaxFaultsPerWafer = 3000
ApplyDieCalib = 1
"""
ZONE_INI = """[General]
ZoneName = PI Opening
[Surface]
High_Delta = 25
BrightLength = 5
"""


def _mk_recipe(d: Path):
    d.mkdir(parents=True, exist_ok=True)
    (d / "GlobalRTP.ini").write_text(GLOBAL_RTP, encoding="utf-8")
    (d / "Zones").mkdir(exist_ok=True)
    (d / "Zones" / "Zone1.ini").write_text(ZONE_INI, encoding="utf-8")


def _pivot(tmp):
    recipe = Path(tmp) / "R_TB500_PI3" / "PI"
    _mk_recipe(recipe)
    cfgs = ini_parser.scan_tree(Path(tmp) / "R_TB500_PI3", default_equipment="AOI-13")
    rows, machines = ini_parser.build_pivot(cfgs)
    return rows, machines


def test_build_initial_and_final():
    with tempfile.TemporaryDirectory() as tmp:
        rows, _ = _pivot(tmp)
        assert rows
        init = os.path.join(tmp, "01_초안.xlsx")
        formbuilder.build_initial_workbook(rows, init, level="PI3", source="AOI-13")
        assert os.path.isfile(init)

        wb = openpyxl.load_workbook(init)
        ws = wb[formbuilder.INIT_SHEET]
        heads = [c.value for c in ws[1]]
        assert heads == formbuilder.INIT_HEADERS
        assert ws.max_row - 1 == len(rows)            # 헤더 제외 = 파싱 행 수
        # 최종 Parameter 기본값 = 추천 Parameter
        gi = heads.index("추천 Parameter"); fi = heads.index("최종 Parameter")
        for r in ws.iter_rows(min_row=2, values_only=True):
            assert r[fi] == r[gi]
        wb.close()

        # 사람이 편집한 상황을 흉내: 한 행 사용=N, 한 행 최종 이름 변경
        wb = openpyxl.load_workbook(init)
        ws = wb[formbuilder.INIT_SHEET]
        ui = formbuilder.INIT_HEADERS.index("사용")
        ws.cell(2, ui + 1).value = "N"                # 첫 데이터 행 제외
        ws.cell(3, fi + 1).value = "내가 지정한 이름"     # 둘째 행 이름 변경
        wb.save(init)
        wb.close()

        final = os.path.join(tmp, "02_확정.xlsx")
        res = formbuilder.build_final_from_initial(
            final and init, final, level="PI3", aoi="AOI-13", user="tester")
        assert res["kept"] == len(rows) - 1 and res["dropped"] == 1
        assert res["sheet"] == "PI_ALL"

        # final 은 공용 양식(PI_ALL) + _EXTRACT_MAP 을 가진다
        repo = engine.ParamRepository(final)
        repo.load()
        assert len(repo.rows) == len(rows) - 1
        names = {engine._s(pr.get("Parameter")) for pr in repo.rows}
        assert "내가 지정한 이름" in names
        emap = extract_io.read_extract_map(final)
        assert emap                                   # 재추출 메타 보존
        print("  formbuilder OK: initial 생성 + 사용/이름편집 반영 final + _EXTRACT_MAP")


def test_final_rejects_when_all_unused():
    with tempfile.TemporaryDirectory() as tmp:
        rows, _ = _pivot(tmp)
        init = os.path.join(tmp, "init.xlsx")
        formbuilder.build_initial_workbook(rows, init)
        wb = openpyxl.load_workbook(init)
        ws = wb[formbuilder.INIT_SHEET]
        ui = formbuilder.INIT_HEADERS.index("사용") + 1
        for r in range(2, ws.max_row + 1):
            ws.cell(r, ui).value = "N"
        wb.save(init); wb.close()
        try:
            formbuilder.build_final_from_initial(init, os.path.join(tmp, "f.xlsx"))
            assert False, "빈 선택인데 예외가 안 났다"
        except ValueError:
            pass
    print("  formbuilder OK: 사용 행 없으면 ValueError")


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
