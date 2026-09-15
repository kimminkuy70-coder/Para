import sys
import tempfile
from pathlib import Path
import unittest
from zipfile import ZipFile
from xml.etree import ElementTree
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import openpyxl
from param_manager import wph, wph_status as status


class StatusTests(unittest.TestCase):
    def test_counts_are_per_report_and_per_wafer(self):
        rows = [dict(source_file='a.htm', wafer_statuses=[
            {'status': 'Scan 2D Error. + Aborted. + Skipped.'}, {'status': 'Aborted.'}]),
            dict(source_file='b.htm', wafer_statuses=[{'status': 'Pass'}]),
            dict(source_file='c.htm', wafer_statuses=[])]
        counts, summary, reports, details = status.analyze(rows, [])
        self.assertEqual(counts, {'이슈 포함': 1, '정상 상태만': 1, '상태 확인 불가': 1})
        self.assertEqual(summary[('작업 중단', 'Aborted.')], [1, 2])
        self.assertEqual(len(details), 5)
        self.assertEqual(len(reports), 3)
        self.assertEqual(status.classify('Failed'), [('기타 상태', 'Failed')])
        self.assertEqual(status.classify('Pass'), [])

    def test_html_status_extraction(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'x_BatchReport.htm'
            p.write_text('<table><tr><th>No</th><th>Wafer ID</th><th>Scanned Dice</th>'
                         '<th>Yield</th><th>Pass/Fail</th></tr><tr><td>2</td><td>W2</td>'
                         '<td>0</td><td>0</td><td>Wafer Map Import failed.</td></tr></table>')
            row = wph.extract_row(wph.parse_report(p))
            self.assertEqual(row['wafer_statuses'][0], dict(slot='2', wafer_id='W2', status='Wafer Map Import failed.'))

    def test_workbook_and_chart_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'out.xlsx'
            rows = [dict(source_file='=report.htm', machine='AOI-1',
                         wafer_statuses=[dict(status='Aborted.', slot='1', wafer_id='=ID')])]
            errors = [dict(machine='AOI-2', source_file='broken.htm', error='decode failure')]
            wph.write_wph_excel(p, rows, parse_errors=errors)
            wb = openpyxl.load_workbook(p)
            try:
                summary = wb['07_상태요약']
                self.assertEqual(summary['B2'].value, 2)
                self.assertEqual(summary['B6'].value, 1)
                self.assertEqual(len(summary._charts), 2)
                self.assertEqual(wb['08_Report목록']['B2'].data_type, 's')
                self.assertEqual(wb['09_상태상세']['D2'].data_type, 's')
                self.assertEqual(wb['10_파싱오류']['B2'].value, 'broken.htm')
                for chart in summary._charts:
                    self.assertEqual(len(chart.series), 1)
                    self.assertIn('07_상태요약', chart.series[0].val.numRef.f)
                wb.save(Path(d) / 'roundtrip.xlsx')
            finally:
                wb.close()
            with ZipFile(p) as z:
                self.assertIsNone(z.testzip())
                for name in z.namelist():
                    if name.endswith('.xml'):
                        ElementTree.fromstring(z.read(name))

if __name__ == '__main__':
    unittest.main()
