"""읽기 전용 화면을 **오프라인 단일 HTML**로 렌더하는 공용 빌더(헤드리스).

목적(브랜치 `claude/ux-html-views`): tkinter로만 보여주던 읽기 전용 결과 화면
(값 확인 취합 스냅샷 · 이력 diff · Commonality 결과 · 요약 대시보드)을 **브라우저가
렌더하는 HTML로도 볼 수 있게** 한다. tkinter 렌더 렉을 피하고 인쇄·공유가 쉬워진다.

경계(반드시 지킬 것)
--------------------
- **읽기 전용·한 방향**: 파이썬이 데이터를 계산 → 로컬 HTML 파일로 저장 → 브라우저로
  연다. 브라우저에서 되쓰기(편집 저장)는 하지 않는다(서버/브리지 = 보안상 금지).
  편집이 필요한 화면(값 확인 비고·색상, 특이사항/참고자료/장비IP, 양식 편집)은
  tkinter 그대로 두고, 여기서는 **'HTML로 보기' 스냅샷만** 추가한다.
- **오프라인 단일 파일**: 외부 CDN·스크립트·폰트 금지. CSS는 인라인, 차트는 인라인 SVG.
- **텍스트 이스케이프**: 원본 문자열(파라미터명·비고·상태 등)은 `esc()` 로 반드시 이스케이프.
- **산출물은 로컬만**(`localdirs`). 저장폴더(OneDrive)에 쓰지 않는다.
- 추가 패키지 없음(stdlib 문자열 조립만). 기존 `wph_html` 과 같은 원칙.

헤드리스 · 테스트됨(`tests/test_htmlview.py`).
"""

from __future__ import annotations

import html as _html
from datetime import datetime

# 네이비(구조) + 라임(강조) + 미니멀. 결과 리포트/대시보드 공통 톤.
PAGE_CSS = """
:root{--navy:#0f1e3d;--navy2:#1b345f;--lime:#a3e635;--lime2:#84cc16;
--ink:#10203a;--muted:#54627a;--faint:#8592a4;--line:#e0e5ee;--line2:#eef1f6;
--bg:#f4f6fa;--paper:#fff;--band:#f6f8fc;--ok:#2f7d32;--warn:#b45309;--bad:#c0392b;
--okbg:#e7f3d8;--warnbg:#fdf1d8;--badbg:#fbe6e3;--limebg:#eef7cf;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:14px/1.65 "Malgun Gothic","맑은 고딕","Segoe UI",system-ui,sans-serif}
.wrap{max-width:1160px;margin:0 auto;padding:0 18px 64px}
header{background:var(--navy);color:#fff;padding:30px max(18px,calc((100% - 1160px)/2)) 24px;
border-bottom:4px solid var(--lime)}
header .kick{color:var(--lime);font-size:12px;font-weight:700;letter-spacing:2px}
header h1{margin:8px 0 2px;font-size:26px;font-weight:800;letter-spacing:-.01em}
header .sub{color:#c4d0e6;font-size:13px}
header .meta{margin-top:14px;display:flex;flex-wrap:wrap;gap:8px 22px;font-size:12.5px;color:#c4d0e6}
header .meta b{color:#fff;font-weight:600;margin-right:5px}
section{background:var(--paper);border:1px solid var(--line);border-radius:12px;
padding:16px 18px;margin:16px 0}
section>h2{margin:0 0 12px;font-size:16px;font-weight:800;display:flex;align-items:center;gap:9px}
section>h2::before{content:"";width:4px;height:16px;background:var(--lime);border-radius:2px;display:inline-block}
.tag{font-size:11px;font-weight:700;color:#fff;background:var(--navy2);border-radius:999px;padding:2px 9px}
.tag.lime{background:var(--lime);color:var(--navy)}
.tag.bad{background:var(--bad)}.tag.warn{background:var(--warn)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:14px 0}
.card{background:var(--paper);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.card .k{color:var(--muted);font-size:12px}
.card .v{font-size:26px;font-weight:800;margin-top:4px;color:var(--navy2)}
.card .u{color:var(--faint);font-size:12px;margin-left:4px;font-weight:500}
.scroll{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{padding:7px 10px;border-bottom:1px solid var(--line);text-align:left;
vertical-align:top;white-space:nowrap}
thead th{background:var(--navy);color:#fff;font-weight:600;position:sticky;top:0}
tbody tr:nth-child(even){background:var(--band)}
tfoot td{font-weight:700;background:var(--band)}
td.num,th.num{text-align:right}
td.c,th.c{text-align:center}
.grp td{background:var(--limebg);font-weight:700;color:var(--navy)}
.chg{background:var(--warnbg)}.add{background:var(--okbg)}.del{background:var(--badbg)}
.pill{display:inline-block;font-size:11px;padding:1px 8px;border-radius:999px}
.pill.ok{color:var(--ok);background:var(--okbg)}
.pill.warn{color:var(--warn);background:var(--warnbg)}
.pill.bad{color:var(--bad);background:var(--badbg)}
.note{color:var(--muted);font-size:12.5px;margin-top:10px}
.empty{color:var(--faint);padding:22px;text-align:center}
footer{color:var(--faint);font-size:12px;text-align:center;margin-top:26px}
@media print{body{background:#fff}header{background:#fff;color:var(--ink);border-bottom:3px solid var(--navy)}
header .kick,header .sub,header .meta,header .meta b{color:var(--muted)}
header .meta b{color:var(--ink)}section{border:0;border-radius:0;padding:12px 0;break-inside:auto}
thead th{background:#e9edf4;color:var(--ink)}tr,.card,.note{break-inside:avoid}thead{display:table-header-group}}
"""


def esc(x) -> str:
    """어떤 값이든 안전하게 HTML 이스케이프(None→'')."""
    return _html.escape("" if x is None else str(x))


def _cls(name: str) -> str:
    return f' class="{name}"' if name else ""


def kpi_cards(cards) -> str:
    """[(라벨, 값, 단위)] → KPI 카드 묶음."""
    if not cards:
        return ""
    cells = []
    for c in cards:
        label, value = c[0], c[1]
        unit = c[2] if len(c) > 2 else ""
        u = f'<span class="u">{esc(unit)}</span>' if unit else ""
        cells.append(f'<div class="card"><div class="k">{esc(label)}</div>'
                     f'<div class="v">{esc(value)}{u}</div></div>')
    return '<div class="cards">' + "".join(cells) + "</div>"


def table(headers, rows, *, aligns=None, foot=None, row_class=None) -> str:
    """표 하나. headers=[str], rows=[[cell,...]]. aligns=['num'|'c'|''..] 열 정렬.
    row_class(row_index, row)→css 클래스(diff 색칠 등). 셀은 전부 이스케이프."""
    aligns = aligns or []

    def _al(i):
        return aligns[i] if i < len(aligns) else ""

    head = "".join(f"<th{_cls(_al(i))}>{esc(h)}</th>" for i, h in enumerate(headers))
    body_rows = []
    for ri, r in enumerate(rows):
        rc = row_class(ri, r) if row_class else ""
        tds = "".join(f"<td{_cls(_al(i))}>{esc(v)}</td>" for i, v in enumerate(r))
        body_rows.append(f"<tr{_cls(rc)}>{tds}</tr>")
    tf = ""
    if foot:
        tf = "<tfoot><tr>" + "".join(
            f"<td{_cls(_al(i))}>{esc(v)}</td>" for i, v in enumerate(foot)) + "</tr></tfoot>"
    body = "".join(body_rows) or (
        f'<tr><td class="empty" colspan="{max(1, len(headers))}">내용이 없습니다.</td></tr>')
    return (f'<div class="scroll"><table><thead><tr>{head}</tr></thead>'
            f'<tbody>{body}</tbody>{tf}</table></div>')


def section(title, body_html, *, tag="", note="") -> str:
    """제목(라임 바) + 본문 카드. tag=(라벨, css) 배지 옵션, note=하단 회색 설명."""
    t = ""
    if tag:
        if isinstance(tag, (list, tuple)):
            label, cls = tag[0], (tag[1] if len(tag) > 1 else "")
        else:
            label, cls = tag, ""
        t = f' <span class="tag {cls}">{esc(label)}</span>'
    n = f'<div class="note">{esc(note)}</div>' if note else ""
    return f"<section><h2>{esc(title)}{t}</h2>{body_html}{n}</section>"


def page(title, sections_html, *, subtitle="", meta=None, kicker="CAMTEK AOI MANAGER",
         footer="Para — 읽기 전용 보기(오프라인). 편집은 프로그램에서.") -> str:
    """전체 문서. sections_html=문자열(여러 section 이어붙임). meta={라벨:값}."""
    meta = meta or {}
    mrow = ""
    if meta:
        mrow = '<div class="meta">' + "".join(
            f"<div><b>{esc(k)}</b>{esc(v)}</div>" for k, v in meta.items()) + "</div>"
    sub = f'<div class="sub">{esc(subtitle)}</div>' if subtitle else ""
    return (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{esc(title)}</title><style>{PAGE_CSS}</style></head><body>"
        f'<header><div class="kick">{esc(kicker)}</div>'
        f"<h1>{esc(title)}</h1>{sub}{mrow}</header>"
        f'<div class="wrap">{sections_html}'
        f"<footer>{esc(footer)}</footer></div></body></html>")


def write(path, html_text) -> str:
    """HTML 문자열을 로컬 파일로 저장(utf-8). 경로는 호출측이 localdirs 로 정한다."""
    from pathlib import Path
    Path(path).write_text(html_text, encoding="utf-8")
    return str(path)


def stamp_now() -> str:
    """meta 표기용 현재 시각 문자열."""
    return datetime.now().strftime("%Y-%m-%d %H:%M")
