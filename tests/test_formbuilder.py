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


def test_final_stores_scales():
    with tempfile.TemporaryDirectory() as tmp:
        rows, _ = _pivot(tmp)
        init = os.path.join(tmp, "init.xlsx")
        formbuilder.build_initial_workbook(rows, init, level="PI3")
        final = os.path.join(tmp, "form.xlsx")
        scales = {"PI": 0.8456665875666588, "PI-bubble": 0.7696441409644141}
        formbuilder.build_final_from_initial(init, final, level="PI3", scales=scales)
        got = extract_io.read_scales(final)
        assert got == scales, got
        # '초기 추천값'(대표값)은 최종 스키마에 없어야 함
        assert "초기 추천값" not in engine.META_FIELDS
    print("  formbuilder OK: 변형별 계수 양식에 저장/판독 + 추천값 스키마 제거")


def test_rename_level_draft_and_final():
    """레시피 이름 수정: 초안(양식초안 PI 열·사용법)과 확정본(PI_ALL PI 열·추출_요약)
    안의 레벨 이름이 함께 바뀌고, 확정 재생성 시 새 이름이 유지된다."""
    with tempfile.TemporaryDirectory() as tmp:
        rows, _ = _pivot(tmp)
        init = os.path.join(tmp, "init.xlsx")
        formbuilder.build_initial_workbook(rows, init, level="PI3", source="AOI-13")
        final = os.path.join(tmp, "form.xlsx")
        formbuilder.build_final_from_initial(init, final, level="PI3", aoi="AOI-13")

        # 초안 이름 변경 → PI 열 전부 + 사용법 줄
        n = formbuilder.rename_level(init, "PI3", "PI3-NEW")
        assert n >= len(rows) + 1, n
        wb = openpyxl.load_workbook(init)
        ws = wb[formbuilder.INIT_SHEET]
        pi = formbuilder.INIT_HEADERS.index("PI")
        vals = {r[pi] for r in ws.iter_rows(min_row=2, values_only=True)}
        assert vals == {"PI3-NEW"}, vals
        info = [c.value for c in wb["사용법"]["A"]]
        assert "레시피 레벨: PI3-NEW" in info
        wb.close()

        # 이름 바뀐 초안 → 확정 재생성: 새 이름이 그대로 반영
        final2 = os.path.join(tmp, "form2.xlsx")
        formbuilder.build_final_from_initial(init, final2, level="PI3-NEW")
        repo = engine.ParamRepository(final2)
        repo.load()
        assert {engine._s(pr.get("PI")) for pr in repo.rows} == {"PI3-NEW"}

        # 확정본 직접 이름 변경(초안 없는 옛 버전 대응) → PI_ALL + 추출_요약
        n2 = formbuilder.rename_level(final, "PI3", "PI3-NEW")
        assert n2 > 0
        repo2 = engine.ParamRepository(final)
        repo2.load()
        assert {engine._s(pr.get("PI")) for pr in repo2.rows} == {"PI3-NEW"}
        wb = openpyxl.load_workbook(final)
        sm = wb[extract_io.SHEET_SUMMARY]
        d = {engine._s(r[0]): engine._s(r[1])
             for r in sm.iter_rows(min_row=2, values_only=True) if r and r[0]}
        assert d.get("레시피 레벨") == "PI3-NEW", d
        wb.close()
        # 같은 이름/빈 이름은 no-op
        assert formbuilder.rename_level(final, "PI3-NEW", "PI3-NEW") == 0
        assert formbuilder.rename_level(final, "PI3-NEW", "") == 0
    print("  formbuilder OK: rename_level — 초안/확정/요약 레벨 이름 일괄 변경")


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
