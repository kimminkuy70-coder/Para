"""통합 파이프라인(재설계) — 저장폴더 기준 전체 흐름을 코드로 검증.

참고자료(호기) → 양식 만들기(양식 폴더) → 값 취합(전체 호기·직전 이어받기) →
이력 비교. GUI(tkinter)는 개발환경에서 못 돌리므로 이 뼈대를 검증한다.
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from param_manager import (collate, engine, formbuilder, history,  # noqa: E402
                           ini_parser, refdata, workdirs)

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


def test_full_pipeline():
    with tempfile.TemporaryDirectory() as tmp:
        save = os.path.join(tmp, "저장폴더")
        os.makedirs(save)
        # 참고자료: 호기 3대
        refp = refdata.ref_path(save)
        refdata.save_reference(refp, [
            {"호기": "AOI-24", "IP": "10.0.0.24", "비고": ""},
            {"호기": "AOI-25", "IP": "10.0.0.25", "비고": ""},
            {"호기": "AOI-26", "IP": "10.0.0.26", "비고": ""}])
        machines = refdata.machines(refdata.load_reference(refp))
        assert machines == ["AOI-24", "AOI-25", "AOI-26"]

        # 양식 만들기: PI3 (개명 포함) → 양식/PI3/{stamp}/ 확정본
        rows = _pivot(os.path.join(tmp, "A"), "AOI-24")
        init = os.path.join(tmp, "init.xlsx")
        formbuilder.build_initial_workbook(rows, init, level="PI3")
        st = workdirs.stamp()
        run = workdirs.form_run_dir(save, "PI3", st)
        final = workdirs.form_final_path(run, "PI3", "AOI-24", st)
        formbuilder.build_final_from_initial(init, final, level="PI3")
        assert workdirs.latest_form(save, "PI3") == final

        # 1차 취합: AOI-25
        p25 = _pivot(os.path.join(tmp, "B25"), "AOI-25", wafer="5000")
        r1 = collate.build_collation(save, ["PI3"], p25, machines)
        c1 = workdirs.collate_path(save, "20260707_120000")
        collate.write_collation(c1, r1, machines)

        # 2차 취합: AOI-24(직전 이어받기)
        p24 = _pivot(os.path.join(tmp, "B24"), "AOI-24", wafer="7000")
        r2 = collate.build_collation(save, ["PI3"], p24, machines, prev_collate_path=c1)
        c2 = workdirs.collate_path(save, "20260707_130000")
        collate.write_collation(c2, r2, machines)

        assert workdirs.latest_collate(save) == c2   # 최신 자동 = 값 확인 소스

        # 이력: c1 → c2 에서 AOI-24 값이 (빈)→7000
        diff = history.diff_files(c1, c2)
        chg = {(c.param, c.machine): c for c in diff.changes}
        key = ("Max Defects Per Wafer", "AOI-24")
        assert key in chg and chg[key].new == "7000"
        assert chg[key].sheet == "PI3"
        print("  pipeline OK: 참고자료→양식→취합(누적)→최신자동→이력 일관")


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
