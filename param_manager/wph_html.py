"""WPH 조사 결과를 **.html 리포트**로 만든다(헤드리스, 파일/네트워크 추가 접근 없음).

역할
----
`wph.investigate` 가 이미 파싱한 행(rows)과 오류(errors)만 받아서

  · WPH 요약(전체 합산) · 호기·레시피별 WPH
  · 에러 ① 전체 분류 · ② 호기별 · ③ 호기별→레시피별
  · Wafer scan 상태 요약(정상 / error / 확인불가)
  · Report 목록(원자료) · 파싱오류

를 **선택(sections dict)** 해서 단일 .html 로 만든다. recipe 는 A안(리포트 내부
Job/Setup 의 Job 이름, `wph.extract_row` 가 채운 `recipe`)을 쓴다.

- **원본 read-only·산출물 로컬만**: 이 모듈은 파일을 **읽지도** 않는다. 이미 메모리에
  있는 rows/errors 만 가공한다. 결과 .html 은 호출측이 로컬 조사 폴더에 저장한다.
- 에러 분류·집계 규칙은 `wph_status` 와 동일(같은 `classify` 재사용).
- `compute()` 가 낸 표는 GUI(tksheet) 미리보기와 .html 이 **같은 숫자**를 쓰도록
  `preview_tables()` 로도 돌려준다.

헤드리스 · 테스트됨(`tests/test_wph_html.py`).
"""

from __future__ import annotations

import html as _html
from collections import Counter, OrderedDict

from . import wph_status

# 섹션 키 → 화면/HTML 제목. 순서가 곧 표시 순서.
SECTION_TITLES = OrderedDict([
    ("wph_summary", "WPH 요약 (전체 합산)"),
    ("wph_by_recipe", "호기 · 레시피별 WPH"),
    ("scan_status", "Wafer scan 상태 요약"),
    ("err_overall", "에러 ① 전체 에러 분류"),
    ("err_by_machine", "에러 ② 호기별 에러 분류"),
    ("err_by_recipe", "에러 ③ 호기별 → 레시피별 에러 분류"),
    ("raw", "Report 목록 (원자료)"),
    ("parse_errors", "파싱오류 (읽지 못한 Report)"),
])

# scan 상태 3분류 표기(사용자 지정: 정상 / error / 확인불가)
STATE_NORMAL, STATE_ERROR, STATE_UNKNOWN = "정상", "error", "확인불가"


def default_sections(errors=None) -> dict:
    """기본 = 전부 켜짐. 파싱오류는 실제 오류가 있을 때만 기본 켜짐."""
    s = {k: True for k in SECTION_TITLES}
    s["parse_errors"] = bool(errors)
    return s


# ---------------------------------------------------------------------------
#  숫자/시간 포맷
# ---------------------------------------------------------------------------
def _wph(wafers, batch_sec):
    try:
        return wafers * 3600.0 / batch_sec if batch_sec else None
    except (TypeError, ZeroDivisionError):
        return None


def _hms(sec):
    try:
        sec = int(round(float(sec)))
    except (TypeError, ValueError):
        return ""
    return f"{sec // 3600:d}:{(sec % 3600) // 60:02d}:{sec % 60:02d}"


def _f1(x):
    return "" if x is None else f"{x:.1f}"


def _is_valid(row, valid_wafers):
    return (row.get("wafers") == valid_wafers
            and (row.get("avg_scan_sec") or 0) > 0
            and (row.get("batch_sec") or 0) > 0)


# ---------------------------------------------------------------------------
#  에러 집계 (wph_status.classify 재사용, 그룹만 추가)
# ---------------------------------------------------------------------------
def _tally(rows, keyfn):
    """rows → {group_key: {(category,original): [report수, wafer수]}}.

    wph_status.analyze 와 같은 규칙: 리포트당 카테고리 1회(report), wafer 는 발생 수.
    '상태 확인 불가' 의 wafer 수는 리포트에 wafer 표가 있을 때만 센다.
    """
    out: "OrderedDict[object, dict]" = OrderedDict()
    for row in rows:
        statuses = row.get("wafer_statuses") or [{"status": "", "slot": "", "wafer_id": ""}]
        occ = Counter()
        for st in statuses:
            for cat, orig in wph_status.classify(st.get("status")):
                occ[(cat, orig)] += 1
        if not occ:
            continue
        bucket = out.setdefault(keyfn(row), OrderedDict())
        has_table = bool(row.get("wafer_statuses"))
        for key, n in occ.items():
            tally = bucket.setdefault(key, [0, 0])
            tally[0] += 1
            tally[1] += n if (key[0] != "상태 확인 불가" or has_table) else 0
    return out


def _issue_report_total(rows, keyfn=None):
    """이슈 Report 수(중복 제외) — 한 리포트에 이슈가 여럿이어도 1로 센다."""
    if keyfn is None:
        n = 0
        for row in rows:
            statuses = row.get("wafer_statuses") or []
            if any(k[0] != "상태 확인 불가"
                   for st in statuses for k in wph_status.classify(st.get("status"))):
                n += 1
        return n
    counts = Counter()
    for row in rows:
        statuses = row.get("wafer_statuses") or []
        if any(k[0] != "상태 확인 불가"
               for st in statuses for k in wph_status.classify(st.get("status"))):
            counts[keyfn(row)] += 1
    return counts


def _machine(row):
    return row.get("machine", "") or "(미상)"


def _mrec(row):
    return (row.get("machine", "") or "(미상)", row.get("recipe", "") or "(미상)")


# ---------------------------------------------------------------------------
#  compute — 화면/HTML 공용 데이터
# ---------------------------------------------------------------------------
def compute(rows, errors=None, *, valid_wafers=25) -> dict:
    """rows/errors → 모든 섹션의 표 데이터(딕셔너리). 렌더러·미리보기 공용."""
    errors = errors or []
    valid = [r for r in rows if _is_valid(r, valid_wafers)]

    # 전체 합산
    tot_wafer = sum(r["wafers"] for r in valid)
    tot_batch = sum(r["batch_sec"] for r in valid)
    cum = (tot_wafer / (tot_batch / 3600.0)) if tot_batch else 0.0
    per = [_wph(r["wafers"], r["batch_sec"]) for r in valid]
    avg = sum(per) / len(per) if per else 0.0
    no_time = sum(1 for r in valid if not r.get("batch_end"))
    summary = {
        "valid_lots": len(valid), "total_wafer": tot_wafer,
        "cum_wph": cum, "avg_wph": avg, "no_time": no_time,
        "valid_wafers": valid_wafers, "report_count": len(rows),
    }

    # 호기·레시피별 WPH (valid 기준)
    def _grp(keyfn):
        g = OrderedDict()
        for r in valid:
            k = keyfn(r)
            b = g.setdefault(k, {"lots": 0, "wafer": 0, "batch": 0, "per": []})
            b["lots"] += 1
            b["wafer"] += r["wafers"]
            b["batch"] += r["batch_sec"]
            b["per"].append(_wph(r["wafers"], r["batch_sec"]))
        rows_out = []
        for k, b in g.items():
            cwph = b["wafer"] / (b["batch"] / 3600.0) if b["batch"] else 0.0
            awph = sum(b["per"]) / len(b["per"]) if b["per"] else 0.0
            rows_out.append({"key": k, "lots": b["lots"], "wafer": b["wafer"],
                             "cum_wph": cwph, "avg_wph": awph})
        return rows_out
    wph_by_machine = _grp(_machine)
    wph_by_recipe = _grp(_mrec)

    # scan 상태 요약(정상/error/확인불가) — 리포트 단위
    st = Counter()
    for row in rows:
        statuses = row.get("wafer_statuses") or []
        cats = [k for stt in statuses for k in wph_status.classify(stt.get("status"))]
        if any(c[0] != "상태 확인 불가" for c in cats):
            st[STATE_ERROR] += 1
        elif cats:
            st[STATE_UNKNOWN] += 1
        else:
            st[STATE_NORMAL] += 1
    scan_status = {"normal": st[STATE_NORMAL], "error": st[STATE_ERROR],
                   "unknown": st[STATE_UNKNOWN], "total": len(rows)}

    # 에러 ①②③
    err_overall = _tally(rows, lambda _r: "전체")
    err_by_machine = _tally(rows, _machine)
    err_by_recipe = _tally(rows, _mrec)
    issue_total = _issue_report_total(rows)

    return {
        "summary": summary,
        "wph_by_machine": wph_by_machine,
        "wph_by_recipe": wph_by_recipe,
        "scan_status": scan_status,
        "err_overall": err_overall.get("전체", OrderedDict()),
        "err_by_machine": err_by_machine,
        "err_by_recipe": err_by_recipe,
        "issue_report_total": issue_total,
        "rows": rows,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
#  preview_tables — GUI(tksheet) 미리보기용 표
# ---------------------------------------------------------------------------
def preview_tables(computed, sections, *, by_recipe=True) -> list:
    """[(제목, [헤더...], [[셀...]...])] — 선택 섹션만. .html 과 같은 숫자."""
    c, out = computed, []
    s = computed["summary"]

    if sections.get("wph_summary"):
        out.append(("WPH 요약 (전체 합산)", ["항목", "값"], [
            [f"유효 {s['valid_wafers']}매 Lot", f"{s['valid_lots']} 건"],
            ["총 Wafer", f"{s['total_wafer']} 매"],
            ["누적 WPH", _f1(s["cum_wph"])],
            ["평균 WPH", _f1(s["avg_wph"])],
            ["제외(시간 미확인)", f"{s['no_time']} 건"],
        ]))
    if sections.get("wph_by_recipe"):
        grp = c["wph_by_recipe"] if by_recipe else c["wph_by_machine"]
        hdr = (["호기", "Recipe", "유효 Lot", "총 Wafer", "누적 WPH", "평균 WPH"]
               if by_recipe else ["호기", "유효 Lot", "총 Wafer", "누적 WPH", "평균 WPH"])
        body = []
        for r in grp:
            k = r["key"]
            base = list(k) if by_recipe else [k]
            body.append(base + [r["lots"], r["wafer"], _f1(r["cum_wph"]), _f1(r["avg_wph"])])
        out.append(("호기 · 레시피별 WPH" if by_recipe else "호기별 WPH", hdr, body))
    if sections.get("scan_status"):
        ss = c["scan_status"]
        out.append(("Wafer scan 상태 요약", ["상태", "Report 수"], [
            [STATE_NORMAL, ss["normal"]], [STATE_ERROR, ss["error"]],
            [STATE_UNKNOWN, ss["unknown"]], ["합계", ss["total"]],
        ]))
    if sections.get("err_overall"):
        body = [[cat, orig, v[0], v[1]] for (cat, orig), v in c["err_overall"].items()]
        body.append(["이슈 Report 합계(중복 제외)", "", c["issue_report_total"], ""])
        out.append(("에러 ① 전체 에러 분류", ["분류", "원문", "Report", "Wafer"], body))
    if sections.get("err_by_machine"):
        body = []
        for m, d in c["err_by_machine"].items():
            for (cat, orig), v in d.items():
                body.append([m, cat, v[0], v[1]])
        out.append(("에러 ② 호기별", ["호기", "분류", "Report", "Wafer"], body))
    if sections.get("err_by_recipe"):
        body = []
        for (m, rec), d in c["err_by_recipe"].items():
            for (cat, orig), v in d.items():
                body.append([m, rec, cat, v[0], v[1]])
        out.append(("에러 ③ 호기별 → 레시피별", ["호기", "Recipe", "분류", "Report", "Wafer"], body))
    if sections.get("raw"):
        body = []
        for i, r in enumerate(c["rows"], start=1):
            end = r.get("batch_end")
            body.append([i, r.get("machine", ""), r.get("recipe", ""),
                         r.get("wafers", ""), _hms(r.get("avg_scan_sec")),
                         _hms(r.get("batch_sec")), _f1(_wph(r.get("wafers"), r.get("batch_sec"))),
                         end.strftime("%Y-%m-%d %H:%M") if end else (r.get("batch_end_raw") or "")])
        out.append(("Report 목록", ["No", "호기", "Recipe", "Wafers", "Avg Scan",
                                   "Batch", "Actual WPH", "Batch End"], body))
    if sections.get("parse_errors") and c["errors"]:
        out.append(("파싱오류", ["파일", "사유"], [[n, m] for n, m in c["errors"]]))
    return out


# ---------------------------------------------------------------------------
#  HTML 렌더
# ---------------------------------------------------------------------------
def _esc(x):
    return _html.escape("" if x is None else str(x))


_CSS = """
:root{--bg:#f4f6f9;--card:#fff;--ink:#1f2a37;--muted:#6b7280;--line:#e3e8ef;
--head:#17365d;--band:#f0f4fa;--green:#2e7d32;--greenbg:#e2f0d9;--bad:#b91c1c;
--badbg:#fee2e2;--warn:#b45309;--warnbg:#fef3c7;--bar:#2f6fdb}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:14px/1.5 "Segoe UI","Malgun Gothic",system-ui,sans-serif}
.wrap{max-width:1120px;margin:0 auto;padding:20px 18px 60px}
h1{font-size:22px;margin:6px 0 2px}.sub{color:var(--muted);font-size:13px;margin-bottom:16px}
.meta{display:flex;flex-wrap:wrap;gap:8px 20px;background:var(--card);border:1px solid var(--line);
border-radius:10px;padding:12px 16px;margin-bottom:18px}
.meta b{color:var(--muted);font-weight:600;margin-right:6px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:22px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.card .k{color:var(--muted);font-size:12px}.card .v{font-size:26px;font-weight:700;margin-top:4px}
.card .u{color:var(--muted);font-size:12px;margin-left:4px;font-weight:500}
section{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin-bottom:18px}
section>h2{font-size:15px;margin:0 0 12px;display:flex;align-items:center;gap:8px}
.tag{font-size:11px;color:#fff;background:var(--head);border-radius:999px;padding:2px 9px;font-weight:600}
.tag.e{background:var(--bad)}.tag.w{background:var(--warn)}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{padding:7px 10px;text-align:right;border-bottom:1px solid var(--line);white-space:nowrap}
th:first-child,td:first-child,th.l,td.l{text-align:left}
thead th{background:var(--head);color:#fff;font-weight:600}
tbody tr:nth-child(even){background:var(--band)}
tfoot td{font-weight:700;background:var(--band)}
.mach{font-weight:700}.rec{color:var(--muted)}
.scroll{overflow-x:auto}
.pill{display:inline-block;font-size:11px;padding:1px 8px;border-radius:999px}
.ok{color:var(--green);background:var(--greenbg)}.badp{color:var(--bad);background:var(--badbg)}
.warnp{color:var(--warn);background:var(--warnbg)}
.note{color:var(--muted);font-size:12px;margin-top:10px}
footer{color:var(--muted);font-size:12px;text-align:center;margin-top:8px}
"""


def _table(headers, body, *, foot=None, firstcols_left=1):
    def cell(tag, v, i):
        cls = ' class="l"' if i < firstcols_left else ""
        return f"<{tag}{cls}>{_esc(v)}</{tag}>"
    h = "".join(cell("th", v, i) for i, v in enumerate(headers))
    rows = "".join("<tr>" + "".join(cell("td", v, i) for i, v in enumerate(r)) + "</tr>"
                   for r in body)
    tf = ""
    if foot:
        tf = "<tfoot><tr>" + "".join(cell("td", v, i) for i, v in enumerate(foot)) + "</tr></tfoot>"
    return (f'<div class="scroll"><table><thead><tr>{h}</tr></thead>'
            f'<tbody>{rows}</tbody>{tf}</table></div>')


def build_html(computed, *, title, meta=None, sections=None, by_recipe=True) -> str:
    """compute() 결과 → 선택 섹션만 담은 .html 문자열."""
    sections = sections or default_sections(computed.get("errors"))
    meta = meta or {}
    s = computed["summary"]
    parts = [f'<!doctype html><html lang="ko"><head><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width, initial-scale=1">',
             f"<title>{_esc(title)}</title><style>{_CSS}</style></head><body><div class='wrap'>",
             f"<h1>{_esc(title)}</h1>",
             "<div class='sub'>Wafers Per Hour · batch report 취합 결과</div>"]

    if meta:
        parts.append("<div class='meta'>"
                     + "".join(f"<div><b>{_esc(k)}</b>{_esc(v)}</div>" for k, v in meta.items())
                     + "</div>")

    if sections.get("wph_summary"):
        cards = [("유효 %d매 Lot" % s["valid_wafers"], s["valid_lots"], "건"),
                 ("총 Wafer", s["total_wafer"], "매"),
                 ("누적 WPH", _f1(s["cum_wph"]), "WPH"),
                 ("평균 WPH", _f1(s["avg_wph"]), "WPH"),
                 ("제외(시간 미확인)", s["no_time"], "건")]
        parts.append("<div class='cards'>" + "".join(
            f"<div class='card'><div class='k'>{_esc(k)}</div>"
            f"<div class='v'>{_esc(v)}<span class='u'>{_esc(u)}</span></div></div>"
            for k, v, u in cards) + "</div>")

    if sections.get("wph_by_recipe"):
        grp = computed["wph_by_recipe"] if by_recipe else computed["wph_by_machine"]
        if by_recipe:
            hdr = ["호기", "Recipe", "유효 Lot", "총 Wafer", "누적 WPH", "평균 WPH"]
            body = [[k[0], k[1], r["lots"], r["wafer"], _f1(r["cum_wph"]), _f1(r["avg_wph"])]
                    for r in grp for k in [r["key"]]]
            left = 2
        else:
            hdr = ["호기", "유효 Lot", "총 Wafer", "누적 WPH", "평균 WPH"]
            body = [[r["key"], r["lots"], r["wafer"], _f1(r["cum_wph"]), _f1(r["avg_wph"])]
                    for r in grp]
            left = 1
        parts.append("<section><h2><span class='tag'>요약</span> "
                     + ("호기 · 레시피별 WPH" if by_recipe else "호기별 WPH") + "</h2>"
                     + _table(hdr, body, firstcols_left=left)
                     + ("<div class='note'>여러 호기 선택 시 호기로 먼저 묶고 그 안에서 "
                        "recipe별로 나눕니다.</div>" if by_recipe else "") + "</section>")

    if sections.get("scan_status"):
        ss = computed["scan_status"]
        body = [[STATE_NORMAL, ss["normal"]], [STATE_ERROR, ss["error"]],
                [STATE_UNKNOWN, ss["unknown"]]]
        parts.append("<section><h2><span class='tag'>상태</span> Wafer scan 상태 요약</h2>"
                     + _table(["상태", "Report 수"], body,
                              foot=["합계", ss["total"]]) + "</section>")

    if sections.get("err_overall"):
        body = [[cat, orig, v[0], v[1]] for (cat, orig), v in computed["err_overall"].items()]
        parts.append("<section><h2><span class='tag e'>에러 ①</span> 전체 에러 분류</h2>"
                     + _table(["에러 분류", "상태 원문", "Report 수", "Wafer 수"], body,
                              foot=["이슈 Report 합계(중복 제외)", "",
                                    computed["issue_report_total"], ""], firstcols_left=2)
                     + "<div class='note'>분류·원문은 07_상태요약/09_상태상세와 동일. "
                       "유형별 Report는 중복 허용, 이슈 Report 합계는 중복 제외.</div></section>")

    if sections.get("err_by_machine"):
        body = [[m, cat, v[0], v[1]] for m, d in computed["err_by_machine"].items()
                for (cat, orig), v in d.items()]
        parts.append("<section><h2><span class='tag e'>에러 ②</span> 호기별 에러 분류</h2>"
                     + _table(["호기", "에러 분류", "Report 수", "Wafer 수"], body,
                              firstcols_left=2) + "</section>")

    if sections.get("err_by_recipe"):
        body = [[m, rec, cat, v[0], v[1]] for (m, rec), d in computed["err_by_recipe"].items()
                for (cat, orig), v in d.items()]
        parts.append("<section><h2><span class='tag e'>에러 ③</span> 호기별 → 레시피별 "
                     "에러 분류</h2>"
                     + _table(["호기", "Recipe", "에러 분류", "Report 수", "Wafer 수"], body,
                              firstcols_left=3) + "</section>")

    if sections.get("raw"):
        body = []
        for i, r in enumerate(computed["rows"], start=1):
            end = r.get("batch_end")
            body.append([i, r.get("machine", ""), r.get("recipe", ""), r.get("wafers", ""),
                         _hms(r.get("avg_scan_sec")), _hms(r.get("batch_sec")),
                         _f1(_wph(r.get("wafers"), r.get("batch_sec"))),
                         end.strftime("%Y-%m-%d %H:%M") if end else (r.get("batch_end_raw") or "")])
        parts.append("<section><h2><span class='tag'>원자료</span> Report 목록</h2>"
                     + _table(["No", "호기", "Recipe", "Wafers", "Avg Scan", "Batch",
                               "Actual WPH", "Batch End (생성일자)"], body, firstcols_left=3)
                     + "</section>")

    if sections.get("parse_errors") and computed["errors"]:
        parts.append("<section><h2><span class='tag w'>파싱오류</span> 읽지 못한 Report</h2>"
                     + _table(["파일", "사유"], [[n, m] for n, m in computed["errors"]],
                              firstcols_left=2) + "</section>")

    parts.append("<footer>같은 조사 폴더의 WPH_통합.xlsx · 호기별 취합.txt 와 함께 생성. "
                 "원본 batch report는 읽기 전용.</footer></div></body></html>")
    return "".join(parts)


def write_html(path, computed, *, title, meta=None, sections=None, by_recipe=True) -> str:
    from pathlib import Path
    Path(path).write_text(
        build_html(computed, title=title, meta=meta, sections=sections, by_recipe=by_recipe),
        encoding="utf-8")
    return str(path)
