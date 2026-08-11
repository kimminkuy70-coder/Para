"""초기 설정 3개 파일 I/O (재설계) — 저장 폴더 안의 독립 엑셀 파일.

- 장비 IP 주소.xlsx : 시트 "장비 IP 주소", 헤더 [호기, IP]. **호기 버튼·IP 매칭의 기준**.
- 참고자료.xlsx      : 사람이 자유롭게 메모하는 자유형 표(셀 색상 지원).
- 특이사항.xlsx      : 시트 "특이사항", 헤더 = engine.SPECIAL_HEADERS(셀 색상 지원).

셀 색상은 각 파일에 openpyxl PatternFill 로 저장/복원한다. colors={(row,col): '#RRGGBB'}.
(row,col 은 0-based 데이터 좌표. 특이사항은 헤더 1행 아래, 참고자료는 그리드 그대로.)
"""

from __future__ import annotations

import os

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill

from . import engine

IP_FILENAME = "장비 IP 주소.xlsx"
REF_FILENAME = "참고자료.xlsx"
SPECIAL_FILENAME = "특이사항.xlsx"
IP_SHEET = "장비 IP 주소"
REF_SHEET = "참고자료"
SPECIAL_SHEET = "특이사항"
# 접속ID 는 장비마다 다를 수 있고 **여러 사람이 같이 써야 하므로** 공유 파일에 둔다.
# (비밀번호는 절대 저장하지 않는다 — 메모리에만.)
IP_HEADERS = ["호기", "IP", "접속ID"]
DEFAULT_LOGIN_ID = "amkor"          # 비어 있을 때만 쓰는 기본값
REF_DEFAULT_HEADERS = ["구분", "내용", "비고"]     # 자유형이라 사람이 바꿔도 됨
SPECIAL_HEADERS = list(engine.SPECIAL_HEADERS)
SPECIAL_BOOL_COL = engine.SPECIAL_BOOL_COL


def ip_path(save_dir: str) -> str:
    return os.path.join(save_dir, IP_FILENAME)


def ref_path(save_dir: str) -> str:
    return os.path.join(save_dir, REF_FILENAME)


def special_path(save_dir: str) -> str:
    return os.path.join(save_dir, SPECIAL_FILENAME)


# --------------------------------------------------------------------------
# 공통: 헤더 스타일 / 색상 read·write
# --------------------------------------------------------------------------
def _style_header(ws) -> None:
    fill = PatternFill("solid", fgColor="1F4E78")
    white = Font(color="FFFFFF", bold=True)
    for c in ws[1]:
        c.fill = fill
        c.font = white
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.freeze_panes = "A2"


def _argb(hx: str) -> str:
    return "FF" + str(hx).lstrip("#").upper()[-6:]


def _read_colors(ws, nrows: int, ncols: int, row_offset: int) -> dict:
    """데이터 셀의 채우기색 → {(r,c): '#RRGGBB'}. row_offset=헤더 유무(0/1)."""
    colors = {}
    for r in range(nrows):
        for c in range(ncols):
            cell = ws.cell(r + 1 + row_offset, c + 1)
            fill = cell.fill
            if fill is not None and fill.patternType == "solid":
                rgb = getattr(fill.fgColor, "rgb", None)
                if isinstance(rgb, str) and len(rgb) == 8 and \
                        rgb.upper() not in ("00000000", "FFFFFFFF"):
                    colors[(r, c)] = "#" + rgb[-6:]
    return colors


def _apply_colors(ws, colors: dict, row_offset: int) -> None:
    for (r, c), hx in (colors or {}).items():
        try:
            ws.cell(r + 1 + row_offset, c + 1).fill = PatternFill("solid", fgColor=_argb(hx))
        except Exception:  # noqa: BLE001
            pass


def _first_sheet(wb, preferred: str):
    return wb[preferred] if preferred in wb.sheetnames else wb[wb.sheetnames[0]]


# --------------------------------------------------------------------------
# 장비 IP 주소 (호기·IP)
# --------------------------------------------------------------------------
def create_blank_ip(path: str) -> str:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = IP_SHEET
    ws.append(IP_HEADERS)
    _style_header(ws)
    for col, w in zip("ABC", (14, 18, 16)):
        ws.column_dimensions[col].width = w
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    wb.save(path)
    return path


def load_ip(path: str) -> list[dict]:
    """장비 IP 주소.xlsx → [{호기, IP}] (헤더 변동 허용, 첫 두 칸 폴백)."""
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = _first_sheet(wb, IP_SHEET)
    heads = [engine._s(c.value).strip() for c in ws[1]]
    hidx = {h: i for i, h in enumerate(heads)}
    out = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row is None or all(v in (None, "") for v in row):
            continue
        ho = (engine._s(row[hidx["호기"]]).strip() if "호기" in hidx and hidx["호기"] < len(row)
              else (engine._s(row[0]).strip() if row else ""))
        ip = (engine._s(row[hidx["IP"]]).strip() if "IP" in hidx and hidx["IP"] < len(row)
              else (engine._s(row[1]).strip() if len(row) > 1 else ""))
        if not ho:
            continue
        uid = (engine._s(row[hidx["접속ID"]]).strip()
               if "접속ID" in hidx and hidx["접속ID"] < len(row) else "")
        out.append({"호기": ho, "IP": ip, "접속ID": uid})
    wb.close()
    return out


def save_ip(path: str, rows: list[dict]) -> str:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = IP_SHEET
    ws.append(IP_HEADERS)
    for r in rows:
        ws.append([engine._s(r.get(h)) for h in IP_HEADERS])
    _style_header(ws)
    for col, w in zip("ABC", (14, 18, 16)):
        ws.column_dimensions[col].width = w
    wb.save(path)
    return path


def machines(ip_rows: list[dict]) -> list[str]:
    out = []
    for r in ip_rows:
        m = engine._s(r.get("호기")).strip()
        if m and m not in out:
            out.append(m)
    return out


def ip_for(ip_rows: list[dict], machine: str) -> str:
    for r in ip_rows:
        if engine._s(r.get("호기")).strip() == engine._s(machine).strip():
            return engine._s(r.get("IP")).strip()
    return ""


def login_id_for(ip_rows: list[dict], machine: str) -> str:
    """호기의 장비 접속 ID(공유 파일). 비어 있으면 기본값."""
    for r in ip_rows:
        if engine._s(r.get("호기")).strip() == engine._s(machine).strip():
            uid = engine._s(r.get("접속ID")).strip()
            if uid:
                return uid
    return DEFAULT_LOGIN_ID


def set_login_id(ip_rows: list[dict], machine: str, login_id: str) -> bool:
    """호기의 접속 ID 기록(공유 파일에 저장하기 위한 갱신). 반환: 바뀌었는가."""
    machine = engine._s(machine).strip()
    login_id = engine._s(login_id).strip()
    for r in ip_rows:
        if engine._s(r.get("호기")).strip() == machine:
            if engine._s(r.get("접속ID")).strip() == login_id:
                return False
            r["접속ID"] = login_id
            return True
    if machine:
        ip_rows.append({"호기": machine, "IP": "", "접속ID": login_id})
        return True
    return False


def add_machine(ip_rows: list[dict], machine: str, ip: str = "") -> bool:
    machine = engine._s(machine).strip()
    for r in ip_rows:
        if engine._s(r.get("호기")).strip() == machine:
            if ip:
                r["IP"] = ip
            return False
    ip_rows.append({"호기": machine, "IP": engine._s(ip).strip()})
    return True


# --------------------------------------------------------------------------
# 참고자료 (자유형 메모 그리드 + 색상)
# --------------------------------------------------------------------------
def create_blank_reference(path: str) -> str:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = REF_SHEET
    ws.append(REF_DEFAULT_HEADERS)
    for col, w in zip("ABC", (20, 60, 30)):
        ws.column_dimensions[col].width = w
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    wb.save(path)
    return path


def load_reference(path: str) -> tuple[list[list[str]], dict]:
    """참고자료.xlsx → (자유형 grid[list[list]], colors{(r,c):'#RRGGBB'})."""
    wb = openpyxl.load_workbook(path)
    ws = _first_sheet(wb, REF_SHEET)
    grid = []
    for row in ws.iter_rows(values_only=True):
        grid.append([engine._s(v) for v in row])
    while grid and all(v == "" for v in grid[-1]):
        grid.pop()
    ncols = max((len(r) for r in grid), default=0)
    colors = _read_colors(ws, len(grid), ncols, row_offset=0)
    wb.close()
    return grid, colors


def save_reference(path: str, grid: list[list[str]], colors: dict | None = None) -> str:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = REF_SHEET
    for row in grid:
        ws.append([engine._s(v) for v in row])
    _apply_colors(ws, colors, row_offset=0)
    wb.save(path)
    return path


# --------------------------------------------------------------------------
# 특이사항 (+색상)
# --------------------------------------------------------------------------
def create_blank_special(path: str) -> str:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = SPECIAL_SHEET
    ws.append(SPECIAL_HEADERS)
    _style_header(ws)
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    wb.save(path)
    return path


def load_special(path: str) -> tuple[list[dict], dict]:
    wb = openpyxl.load_workbook(path)
    ws = _first_sheet(wb, SPECIAL_SHEET)
    heads = [engine._s(c.value).strip() for c in ws[1]]
    hidx = {h: i for i, h in enumerate(heads)}
    out = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row is None or all(v in (None, "") for v in row):
            continue
        rec = {}
        for h in SPECIAL_HEADERS:
            i = hidx.get(h)
            v = row[i] if i is not None and i < len(row) else None
            if h == SPECIAL_BOOL_COL:
                rec[h] = engine._s(v).strip() in ("☑", "Y", "1", "True", "종료", "예")
            else:
                rec[h] = v
        out.append(rec)
    colors = _read_colors(ws, len(out), len(SPECIAL_HEADERS), row_offset=1)
    wb.close()
    return out, colors


def save_special(path: str, rows: list[dict], colors: dict | None = None) -> str:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = SPECIAL_SHEET
    ws.append(SPECIAL_HEADERS)
    for rec in rows:
        line = []
        for h in SPECIAL_HEADERS:
            v = rec.get(h)
            if h == SPECIAL_BOOL_COL:
                v = "☑" if bool(v) else "☐"
            line.append(engine._s(v))
        ws.append(line)
    _style_header(ws)
    _apply_colors(ws, colors, row_offset=1)
    wb.save(path)
    return path
