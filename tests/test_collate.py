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
