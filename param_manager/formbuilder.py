"""양식 만들기(AOI 스펙 1.1.2) — 헤드리스 로직.

흐름:
  1) 장비/로컬 폴더 파싱(ini_parser.build_pivot) → `build_initial_workbook()` 로
     **편집용 initial 엑셀** 생성. 사람이 실제 Excel 로 열어 '사용' 여부와
     '최종 Parameter'(장비 화면에 뜨는 이름)를 직접 지정/수정한다.
  2) 편집·저장 후 프로그램의 '편집 완료' → `build_final_from_initial()` 로
     선택된 행만 **final(양식) 엑셀** 생성(공용 PI_ALL/RDL_ALL 양식 + `_EXTRACT_MAP`).
  원형 initial 은 호출측(GUI)에서 따로 보존한다(스펙 요구).

GUI(equip_app)는 이 두 함수만 호출하고, 실제 Excel 열기/버전 저장은 바깥에서 한다.
"""

from __future__ import annotations

import os

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

from . import engine, extract_io

# 편집용 initial 시트 컬럼(실제 Excel 에서 사람이 편집)
INIT_SHEET = "양식초안"
INIT_HEADERS = [
    "사용", "PI", "Recipe", "Zone", "Alg", "추천 Parameter", "최종 Parameter",
    "대표값(참고)", "비고",
    # ↓ 참고/재추출 메타(값 갱신 매칭용) — 사람이 굳이 안 건드려도 됨
    "설정파일", "설정 Section", "설정 Parameter", "Raw Value", "변환방식",
]
_USED_TRUE = {"Y", "YES", "1", "TRUE", "O", "예", "사용"}
_USED_FALSE = {"", "N", "NO", "0", "FALSE", "X", "아니오", "미사용"}


def _rep_value(values: dict) -> str:
    for v in values.values():
        if engine._s(v) != "":
            return engine._s(v)
    return ""


def _row_from_pivot(r: dict) -> list:
    ext = r.get("extract") or {}
    return [
        "Y", engine._s(r.get("recipe")), engine._s(r.get("mag")),
        engine._s(r.get("zone")), engine._s(r.get("alg")),
        engine._s(r.get("param")), engine._s(r.get("param")),  # 최종=추천 기본값
        _rep_value(r.get("values") or {}), "",
        engine._s(ext.get("src_file")), engine._s(ext.get("section")),
        engine._s(ext.get("key")), _rep_value(r.get("raws") or {}),
        engine._s(ext.get("transform") or "RAW"),
    ]


def build_initial_workbook(pivot_rows: list[dict], dest_xlsx: str,
                           level: str = "", source: str = "") -> str:
    """파싱 피벗 → 편집용 initial 엑셀. 반환: dest_xlsx.

    pivot_rows: ini_parser.build_pivot()[0] (각 dict: layer/recipe/mag/zone/alg/
                param/values/raws/unit/extract).
    """
    os.makedirs(os.path.dirname(os.path.abspath(dest_xlsx)) or ".", exist_ok=True)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = INIT_SHEET
    ws.append(INIT_HEADERS)
    # 정렬: 레벨 → 변형 → Zone → Alg → Parameter
    rows = sorted(pivot_rows, key=lambda r: (
        engine._s(r.get("recipe")), engine._s(r.get("mag")),
        engine._s(r.get("zone")), engine._s(r.get("alg")),
        engine._s(r.get("param"))))
    for r in rows:
        ws.append(_row_from_pivot(r))

    # 스타일 + '사용' 드롭다운(Y/N)
    hdr_fill = PatternFill("solid", fgColor="1F4E78")
    white = Font(color="FFFFFF", bold=True)
    for c in ws[1]:
        c.fill = hdr_fill
        c.font = white
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.freeze_panes = "B2"
    widths = {"A": 6, "B": 8, "C": 12, "D": 18, "E": 18, "F": 26, "G": 26,
              "H": 12, "I": 24, "J": 16, "K": 20, "L": 22, "M": 12, "N": 16}
    for col, w in widths.items():
        ws.column_dimensions[col].width = w
    if ws.max_row >= 2:
        dv = DataValidation(type="list", formula1='"Y,N"', allow_blank=True)
        dv.prompt = "이 파라미터를 양식에 넣으려면 Y, 빼려면 N"
        ws.add_data_validation(dv)
        dv.add(f"A2:A{ws.max_row}")

    # 사용법 안내 시트
    info = wb.create_sheet("사용법")
    for line in [
        ["양식 만들기 — 초안 편집 방법"],
        ["1) '사용' 열에서 필요 없는 행은 N 으로 바꾸거나 행을 삭제하세요."],
        ["2) '최종 Parameter' 열을 장비 화면에 뜨는 실제 이름으로 수정하세요(기본=추천)."],
        ["3) 저장 후, 프로그램에서 '편집 완료'를 누르면 final(양식) 파일이 만들어집니다."],
        ["※ 설정파일/Section/Parameter/Raw/변환방식 열은 값 갱신 매칭용 참고 정보입니다."],
        [f"소스: {source}"],
        [f"레시피 레벨: {level}"],
    ]:
        info.append(line)
    info.column_dimensions["A"].width = 90
    wb.save(dest_xlsx)
    return dest_xlsx


def _is_used(val) -> bool:
    s = engine._s(val).strip().upper()
    if s in _USED_TRUE:
        return True
    if s in _USED_FALSE:
        return False
    return True                 # 알 수 없는 값이면 '사용'으로 간주(안전)


def read_initial_rows(initial_xlsx: str) -> list[dict]:
    """편집된 initial 엑셀 → 컬럼명 기준 dict 목록(헤더 위치 변동 허용)."""
    wb = openpyxl.load_workbook(initial_xlsx, data_only=True)
    ws = wb[INIT_SHEET] if INIT_SHEET in wb.sheetnames else wb[wb.sheetnames[0]]
    heads = [engine._s(c.value).strip() for c in ws[1]]
    hidx = {h: i for i, h in enumerate(heads) if h}
    out = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row is None:
            continue
        rec = {h: (row[i] if i < len(row) else None) for h, i in hidx.items()}
        out.append(rec)
    wb.close()
    return out


def _detect_sheet(records: list[dict]) -> str:
    for rec in records:
        if engine._s(rec.get("PI")).upper().startswith("RDL"):
            return "RDL_ALL"
    return "PI_ALL"


def build_final_from_initial(initial_xlsx: str, dest_xlsx: str,
                             sheet_name: str | None = None,
                             user: str | None = None, level: str = "",
                             aoi: str = "", source: str = "",
                             scales: dict | None = None) -> dict:
    """편집된 initial → final(양식) 엑셀. 반환: {'path','kept','dropped','sheet'}.

    - '사용'=N/빈행/Parameter 공란 행은 제외.
    - Parameter = '최종 Parameter'(없으면 '추천 Parameter').
    - 공용 PI_ALL/RDL_ALL 양식 + `_EXTRACT_MAP`(값 재추출용)으로 기록.
    """
    rows = read_initial_rows(initial_xlsx)
    records, extracts = [], []
    dropped = 0
    for r in rows:
        param = engine._s(r.get("최종 Parameter")).strip() or \
            engine._s(r.get("추천 Parameter")).strip()
        pi = engine._s(r.get("PI")).strip()
        if not param or not pi:
            dropped += 1
            continue
        if not _is_used(r.get("사용")):
            dropped += 1
            continue
        records.append({
            "PI": pi, "Recipe": engine._s(r.get("Recipe")).strip(),
            "Zone": engine._s(r.get("Zone")).strip(),
            "Alg": engine._s(r.get("Alg")).strip(), "Parameter": param,
            "비고": engine._s(r.get("비고")).strip(),
        })
        extracts.append({
            "src_file": engine._s(r.get("설정파일")),
            "section": engine._s(r.get("설정 Section")),
            "key": engine._s(r.get("설정 Parameter")),
            "raw": r.get("Raw Value"),
            "transform": engine._s(r.get("변환방식")) or "RAW",
            "source_path": "",
        })
    if not records:
        raise ValueError("사용할 행이 없습니다. '사용' 열과 'PI/최종 Parameter'를 확인하세요.")
    sheet = sheet_name or _detect_sheet(records)
    extract_io.write_snapshot(
        dest_xlsx, records, machines=[], sheet_name=sheet, extracts=extracts,
        stage="final", level=level, aoi=aoi, source=source, user=user, scales=scales)
    return {"path": dest_xlsx, "kept": len(records), "dropped": dropped, "sheet": sheet}
