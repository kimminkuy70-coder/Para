"""멈춘 이유 요약 필터(이슈 #80) — Lot 마다 (Error 원문 · 호기 · 레시피)별 묶음 cx · 작업자 중단 sx.

Error 가 난 Batch Report 의 호기 · 레시피로 센다(재스캔한 호기가 아니라).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from param_manager import batchview
from test_lotmodel import report, full, records


class ReasonFilter(unittest.TestCase):
    def setUp(self):
        self.p = batchview.View(records(
            # BAW: AOI-1 에서 S25 Error → AOI-2 로 옮겨 재스캔 Pass
            ("AOI-1", report("BAW", full(["Scan 2D Error."]), "2026-09-01 10:00", minutes=50)),
            ("AOI-2", report("BAW", [("25", "Pass")], "2026-09-01 11:30", minutes=10)),
            # NSW: AOI-2 에서 같은 Error, 재스캔 없음(Pass 못 함)
            ("AOI-2", report("NSW", full(["Scan 2D Error."]), "2026-09-02 10:00", minutes=50)),
        )).payload()
        self.R = self.p['R']

    def lot(self, code):
        return next(l for l in self.p['lots'] if l['code'] == code)

    def test_error_counted_on_machine_where_it_happened(self):
        baw = self.lot('BAW')
        self.assertEqual(baw['cx'], [['Scan 2D Error.', 'AOI-1', self.R[0]['r'], 1, False]])
        self.assertEqual(baw['sx'], [])
        nsw = self.lot('NSW')
        self.assertEqual(nsw['cx'], [['Scan 2D Error.', 'AOI-2', self.R[2]['r'], 1, True]])

    def test_cx_sums_match_cz(self):
        for lot in self.p['lots']:
            per = {}
            for c, _m, _r, w, _o in lot['cx']:
                per[c] = per.get(c, 0) + w
            self.assertEqual(per, {c: w for c, w, _ in lot['cz']})

    def test_frontend_has_filters(self):
        src = (Path(__file__).resolve().parents[1] / 'frontend' / 'src' / 'BatchLot.tsx').read_text(encoding='utf-8')
        for text in ('레시피 필터', '호기 필터', 'Error 필터', '호기별 표', '필터 지우기'):
            self.assertIn(text, src)


if __name__ == '__main__':
    unittest.main()
