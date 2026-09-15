"""Native WPH charts over numeric snapshots, independent of Excel recalculation."""
from collections import defaultdict
from datetime import datetime
import math


def format_chart(chart, *, horizontal=False):
    from openpyxl.chart.text import RichText
    from openpyxl.drawing.text import Paragraph, ParagraphProperties, CharacterProperties
    from openpyxl.chart.layout import Layout, ManualLayout
    chart.width, chart.height = 34, 17
    chart.legend = None
    chart.x_axis.axPos = 'l' if horizontal else 'b'
    chart.y_axis.axPos = 'b' if horizontal else 'l'
    chart.txPr = RichText(p=[Paragraph(pPr=ParagraphProperties(
        defRPr=CharacterProperties(sz=1100, solidFill='202020')))])
    for axis in (chart.x_axis, chart.y_axis):
        axis.delete = False
        axis.tickLblPos = 'low'
        axis.majorTickMark = 'out'
        axis.minorTickMark = 'none'
        axis.txPr = RichText(p=[Paragraph(pPr=ParagraphProperties(
            defRPr=CharacterProperties(sz=1100, solidFill='202020')))])
        if hasattr(axis, 'tickLblSkip'):
            axis.tickLblSkip = 1
            axis.tickMarkSkip = 1
    if chart.title and chart.title.tx and chart.title.tx.rich:
        for p in chart.title.tx.rich.p:
            p.pPr = ParagraphProperties(defRPr=CharacterProperties(sz=1400, b=True))
        chart.title.overlay = False
    if horizontal:
        chart.layout = Layout(manualLayout=ManualLayout(
            x=.40, y=.14, w=.50, h=.68, xMode='edge', yMode='edge'))
    else:
        chart.layout = Layout(manualLayout=ManualLayout(
            x=.14, y=.14, w=.76, h=.62, xMode='edge', yMode='edge'))


def value_labels(chart, number_format='0'):
    from openpyxl.chart.label import DataLabelList
    labels = DataLabelList()
    labels.showVal = True
    labels.showCatName = False
    labels.showSerName = False
    labels.showLegendKey = False
    labels.showPercent = False
    labels.showBubbleSize = False
    labels.dLblPos = 'outEnd'
    labels.numFmt = number_format
    labels.txPr = chart.txPr
    chart.dataLabels = labels


def category_labels(chart, sheet, column, first, last):
    """Store readable category strings in chart XML as well as cell references."""
    from openpyxl.chart import Reference
    from openpyxl.chart.data_source import AxDataSource, StrRef, StrData, StrVal
    labels = [str(sheet.cell(r, column).value or '') for r in range(first, last + 1)]
    source = AxDataSource(strRef=StrRef(
        f=str(Reference(sheet, min_col=column, min_row=first, max_row=last)),
        strCache=StrData(ptCount=len(labels), pt=[StrVal(idx=i, v=value) for i, value in enumerate(labels)])))
    for series in chart.series:
        series.cat = source


def summarize(rows, valid_wafers):
    machines = defaultdict(lambda: [0, 0, 0.0])
    reports = []
    bands = [0] * 6
    for index, row in enumerate(rows, 1):
        try:
            wafers, scan, batch = (float(row.get(k)) for k in ('wafers', 'avg_scan_sec', 'batch_sec'))
        except (ValueError, TypeError):
            continue
        if not all(math.isfinite(x) for x in (wafers, scan, batch)) or wafers != valid_wafers or scan <= 0 or batch <= 0:
            continue
        machine = str(row.get('machine') or '(호기 미지정)')
        item = machines[machine]
        item[0] += 1
        item[1] += wafers
        item[2] += batch
        end = row.get('batch_end')
        if not isinstance(end, datetime):
            from .wph import parse_batch_datetime
            end = parse_batch_datetime(row.get('batch_end_raw') or str(end or ''))
        if end is not None and end.tzinfo is not None:
            end = end.replace(tzinfo=None)  # equipment wall clock, no timezone conversion
        reports.append([index, wafers * 3600 / batch, row.get('source_file', ''), machine, end, batch / 60])
        bands[min(int(scan // 30), 5)] += 1
    reports.sort(key=lambda r: (r[4] is None, r[4] or datetime.max, r[0]))
    return machines, reports, bands


def add_charts(wb, rows, valid_wafers):
    from openpyxl.chart import BarChart, ScatterChart, Series, Reference
    from openpyxl.utils.datetime import to_excel
    from openpyxl.styles import Font
    data, dashboard = wb['04_그래프데이터'], wb['05_대시보드']
    machines, reports, bands = summarize(rows, valid_wafers)
    timed = [r for r in reports if r[4] is not None]
    blocks = [
        (13, ['호기', '누적 WPH'], [[m, v[1] * 3600 / v[2]] for m, v in machines.items()]),
        (16, ['Batch End (시간순)', 'Actual WPH', 'Report 파일명', '호기', 'Batch 소요시간 (분)'],
         [[to_excel(r[4], wb.epoch), r[1], r[2], r[3], r[5]] for r in timed]),
        (21, ['Avg Scan 시간 구간', 'Report 수'], list(zip(
            ['0~30초 미만', '30~60초 미만', '60~90초 미만', '90~120초 미만', '120~150초 미만', '150초 이상'], bands))),
    ]
    for column, headers, values in blocks:
        for offset, header in enumerate(headers):
            data.cell(1, column + offset, header)
        for r, values_row in enumerate(values or [['유효 데이터 없음', 0]], 2):
            for offset, value in enumerate(values_row):
                cell = data.cell(r, column + offset, value)
                if isinstance(value, str):
                    cell.data_type = 's'
    for r in range(2, len(timed) + 2):
        data.cell(r, 16).number_format = 'yyyy-mm-dd hh:mm:ss'
    dashboard['A9'] = '아래 차트는 조사 시점의 유효 Lot 집계입니다. Raw Data 수동 수정 시 다시 조사하세요.'
    dashboard['A9'].font = Font(color='666666')
    dashboard['A10'] = f'시간 추이: Batch End 기준 / 시간 확인 불가 {len(reports) - len(timed)}건 제외 (집계·분포에는 포함)'
    for r in range(11, 180):
        dashboard.row_dimensions[r].height = 18
    for column, count, title, anchor in [
        (13, len(machines), '호기별 누적 WPH', 'A12'),
        (21, 6, 'Avg Scan 시간 분포 — Report 수', 'A48'),
    ]:
        chart = BarChart()
        chart.title, chart.style, chart.legend = title, 10, None
        format_chart(chart)
        chart.add_data(Reference(data, min_col=column + 1, min_row=1, max_row=max(1, count) + 1), titles_from_data=True)
        category_labels(chart, data, column, 2, max(1, count) + 1)
        chart.y_axis.title = 'Report 수' if column == 21 else 'WPH'
        chart.x_axis.title = '평균 Scan 시간 구간 (초)' if column == 21 else 'AOI 호기'
        chart.y_axis.numFmt = '0' if column == 21 else '0.00'
        chart.y_axis.numFmt.sourceLinked = False
        value_labels(chart, '0"건"' if column == 21 else '0.00" WPH"')
        dashboard.add_chart(chart, anchor)
    for column, title, unit, anchor in [
        (17, '시간순 Actual WPH', 'WPH', 'A84'),
        (20, '시간순 Batch 소요시간', '분', 'A120'),
    ]:
        chart = ScatterChart()
        chart.title, chart.style = title, 13
        chart.scatterStyle = 'lineMarker'
        format_chart(chart)
        chart.x_axis.title = 'Batch End (배치 종료 시각)'
        chart.x_axis.numFmt = 'mm-dd hh:mm'
        chart.x_axis.numFmt.sourceLinked = False
        chart.y_axis.title = unit
        chart.y_axis.numFmt = '0.00'
        chart.y_axis.numFmt.sourceLinked = False
        if timed:
            series = Series(Reference(data, min_col=column, min_row=2, max_row=len(timed) + 1),
                            Reference(data, min_col=16, min_row=2, max_row=len(timed) + 1), title=unit)
            series.marker.symbol = 'circle'
            series.marker.size = 4
            series.smooth = False
            chart.series.append(series)
            start, end = to_excel(timed[0][4], wb.epoch), to_excel(timed[-1][4], wb.epoch)
            # Five visible date/time ticks, including both ends; not viewer defaults.
            lower, upper = (start, end) if end > start else (start - 2 / 1440, end + 2 / 1440)
            chart.x_axis.scaling.min, chart.x_axis.scaling.max = lower, upper
            chart.x_axis.majorUnit = (upper - lower) / 4
            chart.x_axis.numFmt = 'mm-dd hh:mm:ss' if upper - lower < 5 / 1440 else 'yyyy-mm-dd hh:mm'
            chart.x_axis.numFmt.sourceLinked = False
        else:
            dashboard.cell(int(anchor[1:]) - 1, 1, f'{title}: 시간 확인 가능한 유효 Report가 없습니다.')
        dashboard.add_chart(chart, anchor)
    wb.active = wb.index(dashboard)
