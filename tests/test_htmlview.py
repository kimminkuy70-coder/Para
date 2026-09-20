"""htmlview 공용 빌더 테스트 — 이스케이프·표·KPI·섹션·전체 문서·파일 저장."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from param_manager import htmlview as hv  # noqa: E402


def test_escape_and_table():
    # 원본 문자열의 위험한 문자는 반드시 이스케이프(스크립트 삽입 방지)
    html = hv.table(["항목", "값"], [["<b>a</b>", "x&y"], ["정상", '"q"']])
    assert "<b>a</b>" not in html                 # 원문 태그가 살아있으면 안 됨
    assert "&lt;b&gt;a&lt;/b&gt;" in html
    assert "x&amp;y" in html and "&quot;q&quot;" in html
    print("  htmlview OK: 이스케이프·표")


def test_empty_and_aligns_and_rowclass():
    # 빈 표는 '내용이 없습니다' 안내
    assert "내용이 없습니다" in hv.table(["a", "b"], [])
    # 정렬 클래스·행 클래스(diff 색칠)
    html = hv.table(["p", "n"], [["a", "1"], ["b", "2"]],
                    aligns=["", "num"], row_class=lambda i, r: "chg" if i == 1 else "")
    assert 'class="num"' in html and 'class="chg"' in html
    print("  htmlview OK: 빈 표·정렬·행 클래스")


def test_cell_class():
    # 셀별 색칠(이탈 셀 등) — cell_class 콜백이 해당 td 에만 클래스 부여
    html = hv.table(["S/M", "p1", "p2"], [["A", "1", "2"], ["B", "9", "3"]],
                    cell_class=lambda ri, ci, v: "out" if (ri == 1 and ci == 1) else "")
    assert 'class="out"' in html
    assert html.count("out") == 1                 # 딱 한 셀만
    print("  htmlview OK: 셀별 클래스(이탈 색칠)")


def test_kpi_and_section():
    k = hv.kpi_cards([("정상률", "86.1", "%"), ("이슈", 72)])
    assert "정상률" in k and "86.1" in k and ">%<" in k and "72" in k
    s = hv.section("요약", "<p>x</p>", tag=("스냅샷", "lime"), note="참고")
    assert "요약" in s and "스냅샷" in s and "참고" in s and "tag lime" in s
    print("  htmlview OK: KPI·섹션·배지")


def test_page_and_write():
    body = hv.section("A", hv.table(["h"], [["v"]]))
    html = hv.page("값 확인 스냅샷", body, subtitle="읽기 전용",
                   meta={"기준": "2026-09-20", "호기": "AOI-21"})
    assert html.startswith("<!doctype html>")
    assert "<title>값 확인 스냅샷</title>" in html
    assert "읽기 전용" in html and "AOI-21" in html
    assert "cdn" not in html.lower() and "http://" not in html and "https://" not in html  # 오프라인
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "v.html")
        hv.write(p, html)
        assert open(p, encoding="utf-8").read().endswith("</html>")
    print("  htmlview OK: 전체 문서(오프라인)·파일 저장")


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
