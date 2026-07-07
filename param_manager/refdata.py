"""참고자료 / 특이사항 독립 엑셀 파일 I/O (3차 재설계).

저장 폴더 안의 `참고자료.xlsx`·`특이사항.xlsx` 를 표준 양식으로 읽고 쓴다.
- 참고자료: 시트 "참고자료", 헤더 [호기, IP, 비고]. 호기 버튼·IP 매칭의 기준.
- 특이사항: 시트 "특이사항", 헤더 = engine.SPECIAL_HEADERS.

기존 '공용 파일 안의 시트' 모델을 대체한다(파일 분리).
"""

from __future__ import annotations

import os

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill

from . import engine

REF_FILENAME = "참고자료.xlsx"
SPECIAL_FILENAME = "특이사항.xlsx"
REF_SHEET = "참고자료"
SPECIAL_SHEET = "특이사항"
REF_HEADERS = ["호기", "IP", "비고"]
SPECIAL_HEADERS = list(engine.SPECIAL_HEADERS)
SPECIAL_BOOL_COL = engine.SPECIAL_BOOL_COL


def ref_path(save_dir: str) -> str:
    return os.path.join(save_dir, REF_FILENAME)


def special_path(save_dir: str) -> str:
    return os.path.join(save_dir, SPECIAL_FILENAME)


# --------------------------------------------------------------------------
# 공통 스타일 헤더
# --------------------------------------------------------------------------
def _style_header(ws) -> None:
    fill = PatternFill("solid", fgColor="1F4E78")
    white = Font(color="FFFFFF", bold=True)
    for c in ws[1]:
        c.fill = fill
        c.font = white
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.freeze_panes = "A2"


def create_blank_reference(path: str) -> str:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = REF_SHEET
    ws.append(REF_HEADERS)
    _style_header(ws)
    for col, w in zip("ABC", (14, 18, 40)):
        ws.column_dimensions[col].width = w
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    wb.save(path)
    return path


def create_blank_special(path: str) -> str:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = SPECIAL_SHEET
    ws.append(SPECIAL_HEADERS)
    _style_header(ws)
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    wb.save(path)
    return path


# --------------------------------------------------------------------------
# 참고자료
# --------------------------------------------------------------------------
def _first_sheet(wb, preferred: str):
    return wb[preferred] if preferred in wb.sheetnames else wb[wb.sheetnames[0]]


def load_reference(path: str) -> list[dict]:
    """참고자료.xlsx → [{호기, IP, 비고}] (헤더 위치 변동 허용, 빈 행 제외)."""
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = _first_sheet(wb, REF_SHEET)
    heads = [engine._s(c.value).strip() for c in ws[1]]
    hidx = {h: i for i, h in enumerate(heads)}
    out = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row is None or all(v in (None, "") for v in row):
            continue

        def cell(name):
            i = hidx.get(name)
            return engine._s(row[i]).strip() if i is not None and i < len(row) else ""
        # 헤더가 다르면(자유 양식) 첫 셀=호기, 둘째=IP 로 폴백
        ho = cell("호기") or engine._s(row[0]).strip() if row else ""
        ip = cell("IP") or (engine._s(row[1]).strip() if len(row) > 1 else "")
        bigo = cell("비고")
        if not ho:
            continue
        out.append({"호기": ho, "IP": ip, "비고": bigo})
    wb.close()
    return out


def save_reference(path: str, rows: list[dict]) -> str:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = REF_SHEET
    ws.append(REF_HEADERS)
    for r in rows:
        ws.append([engine._s(r.get("호기")), engine._s(r.get("IP")),
                   engine._s(r.get("비고"))])
    _style_header(ws)
    for col, w in zip("ABC", (14, 18, 40)):
        ws.column_dimensions[col].width = w
    wb.save(path)
    return path


def machines(rows: list[dict]) -> list[str]:
    """참고자료 행 → 호기 이름 목록(순서 유지, 중복 제거)."""
    out = []
    for r in rows:
        m = engine._s(r.get("호기")).strip()
        if m and m not in out:
            out.append(m)
    return out


def ip_for(rows: list[dict], machine: str) -> str:
    for r in rows:
        if engine._s(r.get("호기")).strip() == engine._s(machine).strip():
            return engine._s(r.get("IP")).strip()
    return ""


def add_machine(rows: list[dict], machine: str, ip: str = "", bigo: str = "") -> bool:
    """호기 추가(이미 있으면 IP만 갱신). 반환: 새로 추가했으면 True."""
    machine = engine._s(machine).strip()
    for r in rows:
        if engine._s(r.get("호기")).strip() == machine:
            if ip:
                r["IP"] = ip
            return False
    rows.append({"호기": machine, "IP": engine._s(ip).strip(), "비고": bigo})
    return True


# --------------------------------------------------------------------------
# 특이사항
# --------------------------------------------------------------------------
def load_special(path: str) -> list[dict]:
    wb = openpyxl.load_workbook(path, data_only=True)
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
    wb.close()
    return out


def save_special(path: str, rows: list[dict]) -> str:
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
    wb.save(path)
    return path
