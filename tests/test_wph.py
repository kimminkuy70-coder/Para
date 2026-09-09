"""WPH 조사 테스트 — batch report 파싱·recipe 접두 검색·취합텍스트·수식 엑셀.

GUI/Excel 계산기는 개발환경 미지원이므로, 수식은 **문자열로** 검증한다
(참조 양식과 동일한 수식·구조·생성일자 열·유효매수 반영).
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from param_manager import wph  # noqa: E402


def _report_html(lot, wafers, avg, batch, batch_end, recipe="2D_WBG"):
    """batch report 1개(HTML) — 메타 테이블 + 웨이퍼 테이블."""
    wrows = "".join(
        f"<tr><td>{i}</td><td>{lot}</td><td>{i}</td><td>0</td>"
        f"<td>29</td><td>0</td><td>29</td><td>100%</td><td>Pass</td><td>{recipe}</td></tr>"
        for i in range(1, wafers + 1))
    return f"""<html><body>
    <table><tr><td>Batch Info</td><td>Date: 26-Jul-02</td></tr>
      <tr><td>Batch End</td><td>{batch_end}</td></tr>
      <tr><td>Batch Time</td><td>{batch}</td></tr>
      <tr><td>Wafers Scanned</td><td>{wafers}</td></tr>
      <tr><td>Avg. Scan Time</td><td>{avg}</td></tr>
      <tr><td>Yield</td><td>100</td></tr></table>
    <table><tr><th>No</th><th>Lot</th><th>Wafer ID</th><th>Faults</th>
      <th>Scanned Dice</th><th>Bad Dice</th><th>Good Dice</th><th>Yield</th>
      <th>Pass/Fail</th><th>Recipe(s)</th></tr>{wrows}</table>
    </body></html>"""


def _make_folder(d):
    """recipe 접두가 섞인 Report 폴더를 만든다."""
    files = {
        # recipe A: 25매 2건 + 3매 1건
        "2D@RE-GA285ABB_0859840PD-0A_6392_L1_26-Aug-30_(21.41.39)_BatchReport.htm":
            _report_html("L1", 25, "00:01:44", "00:53:23", "30-Aug-26 09:41:31 PM"),
        "2D@RE-GA285ABB_0859840PD-0A_6392_L2_26-Jul-10_(11.35.02)_BatchReport.htm":
            _report_html("L2", 25, "00:01:35", "00:47:30", "10-Jul-26 11:34:55 AM"),
        "2D@RE-GA285ABB_0859840PD-0A_6392_L3_26-Jul-02_(04.15.08)_BatchReport.htm":
            _report_html("L3", 3, "00:01:34", "00:08:16", "02-Jul-26 04:15:07 AM"),
        # recipe B: 다른 recipe(접두가 다름)
        "2D@OTHER-RECIPE_9999_L9_26-Jul-01_(01.00.00)_BatchReport.htm":
            _report_html("L9", 25, "00:02:00", "00:50:00", "01-Jul-26 01:00:00 AM"),
        # report 가 아닌 파일(무시돼야 함)
        "readme.txt": "not a report",
    }
    for name, content in files.items():
        with open(os.path.join(d, name), "w", encoding="utf-8") as f:
            f.write(content)


def test_value_parsers():
    assert wph.hms_to_seconds("00:01:44") == 104
    assert wph.hms_to_seconds("00:53:23") == 3203
    assert wph.hms_to_seconds("1:35") == 95            # MM:SS
    assert wph.hms_to_seconds("") is None
    dt = wph.parse_batch_datetime("30-Aug-26 09:41:31 PM")
    assert (dt.year, dt.month, dt.day, dt.hour, dt.minute) == (2026, 8, 30, 21, 41)
    assert wph.parse_batch_datetime("30-Aug-26 12:00:00 AM").hour == 0   # 자정
    assert wph.parse_batch_datetime("30-Aug-26 12:30:00 PM").hour == 12  # 정오
    assert wph.parse_batch_datetime("깨진값") is None
    print("  wph OK: 시간→초·Batch End→datetime(AM/PM·자정·정오·오류)")


def test_report_parse_and_extract():
    with tempfile.TemporaryDirectory() as d:
        _make_folder(d)
        p = os.path.join(
            d, "2D@RE-GA285ABB_0859840PD-0A_6392_L1_26-Aug-30_(21.41.39)_BatchReport.htm")
        rep = wph.parse_report(p)
        assert len(rep["wafers"]) == 25
        row = wph.extract_row(rep)
        assert row["wafers"] == 25
        assert row["avg_scan_sec"] == 104
        assert row["batch_sec"] == 3203
        assert row["batch_end"].hour == 21
    print("  wph OK: 리포트 파싱 + BATCH_INFO 추출(매수·초·생성일자)")


def test_recipe_prefix_search():
    with tempfile.TemporaryDirectory() as d:
        _make_folder(d)
        pref = "2D@RE-GA285ABB_0859840PD-0A"
        # 접두 매칭: recipe A 3건만(다른 recipe·txt 제외)
        assert wph.count_reports(d, pref) == 3
        names = wph.list_reports(d, pref)
        assert len(names) == 3 and all(n.startswith(pref) for n in names)
        # 대소문자 무시
        assert wph.count_reports(d, pref.lower()) == 3
        # 접두 없이 = report 파일 전체(txt 제외) 4건
        assert wph.count_reports(d, "") == 4
        # 없는 접두
        assert wph.count_reports(d, "ZZZ") == 0
    print("  wph OK: recipe 접두 검색·카운트(대소문자무시·타recipe/비report 제외)")


def test_collect_rows_readonly():
    with tempfile.TemporaryDirectory() as d:
        _make_folder(d)
        before = {n: os.path.getmtime(os.path.join(d, n)) for n in os.listdir(d)}
        rows, errors = wph.collect_rows(d, "2D@RE-GA285ABB_0859840PD-0A")
        assert not errors and len(rows) == 3
        # full-lot(25) 2건 + 3매 1건
        assert sum(1 for r in rows if r["wafers"] == 25) == 2
        # 원본 무변경(read-only)
        after = {n: os.path.getmtime(os.path.join(d, n)) for n in os.listdir(d)}
        assert before == after, "원본 파일이 변경되면 안 됨"
    print("  wph OK: 접두 수집(원본 read-only·오류없음)")


def test_combined_text():
    with tempfile.TemporaryDirectory() as d:
        _make_folder(d)
        text, n, errors = wph.build_combined_text(
            d, "2D@RE-GA285ABB_0859840PD-0A", "AOI-21", "2D@RE-GA285ABB_0859840PD-0A")
        assert n == 3 and not errors
        assert "MACHINE: AOI-21" in text and "RECIPE: 2D@RE-GA285ABB" in text
        assert "[BATCH_INFO]" in text and "[WAFER_RESULTS]" in text
        assert "REPORT_FILE_COUNT: 3" in text
    print("  wph OK: 취합 텍스트(호기·recipe 헤더·리포트 수)")


def test_excel_structure_and_valid_wafers():
    import openpyxl
    with tempfile.TemporaryDirectory() as d:
        rows = [
            {"source_file": "r1.htm", "wafers": 25, "avg_scan_sec": 104,
             "batch_sec": 3203, "machine": "AOI-21",
             "batch_end": wph.parse_batch_datetime("30-Aug-26 09:41:31 PM")},
            {"source_file": "r2.htm", "wafers": 3, "avg_scan_sec": 94,
             "batch_sec": 496, "machine": "AOI-22",
             "batch_end": None, "batch_end_raw": "raw-date"},
        ]
        out = os.path.join(d, "wph.xlsx")
        wph.write_wph_excel(out, rows, valid_wafers=25, title="T")
        wb = openpyxl.load_workbook(out)
        assert wb.sheetnames == ["00_사용안내", "01_Raw_Data", "02_25매_통계",
                                 "03_이상치", "04_그래프데이터", "05_대시보드"]
        ws = wb["01_Raw_Data"]
        assert ws["A1"].value == "Report"
        # 통합 엑셀: 호기(U) + 생성일자(V) 열
        assert ws["U1"].value == "호기" and ws["V1"].value == "Batch End (생성일자)"
        assert ws["U2"].value == "AOI-21" and ws["U3"].value == "AOI-22"
        # 입력값
        assert ws["C2"].value == 25 and ws["D2"].value == 104 and ws["E2"].value == 3203
        # 핵심 수식(WPH·Valid) — 참조와 동일
        assert ws["J2"].value == '=IFERROR(C2*3600/E2,"")'
        assert ws["L2"].value == '=IF(AND(C2=25,D2>0,E2>0),"Y","")'
        # 생성일자: datetime → 날짜셀, 없으면 raw 문자열
        from datetime import datetime as _dt
        assert isinstance(ws["V2"].value, _dt)
        assert ws["V3"].value == "raw-date"
        # 통계 시트가 Raw_Data N/O 수식이 참조하는 이름과 일치
        assert "'02_25매_통계'!" in ws["N2"].value
        # 수식 용량(참조와 동일 2001행까지)
        assert ws["J2001"].value == '=IFERROR(C2001*3600/E2001,"")'

        # 유효매수 변경 → 시트명·Valid 판정·헤더 반영
        out2 = os.path.join(d, "wph13.xlsx")
        wph.write_wph_excel(out2, rows, valid_wafers=13)
        wb2 = openpyxl.load_workbook(out2)
        assert "02_13매_통계" in wb2.sheetnames
        ws2 = wb2["01_Raw_Data"]
        assert ws2["L2"].value == '=IF(AND(C2=13,D2>0,E2>0),"Y","")'
        assert ws2["L1"].value == "Valid 13"
        assert "'02_13매_통계'!" in ws2["N2"].value
    print("  wph OK: 엑셀 6시트·입력/수식·생성일자(U)·유효매수 변경 반영")


def test_combined_multi_machine():
    """여러 호기 → 취합 텍스트는 호기별, 결과 엑셀은 통합 1개(호기 열로 구분)."""
    import openpyxl
    with tempfile.TemporaryDirectory() as d:
        rows = []
        for m, n in (("AOI-21", 3), ("AOI-22", 2)):
            for i in range(n):
                rows.append({"source_file": f"{m}_{i}.htm", "wafers": 25,
                             "avg_scan_sec": 100, "batch_sec": 3000, "machine": m,
                             "batch_end": None, "batch_end_raw": ""})
        out = os.path.join(d, wph.combined_excel_filename(["AOI-21", "AOI-22"]))
        wph.write_wph_excel(out, rows, valid_wafers=25, title="통합")
        ws = openpyxl.load_workbook(out)["01_Raw_Data"]
        # 두 호기 행이 한 엑셀에 모두 들어가고 Report 번호는 연속
        machines = [ws.cell(row=r, column=21).value for r in range(2, 7)]
        assert machines == ["AOI-21", "AOI-21", "AOI-21", "AOI-22", "AOI-22"]
        assert ws["A2"].value == 1 and ws["A6"].value == 5
    # 파일명 헬퍼
    assert wph.text_filename("AOI-21", "2D@R").endswith("_취합.txt")
    assert "AOI-21" in wph.text_filename("AOI-21", "2D@R")
    assert wph.combined_excel_filename(["AOI-21", "AOI-22"]) == "WPH_AOI-21_AOI-22_통합.xlsx"
    assert wph.combined_excel_filename(["A", "B", "C", "D", "E"]) == "WPH_A외4_통합.xlsx"
    print("  wph OK: 통합 엑셀(호기 열·연속 Report) + 파일명 헬퍼(텍스트 호기별·통합)")


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
