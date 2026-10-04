"""Wafer Map 수정하기: 탐색·파싱·TXT↔Excel 변환·**원본 바이트 보존(왕복 동일)**·수정 반영·PNG 검사·어댑터 흐름.

핵심은 '원본 유지': 사람이 손대지 않은 맵은 TXT → Excel → TXT 를 거쳐도 바이트가 완전히 같아야 한다
(인코딩·줄바꿈·앞자리 0 보존). matplotlib 없이도 돌도록 엔진에는 openpyxl 만 쓴다.
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from param_manager import wafermap as wm  # noqa: E402
from param_manager.desktop_wafermap import DesktopWaferMap  # noqa: E402


def sample_rows():
    """8x8 예시 맵: 모서리는 ___(웨이퍼 외곽), 안쪽은 000(양품) + 몇 개 불량."""
    o, g = '___', '000'
    return [
        [o, o, g, g, g, g, o, o],
        [o, g, g, '003', g, g, g, o],
        [g, g, g, g, g, '007', g, g],
        [g, g, '022', g, g, g, g, g],
        [g, g, g, g, g, g, '014', g],
        [g, g, g, '031', g, g, g, g],
        [o, g, g, g, g, g, g, o],
        [o, o, g, g, '090', g, o, o],
    ]


def sample_txt(newline='\n', bom=False):
    rows = sample_rows()
    headers = ['WAFER:W01', 'DEVICE:DEV-A', 'LOT:LOT01', 'ROWCT:8', 'COLCT:8']
    lines = headers + ['RowData:' + ' '.join(r) for r in rows]
    text = newline.join(lines) + newline
    data = text.encode('utf-8')
    return (b'\xef\xbb\xbf' + data) if bom else data


class ParseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, name, data):
        p = self.dir / name
        p.write_bytes(data)
        return p

    def test_decode_newline_and_bom(self):
        _, enc, nl = wm.decode(self._write('a.txt', sample_txt('\r\n')))
        self.assertEqual((enc, nl), ('utf-8', '\r\n'))
        _, enc, nl = wm.decode(self._write('b.txt', sample_txt('\n', bom=True)))
        self.assertEqual((enc, nl), ('utf-8-sig', '\n'))

    def test_parse_txt(self):
        d = wm.parse_txt(self._write('c.txt', sample_txt()))
        self.assertEqual((d['row_count'], d['col_count']), (8, 8))
        self.assertEqual(d['meta']['WAFER'], 'W01')
        self.assertEqual(len(d['rows']), 8)
        self.assertIn('003', d['rows'][1])

    def test_parse_rejects_bad_columns(self):
        broken = sample_txt().replace(b'RowData:___ ___ 000', b'RowData:___ ___', 1)
        with self.assertRaises(ValueError):
            wm.parse_txt(self._write('d.txt', broken))

    def test_discover_skips_generated_and_locks(self):
        self._write('map.txt', sample_txt())
        self._write('map_Converted.txt', sample_txt())     # Excel→TXT 산출물: TXT 모드에서 제외
        self._write('~$map.xlsx', b'lock')                   # Excel 잠금 파일: 항상 제외
        txts = wm.discover(self.dir, ('.txt',))
        self.assertEqual([p.name for p in txts], ['map.txt'])

    def test_png_size(self):
        png = (b'\x89PNG\r\n\x1a\n' + b'\x00\x00\x00\rIHDR'
               + (320).to_bytes(4, 'big') + (240).to_bytes(4, 'big'))
        self.assertEqual(wm.png_size(png), (320, 240))
        self.assertIsNone(wm.png_size(b'not a png'))


class RoundTripTests(unittest.TestCase):
    """원본 유지 점검: 손대지 않은 맵은 왕복 후 바이트가 동일해야 한다."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _roundtrip(self, original_bytes):
        src = self.dir / 'W01.txt'
        src.write_bytes(original_bytes)
        before = src.read_bytes()
        xlsx = self.dir / 'W01_Map_Edit.xlsx'
        wm.txt_to_excel(src, xlsx)
        self.assertEqual(src.read_bytes(), before, '원본 TXT 가 변경되면 안 됩니다')
        back = self.dir / 'W01_Converted.txt'
        wm.excel_to_txt(xlsx, back)
        return back.read_bytes()

    def test_roundtrip_lf_identical(self):
        data = sample_txt('\n')
        self.assertEqual(self._roundtrip(data), data)

    def test_roundtrip_crlf_identical(self):
        data = sample_txt('\r\n')
        self.assertEqual(self._roundtrip(data), data)

    def test_roundtrip_bom_identical(self):
        data = sample_txt('\r\n', bom=True)
        self.assertEqual(self._roundtrip(data), data)
        self.assertTrue(self._roundtrip(data).startswith(b'\xef\xbb\xbf'))

    def test_no_spurious_bom_when_absent(self):
        data = sample_txt('\n')
        self.assertFalse(self._roundtrip(data).startswith(b'\xef\xbb\xbf'))

    def test_roundtrip_trailing_blank_lines(self):
        # 실제 장비 TXT 처럼 마지막 RowData 뒤에 빈 줄이 있어도 그대로 보존
        data = sample_txt('\r\n') + b'\r\n\r\n'
        self.assertEqual(self._roundtrip(data), data)

    def test_roundtrip_empty_header_values(self):
        # 값이 빈 헤더(XDIES:/YDIES: 처럼)도 그대로 보존
        extra = b'XDIES:\r\nYDIES:\r\n'
        data = extra + sample_txt('\r\n')
        self.assertEqual(self._roundtrip(data), data)

    def test_edit_one_die_changes_only_that_code(self):
        """Excel 에서 한 die 를 003→022 로 고치면 TXT 에서도 그 자리만 바뀐다 (나머지 동일)."""
        from openpyxl import load_workbook
        src = self.dir / 'W01.txt'
        src.write_bytes(sample_txt('\n'))
        xlsx = self.dir / 'W01_Map_Edit.xlsx'
        wm.txt_to_excel(src, xlsx)
        wb = load_workbook(xlsx)
        ws = wb['Map_Edit']
        # 원본에서 003 은 (rows[1][3]) → 시트 5행,5열(start_row=5,start_col=2 → row 6, col 5)
        target = ws.cell(6, 5)
        self.assertEqual(target.value, '003')
        target.value = '022'
        wb.save(xlsx)
        back = self.dir / 'W01_Converted.txt'
        wm.excel_to_txt(xlsx, back)
        expect = sample_txt('\n').replace(b'RowData:___ 000 000 003', b'RowData:___ 000 000 022', 1)
        self.assertEqual(back.read_bytes(), expect)


class HeaderEditTests(unittest.TestCase):
    """헤더 수정 시트: 원본/수정 값·수정 값 우선·빈칸이면 원본 유지·맵 크기 보호."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.src = self.dir / 'W01.txt'
        self.src.write_bytes(sample_txt('\r\n'))
        self.xlsx = self.dir / 'W01_Map_Edit.xlsx'
        wm.txt_to_excel(self.src, self.xlsx)

    def tearDown(self):
        self.tmp.cleanup()

    def _set_edit(self, key, new):
        from openpyxl import load_workbook
        wb = load_workbook(self.xlsx)
        he = wb['Header_Edit']
        for r in range(wm.HEADER_EDIT_START, he.max_row + 1):
            if he.cell(r, 1).value == key:
                he.cell(r, 3).value = new
                break
        else:
            raise AssertionError(f'{key} 행을 찾지 못함')
        wb.save(self.xlsx)

    def test_sheet_lists_original_values(self):
        from openpyxl import load_workbook
        wb = load_workbook(self.xlsx)
        self.assertIn('Header_Edit', wb.sheetnames)
        self.assertEqual(wb['Original_Header'].sheet_state, 'hidden')
        he = wb['Header_Edit']
        found = {he.cell(r, 1).value: he.cell(r, 2).value
                 for r in range(wm.HEADER_EDIT_START, he.max_row + 1) if he.cell(r, 1).value}
        self.assertEqual(found['WAFER'], 'W01')
        self.assertEqual(found['DEVICE'], 'DEV-A')
        self.assertEqual(found['ROWCT'], '8')
        desc = {he.cell(r, 1).value: he.cell(r, 4).value
                for r in range(wm.HEADER_EDIT_START, he.max_row + 1) if he.cell(r, 1).value}
        self.assertIn('디바이스', desc['DEVICE'])          # 비고(설명) 열
        self.assertIn('행', desc['ROWCT'])
        self.assertTrue(he.column_dimensions['E'].hidden)  # Line_No 연결 열은 숨김

    def test_empty_edit_keeps_original_bytes(self):
        back = self.dir / 'out.txt'
        wm.excel_to_txt(self.xlsx, back)
        self.assertEqual(back.read_bytes(), sample_txt('\r\n'))   # 아무것도 안 고치면 바이트 동일

    def test_edit_changes_only_that_header(self):
        self._set_edit('DEVICE', 'DEV-B')
        back = self.dir / 'out.txt'
        wm.excel_to_txt(self.xlsx, back)
        expect = sample_txt('\r\n').replace(b'DEVICE:DEV-A', b'DEVICE:DEV-B', 1)
        self.assertEqual(back.read_bytes(), expect)

    def test_protected_size_edit_ignored(self):
        self._set_edit('ROWCT', 99)                               # 맵 크기는 못 바꾼다
        back = self.dir / 'out.txt'
        wm.excel_to_txt(self.xlsx, back)
        self.assertEqual(back.read_bytes(), sample_txt('\r\n'))   # ROWCT 그대로 8

    def test_edit_preserves_leading_zero(self):
        self.src.write_bytes(sample_txt('\r\n').replace(b'LOT:LOT01', b'BCEQU:000', 1))
        wm.txt_to_excel(self.src, self.xlsx)
        self._set_edit('BCEQU', '007')
        back = self.dir / 'out.txt'
        wm.excel_to_txt(self.xlsx, back)
        self.assertIn(b'BCEQU:007', back.read_bytes())
        self.assertNotIn(b'BCEQU:7\r', back.read_bytes())


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        (self.dir / 'sub').mkdir()
        (self.dir / 'W01.txt').write_bytes(sample_txt('\r\n'))
        (self.dir / 'sub' / 'W02.txt').write_bytes(sample_txt('\n'))
        DesktopWaferMap.extra_roots = []
        self.wm = DesktopWaferMap(None)

    def tearDown(self):
        self.tmp.cleanup()

    def test_scan_lists_valid_txt(self):
        r = self.wm.scan({'root': str(self.dir), 'mode': 'txt'})
        self.assertEqual(r['valid'], 2)
        wafers = sorted(i['wafer'] for i in r['items'])
        self.assertEqual(wafers, ['W01', 'W01'])  # both headers say WAFER:W01
        self.assertTrue(all('003' in i['bins'] for i in r['items']))

    def _txt_job_index(self, suffix):
        """src 가 suffix 로 끝나는 scan 항목을 골라 start → 그 파일의 job 인덱스를 돌려준다."""
        r = self.wm.scan({'root': str(self.dir), 'mode': 'txt'})
        ids = [i['id'] for i in r['items'] if i['valid']]
        job = self.wm.start({'ids': ids, 'output': ''})['job']
        return next(n for n, it in enumerate(job['items']) if it['src'].endswith(suffix))

    def test_convert_writes_outputs_next_to_source_and_image_payload(self):
        idx = self._txt_job_index('W01.txt')
        before = (self.dir / 'W01.txt').read_bytes()
        out = self.wm.convert({'index': idx})
        self.assertTrue(Path(out['output']).exists())
        self.assertTrue(out['output'].endswith('W01_Map_Edit.xlsx'))
        self.assertEqual(out['map']['col_count'], 8)
        self.assertIn('003', out['map']['present'])
        self.assertEqual(len(out['map']['images']), 2)
        self.assertEqual((self.dir / 'W01.txt').read_bytes(), before, '원본 보존')
        # 결과를 원본 폴더에서 열 수 있도록 루트가 등록되어야 한다
        self.assertIn(str(self.dir), DesktopWaferMap.extra_roots)

    def test_image_requires_png(self):
        idx = self._txt_job_index('W01.txt')
        self.wm.convert({'index': idx})
        import base64
        with self.assertRaises(ValueError):
            self.wm.image({'index': idx, 'kind': 'code', 'data': base64.b64encode(b'nope').decode()})
        png = (b'\x89PNG\r\n\x1a\n' + b'\x00\x00\x00\rIHDR' + (4).to_bytes(4, 'big') + (4).to_bytes(4, 'big')
               + b'\x00' * 20)
        r = self.wm.image({'index': idx, 'kind': 'code', 'data': base64.b64encode(png).decode()})
        self.assertTrue(Path(r['path']).exists())
        self.assertTrue(r['path'].endswith('_BinCode_Map.png'))

    def test_excel_to_txt_mode_roundtrip_via_adapter(self):
        # W01(CRLF) 을 TXT→Excel 로 만든 뒤, Excel→TXT 모드로 되돌려 원본과 바이트 비교
        self.wm.convert({'index': self._txt_job_index('W01.txt')})   # W01_Map_Edit.xlsx 생성
        wm2 = DesktopWaferMap(None)
        r = wm2.scan({'root': str(self.dir), 'mode': 'excel'})
        start = wm2.start({'ids': [i['id'] for i in r['items'] if i['valid']], 'output': ''})
        idx = next(n for n, it in enumerate(start['job']['items']) if it['src'].endswith('W01_Map_Edit.xlsx'))
        out = wm2.convert({'index': idx})
        self.assertEqual(Path(out['output']).read_bytes(), sample_txt('\r\n'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
