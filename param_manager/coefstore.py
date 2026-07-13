"""변환계수 저장소 — '변환계수.xlsx'(저장폴더 독립 파일).

변환계수는 **장비 렌즈 특성**이라 장비마다 다르고, **같은 호기·같은 MAG**(OpticPreset
Scan2d 의 Mag 값)면 레시피가 달라도 같은 계수를 쓴다(사용자 확정 2026-07).
→ 키 = (호기, MAG). 값 = 변환계수. 변형(PI/PI-bubble/x5/x20)은 사람이 보기 위한 참고열.

  헤더: [호기, MAG, 변형, 계수, 비고]

파일은 장비 IP 주소.xlsx 처럼 **사람이 관리**하되, 양식 만들기·수집 때 OpticPreset 의
Mag + coef_detector 추정 계수로 **자동 upsert** 된다(없는 (호기,MAG)만 추가/갱신).
"""

from __future__ import annotations

import os

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill

from . import engine

COEF_FILENAME = "변환계수.xlsx"
COEF_SHEET = "변환계수"
COEF_HEADERS = ["호기", "MAG", "변형", "계수", "비고"]
_HDR_FILL = "1F4E78"


def coef_path(save_dir: str) -> str:
    return os.path.join(save_dir, COEF_FILENAME)


def _machine_norm(s) -> str:
    """호기 매칭 정규화 — 대소문자/구분자 무시(AOI-K2 == aoi_k2). 숫자 0패딩도 흡수."""
    import re
    txt = str(s or "").lower()
    letters = re.sub(r"[^a-z]", "", txt)
    nums = re.findall(r"\d+", txt)
    return letters + "".join(str(int(n)) for n in nums)


def mag_norm(mag) -> str:
    """MAG 매칭 정규화 — 숫자면 소수 4자리 반올림 문자열, 아니면 소문자 압축."""
    s = engine._s(mag).strip()
    if s == "":
        return ""
    try:
        return f"{round(float(s), 4):g}"
    except ValueError:
        import re
        return re.sub(r"[^0-9a-z]", "", s.lower())


def _style_header(ws) -> None:
    fill = PatternFill("solid", fgColor=_HDR_FILL)
    white = Font(color="FFFFFF", bold=True)
    for c in ws[1]:
        c.fill = fill
        c.font = white
        c.alignment = Alignment(horizontal="center", vertical="center")


def create_blank(path: str) -> str:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = COEF_SHEET
    ws.append(COEF_HEADERS)
    _style_header(ws)
    for col, w in zip("ABCDE", (12, 12, 14, 22, 20)):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A2"
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    wb.save(path)
    return path


def load(path: str) -> list[dict]:
    """변환계수.xlsx → [{호기, MAG, 변형, 계수, 비고}] (헤더 변동 허용)."""
    if not os.path.isfile(path):
        return []
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb[COEF_SHEET] if COEF_SHEET in wb.sheetnames else wb[wb.sheetnames[0]]
    heads = [engine._s(c.value).strip() for c in ws[1]]
    hidx = {h: i for i, h in enumerate(heads) if h}
    out = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row is None or all(v in (None, "") for v in row):
            continue

        def g(h, default=""):
            i = hidx.get(h)
            return engine._s(row[i]).strip() if i is not None and i < len(row) else default
        ho = g("호기")
        if not ho:
            continue
        out.append({"호기": ho, "MAG": g("MAG"), "변형": g("변형"),
                    "계수": g("계수"), "비고": g("비고")})
    wb.close()
    return out


def save(path: str, rows: list[dict]) -> str:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = COEF_SHEET
    ws.append(COEF_HEADERS)
    for r in rows:
        ws.append([engine._s(r.get(h)) for h in COEF_HEADERS])
    _style_header(ws)
    for col, w in zip("ABCDE", (12, 12, 14, 22, 20)):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A2"
    wb.save(path)
    return path


def _coef_float(v):
    try:
        return float(engine._s(v).strip())
    except ValueError:
        return None


def lookup(rows: list[dict], machine: str, mag) -> float | None:
    """(호기, MAG) → 계수(float). MAG 는 숫자 근사 매칭. 없으면 None."""
    mk, gk = _machine_norm(machine), mag_norm(mag)
    if not mk:
        return None
    for r in rows:
        if _machine_norm(r.get("호기")) != mk:
            continue
        if gk and mag_norm(r.get("MAG")) != gk:
            continue
        if not gk and mag_norm(r.get("MAG")) != "":
            continue                      # MAG 지정 없는 조회는 MAG 없는 행에만
        c = _coef_float(r.get("계수"))
        if c is not None:
            return c
    return None


def machine_coefs(rows: list[dict], machine: str) -> list[dict]:
    """한 호기의 계수 행들(표시용). 변형/ MAG 순."""
    mk = _machine_norm(machine)
    out = [r for r in rows if _machine_norm(r.get("호기")) == mk]
    return sorted(out, key=lambda r: (engine._s(r.get("변형")), mag_norm(r.get("MAG"))))


def upsert(rows: list[dict], machine: str, mag, coef, variant: str = "",
           overwrite: bool = False) -> bool:
    """(호기, MAG) 행 추가/갱신. overwrite=False 면 이미 있으면 계수 유지(사람 우선).
    반환: 실제로 추가/갱신했으면 True."""
    if coef is None or engine._s(coef).strip() == "":
        return False
    mk, gk = _machine_norm(machine), mag_norm(mag)
    for r in rows:
        if _machine_norm(r.get("호기")) == mk and mag_norm(r.get("MAG")) == gk:
            if overwrite:
                r["계수"] = engine._s(coef)
                if variant:
                    r["변형"] = variant
                return True
            return False                  # 이미 있음(사람 값 우선)
    rows.append({"호기": engine._s(machine), "MAG": engine._s(mag),
                 "변형": variant, "계수": engine._s(coef), "비고": "자동추정"})
    return True


def make_lookup(rows: list[dict]):
    """scan_tree(coef_lookup=...) 용 콜백. (equipment, mag_value, config_dir)->계수|None."""
    def _cb(equipment, mag_value, config_dir=None):
        return lookup(rows, equipment, mag_value)
    return _cb
