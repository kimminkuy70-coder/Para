"""history 테스트 — 두 취합 엑셀 비교(값변경/추가/삭제) + 변경내역 엑셀."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import openpyxl  # noqa: E402

from param_manager import engine, history  # noqa: E402


def _form(path, rows, machines):
    """rows: [(PI,Recipe,Zone,Alg,Parameter, {호기:값})]."""
    recs = []
    for pi, recipe, zone, alg, param, vals in rows:
        rec = {"PI": pi, "Recipe": recipe, "Zone": zone, "Alg": alg,
               "Parameter": param, "초기 추천값": "", "비고": ""}
        rec.update(vals)
        recs.append(rec)
    engine.create_from_records(path, recs, machines, sheet_name="PI_ALL")


def test_diff_and_excel():
    with tempfile.TemporaryDirectory() as tmp:
        old = os.path.join(tmp, "v1.xlsx")
        new = os.path.join(tmp, "v2.xlsx")
        _form(old, [
            ("PI3", "PI", "GlobalRTP", "GLOBAL_RTP", "Max Defects Per Wafer",
             {"AOI-13": "3000", "AOI-14": "3000"}),
            ("PI3", "PI", "PI Opening", "Surface", "Contrast Delta - Bright",
             {"AOI-13": "25"}),
            ("PI3", "PI", "GlobalRTP", "GLOBAL_RTP", "삭제될 항목",
             {"AOI-13": "1"}),
        ], ["AOI-13", "AOI-14"])
        _form(new, [
            ("PI3", "PI", "GlobalRTP", "GLOBAL_RTP", "Max Defects Per Wafer",
             {"AOI-13": "5000", "AOI-14": "3000"}),          # AOI-13 값변경
            ("PI3", "PI", "PI Opening", "Surface", "Contrast Delta - Bright",
             {"AOI-13": "25", "AOI-14": "30"}),              # AOI-14 추가
            ("PI3", "PI", "GlobalRTP", "GLOBAL_RTP", "새 항목",
             {"AOI-13": "9"}),                               # 행 추가
        ], ["AOI-13", "AOI-14"])

        diff = history.diff_files(old, new)
        kinds = {(c.param, c.machine): c for c in diff.changes}
        assert kinds[("Max Defects Per Wafer", "AOI-13")].kind == "값변경"
        assert kinds[("Max Defects Per Wafer", "AOI-13")].old == "3000"
        assert kinds[("Max Defects Per Wafer", "AOI-13")].new == "5000"
        assert kinds[("Contrast Delta - Bright", "AOI-14")].kind == "추가"
        assert {r["Parameter"] for r in diff.added_rows} == {"새 항목"}
        assert {r["Parameter"] for r in diff.removed_rows} == {"삭제될 항목"}

        dest = os.path.join(tmp, "변경내역.xlsx")
        history.write_diff_excel(diff, dest, old_label="v1", new_label="v2",
                                 memos={("PI3", "PI", "GlobalRTP", "GLOBAL_RTP",
                                         "Max Defects Per Wafer", "AOI-13"): "감도 상향"})
        wb = openpyxl.load_workbook(dest)
        assert history.DIFF_SHEET in wb.sheetnames
        ws = wb[history.DIFF_SHEET]
        heads = [c.value for c in ws[1]]
        assert heads == history.DIFF_HEADERS
        # 메모가 비고 열에 실렸는지
        memo_col = heads.index("비고(메모)")
        memos_found = [r[memo_col] for r in ws.iter_rows(min_row=2, values_only=True)]
        assert "감도 상향" in memos_found
        wb.close()
    print("  history OK: 값변경/추가/행추가·삭제 + 변경내역 엑셀 + 비고 메모")


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
