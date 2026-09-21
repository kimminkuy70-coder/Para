"""Local, self-contained HTML/SVG and native Excel charts from shared tables."""
from __future__ import annotations

import html
import math
import os
import tempfile
from datetime import datetime
from pathlib import Path

NOTES = [
    "스캔 가동률은 선택·누적 Report의 Batch Time / 달력시간 proxy입니다. OEE가 아니며 대기·PM·전원 OFF를 구분하지 않습니다.",
    "Batch Start 기간에 스캔시간 전체를 귀속합니다. 진행 중 주·월은 기간 시작~마지막 데이터 시각을 분모로 사용합니다. 100% 초과와 음수 유휴는 숨기지 않습니다.",
    "원본에서 사라진 Report도 현재 검색 조건에 맞으면 로컬 누적 자료에 포함합니다. 연결 실패·선택 자료만 있는 기간은 완전한 설비 이력으로 볼 수 없습니다.",
    "Aborted는 원본 순서상 첫 이슈(첫 Aborted 포함) 이후를 연쇄로 추정합니다. Skipped·빈 상태는 트리거에서 제외합니다. 실제 원인/작업자 조치를 확정하지 않습니다.",
    "재시작 간격은 같은 호기·전체 Job/Setup의 다음 시작 - 이슈 배치 종료입니다. 0~1440분만 baseline에 포함하며 실제 수리시간이 아닙니다.",
    "품질 이상은 이전 배치의 정상 Pass 분포와 비교한 wafer 후보입니다. 최소 표본/수율 하락 기준은 조사 설정이며 인증된 Hold 기준이 아닙니다. 자동 제어는 하지 않습니다.",
    "오류 한 행에 여러 상태가 있을 수 있어 유형별 합계는 전체 Report 수보다 클 수 있습니다. 빈 상태는 확인 불가로 별도 표시합니다.",
    "원본값은 HTML에서 이스케이프하고 Excel에서 텍스트로 저장합니다. 외부 스크립트·서버·인터넷 요청을 사용하지 않습니다.",
]

# Section label, one-line purpose, and interpretation notes per metric key.
METRIC_NAME = {
    "M01": "처리량 (WPH)", "M02": "스캔 가동률 · 유휴", "M03": "오류 유형별 빈도",
    "M04": "Error 성격 분류", "M05": "Aborted 왜곡 보정", "M06": "재시작 간격",
    "M07": "복구 baseline", "M08": "Recipe별 정상 Dice 통계", "M09": "품질 이상 후보",
    "M10": "Lot 스캔 이슈율", "M11": "미분류 상태 포착",
}
PURPOSE = {
    "M01": "유효 Lot(설정 매수 충족)만으로 산출한 실제 처리량 — 호기·Recipe 비교와 시간 추이.",
    "M02": "선택·누적 Report의 스캔시간 ÷ 달력시간 proxy. OEE가 아닌 상대 비교용. 일/주/월 전환.",
    "M03": "어떤 오류부터 대응하면 효과가 큰지 우선순위 — 발생 Wafer·Report·Lot 수를 함께 표시.",
    "M04": "자동화 방식 결정: 예방형(반자동 사전검증) vs 조치형(Auto Setup 후보). Wafer·Report·Lot 기준.",
    "M05": "작업 중단 이후 연쇄로 표기되는 Aborted를 분리해 실제 직접 중단 규모(Wafer·Lot) 파악.",
    "M06": "이슈가 난 리포트 종료 → 같은 lot의 다음 리포트 시작까지 간격(재스캔 지연). 유형별 소요 비교(실측 아님).",
    "M07": "재시작 간격의 대표값(복구 baseline proxy). 개선 전후 비교 기준선.",
    "M08": "정상(Pass) wafer의 Recipe(Job/Setup)별 Scanned·Bad·Good Dice 통계 — 자동 Hold 임계치 근거.",
    "M09": "과거 정상 분포 대비 튀는 wafer 후보. 참고용이며 자동 제어에 쓰지 않음.",
    "M10": "Lot(=Job/Setup+Lot) 단위로 스캔 중 이슈·재스캔이 있었는지, 전체 Lot 중 문제 Lot 비중.",
    "M11": "사전 정의 목록에 없는 상태 문구를 자동 포착해 누락 방지.",
}
INTERPRET = {
    "M01": [("teal", "읽는 법", "합산 WPH는 웨이퍼를 batch time 총합으로 나눈 가중 처리량, 평균 WPH는 배치별 WPH의 산술평균입니다."),
            ("navy", "유효 스캔 = 무에러 완전 lot", "유효 스캔 수는 Wafers Scanned가 설정 매수(예: 25)와 정확히 같고 Batch Time>0 인 리포트만 셉니다. 스캔 에러가 있으면 Wafers Scanned가 그만큼 줄어 25 미만이 되므로 **에러 lot은 자동으로 빠집니다**(실데이터 158건 전부 무에러). 한 리포트=한 lot의 완전 스캔이라 사실상 '무에러 완전 lot 수'입니다.")],
    "M02": [("navy", "용어 설명", "· 스캔 시간(h): batch report의 Batch Time(스캔 시작~끝) 합 = 이 장비가 실제로 웨이퍼를 검사한 시간. 자정을 넘긴 배치는 걸친 날짜에 나눠 담습니다. · 기간 길이(h): 보는 단위의 달력 시간(일=24h, 주=168h, 진행 중 기간은 시작~현재). · 가동률(%): 스캔 시간 ÷ 기간 길이 ×100. 100%면 그 기간 내내 쉼 없이 스캔. · 비스캔 시간(h): 기간 길이 − 스캔 시간. · Batch 수: 그 기간에 '시작한' 배치 수 — 전날 시작해 자정을 넘어온 배치의 스캔 시간도 이 날에 잡히므로, Batch 수는 적어도 스캔 시간이 클 수 있습니다(예: 하루 2배치인데 앞 배치가 밤새 돌면 가동률이 99%까지 나옵니다)."),
            ("amber", "주의 — OEE가 아닙니다", "스캔 안 한 나머지 시간이 '대기'인지 'PM(정비)'인지 '전원 OFF'인지 '셋업'인지 batch report만으로는 구분할 수 없어, 그 전부를 비스캔으로 묶습니다. 그래서 진짜 설비효율(OEE)이 아니라 '그 기간에 몇 %를 스캔에 썼나'라는 스캔 점유율 근사치이며, 절대값보다 호기끼리·기간끼리 상대 비교에 쓰세요. (드물게 리포트의 Batch Time이 실제 경과보다 길면 가동률이 100%를 넘을 수 있고, 그 경우 기간 상태에 표시합니다.)")],
    "M03": [("teal", "읽는 법", "한 wafer에 여러 상태가 겹칠 수 있어 유형별 합계가 전체 Report 수보다 클 수 있습니다. Lot 수는 같은 (Job/Setup, Lot)이 재스캔으로 여러 리포트가 돼도 1로 셉니다. 막대 색은 성격별 묶음입니다.")],
    "M04": [("navy", "활용", "예방형은 반자동 사전검증으로, 조치형은 Auto Setup 후보로 분기해 대응 방식을 정합니다. 아래 표는 각 성격에 어떤 Error 유형이 묶이는지입니다.")],
    "M05": [("rust", "한계", "연쇄/직접 구분은 wafer 스캔 순서 기반 추정입니다. 장비 상세 Error Log가 연동되면 수동/자동 중단을 실측으로 구분해 신뢰도가 올라갑니다.")],
    "M06": [("rust", "한계", "간격은 배치 간 시각차 기반 proxy로 실제 수리시간이 아닙니다. 0~1440분만 집계에 포함합니다.")],
    "M07": [("slate", "참고", "baseline은 인증된 기준이 아니라 개선 추적용 대표값입니다.")],
    "M08": [("amber", "주의", "임계치 후보는 정상 분포의 P95 등 통계값입니다. 인증된 Hold 기준이 아니며 사람이 확인 후 적용하세요."),
            ("teal", "읽는 법", "Recipe = Job/Setup(예: 2D@R2-…-0B/Setup1). Good Dice = Scanned − Bad. 막대는 recipe별 정상 wafer의 Scanned/Bad/Good 평균입니다.")],
    "M09": [("rust", "한계", "이상 후보는 과거 정상 대비 상대 비교입니다. 자동 Hold·제어에 직접 쓰지 않습니다.")],
    "M10": [("teal", "읽는 법", "batch report에는 lot 기대 매수가 없어 '완주율'은 측정하지 않습니다(B안). 대신 lot마다 스캔 중 이슈가 있었는지와 재스캔(리포트≥2) 여부를 보고, 전체 lot 중 문제 lot 비중을 냅니다. 이슈 발생 Lot = 어느 리포트에서든 error/중단/skip이 있던 lot. 재스캔 Lot = 리포트가 2장 이상(중단 후 다시 스캔). 둘은 관련은 있지만 다릅니다 — 이슈인데 재스캔이 없는 lot(단발 에러)도, 이슈 표기 없이 나눠 스캔된 lot도 있습니다."),
            ("slate", "스캔 시도 1회 = ?", "'스캔 시도(리포트) 수'가 1인 문제 lot은 이 장비(현재 분석 호기)에서 한 번 스캔→에러→재스캔 기록이 없다는 뜻입니다. 그 웨이퍼는 다른 AOI로 넘어가 재검사됐을 가능성이 높습니다(이 분석은 호기 1대만 봅니다)."),
            ("navy", "활용", "'문제 Lot 상세'의 스캔 시도 수가 크거나 포함 이슈 유형이 반복되는 lot이 자동화·개선 1순위입니다. 포함 이슈 유형은 batch report 원문 그대로이며 유형마다 한 줄로 적습니다.")],
    "M11": [("navy", "활용", "새 문구가 잡히면 분류 규칙에 추가해 다음 실행부터 정상 집계되도록 하세요.")],
}
# Category-character grouping colours (M03/M04), abort/lot-issue colours.
BAR_BASE = "#347b9d"
CHAR_COLOR = {"예방형": "#0e5f5c", "조치형": "#b7791f", "중단": "#1f3a5f",
              "결과형": "#64748b", "미확인": "#c0392b", "Unclassified": "#c0392b"}
ISSUE_COLOR = {"이슈 발생 Lot": "#c0392b", "정상 Lot": "#0e5f5c", "재스캔(리포트≥2) Lot": "#b7791f"}
ABORT_COLOR = {"원본 Aborted": "#1f3a5f", "직접 추정": "#c0392b", "연쇄 추정": "#94a3b8"}
DICE_COLOR = {"Scanned 평균": "#1f3a5f", "Bad 평균": "#c0392b", "Good 평균": "#0e5f5c"}
CHAR_DESC = {
    "예방형": "장비를 세우진 않지만 사전 검증으로 막을 수 있는 유형(맵·Bin·판독 등). 반자동 사전검증 대상.",
    "조치형": "Focus·Align·Clean Reference처럼 자동 셋업 보정이 필요한 유형. Auto Setup 후보.",
    "중단": "스캔이 중단(Aborted)된 유형. 작업자·장비 중단 포함.",
    "결과형": "검사에서 제외(Skipped)된 유형. 스캔 자체를 안 함.",
    "미확인": "분류 규칙에 아직 없거나 상태를 확인할 수 없는 유형.",
}

PAGE_CSS = """
:root{--ink:#1b2430;--soft:#54606e;--faint:#8592a0;--line:#dde2e9;--line2:#eef1f5;
--bg:#eceff3;--paper:#fff;--navy:#1f3a5f;--teal:#0e5f5c;--amber:#b7791f;--rust:#c0392b;--slate:#64748b;
--navy-bg:#eef2f8;--teal-bg:#e6f1f0;--amber-bg:#f7efdd;--rust-bg:#fbeae8;--slate-bg:#eef1f5;}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"Malgun Gothic","맑은 고딕",-apple-system,"Segoe UI",sans-serif;color:var(--ink);background:var(--bg);font-size:14px;line-height:1.65}
.doc{max-width:1040px;margin:26px auto;background:var(--paper);box-shadow:0 2px 10px rgba(0,0,0,.10)}
.pad{padding:8px 42px 54px}
.head{border-top:6px solid var(--navy);padding:30px 42px 20px;border-bottom:2px solid var(--ink)}
.head .kick{font-size:12px;font-weight:700;color:var(--navy);letter-spacing:.05em;margin-bottom:8px}
.head h1{font-size:24px;font-weight:800;letter-spacing:-.02em}
.head h1 .draft{margin-left:8px;font-size:11px;font-weight:800;color:#fff;background:var(--amber);padding:2px 9px;border-radius:4px;vertical-align:middle}
.head .meta{margin-top:16px;display:flex;flex-wrap:wrap;gap:8px 18px;font-size:12.3px;color:var(--soft)}
.head .meta b{color:var(--ink)}
.head .job{font-family:Consolas,monospace;font-size:11.5px;background:#f1f3f6;color:var(--navy);padding:1px 7px;border-radius:4px}
h2{font-size:17px;font-weight:800;color:var(--navy);margin:34px 0 4px;padding-left:12px;border-left:5px solid var(--navy)}
h2 .mtag{font-size:12px;font-weight:700;color:var(--faint);margin-left:6px}
.sub{color:var(--soft);font-size:13px;margin:0 0 14px 14px}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:16px 0}
.kpi{border:1px solid var(--line);border-top:3px solid var(--navy);border-radius:6px;padding:15px 13px;text-align:center}
.kpi.t{border-top-color:var(--teal)}.kpi.a{border-top-color:var(--amber)}.kpi.r{border-top-color:var(--rust)}
.kpi .n{font-size:24px;font-weight:800;color:var(--navy);line-height:1.1}
.kpi.t .n{color:var(--teal)}.kpi.a .n{color:var(--amber)}.kpi.r .n{color:var(--rust)}
.kpi .l{font-size:11.5px;color:var(--soft);margin-top:6px;line-height:1.4}
.chartbox{border:1px solid var(--line);border-radius:8px;padding:16px 16px 12px;margin:12px 0;overflow-x:auto}
.chartbox .cap{font-size:12px;color:var(--faint);margin-bottom:10px}
.note{border:1px solid var(--line);border-left:3px solid var(--teal);background:var(--teal-bg);padding:11px 15px;border-radius:0 4px 4px 0;margin:12px 0;font-size:13px}
.note.amber{border-left-color:var(--amber);background:var(--amber-bg)}
.note.rust{border-left-color:var(--rust);background:var(--rust-bg)}
.note.navy{border-left-color:var(--navy);background:var(--navy-bg)}
.note.slate{border-left-color:var(--slate);background:var(--slate-bg)}
.note .t{font-weight:800;font-size:11.5px;display:block;margin-bottom:3px;color:var(--teal)}
.note.amber .t{color:var(--amber)}.note.rust .t{color:var(--rust)}.note.navy .t{color:var(--navy)}.note.slate .t{color:var(--slate)}
table{width:100%;border-collapse:collapse;margin:12px 0;font-size:13px}
th,td{border:1px solid var(--line);padding:8px 11px;text-align:left;vertical-align:top;overflow-wrap:anywhere}
thead th{background:var(--navy);color:#fff;font-weight:700;font-size:12px;position:sticky;top:0}
tbody tr:nth-child(even) td{background:#fafbfc}
table.sortable th{cursor:pointer;user-select:none;white-space:nowrap}
table.sortable th:hover{filter:brightness(1.3)}
table.sortable th[data-dir=asc]::after{content:" ▲";font-size:9px}
table.sortable th[data-dir=desc]::after{content:" ▼";font-size:9px}
svg{display:block;max-width:100%;height:auto;font-family:inherit}
svg text{font-size:12px;fill:var(--soft)}
svg .val{font-size:11px;font-weight:700;fill:var(--ink)}
.lgd{display:flex;flex-wrap:wrap;gap:14px;margin-top:10px;font-size:11.5px;color:var(--soft)}
.lgd .i{display:flex;align-items:center;gap:5px}
.lgd .sw{width:14px;height:12px;border-radius:2px;display:inline-block}
details{margin:8px 0}summary{cursor:pointer;font-size:12.5px;color:var(--soft);font-weight:700}
.metricnav{display:flex;flex-wrap:wrap;gap:6px;margin:18px 0 10px;padding:12px;background:var(--slate-bg);border:1px solid var(--line);border-radius:8px;position:sticky;top:0;z-index:2}
.mbtn{padding:7px 13px;border:1px solid var(--line);background:#fff;color:var(--soft);border-radius:7px;cursor:pointer;font:inherit;font-size:12.5px;font-weight:700}
.mbtn:hover{border-color:var(--navy);color:var(--navy)}
.mbtn.on{background:var(--navy);color:#fff;border-color:var(--navy)}
.mbtn.help{background:#fff;color:var(--teal);border-color:var(--teal)}
.mbtn.help.on{background:var(--teal);color:#fff}
.mbtn .mtiny{font-size:10px;opacity:.7;font-weight:600}
.periodnav{display:flex;gap:6px;margin:8px 0}
.periodnav button{padding:6px 16px;border:1px solid var(--navy);background:#fff;color:var(--navy);border-radius:6px;cursor:pointer;font:inherit;font-weight:700}
.periodnav button:hover{background:var(--navy-bg)}
.info{font-size:12px;color:var(--soft);margin:4px 0}
aside{background:var(--slate-bg);border:1px solid var(--line);border-radius:8px;padding:14px 18px;margin:16px 0}
aside h2{border:none;padding:0;margin:0 0 6px;font-size:14px}
aside ul{margin:4px 0 0 18px}aside li{margin:3px 0;font-size:12.5px;color:var(--soft)}
.foot{margin-top:26px;padding-top:14px;border-top:1px solid var(--line);font-size:11.5px;color:var(--faint)}
@media(max-width:720px){.pad,.head{padding-left:16px;padding-right:16px}.kpis{grid-template-columns:repeat(2,1fr)}}
@media print{body{background:#fff}.doc{box-shadow:none;margin:0}.chartbox,table,.note,.kpi,section{break-inside:avoid}}
"""


def display(value):
    if value is None:
        return "—"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, float):
        return f"{value:,.2f}"
    return str(value)


def esc(value):
    return html.escape(display(value), quote=True)


def atomic_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".batch-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def chart_data(table):
    rows, title = table["rows"], table["title"]
    if title in {"유형별 빈도", "유형별 Wafer 발생 빈도", "유형별 Lot 발생 빈도"}:
        col = {"유형별 빈도": 6, "유형별 Wafer 발생 빈도": 5, "유형별 Lot 발생 빈도": 7}[title]
        unit = {"유형별 빈도": "Report 수 (건)", "유형별 Wafer 발생 빈도": "Wafer 발생 (건)", "유형별 Lot 발생 빈도": "Lot 수 (건)"}[title]
        return [(f"{r[3]} / {r[4]}", r[col]) for r in rows if r[0] == "전체"], unit
    if title == "유형별 재시작 간격 (유형 중복 허용)":
        return [(r[0], r[2]) for r in rows if r[2] is not None], "평균 재시작 간격 (분)"
    if title in {"Error 성격 분류", "Aborted 보정", "Lot 이슈 요약"}:
        return [(r[0], r[1]) for r in rows], table["headers"][1]
    return [], ""


def _bar_fill(title, label, cat2char):
    """Colour a bar by its meaning so the chart groups read at a glance."""
    if title in {"유형별 빈도", "유형별 Wafer 발생 빈도", "유형별 Lot 발생 빈도"}:
        category = label.split(" / ")[0]
        return CHAR_COLOR.get((cat2char or {}).get(category), BAR_BASE)
    if title == "Error 성격 분류":
        return CHAR_COLOR.get(label, BAR_BASE)
    if title == "Lot 이슈 요약":
        return ISSUE_COLOR.get(label, BAR_BASE)
    if title == "Aborted 보정":
        return ABORT_COLOR.get(label, BAR_BASE)
    return BAR_BASE


_LEGEND_NAMES = {"예방형": "예방형 (반자동 사전검증)", "조치형": "조치형 (Auto Setup 후보)",
                 "중단": "작업 중단", "결과형": "검사 제외(결과형)", "미확인": "미확인·미분류"}


def _legend(title, values, cat2char):
    """Distinct colour groups actually present, in a stable order."""
    seen = []
    for label, _ in values:
        if title in {"유형별 빈도", "유형별 Wafer 발생 빈도", "유형별 Lot 발생 빈도"}:
            char = (cat2char or {}).get(label.split(" / ")[0]) or "미확인"
            item = (CHAR_COLOR.get(char, BAR_BASE), _LEGEND_NAMES.get(char, char))
        elif title == "Error 성격 분류":
            item = (CHAR_COLOR.get(label, BAR_BASE), _LEGEND_NAMES.get(label, label))
        elif title in {"Lot 이슈 요약", "Aborted 보정"}:
            table_color = ISSUE_COLOR if title == "Lot 이슈 요약" else ABORT_COLOR
            item = (table_color.get(label, BAR_BASE), label)
        else:
            return ""
        if item not in seen:
            seen.append(item)
    if len(seen) <= 1:
        return ""
    return ('<div class="lgd">' + ''.join(
        f'<span class="i"><span class="sw" style="background:{c}"></span>{esc(t)}</span>' for c, t in seen) + '</div>')


def bars(table, cat2char=None):
    values, unit = chart_data(table)
    if not values:
        return ""
    title = table["title"]
    values = sorted(values, key=lambda r: r[1], reverse=True)
    axis_x, bar_x, bar_w = 470, 490, 640
    height, maximum = 54 + len(values) * 46, max(v for _, v in values) or 1
    out = [f'<svg role="img" aria-label="{esc(title)}" viewBox="0 0 1180 {height}" style="min-width:820px">',
           f'<text x="{bar_x}" y="22">{esc(unit)}</text>',
           f'<line x1="{bar_x}" y1="30" x2="{bar_x}" y2="{height - 14}" stroke="#dde2e9"/>']
    for i, (label, value) in enumerate(values):
        y, width = 42 + i * 46, bar_w * value / maximum
        # Full category text is in the table below; wrap long labels over two lines.
        chunks = [label[j:j + 44] for j in range(0, len(label), 44)]
        short = chunks[:2]
        if len(chunks) > 2:
            short[-1] = short[-1][:-1] + "…"
        fill = _bar_fill(title, label, cat2char)
        out.append(f'<g><title>{esc(label)}: {esc(value)} {esc(unit)}</title>')
        for n, chunk in enumerate(short):
            out.append(f'<text x="{axis_x}" y="{y + 12 + n * 15}" text-anchor="end" font-size="12.5">{esc(chunk)}</text>')
        out.append(f'<rect x="{bar_x}" y="{y}" width="{width:.2f}" height="26" rx="3" fill="{fill}"/>')
        out.append(f'<text class="val" x="{bar_x + 8 + width:.2f}" y="{y + 18}">{esc(value)}</text></g>')
    out.append('</svg>')
    out.append(_legend(title, values, cat2char))
    return ''.join(out)


def trend(table):
    utilization = table['title'].startswith('스캔 가동률 ·')
    rows = ([(r[1], r[0], table['title'], r[5]) for r in table['rows'] if r[5] is not None]
            if utilization else [r for r in table["rows"] if isinstance(r[0], datetime)])
    if not rows:
        return ""
    times = [r[0].timestamp() for r in rows]
    lo, hi = min(times), max(times)
    # 가동률은 Y축을 0~100%로 고정해 일/주/월 그래프가 같은 눈금으로 비교되게 한다
    # (100% 초과 anomaly 는 맨 위에 붙는다). 그 외(WPH)는 데이터 최대값 기준.
    maximum = 100 if utilization else (max(r[3] for r in rows) or 1)
    groups = {}
    for r in rows:
        groups.setdefault(r[1], []).append(r)
    unit = '스캔 가동률 (%)' if utilization else 'Actual WPH (wafer/h)'
    parts = [f'<svg role="img" aria-label="{esc(table["title"])}" viewBox="0 0 1200 430" style="min-width:900px">',
             f'<text x="10" y="20">{esc(unit)}</text>']
    for i in range(5):
        x, t = 80 + i * 250, lo + (hi - lo) * i / 4
        parts.append(f'<line x1="{x}" y1="40" x2="{x}" y2="330" stroke="#dce3eb"/>')
        parts.append(f'<text x="{x}" y="365" text-anchor="middle" font-size="13">{datetime.fromtimestamp(t):%Y-%m-%d}</text>')
        parts.append(f'<text x="{x}" y="384" text-anchor="middle" font-size="13">{datetime.fromtimestamp(t):%H:%M}</text>')
        y = 330 - 290 * i / 4
        parts.append(f'<text x="70" y="{y}" text-anchor="end">{maximum * i / 4:.1f}</text>')
        parts.append(f'<line x1="80" y1="{y}" x2="1080" y2="{y}" stroke="#dce3eb"/>')
    colors = ["#246d91", "#be5a25", "#764aa1", "#227a58", "#af345d"]
    for index, (machine, items) in enumerate(sorted(groups.items())):
        color = colors[index % len(colors)]
        points = [(80 + (r[0].timestamp() - lo) / (hi - lo or 1) * 1000, max(40, 330 - r[3] / maximum * 290), r) for r in items]
        parts.append(f'<polyline fill="none" stroke="{color}" stroke-width="2" points="' + ' '.join(f'{x:.2f},{y:.2f}' for x, y, _ in points) + '"/>')
        for x, y, r in points:
            parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3" fill="{color}"><title>{esc(machine)} · {esc(r[0])} · {esc(r[2])}: {esc(r[3])} {esc(unit)}</title></circle>')
    parts.append('<text x="560" y="420" text-anchor="middle">' + ('기간 시작' if utilization else 'Batch End (배치 종료 시각)') + '</text></svg>')
    parts.append('<p>' + ' · '.join(f'<span style="color:{colors[i % len(colors)]}">● {esc(m)}</span>' for i, m in enumerate(sorted(groups))) + '</p>')
    return ''.join(parts)


def _cat2char(tables):
    """유형(category) → 성격(character) map from the M03 detail table, for chart colours.

    상태 상세 헤더: 호기, Report, Lot, 원본 순서, Wafer ID, 유형(5), 분류 원문, 성격(7), …
    """
    mapping = {}
    for t in tables:
        if t["title"] == "상태 상세":
            for row in t["rows"]:
                if len(row) > 7 and row[5]:
                    mapping.setdefault(row[5], row[7])
    return mapping


def dice_bars(rows):
    """M08: recipe별 정상 wafer의 Dice 구성을 100% 누적 막대(Good/Bad 비율)로 보여준다.

    Scanned 평균 규모가 recipe마다 크게 달라(수십~수천) 절대 길이는 작은 recipe가
    안 보인다. 그래서 막대는 비율로 통일하고, Scanned/Bad 평균은 막대 오른쪽에 숫자로.
    Bad 비율이 높은 recipe(=결함 많음)가 위로 오도록 정렬 → Hold 후보 판단에 직접 쓰인다.
    """
    data = []
    for r in rows:
        scanned, bad, good = r[2] or 0, r[3] or 0, r[4] or 0
        if scanned or bad or good:
            base = scanned if scanned else (good + bad)
            data.append((r[0], scanned, bad, good, bad / base if base else 0))
    if not data:
        return ""
    data.sort(key=lambda d: d[4], reverse=True)
    axis_x, bar_x, bar_w = 470, 490, 500
    height = 54 + len(data) * 40
    out = [f'<svg role="img" aria-label="Recipe별 Dice 구성" viewBox="0 0 1180 {height}" style="min-width:820px">',
           f'<text x="{bar_x}" y="22">정상 wafer Dice 구성 (막대 = 100%, Bad 비율 높은 순)</text>']
    for i, (name, scanned, bad, good, ratio) in enumerate(data):
        y = 42 + i * 40
        gw = bar_w * (1 - ratio)
        chunks = [name[j:j + 42] for j in range(0, len(name), 42)][:2]
        out.append('<g><title>' + esc(f"{name}: Scanned {scanned:.1f} · Good {good:.1f} · Bad {bad:.1f} (Bad {ratio*100:.1f}%)") + '</title>')
        for n, chunk in enumerate(chunks):
            out.append(f'<text x="{axis_x}" y="{y + 12 + n * 15}" text-anchor="end" font-size="12.5">{esc(chunk)}</text>')
        out.append(f'<rect x="{bar_x}" y="{y}" width="{gw:.2f}" height="24" rx="2" fill="#0e5f5c"/>')
        out.append(f'<rect x="{bar_x + gw:.2f}" y="{y}" width="{bar_w - gw:.2f}" height="24" fill="#c0392b"/>')
        if gw > 44:
            out.append(f'<text x="{bar_x + 6}" y="{y + 17}" font-size="11" fill="#fff">{ratio*100:.0f}% Bad</text>')
        out.append(f'<text class="val" x="{bar_x + bar_w + 10}" y="{y + 17}">Bad {esc(round(bad, 1))} · Scan {esc(round(scanned, 1))}</text></g>')
    out.append('</svg>')
    out.append('<div class="lgd"><span class="i"><span class="sw" style="background:#0e5f5c"></span>Good 비율</span>'
               '<span class="i"><span class="sw" style="background:#c0392b"></span>Bad 비율</span>'
               '<span class="i" style="color:#8592a0">오른쪽 숫자 = Bad·Scanned 평균(개)</span></div>')
    return ''.join(out)


def _cell(value):
    """Escape a cell; render embedded newlines (예: M10 포함 이슈 유형) as separate lines."""
    text = display(value)
    if "\n" in text:
        return "<br>".join(html.escape(line, quote=True) for line in text.split("\n"))
    return html.escape(text, quote=True)


def _table_html(t):
    open_attr = " open" if len(t["rows"]) <= 60 else ""
    out = [f'<details{open_attr}><summary>{esc(t["title"])} · 전체 표 {len(t["rows"])}행 (원문 확인 · 열 머리 클릭=정렬)</summary>',
           '<table class="sortable"><thead><tr>', *('<th onclick="sortTable(this)">' + esc(h) + '</th>' for h in t["headers"]), '</tr></thead><tbody>']
    for row in t["rows"]:
        out.append('<tr>' + ''.join('<td>' + _cell(cell) + '</td>' for cell in row) + '</tr>')
    out.append('</tbody></table></details>')
    return ''.join(out)


def _block(t, cat2char):
    """One table's chart (if any) plus its collapsible source table."""
    title = t["title"]
    if title == "시간순 Actual WPH":
        chart = trend(t)
    elif title.startswith("스캔 가동률 · "):
        chart = trend(t)  # 버킷별 시계열만(최근 기간 막대 제거). Y축 0~100% 고정.
    elif title == "유형별 빈도":
        chart = (bars(dict(t, title="유형별 Wafer 발생 빈도"), cat2char)
                 + bars(dict(t, title="유형별 Lot 발생 빈도"), cat2char))
    elif title == "Recipe별 정상 Dice 통계":
        chart = dice_bars(t["rows"])
    else:
        chart = bars(t, cat2char)
    head = f'<div class="chartbox"><div class="cap">{esc(title)}</div>{chart}</div>' if chart.strip() else ''
    return head + _table_html(t)


def build_html(result, collection, dashboard=False):
    title = "스캔 가동률 대시보드" if dashboard else "배치 리포트 분석"
    summary, batches = result["summary"], result["batches"]
    cat2char = _cat2char(result["tables"])
    starts = [b["start"] for b in batches if b.get("start")]
    ends = [b["end"] for b in batches if b.get("end")]
    span = f"{min(starts):%Y-%m-%d} ~ {max(ends):%Y-%m-%d}" if starts and ends else "—"
    machines = sorted({b["machine"] for b in batches if b.get("machine")})
    wafer_rows = summary.get("Wafer 행 수") or 0
    pass_wafers = summary.get("Pass Wafer 수") or 0
    normal = pass_wafers / wafer_rows * 100 if wafer_rows else None
    lots = summary.get("Lot 수") or 0
    issue_lots = summary.get("이슈 발생 Lot 수") or 0
    rescan_lots = summary.get("재스캔 Lot 수") or 0
    reports = summary.get("Batch(리포트) 수") or 0
    issue_pct = issue_lots / lots * 100 if lots else None
    rescan_pct = rescan_lots / lots * 100 if lots else None
    badge = '<span class="draft">30분 자동 새로고침</span>' if dashboard else ''

    cards = [("t", f"{normal:.1f}%" if normal is not None else "—",
              f"정상 스캔 비율<br>(Pass {pass_wafers:,} / {wafer_rows:,}행)"),
             ("", f"{lots:,}", f"분석 Lot 수<br>(batch report {reports:,}건)"),
             ("a", f"{issue_pct:.1f}%" if issue_pct is not None else "—", f"이슈 발생 Lot<br>({issue_lots:,} / {lots:,})"),
             ("r", f"{rescan_pct:.1f}%" if rescan_pct is not None else "—", f"재스캔 Lot<br>({rescan_lots:,} / {lots:,})")]

    parts = ['<!doctype html><html lang="ko"><head><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width,initial-scale=1">',
             '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;; script-src &#39;unsafe-inline&#39;; img-src data:; connect-src &#39;none&#39;">',
             '<meta http-equiv="refresh" content="1800">' if dashboard else '',
             f'<title>{title}</title><style>{PAGE_CSS}</style></head><body><div class="doc">',
             '<div class="head"><div class="kick">AOI 배치 리포트 분석 · 오프라인 자동 산출</div>',
             f'<h1>{title}{badge}</h1><div class="meta">',
             f'<span><b>분석 대상</b> Lot {lots:,}개 · batch report {len(batches):,}건 · wafer {wafer_rows:,}행</span>',
             f'<span><b>기간</b> {esc(span)}</span>',
             f'<span><b>호기</b> {esc(", ".join(machines)) or "—"} ({len(machines)}대)</span>',
             '<span><b>범위</b> M01–M03 (대시보드)</span>' if dashboard else '',
             '</div></div><div class="pad">',
             f'<div class="info">데이터 생성 {esc(result["created"])} · 신규/변경 파싱 {collection["parsed"]}건 · 캐시 재사용 {collection["reused"]}건 · 원본 목록 밖 누적 {collection["cached_only"]}건 · 읽기/파싱 오류 {len(collection["errors"])}건</div>',
             '<div class="note navy"><span class="t">자동 새로고침 안내</span>이 페이지는 로컬 파일입니다. 자동 새로고침은 파일만 다시 엽니다. 새 데이터는 앱의 [지금 업데이트] 또는 실행 중 하루 1회 자동 분석으로 생성됩니다.</div>' if dashboard else '',
             '<div class="kpis">' + ''.join(f'<div class="kpi {c}"><div class="n">{esc(v)}</div><div class="l">{l}</div></div>' for c, v, l in cards) + '</div>']
    tv = summary.get("시각 누락/역전 Batch 수") or 0
    if tv:
        parts.append(f'<div class="note rust"><span class="t">데이터 품질</span>시각 누락/역전 배치 {tv:,}건 — 해당 지표(가동률·재시작 간격)에서 제외될 수 있습니다.</div>')
    parts.append('<aside><h2>조사 설정 · 선택 범위</h2><ul>'
                 + ''.join(f'<li>{esc(k)}: {esc(v)}</li>' for k, v in result["settings"].items())
                 + f'<li>선택 범위: {esc(collection.get("scope", ""))}</li></ul></aside>')

    shown = [t for t in result["tables"] if not (dashboard and t["key"] not in {"M01", "M02", "M03"})]
    groups = []
    for t in shown:
        if groups and groups[-1][0] == t["key"]:
            groups[-1][1].append(t)
        else:
            groups.append((t["key"], [t]))
    # 지표 버튼 탭 — 한 번에 한 지표만 보여준다(길게 나열돼 읽기 힘든 문제 해결).
    nav = ['<div class="metricnav"><button class="mbtn help" data-sec="help" onclick="showMetric(\'help\')">📘 방법론·lot 기준</button>']
    for i, (key, _) in enumerate(groups):
        nav.append(f'<button class="mbtn{" on" if i == 0 else ""}" data-sec="{key}" onclick="showMetric(\'{key}\')">{esc(METRIC_NAME.get(key, key))} <span class="mtiny">[{key}]</span></button>')
    parts.append(''.join(nav) + '</div>')
    for n, (key, ts) in enumerate(groups, 1):
        parts.append(f'<section class="metric" id="sec-{key}"{"" if n == 1 else " hidden"}><h2>{n}. {esc(METRIC_NAME.get(key, key))} <span class="mtag">[{key}]</span></h2>')
        parts.append(f'<div class="sub">{esc(PURPOSE.get(key, ""))}</div>')
        if key == "M02" and any(x["title"].startswith("스캔 가동률 · ") for x in ts):
            parts.append('<div class="periodnav"><button onclick="period(\'일\')">일</button>'
                         '<button onclick="period(\'주\')">주 (ISO)</button>'
                         '<button onclick="period(\'월\')">월</button></div>')
        for t in ts:
            unit = t["title"].split(" · ")[-1] if t["title"].startswith("스캔 가동률 · ") else ""
            if unit:
                hidden = "" if unit == "일" else " hidden"
                parts.append(f'<div data-period="{unit}"{hidden}>' + _block(t, cat2char) + '</div>')
            else:
                parts.append(_block(t, cat2char))
        if key == "M04":  # 성격 · 설명 · 실제 error 원문 (조사한 batch report 원문 그대로)
            char2raw = {}
            for tbl in result["tables"]:
                if tbl["title"] == "상태 상세":
                    for row in tbl["rows"]:
                        if len(row) > 8 and row[7] and row[8]:
                            char2raw.setdefault(row[7], set()).add(row[8].strip())
            if char2raw:
                parts.append('<div class="chartbox"><div class="cap">성격별 실제 Error 원문 (조사 대상 batch report에서 나온 문구)</div>'
                             '<table style="margin:0"><thead><tr><th>성격</th><th>설명</th><th>포함 Error 유형 (원문)</th></tr></thead><tbody>')
                for char in ("예방형", "조치형", "중단", "결과형", "미확인"):
                    if char in char2raw:
                        name = _LEGEND_NAMES.get(char, char)
                        raws = "<br>".join(esc(r) for r in sorted(char2raw[char]))
                        parts.append(f'<tr><td><b>{esc(name)}</b></td><td>{esc(CHAR_DESC.get(char, ""))}</td><td>{raws}</td></tr>')
                parts.append('</tbody></table></div>')
        for variant, note_title, body in INTERPRET.get(key, []):
            parts.append(f'<div class="note {variant}"><span class="t">{esc(note_title)}</span>{esc(body)}</div>')
        parts.append('</section>')

    parts.append(
        '<section class="metric" id="sec-help" hidden><h2>📘 데이터 가공 방법 · lot 조사 기준</h2>'
        '<div class="sub">이 리포트가 batch report 원본을 어떻게 지표로 바꾸는지 설명합니다.</div>'
        '<div class="note navy"><span class="t">1. 입력 — batch report</span>'
        '장비 Report 폴더에 스캔 1회마다 쌓이는 batch report(HTML) 한 장이 기본 단위입니다. 한 장에는 그 스캔의 '
        'Batch Start/End·Batch Time·Job/Setup·wafer 표(각 wafer의 Lot·Wafer ID·Scanned/Bad/Good Dice·Pass/Fail)가 들어 있습니다. '
        '원본은 읽기만 하고 수정하지 않습니다.</div>'
        '<div class="note teal"><span class="t">2. lot 조사 기준 — 핵심</span>'
        'batch report 1장 = 스캔 세션 1회이지 lot(카세트) 전체가 아닙니다. 스캔이 중단·재스캔되면 <b>한 lot이 리포트 여러 장</b>으로 '
        '나뉩니다(실데이터 최대 9장). 그래서 <b>lot = (Job/Setup, wafer 표 Lot 열의 최빈값)</b>으로 정의하고, 같은 lot의 리포트들을 '
        '묶어서 지표를 lot 기준으로 셉니다. wafer ID를 못 읽어 Lot 칸이 \'LoadPort A\'·\'-\'·빈칸인 행은 lot 판정에서 제외합니다.</div>'
        '<div class="note slate"><span class="t">3. Recipe = Job/Setup</span>'
        'Recipe는 wafer 표의 \'Recipe(s)\' 열(2D/PI_Bubble/x20 등, 지저분)이 아니라 배치의 <b>Job/Setup 전체</b>(예: 2D@R2-DT-GH10N-BIN1-H-U1_0858092PD-0B/Setup1)로 봅니다.</div>'
        '<div class="note amber"><span class="t">4. 성격 분류</span>'
        '각 wafer의 Pass/Fail 원문을 유형으로 분류하고, 유형을 5가지 성격(예방형·조치형·중단·결과형·미확인)으로 묶습니다. '
        '한 원문이 두 성격에 걸칠 수 있습니다(예: \'Alignment Error. Aborted.\' = 조치형 + 중단). 성격별 실제 원문은 M04에서 봅니다.</div>'
        '<div class="note rust"><span class="t">5. 한계 — proxy·추정</span>'
        '가동률(스캔시간/달력시간)·재시작 간격·Aborted 연쇄/직접 구분은 batch report에서 얻을 수 있는 근사치·추정입니다. '
        'OEE·실제 수리시간·실측 중단 구분이 아니며, 자동 설비 제어에 쓰지 않습니다. 이 분석은 <b>호기 1대</b> 기준이라, '
        '다른 AOI로 넘어간 재검사는 여기서 보이지 않습니다.</div>'
        '</section>')

    parts.append('<aside><h2>읽기 오류 · 중복 제외 · 알림</h2><ul>')
    for error in collection["errors"]:
        parts.append('<li>' + esc(f'{error["machine"]} / {error["source_file"]}: {error["error"]}') + '</li>')
    parts.extend('<li>' + esc(n) + '</li>' for n in collection["notices"])
    if not collection["errors"] and not collection["notices"]:
        parts.append('<li>이번 실행에서는 읽기 오류·알림이 없습니다.</li>')
    parts.append('</ul></aside><aside><h2>지표 해석 · 한계 (전체 공통)</h2><ul>'
                 + ''.join('<li>' + esc(n) + '</li>' for n in NOTES) + '</ul></aside>')
    parts.append('<div class="foot">※ 표에 표시된 값은 원본 batch report에서 그대로 파싱한 것이며, proxy·추정으로 표시된 지표는 상대 비교·참고용입니다. 자동 설비 제어에 사용하지 않습니다.</div>')
    parts.append('</div></div><script>'
                 'function period(p){document.querySelectorAll("[data-period]").forEach(function(e){e.hidden=e.dataset.period!==p})}'
                 'function showMetric(k){'
                 'document.querySelectorAll("section.metric").forEach(function(s){s.hidden=(s.id!=="sec-"+k)});'
                 'document.querySelectorAll(".mbtn").forEach(function(b){b.classList.toggle("on",b.dataset.sec===k)});'
                 'window.scrollTo(0,0);}'
                 'function sortTable(th){var t=th.closest("table"),b=t.tBodies[0],i=[].indexOf.call(th.parentNode.children,th),'
                 'd=th.getAttribute("data-dir")==="asc"?"desc":"asc";'
                 '[].forEach.call(t.querySelectorAll("th"),function(h){h.removeAttribute("data-dir")});th.setAttribute("data-dir",d);'
                 'var rows=[].slice.call(b.rows);rows.sort(function(x,y){'
                 'var a=x.cells[i].innerText.trim(),c=y.cells[i].innerText.trim(),'
                 'na=parseFloat(a.replace(/,/g,"")),nc=parseFloat(c.replace(/,/g,"")),'
                 'r=(!isNaN(na)&&!isNaN(nc))?na-nc:a.localeCompare(c,"ko");return d==="asc"?r:-r;});'
                 'rows.forEach(function(rw){b.appendChild(rw)});}'
                 '</script></body></html>')
    return ''.join(parts)


def write_excel(path, result, collection):
    from openpyxl import Workbook
    from openpyxl.chart import BarChart, Reference, ScatterChart, Series
    from openpyxl.utils.datetime import to_excel
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    from .wph_charts import format_chart, category_labels, value_labels

    wb = Workbook()
    wb.remove(wb.active)

    def sheet(title, headers, rows):
        ws = wb.create_sheet(title[:31])
        ws.append(headers)
        for row in rows:
            ws.append(list(row))
        for cells in ws:
            for cell in cells:
                if isinstance(cell.value, str):
                    cell.data_type = 's'  # no formula injection from source text
                if isinstance(cell.value, datetime):
                    cell.number_format = 'yyyy-mm-dd hh:mm:ss'
                elif isinstance(cell.value, float):
                    cell.number_format = '0.00'
                cell.alignment = Alignment(vertical='top', wrap_text=True)
        for cell in ws[1]:
            cell.font = Font(color='FFFFFF', bold=True, size=11)
            cell.fill = PatternFill('solid', fgColor='183047')
        for i in range(1, len(headers) + 1):
            ws.column_dimensions[get_column_letter(i)].width = 28
        ws.row_dimensions[1].height = 34
        ws.freeze_panes = 'A2'
        ws.auto_filter.ref = ws.dimensions
        return ws

    sheet('안내', ['항목', '내용'], list(result['summary'].items()) + list(result['settings'].items()) +
          [('생성', result['created']), ('선택 범위', collection.get('scope', ''))] + [('해석', n) for n in NOTES])
    for i, t in enumerate(result['tables'], 1):
        sheet(f'{i:02}_{t["title"]}'.replace('/', '·'), t['headers'], t['rows'])
    batch_headers = ['호기', 'Report', 'Batch Start', 'Batch End', 'Batch Time (초)', 'Wafers Scanned', 'Wafer 행 수', 'Job/Setup', 'User', 'Scanned Dice', 'Good Dice', 'Bad Dice', 'Yield (%)', '완주율 (%)']
    keys = ['machine', 'source_file', 'start', 'end', 'batch_sec', 'wafers', 'wafer_rows', 'job_setup', 'user', 'scanned_dice', 'good_dice', 'bad_dice', 'yield_pct', 'completion']
    sheet('Batches', batch_headers + ['원본 폴더'], [[b.get(k) for k in keys] + [b.get('source_folder', '')] for b in result['batches']])
    keys = ['machine', 'source_file', 'order', 'no', 'lot', 'wafer_id', 'faults', 'scanned_dice', 'bad_dice', 'good_dice', 'yield_pct', 'status', 'recipe', 'abort_kind']
    sheet('Wafers', ['호기', 'Report', '원본 순서', 'No', 'Lot', 'Wafer ID', 'Faults', 'Scanned Dice', 'Bad Dice', 'Good Dice', 'Yield (%)', 'Pass/Fail 원문', 'Recipe(s)', 'Aborted 추정', '원본 폴더'],
          [[w.get(k) for k in keys] + [w.get('source_folder', '')] for w in result['wafers']])
    sheet('읽기오류', ['호기', 'Report', '사유'], [[e['machine'], e['source_file'], e['error']] for e in collection['errors']])
    sheet('수집정보', ['항목', '값'], [('신규/변경 파싱', collection['parsed']), ('캐시 재사용', collection['reused']), ('원본 목록 밖 누적', collection['cached_only'])] + [('알림', n) for n in collection['notices']])
    charts = wb.create_sheet('그래프')
    data = wb.create_sheet('그래프데이터')
    charts.column_dimensions['A'].width = 24
    anchor = 1
    chart_tables = []
    for t in result['tables']:
        chart_tables.append(t)
        if t['title'] == '유형별 빈도':
            chart_tables.append(dict(t, title='유형별 Wafer 발생 빈도'))
    for t in chart_tables:
        values, unit = chart_data(t)
        if not values:
            continue
        first = data.max_row + 2
        data.cell(first, 1, t['title']).data_type = 's'
        data.cell(first, 2, unit).data_type = 's'
        for r, (label, value) in enumerate(sorted(values, key=lambda v: v[1], reverse=True), first + 1):
            data.cell(r, 1, label).data_type = 's'
            data.cell(r, 2, value)
        chart = BarChart()
        chart.type = 'bar'
        chart.title, chart.x_axis.title, chart.y_axis.title = t['title'], '항목 (전체 원문은 표 참조)', unit
        format_chart(chart, horizontal=True)
        chart.add_data(Reference(data, min_col=2, min_row=first, max_row=first + len(values)), titles_from_data=True)
        category_labels(chart, data, 1, first + 1, first + len(values))
        chart.legend = None
        chart.width, chart.height = 38, max(18, len(values) * .85 + 6)
        chart.x_axis.tickLblPos = 'low'
        chart.y_axis.scaling.min = 0
        if '건' in unit or '수' in unit:
            chart.y_axis.majorUnit = max(1, math.ceil(max(v for _, v in values) / 8))
            chart.y_axis.numFmt = '0'
        value_labels(chart, '0.00"%"' if '%' in unit else '0"건"')
        charts.add_chart(chart, f'A{anchor}')
        # Explicit heights prevent multiple drawings from overlapping.
        end = anchor + math.ceil(chart.height * 28.35 / 18) + 4
        for r in range(anchor, end):
            charts.row_dimensions[r].height = 18
        anchor = end
    # Native time-series charts with real Excel date coordinates and ~5 ticks.
    for t in result['tables']:
        utilization = t['title'].startswith('스캔 가동률 ·')
        if not utilization and t['title'] != '시간순 Actual WPH':
            continue
        points = [(r[0], r[1], r[5]) for r in t['rows'] if r[5] is not None] if utilization else [(r[1], r[0], r[3]) for r in t['rows'] if r[0]]
        if not points:
            continue
        chart = ScatterChart()
        chart.title = t['title'] + ' · 시간 추이'
        format_chart(chart)
        chart.width, chart.height = 38, 20
        chart.scatterStyle = 'lineMarker'
        chart.x_axis.title = '기간 시작' if utilization else 'Batch End (배치 종료 시각)'
        chart.y_axis.title = '스캔 가동률 (%)' if utilization else 'WPH (wafer/h)'
        chart.x_axis.numFmt = 'yyyy-mm-dd hh:mm'
        chart.x_axis.numFmt.sourceLinked = False
        chart.y_axis.scaling.min = 0
        times = [to_excel(p[1]) for p in points]
        lo, hi = min(times), max(times)
        chart.x_axis.scaling.min = lo
        chart.x_axis.scaling.max = hi if hi > lo else lo + 1 / 24
        chart.x_axis.majorUnit = (chart.x_axis.scaling.max - lo) / 4
        for machine in sorted({p[0] for p in points}):
            subset = sorted([p for p in points if p[0] == machine], key=lambda p: p[1])
            first = data.max_row + 2
            data.cell(first, 1, machine).data_type = 's'
            for r, (_, dt, value) in enumerate(subset, first + 1):
                data.cell(r, 1, dt).number_format = 'yyyy-mm-dd hh:mm:ss'
                data.cell(r, 2, value)
            series = Series(Reference(data, min_col=2, min_row=first + 1, max_row=first + len(subset)),
                            Reference(data, min_col=1, min_row=first + 1, max_row=first + len(subset)), title=machine)
            series.smooth = False
            series.marker.symbol = 'circle'
            series.marker.size = 3
            chart.series.append(series)
        from openpyxl.chart.legend import Legend
        chart.legend = Legend(legendPos='b')
        charts.add_chart(chart, f'A{anchor}')
        end = anchor + 38
        for r in range(anchor, end):
            charts.row_dimensions[r].height = 18
        anchor = end
    wb.save(path)
    wb.close()
