"""wph_html 테스트 — 섹션 선택·에러 3단(전체/호기별/호기×레시피)·scan 상태·미리보기 일치."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from param_manager import wph, wph_html  # noqa: E402


def _st(status, n):
    return [{"status": status, "slot": str(i), "wafer_id": str(i)} for i in range(n)]


def _rows():
    end = wph.parse_batch_datetime("30-Aug-26 09:41:31 PM")
    return [
        # AOI-21 / R1 — 정상 25매
        {"machine": "AOI-21", "recipe": "R1", "wafers": 25, "avg_scan_sec": 100,
         "batch_sec": 3000, "batch_end": end, "wafer_statuses": _st("Pass", 25)},
        # AOI-21 / R1 — 25매, 2건 Aborted
        {"machine": "AOI-21", "recipe": "R1", "wafers": 25, "avg_scan_sec": 104,
         "batch_sec": 3200, "batch_end": end,
         "wafer_statuses": _st("Pass", 23) + _st("Aborted.", 2)},
        # AOI-21 / R2 — 25매, 1건 Nothing to Scan
        {"machine": "AOI-21", "recipe": "R2", "wafers": 25, "avg_scan_sec": 110,
         "batch_sec": 3300, "batch_end": None, "batch_end_raw": "??",
         "wafer_statuses": _st("Pass", 24) + _st("Nothing to Scan.", 1)},
        # AOI-22 / R1 — 3매(유효 아님)
        {"machine": "AOI-22", "recipe": "R1", "wafers": 3, "avg_scan_sec": 94,
         "batch_sec": 496, "batch_end": end, "wafer_statuses": _st("Pass", 3)},
    ]


def test_compute_summary_and_wph_groups():
    c = wph_html.compute(_rows(), [("bad.htm", "no table")], valid_wafers=25)
    s = c["summary"]
    assert s["valid_lots"] == 3 and s["total_wafer"] == 75
    assert s["no_time"] == 1                         # R2 는 batch_end 없음
    # 호기별: AOI-21 만 유효 3건
    bym = {r["key"]: r for r in c["wph_by_machine"]}
    assert bym["AOI-21"]["lots"] == 3
    assert "AOI-22" not in bym                        # 3매는 유효 아님 → 집계 제외
    # 호기×레시피
    byr = {r["key"]: r for r in c["wph_by_recipe"]}
    assert byr[("AOI-21", "R1")]["lots"] == 2 and byr[("AOI-21", "R2")]["lots"] == 1
    print("  wph_html OK: 요약·호기별·호기×레시피 WPH")


def test_error_three_tiers():
    c = wph_html.compute(_rows(), [], valid_wafers=25)
    # ① 전체
    cats = {k[0]: v for k, v in c["err_overall"].items()}
    assert cats["작업 중단"] == [1, 2]              # report 1건, wafer 2
    assert cats["검사 대상 없음"] == [1, 1]
    assert c["issue_report_total"] == 2              # 이슈 리포트 2건(중복 제외)
    # ② 호기별 — 이슈는 AOI-21 에만
    assert "AOI-21" in c["err_by_machine"] and "AOI-22" not in c["err_by_machine"]
    # ③ 호기×레시피
    assert ("AOI-21", "R1") in c["err_by_recipe"]    # Aborted
    assert ("AOI-21", "R2") in c["err_by_recipe"]    # Nothing to Scan
    # scan 상태(정상/error/확인불가)
    ss = c["scan_status"]
    assert ss["normal"] == 2 and ss["error"] == 2 and ss["unknown"] == 0
    print("  wph_html OK: 에러 ①②③ + scan 상태(정상/error/확인불가)")


def test_sections_select_and_html():
    c = wph_html.compute(_rows(), [("bad.htm", "x")], valid_wafers=25)
    # 일부만 선택 → 나머지 섹션 미포함
    sec = {k: False for k in wph_html.SECTION_TITLES}
    sec["err_by_recipe"] = True
    sec["wph_summary"] = True
    html = wph_html.build_html(c, title="WPH 통합 (테스트)", meta={"기간": "8월"},
                               sections=sec, by_recipe=True)
    assert "<title>WPH 통합 (테스트)</title>" in html
    assert "에러 ③" in html and "호기별 → 레시피별" in html
    assert "에러 ①" not in html and "Report 목록" not in html   # 미선택
    assert "8월" in html
    # 기본 섹션 = 파싱오류는 오류 있을 때만
    d0 = wph_html.default_sections([])
    d1 = wph_html.default_sections([("a", "b")])
    assert d0["parse_errors"] is False and d1["parse_errors"] is True
    # 미리보기 표와 HTML 이 같은 소스(compute)에서 나옴
    tables = wph_html.preview_tables(c, wph_html.default_sections([("a", "b")]))
    titles = [t[0] for t in tables]
    assert "에러 ③ 호기별 → 레시피별" in titles and "파싱오류" in titles
    print("  wph_html OK: 섹션 on/off·편집 제목·메타·미리보기 표")


def test_write_html_file():
    c = wph_html.compute(_rows(), [], valid_wafers=25)
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "r.html")
        wph_html.write_html(p, c, title="T")
        txt = open(p, encoding="utf-8").read()
        assert txt.startswith("<!doctype html>") and "</html>" in txt
    print("  wph_html OK: .html 파일 저장")


def test_job_recipe_extraction():
    assert wph.job_recipe("CMP2D-DT-GH10N_0856268PD-0A/6392") == "CMP2D-DT-GH10N_0856268PD-0A"
    assert wph.job_recipe("2D@RE-GA285ABB_0859840PD-0A") == "2D@RE-GA285ABB_0859840PD-0A"
    assert wph.job_recipe("") == "(미상)"
    print("  wph OK: Job/Setup → recipe(Job) 추출")


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
