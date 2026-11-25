"""Defect 코드 → 이름(Desc) 표(소유자 2026-11-25): Defect 분석 HTML(rev6 DEFECT_DESC)과 Wafer Map 수정하기(wafermap.DEFECT_CODES)가 같은 표인지,
Wafer Map 범례가 표의 모든 코드를 싣는지, HTML 이 표에 없는 코드는 종전대로(ManReClassify 이름 → #코드) 쓰는지 확인한다."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'vendor'))

from param_manager import wafermap  # noqa: E402

HTMLS = [ROOT / 'frontend/public/defect/AOI_Contrast_Wizard_rev6.html', ROOT / 'frontend/dist/defect/AOI_Contrast_Wizard_rev6.html']


def html_table(path):
    s = path.read_text(encoding='utf-8')
    m = re.search(r"const DEFECT_DESC=new Map\(\[(.*?)\]\);", s)
    assert m, path
    return [(int(c), n) for c, n in re.findall(r"\[(\d+),'([^']*)'\]", m.group(1))], s


class DefectCodeTest(unittest.TestCase):
    def test_same_table(self):
        for p in HTMLS:
            table, _ = html_table(p)
            self.assertEqual(table, wafermap.DEFECT_CODES, p)
        codes = [c for c, _ in wafermap.DEFECT_CODES]
        self.assertEqual(len(codes), len(set(codes)))
        self.assertEqual(dict(wafermap.DEFECT_CODES)[29], 'B R Surface Dark')

    def test_wafermap_tables(self):
        for c, d in wafermap.DEFECT_CODES:
            k = f'{c:03d}'
            self.assertIn(k, wafermap.COLORS)
            self.assertEqual(wafermap.MEAN[k], 'Accept / Good' if c == 0 else d)
            self.assertTrue(wafermap.MEAN_KO[k])
            self.assertIn(wafermap.COLORS[k], wafermap.COLOR_NAME)
        self.assertEqual(len(set(wafermap.COLORS.values())), len(wafermap.COLORS))   # 색이 겹치지 않음
        self.assertNotIn(wafermap.UNKNOWN_COLOR, wafermap.COLORS.values())

    def test_legend_lists_every_code(self):
        from openpyxl import Workbook
        from openpyxl.styles import PatternFill, Font, Border, Side, Alignment
        from openpyxl.utils import get_column_letter
        ws = Workbook().active
        rows = [['___', '000', '777'], ['029', '000', '___']]
        codes = wafermap.write_legend(ws, rows, 2, 3, {}, (PatternFill, Font, Border, Side, Alignment), get_column_letter)
        self.assertEqual(codes[:len(wafermap.DEFECT_CODES)], [f'{c:03d}' for c, _ in wafermap.DEFECT_CODES])
        self.assertEqual(codes[len(wafermap.DEFECT_CODES):], ['___', '777'])   # 표에 없는 코드도 범례 끝에

    def test_html_falls_back(self):
        _, s = html_table(HTMLS[0])
        self.assertIn("const clsOf=(s,code)=>codeName(code,s.cls&&s.cls.names)||`#${code}`;", s)
        self.assertIn("cl=codeName(d.reclassify,r.cls)", s)


if __name__ == '__main__':
    unittest.main()
