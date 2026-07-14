"""내보내기 — 값 확인 데이터에서 원하는 레시피·호기·항목만 골라 **읽기 좋은**
Excel 파일로 저장한다(기존 취합 양식을 활용, 열너비·줄바꿈 조절).

값 수정은 GUI에서 하며(내보낼 파일에만 반영), 여기서는 이미 확정된 행 dict 를
받아 그대로 쓴다(원본 취합/양식은 절대 건드리지 않음).

입력
  recipe_records : {레시피: [행dict]}  — 행dict 는 META_FIELDS + 선택 호기 값
  machines       : 내보낼 호기 열 순서
헤더 = META_FIELDS + machines. 레시피별 시트로 저장.
"""

from __future__ import annotations

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from . import engine

# 열 너비(문자 기준) — 가독성 우선. 없는 열은 기본값.
_META_WIDTH = {"PI": 10, "Recipe": 12, "Zone": 20, "Alg": 24, "Parameter": 44, "비고": 30}
_MACHINE_WIDTH = 16
_WRAP_COLS = {"Zone", "Alg", "Parameter", "비고"}   # 줄바꿈할 긴 텍스트 열


def _safe_sheet(name: str) -> str:
    import re
    return re.sub(r"[\\/*?:\[\]]", "_", str(name))[:31] or "Export"


def write_export(dest_xlsx: str, recipe_records: dict[str, list[dict]],
                 machines: list[str], title: str = "") -> str:
    """레시피별 시트로 내보내기 파일 저장(헤더 스타일·열너비·줄바꿈 조절)."""
    headers = list(engine.META_FIELDS) + list(machines)
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    hdr_fill = PatternFill("solid", fgColor="1F4E78")
    hdr_font = Font(color="FFFFFF", bold=True)
    mac_fill = PatternFill("solid", fgColor="2E75B6")
    thin = Side(style="thin", color="BFBFBF")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    wrap = Alignment(horizontal="left", vertical="center", wrap_text=True)
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for recipe, rows in recipe_records.items():
        ws = wb.create_sheet(_safe_sheet(recipe))
        ws.append(headers)
        for rec in rows:
            ws.append([rec.get(h) for h in headers])

        for ci, h in enumerate(headers, start=1):
            c = ws.cell(row=1, column=ci)
            c.fill = hdr_fill if h in engine.META_FIELDS else mac_fill
            c.font = hdr_font
            c.alignment = center
            c.border = border
            col = get_column_letter(ci)
            if h in _META_WIDTH:
                ws.column_dimensions[col].width = _META_WIDTH[h]
            else:
                ws.column_dimensions[col].width = _MACHINE_WIDTH

        for ri in range(2, ws.max_row + 1):
            for ci, h in enumerate(headers, start=1):
                c = ws.cell(row=ri, column=ci)
                c.border = border
                if h in _WRAP_COLS:
                    c.alignment = wrap
                else:
                    c.alignment = Alignment(horizontal="center", vertical="center",
                                            wrap_text=True)
        ws.freeze_panes = "A2"
        if title:
            ws.sheet_properties.tabColor = "1F4E78"

    if not wb.sheetnames:
        wb.create_sheet("내보내기없음")
    wb.save(dest_xlsx)
    return dest_xlsx
