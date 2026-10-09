"""RTP.txt 설명 → 값 확인 비고(영문 원문 + 한글 번역) 테스트 — 이슈 #23."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from param_manager import (collate, engine, extract_io, formbuilder, ini_parser,  # noqa: E402
                           rtpnotes, workdirs)

GLOBAL = "[GLOBAL_RTP]\nMaxFaultsPerWafer = 3000\n"
ZONE = ("[General]\nZoneName = PI Opening\n[Surface]\nHigh_Delta = 25\nBrightArea = 100\n"
        "Mystery_Key = 7\n[Surface Feature Filter Width]\nLowValue = 2\n")
RTP = """[PI_Opening]
Alg = Surface
Contrast_Delta_-_Bright = 25 ; in {} ( Minimum contrast difference of bright defects~101 )
Min_Defect_Area_-_Bright = 59.29 ; in {area, µ} ( Minimum area of a bright defect~102 )
Mystery_Key = 7 ; ( Vendor only text~103 )
Alg = Surface_Feature_Filter_Width
Low_Value = 2.0 ; in {µ} ( Lower limit of the filter~104 )
"""


def _tree(root, rtp=True):
    rec = Path(root) / "R_TB500_PI3" / "PI"
    (rec / "Zones").mkdir(parents=True, exist_ok=True)
    (rec / "GlobalRTP.ini").write_text(GLOBAL, encoding="utf-8")
    (rec / "Zones" / "Z.ini").write_text(ZONE, encoding="utf-8")
    if rtp:
        (rec / "RTP.txt").write_text(RTP, encoding="utf-8")
    cfgs = ini_parser.scan_tree(Path(root) / "R_TB500_PI3", default_equipment="AOI-24")
    return ini_parser.build_pivot(cfgs)[0]


def _by_param(rows):
    return {r["param"]: r for r in rows}


def test_pivot_gets_english_and_korean():
    with tempfile.TemporaryDirectory() as tmp:
        rows = _by_param(_tree(tmp))
        # 표시명이 같은 것(Contrast Delta - Bright) — 번들 번역 있음
        n = rows["Contrast Delta - Bright"]["note"]
        assert n.startswith("Minimum contrast difference of bright defects / "), n
        assert "밝은 결함 최소 Contrast 차이" in n, n
        # 단위 괄호가 붙은 표시명도 RTP 이름과 맞음
        assert rows["Min Defect Area - Bright (area, µ)"]["desc_en"] == "Minimum area of a bright defect"
        # 알고리즘이 다른 같은 이름(Low Value) — Alg 로 구분
        assert rows["Low Value (µ)"]["desc_en"] == "Lower limit of the filter"
        # 번역이 없으면 영문만, 설명 없는 행은 빈칸
        assert rows["Mystery Key"]["note"] == "Vendor only text"
        assert rows["Max Defects Per Wafer"]["note"] == ""
    print("  rtpnotes OK: 영문 원문 + 한글 번역, 단위 괄호·Alg 구분, 번역 없으면 영문만")


def test_no_rtp_means_no_note():
    with tempfile.TemporaryDirectory() as tmp:
        rows = _tree(tmp, rtp=False)
        assert all(r["note"] == "" and r["desc_en"] == "" for r in rows)
    print("  rtpnotes OK: RTP.txt 없으면 비고 없음")


def test_note_text():
    assert rtpnotes.note_text("Width", "폭") == "Width / 폭"
    assert rtpnotes.note_text("Width", "") == "Width"
    assert rtpnotes.note_text("Width", "width") == "Width"
    assert rtpnotes.note_text("", "폭") == ""


def test_collation_fills_empty_note_only():
    with tempfile.TemporaryDirectory() as tmp:
        save = os.path.join(tmp, "save")
        rows = _tree(os.path.join(tmp, "A"))
        init = os.path.join(tmp, "init.xlsx")
        formbuilder.build_initial_workbook(rows, init, level="PI3")
        st = workdirs.stamp()
        run = workdirs.form_run_dir(save, "PI3", st)
        final = workdirs.form_final_path(run, "PI3", "AOI-24", st)
        formbuilder.build_final_from_initial(init, final, level="PI3")
        res = collate.collate_recipe("PI3", final, rows, ["AOI-24"])
        notes = {engine._s(r.get("Parameter")): engine._s(r.get("비고")) for r in res.records}
        assert notes.get("Contrast Delta - Bright", "").startswith("Minimum contrast difference"), notes

        # 양식에 사람이 적은 비고는 그대로 둔다
        form = os.path.join(tmp, "f.xlsx")
        recs = [{"PI": "PI3", "Recipe": "PI", "Zone": "PI Opening", "Alg": "Surface",
                 "Parameter": "Contrast Delta - Bright", "비고": "사람 메모"}]
        exts = [{"src_file": "Z.ini", "section": "Surface", "key": "High_Delta", "raw": 25,
                 "transform": "RAW", "source_path": ""}]
        extract_io.write_snapshot(form, recs, machines=[], sheet_name="PI_ALL",
                                  extracts=exts, stage="final", level="PI3")
        res2 = collate.collate_recipe("PI3", form, rows, ["AOI-24"])
        assert engine._s(res2.records[0].get("비고")) == "사람 메모"
    print("  collate OK: 빈 비고만 RTP 설명으로 채움, 사람 비고 유지")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            print(f"[RUN] {t.__name__}")
            t()
        except Exception as e:  # noqa: BLE001
            failed += 1
            import traceback
            traceback.print_exc()
            print(f"[FAIL] {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
