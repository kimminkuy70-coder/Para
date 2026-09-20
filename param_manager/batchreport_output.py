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
    if title in {"유형별 빈도", "유형별 Wafer 발생 빈도"}:
        wafer = title == '유형별 Wafer 발생 빈도'
        return [(f"{r[3]} / {r[4]}", r[5 if wafer else 6]) for r in rows if r[0] == "전체"], "Wafer 발생 (건)" if wafer else "Report 수 (건)"
    if title.startswith("스캔 가동률 ·"):
        latest = max((r[1] for r in rows), default=None)
        return [(f"{r[0]} · {display(r[1])[:10]}", r[5]) for r in rows if r[1] == latest and r[5] is not None], "최근 기간 스캔 가동률 (%)"
    if title in {"오류 성격", "Aborted 보정", "완주율 요약"}:
        return [(r[0], r[1]) for r in rows], table["headers"][1]
    return [], ""


def bars(table):
    values, unit = chart_data(table)
    if not values:
        return ""
    values = sorted(values, key=lambda r: r[1], reverse=True)
    height, maximum = 80 + len(values) * 48, max(v for _, v in values) or 1
    out = [f'<svg role="img" aria-label="{esc(table["title"])}" viewBox="0 0 1200 {height}" style="min-width:900px">',
           f'<text x="560" y="26">{esc(unit)}</text>']
    for i, (label, value) in enumerate(values):
        y, width = 46 + i * 48, 500 * value / maximum
        # Full category text below in table; long labels wrap over two lines.
        chunks = [label[j:j + 48] for j in range(0, len(label), 48)]
        short = chunks[:2]
        if len(chunks) > 2:
            short[-1] = short[-1][:-1] + "…"
        out.append(f'<g><title>{esc(label)}: {esc(value)} {esc(unit)}</title>')
        for n, chunk in enumerate(short):
            out.append(f'<text x="8" y="{y + 14 + n * 16}" font-size="13">{esc(chunk)}</text>')
        out.append(f'<rect x="560" y="{y}" width="{width:.2f}" height="28" rx="3" fill="#347b9d"/>')
        out.append(f'<text x="{570 + width:.2f}" y="{y + 20}">{esc(value)}</text></g>')
    out.append('</svg>')
    return ''.join(out)


def trend(table):
    utilization = table['title'].startswith('스캔 가동률 ·')
    rows = ([(r[1], r[0], table['title'], r[5]) for r in table['rows'] if r[5] is not None]
            if utilization else [r for r in table["rows"] if isinstance(r[0], datetime)])
    if not rows:
        return ""
    times = [r[0].timestamp() for r in rows]
    lo, hi = min(times), max(times)
    maximum = max(r[3] for r in rows) or 1
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
        points = [(80 + (r[0].timestamp() - lo) / (hi - lo or 1) * 1000, 330 - r[3] / maximum * 290, r) for r in items]
        parts.append(f'<polyline fill="none" stroke="{color}" stroke-width="2" points="' + ' '.join(f'{x:.2f},{y:.2f}' for x, y, _ in points) + '"/>')
        for x, y, r in points:
            parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3" fill="{color}"><title>{esc(machine)} · {esc(r[0])} · {esc(r[2])}: {esc(r[3])} {esc(unit)}</title></circle>')
    parts.append('<text x="560" y="420" text-anchor="middle">' + ('기간 시작' if utilization else 'Batch End (배치 종료 시각)') + '</text></svg>')
    parts.append('<p>' + ' · '.join(f'<span style="color:{colors[i % len(colors)]}">● {esc(m)}</span>' for i, m in enumerate(sorted(groups))) + '</p>')
    return ''.join(parts)


def build_html(result, collection, dashboard=False):
    title = "스캔 가동률 대시보드" if dashboard else "배치 리포트 분석"
    parts = ['<!doctype html><html lang="ko"><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width,initial-scale=1">',
             '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;; script-src &#39;unsafe-inline&#39;; img-src data:; connect-src &#39;none&#39;">',
             '<meta http-equiv="refresh" content="1800">' if dashboard else '',
             f'<title>{title}</title><style>body{{margin:0;background:#eef2f6;color:#172a40;font:15px/1.6 Segoe UI,Malgun Gothic,sans-serif}}main{{max-width:1500px;margin:auto;padding:28px}}section,aside{{background:white;padding:22px;margin:18px 0;border-radius:12px}}h1{{font-size:28px}}h2{{font-size:21px}}.scroll{{overflow:auto}}table{{border-collapse:collapse;width:100%;font-size:13px}}th,td{{padding:9px 12px;text-align:left;border-bottom:1px solid #dce3eb;vertical-align:top;overflow-wrap:anywhere;min-width:85px}}th{{background:#183047;color:white;position:sticky;top:0}}svg{{width:100%;font:14px Segoe UI,Malgun Gothic,sans-serif}}button{{padding:10px 24px;margin:5px;border:1px solid #246d91;border-radius:5px;cursor:pointer}}.kpi{{display:flex;gap:20px;flex-wrap:wrap}}.kpi div{{background:#183047;color:white;padding:16px 24px;border-radius:8px}}.kpi b{{font-size:26px;display:block}}[hidden]{{display:none!important}}</style><main><h1>{title}</h1>',
             f'<p>데이터 생성: {esc(result["created"])} · 신규/변경 파싱 {collection["parsed"]}건 · 캐시 재사용 {collection["reused"]}건 · 원본 목록 밖 누적 {collection["cached_only"]}건 · 읽기/파싱 오류 {len(collection["errors"])}건</p>',
             '<p>이 페이지는 로컬 파일입니다. 자동 새로고침은 파일만 다시 엽니다. 새 데이터는 앱의 [지금 업데이트] 또는 앱 실행 중 하루 1회 자동 분석으로 생성됩니다.</p>' if dashboard else '',
             '<div class="kpi">' + ''.join(f'<div>{esc(k)}<b>{esc(v)}</b></div>' for k, v in result['summary'].items()) + '</div>',
             '<aside><b>조사 설정</b><p>' + ' · '.join(f'{esc(k)}: {esc(v)}' for k, v in result['settings'].items()) + '</p><b>선택 범위</b><p>' + esc(collection.get('scope', '')) + '</p></aside>',
             '<nav aria-label="가동률 기간"><button onclick="period(\'일\')">일</button><button onclick="period(\'주\')">주 (ISO)</button><button onclick="period(\'월\')">월</button></nav>']
    for t in result["tables"]:
        if dashboard and t['key'] not in {"M01", "M02", "M03"}:
            continue
        unit = t['title'].split(' · ')[-1] if t['title'].startswith('스캔 가동률 · ') else ''
        attrs = f' data-period="{unit}"' + (' hidden' if unit != '일' else '') if unit else ''
        parts.append(f'<section{attrs}><h2>{esc(t["title"])}</h2><div class="scroll">')
        parts.append(trend(t) if t['title'] == '시간순 Actual WPH' else bars(t))
        if t['title'] == '유형별 빈도':
            parts.append(bars(dict(t, title='유형별 Wafer 발생 빈도')))
        if unit:
            parts.append(trend(t))
        parts.append(f'<details{" open" if len(t["rows"]) <= 100 else ""}><summary>전체 표 · {len(t["rows"])}행 (원문 확인)</summary><table><thead><tr>')
        parts.extend('<th>' + esc(h) + '</th>' for h in t['headers'])
        parts.append('</tr></thead><tbody>')
        for row in t['rows']:
            parts.append('<tr>' + ''.join('<td>' + esc(cell) + '</td>' for cell in row) + '</tr>')
        parts.append('</tbody></table></details></div></section>')
    parts.append('<aside><h2>읽기 오류 · 중복 제외</h2>')
    for error in collection['errors']:
        parts.append('<p>' + esc(f'{error["machine"]} / {error["source_file"]}: {error["error"]}') + '</p>')
    parts.extend('<p>' + esc(n) + '</p>' for n in collection['notices'])
    parts.append('</aside><aside><h2>지표 해석 · 한계</h2><ul>' + ''.join('<li>' + esc(n) + '</li>' for n in NOTES) + '</ul></aside>')
    parts.append('<script>function period(p){document.querySelectorAll("[data-period]").forEach(e=>e.hidden=e.dataset.period!==p)}</script></main></html>')
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
