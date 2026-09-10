"""WPH 조사 — batch report(.htm) 취합 → WPH 분석 엑셀(헤드리스).

개요
----
Camtek AOI 장비는 스캔할 때마다 Report 폴더(예: ``P:\\AOI-21\\Reports``)에
**batch report(HTML)** 를 쌓는다. 파일명 앞부분이 recipe 이름이다.

  ``2D@RE-GA285ABB_0859840PD-0A_Setup1_KLV_26-Sep-08_(05.06.24)_BatchReport.htm``
   └───────── recipe ──────────┘

이 모듈은

1. Report 폴더에서 **recipe 검색어(포함 검색)로 원하는 리포트만** 골라(카운트·수집·
   이름 목록으로 선택),
2. 각 리포트의 ``[BATCH_INFO]`` 에서 Wafers Scanned / Avg. Scan Time /
   Batch Time / Batch End 를 뽑고(HTML 파서는 사용자가 준 ``batch_report_to_text.py``
   를 이식),
3. 참조 양식(``GH100_..._WPH_...xlsx``)과 **동일한 6시트 수식 엑셀**을 만든다.
   입력(A:E)만 채우면 F:S·통계·이상치·그래프·대시보드가 **엑셀 수식**으로 자동
   계산된다. 여기에 **batch report 생성일자(Batch End)** 열을 맨 끝(U)에 추가한다.

안전 원칙 (반드시 준수)
----------------------
- **원본 read-only**: Report 폴더의 .htm 는 **읽기만** 한다(수정/삭제/이동 금지).
- **산출물은 로컬만**: 취합 텍스트·결과 엑셀은 로컬 폴더에 쓴다(OneDrive 금지).
- 추가 패키지 금지: 표준 라이브러리 + ``openpyxl`` 만 사용.

헤드리스 · 테스트됨(``tests/test_wph.py``). GUI 연결은 ``equip_app`` 의 'WPH 조사' 탭.
"""

from __future__ import annotations

import html
import os
import re
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable

# ---------------------------------------------------------------------------
#  엑셀 구조 상수(참조 양식과 동일)
# ---------------------------------------------------------------------------
CAPACITY = 2000                       # 입력 가능한 리포트 수(행 2..2001)
FIRST_DATA_ROW = 2
LAST_DATA_ROW = FIRST_DATA_ROW + CAPACITY - 1   # 2001
DEFAULT_VALID_WAFERS = 25             # 유효 full-lot 매수(조사 시 변경 가능)

REPORT_EXTS = (".htm", ".html")

# 색상(참조 양식 그대로)
HEADER_FILL = "17365D"                # 진남색 헤더
HEADER_FONT = "FFFFFF"
INPUT_FILL = "E2F0D9"                 # 연녹색 — 원본 입력(A:E, U)
INPUT_FONT = "008000"
FORMULA_FILL = "DDEBF7"               # 연파랑 — 수식(F:S, T)

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}


# ===========================================================================
#  1. HTML batch report 파서 (batch_report_to_text.py 이식)
# ===========================================================================
class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._depth = 0
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "table":
            self._depth += 1
            if self._depth == 1:
                self._table = []
        elif self._depth == 1 and tag == "tr":
            self._row = []
        elif self._depth == 1 and tag in ("td", "th"):
            self._cell = []
        elif self._cell is not None and tag in ("br", "p", "div", "li"):
            self._cell.append(" ")

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if self._depth == 1 and tag in ("td", "th") and self._cell is not None:
            if self._row is not None:
                self._row.append(clean_text("".join(self._cell)))
            self._cell = None
        elif self._depth == 1 and tag == "tr":
            if self._table is not None and self._row and any(self._row):
                self._table.append(self._row)
            self._row = None
        elif tag == "table":
            if self._depth == 1 and self._table:
                self.tables.append(self._table)
                self._table = None
            self._depth = max(0, self._depth - 1)


def clean_text(value: object) -> str:
    text = html.unescape(str(value or ""))
    text = text.replace("\xa0", " ").replace("\u200b", "")
    return re.sub(r"\s+", " ", text).strip()


def read_html_file(path) -> str:
    data = Path(path).read_bytes()
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr", "cp1252", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            pass
    return data.decode("utf-8", errors="replace")


def parse_tables(path) -> list[list[list[str]]]:
    parser = _TableParser()
    parser.feed(read_html_file(path))
    return parser.tables


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _find_wafer_table(tables):
    for table in tables:
        if not table:
            continue
        keys = {normalize_key(x) for x in table[0]}
        if "waferid" in keys and "scanneddice" in keys and "yield" in keys:
            return table
    return None


def _table_pairs(table) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for row in table:
        cells = [clean_text(x) for x in row if clean_text(x)]
        for i in range(0, len(cells) - 1, 2):
            label, value = cells[i], cells[i + 1]
            if label and value:
                pairs.append((label, value))
    return pairs


def parse_report(path) -> dict:
    """batch report 1개 → {file_name, metadata[(k,v)], wafers[dict], table_count}."""
    path = Path(path)
    tables = parse_tables(path)
    wafer_table = _find_wafer_table(tables)

    metadata: list[tuple[str, str]] = []
    for table in tables:
        if table is not wafer_table:
            metadata.extend(_table_pairs(table))

    wafers: list[dict] = []
    if wafer_table:
        headers = [clean_text(x) for x in wafer_table[0]]
        for row in wafer_table[1:]:
            padded = row + [""] * max(0, len(headers) - len(row))
            wafers.append({headers[i]: clean_text(padded[i])
                           for i in range(len(headers))})
    return {
        "file_name": path.name,
        "metadata": metadata,
        "wafers": wafers,
        "table_count": len(tables),
    }


def _meta_lookup(metadata) -> dict:
    return {normalize_key(k): v for k, v in metadata}


def safe_field(row: dict, *names: str) -> str:
    norm = {normalize_key(k): v for k, v in row.items()}
    for name in names:
        v = norm.get(normalize_key(name))
        if v is not None:
            return v
    return ""


# ===========================================================================
#  2. 값 파싱 (시간 → 초, Batch End → datetime)
# ===========================================================================
def hms_to_seconds(text: str) -> int | None:
    """'00:01:44' → 104, '00:53:23' → 3203. MM:SS 도 허용. 못 읽으면 None."""
    s = clean_text(text)
    if not s:
        return None
    m = re.search(r"(\d{1,3}):(\d{1,2}):(\d{1,2})", s)
    if m:
        h, mi, se = (int(x) for x in m.groups())
        return h * 3600 + mi * 60 + se
    m = re.search(r"(\d{1,3}):(\d{1,2})", s)
    if m:
        mi, se = (int(x) for x in m.groups())
        return mi * 60 + se
    return None


def parse_batch_datetime(text: str) -> datetime | None:
    """'30-Aug-26 09:41:31 PM' → datetime. 로케일 독립(월 약어 직접 매핑)."""
    s = clean_text(text)
    if not s:
        return None
    m = re.search(
        r"(\d{1,2})-([A-Za-z]{3})-(\d{2,4})\s+(\d{1,2}):(\d{2}):(\d{2})\s*([AP]M)?",
        s, re.IGNORECASE)
    if not m:
        return None
    day, mon, year, hh, mm, ss, ap = m.groups()
    month = _MONTHS.get(mon.lower())
    if not month:
        return None
    year = int(year)
    if year < 100:
        year += 2000
    hh = int(hh)
    if ap:
        ap = ap.upper()
        if ap == "PM" and hh != 12:
            hh += 12
        elif ap == "AM" and hh == 12:
            hh = 0
    try:
        return datetime(year, month, int(day), hh, int(mm), int(ss))
    except ValueError:
        return None


def extract_row(report: dict) -> dict:
    """parse_report 결과 → 엑셀 입력 한 행.

    반환: {source_file, wafers(int|None), avg_scan_sec(int|None),
           batch_sec(int|None), batch_end(datetime|None), batch_end_raw(str)}
    """
    meta = _meta_lookup(report.get("metadata") or [])
    wafers = meta.get("wafersscanned")
    try:
        wafers = int(re.search(r"-?\d+", str(wafers)).group()) if wafers else None
    except (AttributeError, ValueError):
        wafers = None
    end_raw = meta.get("batchend", "") or ""
    return {
        "source_file": report.get("file_name", ""),
        "wafers": wafers,
        "avg_scan_sec": hms_to_seconds(meta.get("avgscantime", "")),
        "batch_sec": hms_to_seconds(meta.get("batchtime", "")),
        "batch_end": parse_batch_datetime(end_raw),
        "batch_end_raw": clean_text(end_raw),
    }


# ===========================================================================
#  3. Report 폴더 검색 (recipe 접두 매칭)
# ===========================================================================
def _norm_prefix(text: str) -> str:
    """recipe 검색어 매칭용 정규화 — 대소문자·주변 공백 무시(한글·기호는 보존)."""
    return clean_text(text).lower()


def is_report_file(name: str) -> bool:
    return name.lower().endswith(REPORT_EXTS)


def _matches(name: str, query: str) -> bool:
    """검색어가 파일 이름에 **포함**되면 매칭(접두가 아니라 실제 검색).

    공백으로 나뉜 여러 단어는 **모두 포함**돼야 매칭(순서 무관·AND).
    빈 검색어는 모든 report 매칭.
    """
    nm = _norm_prefix(name)
    terms = [t for t in _norm_prefix(query).split() if t]
    return all(t in nm for t in terms)


def list_reports(folder, query: str = "") -> list[str]:
    """폴더 바로 아래의 batch report 파일 이름 목록(정렬). query 가 포함된 것만.

    원본을 열지 않고 **파일 이름만** 본다(빠르다·원본 무접근).
    """
    folder = Path(folder)
    if not folder.is_dir():
        return []
    out = []
    for entry in os.scandir(folder):
        if not entry.is_file():
            continue
        if not is_report_file(entry.name):
            continue
        if not _matches(entry.name, query):
            continue
        out.append(entry.name)
    return sorted(out, key=str.lower)


def count_reports(folder, query: str = "") -> int:
    """검색어가 포함된 리포트 개수(목록을 다 만들지 않고 센다)."""
    folder = Path(folder)
    if not folder.is_dir():
        return 0
    n = 0
    for entry in os.scandir(folder):
        if entry.is_file() and is_report_file(entry.name):
            if _matches(entry.name, query):
                n += 1
    return n


def _resolve_names(folder, query: str, names) -> list[str]:
    """조사 대상 파일 이름 목록 — names 를 주면 그것만(실재·report 만), 없으면 검색."""
    if names is None:
        return list_reports(folder, query)
    folder = Path(folder)
    out = []
    for nm in names:
        if is_report_file(nm) and (folder / nm).is_file():
            out.append(nm)
    return sorted(out, key=str.lower)


def collect_rows(folder, query: str = "", names=None) -> tuple[list[dict], list[tuple[str, str]]]:
    """리포트를 파싱해 입력 행 목록을 만든다(원본 read-only).

    names 를 주면 **그 파일들만** 조사(체크박스로 고른 것), 없으면 검색어 매칭 전부.
    반환: (rows, errors[(파일명, 사유)]). rows 는 파일 이름순.
    """
    rows: list[dict] = []
    errors: list[tuple[str, str]] = []
    for name in _resolve_names(folder, query, names):
        p = Path(folder) / name
        try:
            rows.append(extract_row(parse_report(p)))
        except Exception as exc:  # noqa: BLE001
            errors.append((name, str(exc)))
    return rows, errors


# ===========================================================================
#  4. 취합 텍스트 (batch_report_to_text.py 출력과 동일 형식)
# ===========================================================================
def _report_to_text(report: dict, index: int, total: int) -> str:
    lines = [
        "=" * 100,
        f"[REPORT {index}/{total}]",
        f"SOURCE_FILE: {report['file_name']}",
        f"HTML_TABLE_COUNT: {report['table_count']}",
        "=" * 100,
        "",
        "[BATCH_INFO]",
    ]
    if report["metadata"]:
        lines.extend(f"{k}: {v}" for k, v in report["metadata"])
    else:
        lines.append("No batch metadata found")
    lines.extend(["", "[WAFER_RESULTS]"])
    wafers = report["wafers"]
    if not wafers:
        lines.append("No wafer result table found")
    else:
        lines.append("\t".join(
            ["No", "Lot", "Wafer ID", "Faults", "Scanned Dice",
             "Bad Dice", "Good Dice", "Yield", "Pass/Fail", "Recipe(s)"]))
        for no, row in enumerate(wafers, start=1):
            lines.append("\t".join([
                str(no), safe_field(row, "Lot"), safe_field(row, "Wafer ID"),
                safe_field(row, "Faults"), safe_field(row, "Scanned Dice"),
                safe_field(row, "Bad Dice"), safe_field(row, "Good Dice"),
                safe_field(row, "Yield"), safe_field(row, "Pass/Fail"),
                safe_field(row, "Recipe(s)", "Recipe")]))
    lines.extend(["", f"WAFER_ROW_COUNT: {len(wafers)}", ""])
    return "\n".join(lines)


def build_combined_text(folder, query: str, machine: str, recipe: str,
                        names=None) -> tuple[str, int, list]:
    """리포트를 취합 텍스트로 만든다. names 를 주면 그 파일들만(체크한 것).

    반환: (text, report_count, errors). 헤더에 호기·recipe 를 박는다.
    """
    reports: list[dict] = []
    errors: list[tuple[str, str]] = []
    for name in _resolve_names(folder, query, names):
        try:
            reports.append(parse_report(Path(folder) / name))
        except Exception as exc:  # noqa: BLE001
            errors.append((name, str(exc)))
    parts = [
        "BATCH REPORTS CONSOLIDATED TEXT",
        f"GENERATED_AT: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"MACHINE: {machine}",
        f"RECIPE: {recipe}",
        f"SOURCE_FOLDER: {folder}",
        f"REPORT_FILE_COUNT: {len(reports)}",
        f"PARSE_ERROR_COUNT: {len(errors)}",
        "",
    ]
    for idx, rep in enumerate(reports, start=1):
        parts.append(_report_to_text(rep, idx, len(reports)))
    if errors:
        parts.extend(["=" * 100, "[PARSE_ERRORS]"])
        parts.extend(f"{n}: {m}" for n, m in errors)
        parts.append("")
    text = "\r\n".join("\n".join(parts).splitlines()) + "\r\n"
    return text, len(reports), errors


def write_combined_text(path, folder, query, machine, recipe,
                        names=None) -> tuple[int, list]:
    text, n, errors = build_combined_text(folder, query, machine, recipe, names)
    Path(path).write_text(text, encoding="utf-8-sig")
    return n, errors


# ===========================================================================
#  5. WPH 분석 엑셀 (참조 양식과 동일한 6시트 수식 구조)
# ===========================================================================
def _thin(openpyxl):
    from openpyxl.styles import PatternFill, Font
    return PatternFill, Font


def write_wph_excel(path, rows: list[dict], *, valid_wafers: int = DEFAULT_VALID_WAFERS,
                    title: str = "") -> str:
    """rows(입력 행 목록)로 참조 양식과 동일한 WPH 분석 엑셀을 만든다.

    rows 항목: {source_file, wafers, avg_scan_sec, batch_sec, batch_end|batch_end_raw}
    valid_wafers: 유효 full-lot 매수(기본 25). 시트 이름·Valid 판정·헤더에 반영.
    """
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    n = int(valid_wafers)
    stats_sheet = f"02_{n}매_통계"
    head_fill = PatternFill("solid", fgColor=HEADER_FILL)
    in_fill = PatternFill("solid", fgColor=INPUT_FILL)
    fm_fill = PatternFill("solid", fgColor=FORMULA_FILL)
    head_font = Font(bold=True, color=HEADER_FONT)
    in_font = Font(color=INPUT_FONT)

    wb = openpyxl.Workbook()

    # ---- 00_사용안내 ------------------------------------------------------
    ws0 = wb.active
    ws0.title = "00_사용안내"
    ws0["A1"] = title or f"AOI {n}매 Lot WPH 자동 분석"
    ws0["A1"].font = Font(bold=True, size=14)
    ws0.merge_cells("A1:H1")
    guide = [
        ("입력 위치", "01_Raw_Data 시트의 A:E 열만 입력합니다. 나머지는 수식입니다."),
        ("추가 방법", f"A:E 열에 리포트를 추가하면 F:S·통계가 자동 계산됩니다(최대 {CAPACITY}개)."),
        ("시간 입력", "Avg Scan sec·Batch sec 는 초 단위 숫자입니다. 예: 00:01:44 = 104초."),
        ("자동 계산", "F:S 열과 통계/이상치/그래프/대시보드는 모두 일반 셀 수식입니다."),
        ("분석 조건", f"Wafers Scanned={n}, Avg Scan sec>0, Batch sec>0 인 행만 유효 {n}매 Lot."),
        ("WPH", "Actual WPH = Wafers Scanned × 3,600 ÷ Batch sec (전체 Batch Time 기준)."),
        ("생성일자", "U열은 batch report 의 Batch End(배치 종료시각)입니다."),
        ("호기별 요약", "06_호기별_WPH 시트에서 호기(U열)마다 유효 Lot·WPH를 따로 봅니다."),
        ("색상", "녹색=원본 입력, 파란색=수식 계산, 주황/연빨강=검토·이상 항목."),
        ("호환성", "Excel 표·동적배열·최신 통계함수를 피하고 STDEV/QUARTILE/INDEX 등만 사용."),
    ]
    for i, (k, v) in enumerate(guide, start=3):
        ws0.cell(row=i, column=1, value=k).font = Font(bold=True)
        ws0.cell(row=i, column=2, value=v)
        ws0.merge_cells(start_row=i, start_column=2, end_row=i, end_column=8)
    ws0.column_dimensions["A"].width = 18
    ws0.column_dimensions["B"].width = 18

    # ---- 01_Raw_Data ------------------------------------------------------
    ws = wb.create_sheet("01_Raw_Data")
    headers = ["Report", "Source File", "Wafers Scanned", "Avg Scan sec", "Batch sec",
               "Avg Scan Time", "Batch Time", "Pure Scan Time", "Non-scan Time",
               "Actual WPH", "Theoretical WPH", f"Valid {n}", "Scan Band",
               "Batch Judgment", "Non-scan Judgment", f"{n}매 Avg Scan Time",
               f"{n}매 Batch Time", f"{n}매 Non-scan Time", f"{n}매 Actual WPH",
               "이상치 순번", "호기", "Batch End (생성일자)"]
    for c, h in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=c, value=h)
        cell.fill = head_fill
        cell.font = head_font
        cell.alignment = Alignment(horizontal="center")
    widths = {"A": 10, "B": 80, "C": 15, "D": 14, "E": 12, "F": 15, "G": 15,
              "H": 16, "I": 16, "J": 12, "K": 16, "L": 10, "M": 14, "N": 18,
              "O": 18, "P": 20, "Q": 20, "R": 20, "S": 20, "T": 13, "U": 12, "V": 22}
    for col, w in widths.items():
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A2"

    lo, hi = FIRST_DATA_ROW, LAST_DATA_ROW
    time_fmt, wph_fmt = "[h]:mm:ss", "0.00"
    for r in range(lo, hi + 1):
        ws.cell(row=r, column=6, value=f'=IF(D{r}="","",D{r}/86400)')
        ws.cell(row=r, column=7, value=f'=IF(E{r}="","",E{r}/86400)')
        ws.cell(row=r, column=8, value=f'=IF(OR(C{r}="",D{r}=""),"",C{r}*D{r}/86400)')
        ws.cell(row=r, column=9, value=f'=IF(OR(G{r}="",H{r}=""),"",G{r}-H{r})')
        ws.cell(row=r, column=10, value=f'=IFERROR(C{r}*3600/E{r},"")')
        ws.cell(row=r, column=11, value=f'=IFERROR(3600/D{r},"")')
        ws.cell(row=r, column=12, value=f'=IF(AND(C{r}={n},D{r}>0,E{r}>0),"Y","")')
        ws.cell(row=r, column=13,
                value=(f'=IF(L{r}<>"Y","",IF(D{r}<=100,"1:40 이하",'
                       f'IF(D{r}<=120,"1:41~2:00","2:01~2:30")))'))
        ws.cell(row=r, column=14,
                value=(f'=IF(L{r}<>"Y","",IF(E{r}>\'{stats_sheet}\'!$K$8*86400,"장시간 이상",'
                       f'IF(E{r}<\'{stats_sheet}\'!$J$8*86400,"단시간 이상","정상범위")))'))
        ws.cell(row=r, column=15,
                value=(f'=IF(L{r}<>"Y","",IF(I{r}>\'{stats_sheet}\'!$K$9,"대기 이상",'
                       f'IF(I{r}<\'{stats_sheet}\'!$J$9,"저대기 이상","정상범위")))'))
        ws.cell(row=r, column=16, value=f'=IF($L{r}="Y",$F{r},"")')
        ws.cell(row=r, column=17, value=f'=IF($L{r}="Y",$G{r},"")')
        ws.cell(row=r, column=18, value=f'=IF($L{r}="Y",$I{r},"")')
        ws.cell(row=r, column=19, value=f'=IF($L{r}="Y",$J{r},"")')
        ws.cell(row=r, column=20,
                value=(f'=IF(AND($L{r}="Y",OR($N{r}<>"정상범위",$O{r}<>"정상범위")),'
                       f'COUNT($T$1:T{r - 1})+1,"")'))
        # 스타일/서식
        for col in range(1, 6):          # A:E 입력
            cc = ws.cell(row=r, column=col)
            cc.fill = in_fill
            cc.font = in_font
        for col in range(6, 21):         # F:T 수식
            ws.cell(row=r, column=col).fill = fm_fill
        for col in (6, 7, 8, 9, 16, 17, 18):
            ws.cell(row=r, column=col).number_format = time_fmt
        for col in (10, 11, 19):
            ws.cell(row=r, column=col).number_format = wph_fmt
        for col in (21, 22):                         # U:호기, V:생성일자(입력)
            ws.cell(row=r, column=col).fill = in_fill
            ws.cell(row=r, column=col).font = in_font

    # 실제 데이터 채우기
    for i, row in enumerate(rows):
        r = lo + i
        ws.cell(row=r, column=1, value=i + 1)
        ws.cell(row=r, column=2, value=row.get("source_file", ""))
        if row.get("wafers") is not None:
            ws.cell(row=r, column=3, value=row["wafers"])
        if row.get("avg_scan_sec") is not None:
            ws.cell(row=r, column=4, value=row["avg_scan_sec"])
        if row.get("batch_sec") is not None:
            ws.cell(row=r, column=5, value=row["batch_sec"])
        ws.cell(row=r, column=21, value=row.get("machine", "") or "")   # U: 호기
        end = row.get("batch_end")
        vcell = ws.cell(row=r, column=22)                               # V: 생성일자
        if isinstance(end, datetime):
            vcell.value = end
            vcell.number_format = "yyyy-mm-dd hh:mm:ss"
        else:
            vcell.value = row.get("batch_end_raw", "") or ""

    # ---- 02_통계 ----------------------------------------------------------
    w2 = wb.create_sheet(stats_sheet)
    w2["A1"] = f"{n}매 Lot 수식 기반 통계"
    w2["A1"].font = Font(bold=True, size=12)
    rd = "'01_Raw_Data'"
    summ = [
        ("N2", "원본 입력 수", "O2", f"=COUNT({rd}!$A${lo}:$A${hi})", "P2", "건"),
        ("N3", f"유효 {n}매 Lot", "O3", f'=COUNTIF({rd}!$L${lo}:$L${hi},"Y")', "P3", "건"),
        ("N4", "총 Wafer", "O4", f'=SUMIF({rd}!$L${lo}:$L${hi},"Y",{rd}!$C${lo}:$C${hi})', "P4", "매"),
        ("N5", "누적 WPH", "O5",
         (f'=IFERROR(SUMIF({rd}!$L${lo}:$L${hi},"Y",{rd}!$C${lo}:$C${hi})/'
          f'(SUMIF({rd}!$L${lo}:$L${hi},"Y",{rd}!$E${lo}:$E${hi})/3600),0)'), "P5", "WPH"),
        ("N6", "평균 WPH", "O6", f"=AVERAGE({rd}!$S${lo}:$S${hi})", "P6", "WPH"),
        ("N7", "중앙 WPH", "O7", f"=MEDIAN({rd}!$S${lo}:$S${hi})", "P7", "WPH"),
    ]
    for lk, lv, ok, ov, pk, pv in summ:
        w2[lk] = lv
        w2[lk].font = Font(bold=True)
        w2[ok] = ov
        w2[pk] = pv
    stat_hdr = ["항목", "건수", "평균", "중앙값", "표준편차", "최소", "Q1", "Q3",
                "최대", "IQR 하한", "IQR 상한", "이상 건수"]
    for c, h in enumerate(stat_hdr, start=1):
        cell = w2.cell(row=6, column=c, value=h)
        cell.fill = head_fill
        cell.font = head_font
    stat_rows = [("Avg. Scan Time", "P"), ("Batch Time", "Q"),
                 ("Non-scan Time", "R"), ("Actual WPH", "S")]
    for i, (label, col) in enumerate(stat_rows):
        r = 7 + i
        rng = f"{rd}!${col}${lo}:${col}${hi}"
        w2.cell(row=r, column=1, value=label)
        w2.cell(row=r, column=2, value=f"=COUNT({rng})")
        w2.cell(row=r, column=3, value=f"=AVERAGE({rng})")
        w2.cell(row=r, column=4, value=f"=MEDIAN({rng})")
        w2.cell(row=r, column=5, value=f"=STDEV({rng})")
        w2.cell(row=r, column=6, value=f"=MIN({rng})")
        w2.cell(row=r, column=7, value=f"=QUARTILE({rng},1)")
        w2.cell(row=r, column=8, value=f"=QUARTILE({rng},3)")
        w2.cell(row=r, column=9, value=f"=MAX({rng})")
        w2.cell(row=r, column=10, value=f"=MAX(0,G{r}-1.5*(H{r}-G{r}))")
        w2.cell(row=r, column=11, value=f"=H{r}+1.5*(H{r}-G{r})")
        w2.cell(row=r, column=12,
                value=f'=COUNTIF({rng},"<"&J{r})+COUNTIF({rng},">"&K{r})')
    for col in "BCDEFGHIJKL":
        w2.column_dimensions[col].width = 12
    w2.column_dimensions["A"].width = 16
    w2.column_dimensions["N"].width = 14
    w2.column_dimensions["O"].width = 12

    # ---- 03_이상치 --------------------------------------------------------
    w3 = wb.create_sheet("03_이상치")
    w3["A1"] = f"{n}매 Lot 이상치 자동 목록"
    w3["A1"].font = Font(bold=True, size=12)
    out_hdr = ["Report", "Source File", "Wafers", "Avg Scan Time", "Batch Time",
               "Non-scan Time", "Actual WPH", "Batch Judgment", "Non-scan Judgment",
               "Scan Band", "원본행번호"]
    for c, h in enumerate(out_hdr, start=1):
        cell = w3.cell(row=3, column=c, value=h)
        cell.fill = head_fill
        cell.font = head_font
    src_cols = ["A", "B", "C", "F", "G", "I", "J", "N", "O", "M"]  # → A..J
    for i in range(100):                 # 이상치 표시 용량 100행
        r = 4 + i
        w3.cell(row=r, column=11,
                value=f'=IFERROR(MATCH({i + 1},{rd}!$T${lo}:$T${hi},0),"")')
        for c, sc in enumerate(src_cols, start=1):
            w3.cell(row=r, column=c,
                    value=(f'=IF($K{r}="","",INDEX({rd}!${sc}${lo}:${sc}${hi},$K{r}))'))
    w3.column_dimensions["B"].width = 70
    for col in ("D", "E", "F"):
        for r in range(4, 104):
            w3.cell(row=r, column={"D": 4, "E": 5, "F": 6}[col]).number_format = time_fmt

    # ---- 04_그래프데이터 --------------------------------------------------
    w4 = wb.create_sheet("04_그래프데이터")
    for c, h in enumerate(["Scan Band", "Report Count", "Total Wafers",
                           "Total Batch hr", "Pooled WPH"], start=1):
        w4.cell(row=1, column=c, value=h).font = Font(bold=True)
    bands = ["1:40 이하", "1:41~2:00", "2:01~2:30"]
    for i, band in enumerate(bands):
        r = 2 + i
        w4.cell(row=r, column=1, value=band)
        w4.cell(row=r, column=2,
                value=f'=COUNTIFS({rd}!$L${lo}:$L${hi},"Y",{rd}!$M${lo}:$M${hi},A{r})')
        w4.cell(row=r, column=3,
                value=(f'=SUMIFS({rd}!$C${lo}:$C${hi},{rd}!$L${lo}:$L${hi},"Y",'
                       f'{rd}!$M${lo}:$M${hi},A{r})'))
        w4.cell(row=r, column=4,
                value=(f'=SUMIFS({rd}!$E${lo}:$E${hi},{rd}!$L${lo}:$L${hi},"Y",'
                       f'{rd}!$M${lo}:$M${hi},A{r})/3600'))
        w4.cell(row=r, column=5, value=f"=IFERROR(C{r}/D{r},0)")
    # Avg Scan bin 히스토그램(G:H) / Batch bin(J:K)
    w4.cell(row=1, column=7, value="Avg Scan bin sec").font = Font(bold=True)
    w4.cell(row=1, column=8, value="Count").font = Font(bold=True)
    w4.cell(row=1, column=10, value="Batch bin min").font = Font(bold=True)
    w4.cell(row=1, column=11, value="Count").font = Font(bold=True)
    for i in range(14):
        r = 2 + i
        g = 60 + i * 5
        w4.cell(row=r, column=7, value=g)
        w4.cell(row=r, column=8,
                value=(f'=COUNTIFS({rd}!$L${lo}:$L${hi},"Y",{rd}!$D${lo}:$D${hi},'
                       f'">="&G{r},{rd}!$D${lo}:$D${hi},"<"&G{r}+5)'))
        j = 35 + i * 5
        w4.cell(row=r, column=10, value=j)
        w4.cell(row=r, column=11,
                value=(f'=COUNTIFS({rd}!$L${lo}:$L${hi},"Y",{rd}!$E${lo}:$E${hi},'
                       f'">="&J{r}*60,{rd}!$E${lo}:$E${hi},"<"&(J{r}+5)*60)'))
    for col in "ABCDE":
        w4.column_dimensions[col].width = 14

    # ---- 05_대시보드 ------------------------------------------------------
    w5 = wb.create_sheet("05_대시보드")
    w5["A1"] = f"{n}매 Lot WPH 자동 대시보드"
    w5["A1"].font = Font(bold=True, size=14)
    w5["A3"], w5["C3"], w5["E3"], w5["G3"] = (
        "유효 " + f"{n}매 Lot", "평균 Avg Scan", "평균 Batch Time", "평균 실제 WPH")
    w5["A4"] = f'=COUNTIF({rd}!$L${lo}:$L${hi},"Y")'
    w5["C4"] = f"=AVERAGE({rd}!$P${lo}:$P${hi})"
    w5["E4"] = f"=AVERAGE({rd}!$Q${lo}:$Q${hi})"
    w5["G4"] = f"=AVERAGE({rd}!$S${lo}:$S${hi})"
    w5["A6"], w5["C6"], w5["E6"], w5["G6"] = (
        "중앙 Avg Scan", "중앙 Batch Time", "중앙 실제 WPH", "누적 실제 WPH")
    w5["A7"] = f"=MEDIAN({rd}!$P${lo}:$P${hi})"
    w5["C7"] = f"=MEDIAN({rd}!$Q${lo}:$Q${hi})"
    w5["E7"] = f"=MEDIAN({rd}!$S${lo}:$S${hi})"
    w5["G7"] = (f'=IFERROR(SUMIF({rd}!$L${lo}:$L${hi},"Y",{rd}!$C${lo}:$C${hi})/'
                f'(SUMIF({rd}!$L${lo}:$L${hi},"Y",{rd}!$E${lo}:$E${hi})/3600),0)')
    for coord in ("C4", "E4", "C7", "E7"):
        w5[coord].number_format = time_fmt
    for coord in ("G4", "G7"):
        w5[coord].number_format = wph_fmt
    for col in "ABCDEFGH":
        w5.column_dimensions[col].width = 16

    # ---- 06_호기별_WPH ----------------------------------------------------
    #  통합 엑셀이라 호기별 WPH 요약을 한 시트에 따로 둔다(호기 열 U 기준 수식).
    machines_seen = []
    for row in rows:
        mm = str(row.get("machine", "") or "").strip()
        if mm and mm not in machines_seen:
            machines_seen.append(mm)
    w6 = wb.create_sheet("06_호기별_WPH")
    w6["A1"] = "호기별 WPH 요약"
    w6["A1"].font = Font(bold=True, size=12)
    w6["A2"] = (f"유효 {n}매 Lot(호기 열 U 기준)만 집계합니다. "
                "통계·WPH는 각 호기별 합산입니다.")
    w6["A2"].font = Font(color="808080")
    m6_hdr = ["호기", f"유효 {n}매 Lot", "총 Wafer", "누적 WPH", "평균 WPH",
              "평균 Avg Scan", "평균 Batch Time"]
    for c, h in enumerate(m6_hdr, start=1):
        cell = w6.cell(row=3, column=c, value=h)
        cell.fill = head_fill
        cell.font = head_font
        cell.alignment = Alignment(horizontal="center")
    uU = f"{rd}!$U${lo}:$U${hi}"          # 호기 열
    uL = f"{rd}!$L${lo}:$L${hi}"          # Valid
    uC = f"{rd}!$C${lo}:$C${hi}"          # Wafers
    uE = f"{rd}!$E${lo}:$E${hi}"          # Batch sec
    for i, mm in enumerate(machines_seen):
        r = 4 + i
        a = f"$A{r}"
        w6.cell(row=r, column=1, value=mm)
        w6.cell(row=r, column=2, value=f'=COUNTIFS({uU},{a},{uL},"Y")')
        w6.cell(row=r, column=3, value=f'=SUMIFS({uC},{uU},{a},{uL},"Y")')
        w6.cell(row=r, column=4,
                value=(f'=IFERROR(SUMIFS({uC},{uU},{a},{uL},"Y")/'
                       f'(SUMIFS({uE},{uU},{a},{uL},"Y")/3600),0)'))
        w6.cell(row=r, column=5,
                value=f'=IFERROR(AVERAGEIFS({rd}!$S${lo}:$S${hi},{uU},{a},{uL},"Y"),0)')
        w6.cell(row=r, column=6,
                value=f'=IFERROR(AVERAGEIFS({rd}!$P${lo}:$P${hi},{uU},{a},{uL},"Y"),0)')
        w6.cell(row=r, column=7,
                value=f'=IFERROR(AVERAGEIFS({rd}!$Q${lo}:$Q${hi},{uU},{a},{uL},"Y"),0)')
        w6.cell(row=r, column=4).number_format = wph_fmt
        w6.cell(row=r, column=5).number_format = wph_fmt
        w6.cell(row=r, column=6).number_format = time_fmt
        w6.cell(row=r, column=7).number_format = time_fmt
    w6.column_dimensions["A"].width = 14
    for col in "BCDEFG":
        w6.column_dimensions[col].width = 16

    wb.save(str(path))
    return str(path)


# ===========================================================================
#  6. 로컬 출력 경로 (OneDrive 금지 — 전부 로컬)
# ===========================================================================
def sanitize(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", str(name or "")).strip(" .") or "WPH"


def new_investigation_dir(local_root: str) -> str:
    """로컬 `{local}/WPH조사/{조사시각}/` 경로를 만들어 돌려준다."""
    from . import localdirs, workdirs
    base = os.path.join(localdirs.active_root() if not local_root else local_root,
                        "WPH조사")
    d = os.path.join(base, f"조사_{workdirs.stamp()}")
    os.makedirs(d, exist_ok=True)
    return d


def text_filename(machine: str, recipe: str) -> str:
    """호기별 취합 텍스트 파일명 — 호기·recipe 를 박는다(조사 폴더가 시각 기준)."""
    return f"{sanitize(machine)}_{sanitize(recipe)}_취합.txt"


def combined_excel_filename(machines) -> str:
    """통합 WPH 결과 엑셀 파일명 — 여러 호기를 하나로 합친다.

    호기가 적으면 이름을 나열하고, 많으면 개수로 줄인다(파일명 길이 제한).
    """
    ms = [sanitize(m) for m in machines if str(m).strip()]
    if not ms:
        tag = "통합"
    elif len(ms) <= 4:
        tag = "_".join(ms)
    else:
        tag = f"{ms[0]}외{len(ms) - 1}"
    return f"WPH_{tag}_통합.xlsx"


def target_filenames(machine: str, recipe: str) -> tuple[str, str]:
    """(취합텍스트 파일명, 결과엑셀 파일명) — 하위호환용(호기별 단일 엑셀)."""
    from . import workdirs
    stem = f"{sanitize(machine)}_{sanitize(recipe)}_{workdirs.stamp()}"
    return f"{stem}_취합.txt", f"{stem}_WPH.xlsx"
