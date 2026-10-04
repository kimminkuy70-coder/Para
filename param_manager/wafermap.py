"""Wafer Map 수정하기 — AOI Wafer Map TXT 를 Excel 로 펼쳐 Bin Code 를 고치고 다시 TXT 로 되돌린다.

외부 도구 'Wafer Map Converter WebView2 v6' 이식. **변환(TXT↔Excel) 로직은 원본 그대로**(openpyxl 전용)
옮겼고, 원본이 numpy+matplotlib 로 그리던 맵 이미지(BinCode_Map · BinMeaning_Map PNG)만 추가 패키지 금지
규칙(openpyxl+tksheet) 때문에 WebView canvas 에서 그린다(Color·Gray 매칭과 같은 방식). 이 모듈은:

* 폴더에서 TXT(또는 편집한 Excel) 를 찾고(`discover`),
* TXT 를 파싱해(`parse_txt`) 헤더·메타·RowData 를 그대로 보존하고,
* TXT → Excel(`txt_to_excel`): Map_Edit 시트(텍스트 '@' 셀, 색칠, 범례·수정 가이드) + Original_Header +
  veryHidden `_Converter_Metadata`(행/열·시작 위치·원본 인코딩·줄바꿈·코드 목록),
* Excel → TXT(`excel_to_txt`): 메타데이터로 **원본 바이트 그대로** 복원(인코딩·줄바꿈, 앞자리 0 `_code`),
* 이미지로 그릴 맵 데이터(`map_payload`)를 돌려준다 — 픽셀은 화면에서.

가장 중요한 원칙: **원본 TXT 는 건드리지 않는다.** 변환은 항상 새 파일(`_Map_Edit.xlsx` / `_Converted.txt`)
을 만들고, 사람이 손대지 않은 맵은 TXT→Excel→TXT 를 거쳐도 바이트가 동일하다.
"""
from pathlib import Path
from collections import Counter
import json


def decode(path):
    data = Path(path).read_bytes()
    nl = '\r\n' if b'\r\n' in data else '\n'
    # utf-8-sig only when a BOM is really there; it also decodes BOM-less UTF-8 and
    # Excel -> TXT would then add a BOM the original never had.
    for enc in (('utf-8-sig',) if data.startswith(b'\xef\xbb\xbf') else ()) + ('utf-8', 'cp949', 'euc-kr'):
        try:
            return data.decode(enc), enc, nl
        except UnicodeDecodeError:
            pass
    raise ValueError('지원 인코딩으로 TXT를 읽을 수 없습니다.')


def parse_txt(path):
    text, enc, nl = decode(path)
    headers = []
    rows = []
    meta = {}
    for line in text.splitlines():
        if line.startswith('RowData:'):
            rows.append(line[8:].strip().split())
        else:
            headers.append(line)
            if ':' in line:
                k, v = line.split(':', 1)
                meta[k.strip()] = v.strip()
    if not {'ROWCT', 'COLCT'} <= meta.keys():
        raise ValueError('ROWCT/COLCT가 없습니다.')
    rc, cc = int(meta['ROWCT']), int(meta['COLCT'])
    if len(rows) != rc:
        raise ValueError(f'RowData 행 오류: {len(rows)}/{rc}')
    bad = [i + 1 for i, r in enumerate(rows) if len(r) != cc]
    if bad:
        raise ValueError(f'열 수 오류 Row: {bad[:8]}')
    return {'headers': headers, 'rows': rows, 'meta': meta, 'encoding': enc, 'newline': nl,
            'row_count': rc, 'col_count': cc}


def discover(root, suffixes, skip_generated=True):
    root = Path(root)
    out = []
    # TXT mode skips TXT made by Excel -> TXT; Excel mode must keep *_Map_Edit.xlsx, which is
    # exactly what users edit and convert back. '~$' files are Excel's lock files.
    generated = ('_Converted',) if '.txt' in suffixes else ()
    for p in root.rglob('*'):
        if not p.is_file() or p.suffix.lower() not in suffixes or p.name.startswith('~$'):
            continue
        if skip_generated and any(x in p.stem for x in generated):
            continue
        out.append(p)
    return sorted(out, key=lambda p: str(p).lower())


def _load_heavy():
    from openpyxl import Workbook, load_workbook
    from openpyxl.styles import PatternFill, Font, Border, Side, Alignment
    from openpyxl.utils import get_column_letter
    return Workbook, load_workbook, PatternFill, Font, Border, Side, Alignment, get_column_letter


COLORS = {'___': 'FFFFFF', '000': 'DDF3DF', '003': 'D62728', '007': 'D08C00', '014': 'E53935',
          '022': '7B1FA2', '031': '1565C0', '090': '666666'}
MEAN = {'000': 'Accept / Good', '003': 'Metal Residue', '007': 'Irregular Bump', '014': 'RDL Defect',
        '022': 'Scratch', '031': 'Foreign Material', '090': 'Customer Map Reject Die', '___': 'Outside Wafer'}
MEAN_KO = {'000': '양품', '003': '금속 잔류물', '007': '범프 불량', '014': 'RDL 불량', '022': '스크래치',
           '031': '이물', '090': '고객 맵 Reject Die', '___': '웨이퍼 외곽 (Die 없음)'}
COLOR_NAME = {'FFFFFF': '흰색', 'DDF3DF': '연두색', 'D62728': '빨강', 'D08C00': '주황', 'E53935': '선홍',
              '7B1FA2': '보라', '1565C0': '파랑', '666666': '회색', 'F4B183': '살구색'}
UNKNOWN_COLOR = 'F4B183'
IMAGE_KINDS = [('code', 'BinCode_Map', 'Bin Code Map'), ('meaning', 'BinMeaning_Map', 'Bin Meaning Map')]


def image_base(out):
    # Output path without its extension. Not with_suffix(''): 'LOT.01_Map_Edit.xlsx' must keep 'LOT.01'.
    out = Path(out)
    return out.with_name(out.name[:-len(out.suffix)] if out.suffix else out.name)


def image_paths(base):
    return [(label, base.with_name(base.name + '_' + suf + '.png')) for _, suf, label in IMAGE_KINDS]


def _font_color(fill):
    r, g, b = (int(fill[i:i + 2], 16) for i in (0, 2, 4))
    return 'FFFFFF' if (r * 299 + g * 587 + b * 114) / 1000 < 140 else '000000'


def _cell_style(code, cache, PatternFill, Font, Border, Side, Alignment):
    # One shared style set per code; the legend uses the same objects, so a copied
    # legend cell pastes exactly like a map die (value, fill and font).
    if code not in cache:
        fill = COLORS.get(code, UNKNOWN_COLOR)
        thin = Side(style='thin', color='B7B7B7')
        cache[code] = (PatternFill('solid', fgColor=fill), Border(left=thin, right=thin, top=thin, bottom=thin),
                       Alignment(horizontal='center', vertical='center'), Font(size=7, color=_font_color(fill)))
    return cache[code]


def _apply(cell, code, cache, styles):
    fill, border, align, font = _cell_style(code, cache, *styles)
    cell.value = code
    cell.fill = fill
    cell.border = border
    cell.alignment = align
    cell.font = font
    cell.number_format = '@'


def write_legend(ws, rows, rc, cc, cache, styles, get_column_letter):
    """Bin Code legend to the right of the map (one blank column gap)."""
    PatternFill, Font, Border, Side, Alignment = styles
    col = cc + 3
    L = lambda i: get_column_letter(col + i)  # noqa: E731
    present = sorted({x for r in rows for x in r})
    codes = [x for x in ['000', '003', '007', '014', '022', '031', '090', '___'] if x in COLORS] + \
            [x for x in present if x not in COLORS]
    first, last = '$B$5', f'${get_column_letter(cc + 1)}${4 + rc}'
    head_fill = PatternFill('solid', fgColor='1F4E78')
    head_font = Font(bold=True, color='FFFFFF', size=9)
    thin = Side(style='thin', color='B7B7B7')
    box = Border(left=thin, right=thin, top=thin, bottom=thin)
    ws.cell(2, col, 'Bin Code 범례 · 수정 가이드').font = Font(bold=True, size=12, color='1F4E78')
    for i, title in enumerate(['Bin Code', '색상', 'Defect 종류', '설명 (한글)', '맵 수량', '이 맵에 있음']):
        c = ws.cell(4, col + i, title)
        c.fill = head_fill
        c.font = head_font
        c.alignment = Alignment(horizontal='center', vertical='center')
        c.border = box
    for n, code in enumerate(codes):
        r = 5 + n
        fill = COLORS.get(code, UNKNOWN_COLOR)
        _apply(ws.cell(r, col), code, cache, styles)
        info = [f'{COLOR_NAME.get(fill, "")} (#{fill})', MEAN.get(code, 'Unknown Bin ' + code),
                MEAN_KO.get(code, '미정의 Bin (색상 규칙 없음)'),
                f'=SUMPRODUCT(--({first}:{last}="{code}"))', '●' if code in present else '']
        for i, v in enumerate(info, 1):
            c = ws.cell(r, col + i, v)
            c.border = box
            c.font = Font(size=9)
            c.alignment = Alignment(horizontal='center' if i in (4, 5) else 'left', vertical='center')
        ws.cell(r, col + 1).fill = PatternFill('solid', fgColor=fill)
        ws.cell(r, col + 1).font = Font(size=9, color=_font_color(fill))
    r = 5 + len(codes)
    ws.cell(r, col + 3, 'Die 합계 (외곽 ___ 제외)').font = Font(bold=True, size=9)
    c = ws.cell(r, col + 4, f'=SUMPRODUCT(--({first}:{last}<>"___"))')
    c.font = Font(bold=True, size=9)
    c.alignment = Alignment(horizontal='center')
    guide = ['수정 방법',
             '1. 왼쪽 범례의 Bin Code 셀(색이 칠해진 셀)을 선택해 Ctrl+C 로 복사합니다.',
             '2. 맵에서 바꿀 die 셀(여러 셀 선택 가능)을 선택하고 Ctrl+V 로 붙여넣습니다. 코드와 색상이 함께 바뀝니다.',
             '3. 직접 입력할 때는 반드시 세 자리 코드(예: 003)로 입력하세요. 셀은 텍스트 형식이라 앞자리 0이 유지됩니다.',
             '4. ___ (웨이퍼 외곽) 셀은 die가 없는 위치이므로 바꾸지 마세요. 맵 크기(행/열)도 바꾸지 마세요.',
             '5. 맵 수량은 수정 즉시 다시 계산됩니다. 저장 후 프로그램에서 [Excel → TXT] 로 변환하면 수정된 TXT와 맵 이미지가 생성됩니다.',
             '* 범례에 없는 코드는 Unknown Bin(살구색)으로 표시되며 TXT에는 그대로 저장됩니다.']
    for i, text in enumerate(guide):
        c = ws.cell(r + 2 + i, col, text)
        c.font = Font(bold=(i == 0), size=10 if i == 0 else 9, color='1F4E78' if i == 0 else '333333')
    for i, w in enumerate([10, 16, 24, 24, 10, 11]):
        ws.column_dimensions[L(i)].width = w
    return codes


def map_payload(rows, meta, base):
    """Everything the WebView canvas needs to draw BinCode_Map / BinMeaning_Map, so no
    numpy/matplotlib is added (original `create_images` logic, moved to the screen).

    rows[0] is the top of the wafer map (as in the Excel row labels and the matplotlib
    `origin='lower'` image). `present` is the legend order; `___` (outside wafer) and the
    notch-at-6-o'clock marker are drawn by the renderer."""
    counts = Counter(x for r in rows for x in r)
    present = ['000'] + [x for x in sorted(counts) if x not in ('000', '___')] if '000' in counts \
        else [x for x in sorted(counts) if x != '___']
    return {
        'wafer': meta.get('WAFER', Path(base).name),
        'row_count': len(rows), 'col_count': len(rows[0]) if rows else 0,
        'rows': rows,
        'counts': {k: counts[k] for k in counts},
        'present': present,
        'colors': COLORS, 'unknown_color': UNKNOWN_COLOR,
        'mean': MEAN, 'mean_ko': MEAN_KO,
        'images': [{'kind': label, 'mode': mode, 'path': str(path)}
                   for (mode, _, label), (_, path) in zip(IMAGE_KINDS, image_paths(Path(base)))],
    }


def txt_to_excel(src, out):
    Workbook, _, PatternFill, Font, Border, Side, Alignment, get_column_letter = _load_heavy()
    styles = (PatternFill, Font, Border, Side, Alignment)
    cache = {}
    d = parse_txt(src)
    rows = d['rows']
    rc = d['row_count']
    cc = d['col_count']
    wb = Workbook()
    ws = wb.active
    ws.title = 'Map_Edit'
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = 'B5'
    ws.cell(1, 2, f"{d['meta'].get('WAFER', Path(src).stem)} Map Edit ({cc} x {rc})")
    ws.cell(1, 2).font = Font(bold=True, size=14, color='FFFFFF')
    ws.cell(1, 2).fill = PatternFill('solid', fgColor='1F4E78')
    ws.merge_cells(start_row=1, start_column=2, end_row=1, end_column=cc + 1)
    for c in range(cc):
        ws.cell(4, 2 + c, c)
        ws.column_dimensions[get_column_letter(2 + c)].width = 3.15
    for r, row in enumerate(rows):
        ws.cell(5 + r, 1, rc - 1 - r)
        ws.row_dimensions[5 + r].height = 17
        for c, code in enumerate(row):
            _apply(ws.cell(5 + r, 2 + c), code, cache, styles)
    write_legend(ws, rows, rc, cc, cache, styles, get_column_letter)
    h = wb.create_sheet('Original_Header')
    h.append(['Line_No', 'Original_Header_Line'])
    for i, line in enumerate(d['headers'], 1):
        h.append([i, line])
    m = wb.create_sheet('_Converter_Metadata')
    m['A1'] = json.dumps({'row_count': rc, 'col_count': cc, 'start_row': 5, 'start_col': 2,
                          'source_encoding': d['encoding'],
                          'source_newline': 'CRLF' if d['newline'] == '\r\n' else 'LF',
                          'valid_codes': sorted({x for r in rows for x in r})}, ensure_ascii=False)
    m.sheet_state = 'veryHidden'
    wb.save(out)
    return {'output': str(out), 'map': map_payload(rows, d['meta'], image_base(out))}


def _code(v):
    # A die typed as 3 is stored by Excel as a number; restore the three-digit code.
    if isinstance(v, (int, float)) and not isinstance(v, bool) and float(v).is_integer():
        return f'{int(v):03d}'
    return str(v).strip()


def excel_to_txt(src, out):
    _, load_workbook, *_ = _load_heavy()
    wb = load_workbook(src, data_only=False)
    if '_Converter_Metadata' in wb.sheetnames:
        md = json.loads(wb['_Converter_Metadata']['A1'].value)
        ws = wb['Map_Edit']
        rc, cc = int(md['row_count']), int(md['col_count'])
        sr, sc = int(md.get('start_row', 5)), int(md.get('start_col', 2))
        headers = [str(wb['Original_Header'].cell(r, 2).value)
                   for r in range(2, wb['Original_Header'].max_row + 1)
                   if wb['Original_Header'].cell(r, 2).value is not None]
        enc = md.get('source_encoding', 'utf-8')
        nl = '\r\n' if md.get('source_newline') == 'CRLF' else '\n'
    elif 'Map_수정' in wb.sheetnames and '원본_헤더' in wb.sheetnames:
        ws = wb['Map_수정']
        h = wb['원본_헤더']
        vals = {str(h.cell(r, 1).value): '' if h.cell(r, 2).value is None else str(h.cell(r, 2).value)
                for r in range(2, h.max_row + 1) if h.cell(r, 1).value is not None}
        rc, cc = int(vals['ROWCT']), int(vals['COLCT'])
        sr, sc = 5, 2
        headers = [f'{k}:{v}' for k, v in vals.items()]
        enc = 'utf-8'
        nl = '\r\n'
    else:
        raise ValueError('지원하는 변환 Excel 형식이 아닙니다.')
    rows = []
    for r in range(rc):
        row = []
        for c in range(cc):
            v = ws.cell(sr + r, sc + c).value
            if v is None or not str(v).strip():
                raise ValueError(f'빈 맵 셀: {ws.cell(sr + r, sc + c).coordinate}')
            row.append(_code(v))
        rows.append(row)
    Path(out).write_text(nl.join(headers + ['RowData:' + ' '.join(r) for r in rows]) + nl, encoding=enc, newline='')
    meta = {}
    for x in headers:
        if ':' in x:
            k, v = x.split(':', 1)
            meta[k] = v
    return {'output': str(out), 'map': map_payload(rows, meta, image_base(out))}


def png_size(data: bytes):
    """(width, height) from a PNG header, or None — so the adapter can reject anything that
    is not the map image the UI was asked to produce (mirrors colorgray.jpeg_size)."""
    if data[:8] != b'\x89PNG\r\n\x1a\n' or data[12:16] != b'IHDR':
        return None
    return int.from_bytes(data[16:20], 'big'), int.from_bytes(data[20:24], 'big')
