"""장비 화면 항목 이름 기억 — (Alg, 원본항목) → 마지막으로 저장한 '장비 화면 항목 이름'.

양식 만들기/commonality 에서 **같은 alg·같은 파라미터**를 매번 같은 이름으로 다시
입력하지 않도록, 양식을 확정할 때마다 사람이 정한 이름을 이 공유 파일에 기억해 둔다.
새 양식을 만들 때 같은 (alg, 원본항목) 이 나오면 그 이름을 자동으로 불러온다
(사람이 그대로 두거나 다시 바꿀 수 있음).

  헤더: [Alg, 원본항목, 장비화면이름, 사용, 비고]
  키   : (Alg, 원본항목) 정규화 — 원본항목 = 실제 ini 항목 이름(설정 Parameter)
  사용 : 마지막으로 확정한 체크박스 상태(Y/N). 새 양식에서 같은 (alg,원본항목)이 나오면
         이 값으로 체크를 미리 맞춘다(매번 같은 항목을 다시 체크하지 않게).

변환계수.xlsx(coefstore)와 같은 원칙:
  · 저장폴더(OneDrive) 공유 파일 → 담당자끼리 같은 이름을 쓴다.
  · **사람이 양식을 확정할 때만** 쓴다(`apply_records`). 파싱/조회는 읽기 전용.
  · KNOWN_DISPLAY_MAP(파서 기본 표시명)은 그대로 기본값이고, 이 파일에 값이 있으면
    그 값(사람이 마지막에 저장한 이름)을 우선한다 — 같은 메커니즘으로 동작한다.
"""

from __future__ import annotations

import os
import re

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill

from . import engine

NAME_FILENAME = "장비화면이름.xlsx"
NAME_SHEET = "장비화면이름"
NAME_HEADERS = ["Alg", "원본항목", "장비화면이름", "사용", "비고"]
_USE_TRUE = {"Y", "YES", "1", "TRUE", "O", "예", "사용", "체크"}
_USE_FALSE = {"N", "NO", "0", "FALSE", "X", "아니오", "미사용"}
_HDR_FILL = "1F4E78"


def name_path(save_dir: str) -> str:
    return os.path.join(save_dir, NAME_FILENAME)


def _norm(s) -> str:
    """매칭 정규화 — 대소문자·공백·구분자(_/-) 무시. **한글 보존**."""
    return re.sub(r"[\s\-_]+", "", engine._s(s).strip().lower())


def _key(alg, orig) -> tuple:
    return (_norm(alg), _norm(orig))


def _style_header(ws) -> None:
    fill = PatternFill("solid", fgColor=_HDR_FILL)
    white = Font(color="FFFFFF", bold=True)
    for c in ws[1]:
        c.fill = fill
        c.font = white
        c.alignment = Alignment(horizontal="center", vertical="center")


_COL_W = (22, 26, 30, 8, 20)      # A,B,C,D(사용),E


def _use_str(use) -> str:
    """bool/None → 'Y'/'N'/''(모름)."""
    if use is None:
        return ""
    return "Y" if use else "N"


def _parse_use(s):
    """저장된 사용 문자열 → True/False/None(빈칸·미인식)."""
    t = engine._s(s).strip().upper()
    if t in _USE_TRUE:
        return True
    if t in _USE_FALSE:
        return False
    return None


def create_blank(path: str) -> str:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = NAME_SHEET
    ws.append(NAME_HEADERS)
    _style_header(ws)
    for col, w in zip("ABCDE", _COL_W):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A2"
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    wb.save(path)
    return path


def load(path: str) -> list[dict]:
    """장비화면이름.xlsx → [{Alg, 원본항목, 장비화면이름, 사용, 비고}] (헤더 변동 허용)."""
    if not os.path.isfile(path):
        return []
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb[NAME_SHEET] if NAME_SHEET in wb.sheetnames else wb[wb.sheetnames[0]]
    heads = [engine._s(c.value).strip() for c in ws[1]]
    hidx = {h: i for i, h in enumerate(heads) if h}
    out = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row is None or all(v in (None, "") for v in row):
            continue

        def g(h, default=""):
            i = hidx.get(h)
            return engine._s(row[i]).strip() if i is not None and i < len(row) else default
        alg, orig = g("Alg"), g("원본항목")
        name = g("장비화면이름")
        if not orig:                       # 원본항목만 있으면 유효(이름 비어도 사용 정보 가능)
            continue
        out.append({"Alg": alg, "원본항목": orig, "장비화면이름": name,
                    "사용": g("사용"), "비고": g("비고")})
    wb.close()
    return out


def save(path: str, rows: list[dict]) -> str:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = NAME_SHEET
    ws.append(NAME_HEADERS)
    for r in rows:
        ws.append([engine._s(r.get(h)) for h in NAME_HEADERS])
    _style_header(ws)
    for col, w in zip("ABCDE", _COL_W):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A2"
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    wb.save(path)
    return path


def lookup(rows: list[dict], alg, orig) -> str | None:
    """(alg, 원본항목) → 저장된 장비 화면 이름. 없으면 None.
    Alg 가 정확히 안 맞아도 원본항목만 맞으면(같은 파라미터) 폴백으로 돌려준다."""
    k = _key(alg, orig)
    by_orig = None
    for r in rows:
        rk = _key(r.get("Alg"), r.get("원본항목"))
        nm = engine._s(r.get("장비화면이름")).strip()
        if not nm:
            continue
        if rk == k:
            return nm
        if by_orig is None and _norm(r.get("원본항목")) == _norm(orig):
            by_orig = nm
    return by_orig


def use_of(rows: list[dict], alg, orig):
    """(alg, 원본항목) → 저장된 체크박스 상태(True/False). 없거나 빈칸이면 None.
    Alg 가 정확히 안 맞아도 원본항목만 맞으면 폴백."""
    k = _key(alg, orig)
    by_orig = None
    for r in rows:
        u = _parse_use(r.get("사용"))
        if u is None:
            continue
        rk = _key(r.get("Alg"), r.get("원본항목"))
        if rk == k:
            return u
        if by_orig is None and _norm(r.get("원본항목")) == _norm(orig):
            by_orig = u
    return by_orig


def make_lookup(rows: list[dict]):
    """editor_model.build_entries 에 넘길 이름 조회 콜백 (alg, orig) -> name|None."""
    def _cb(alg, orig):
        return lookup(rows, alg, orig)
    return _cb


def make_use_lookup(rows: list[dict]):
    """editor_model.build_entries 에 넘길 사용 조회 콜백 (alg, orig) -> bool|None."""
    def _cb(alg, orig):
        return use_of(rows, alg, orig)
    return _cb


def upsert(rows: list[dict], alg, orig, name=None, use=None) -> bool:
    """(alg, 원본항목) 행에 장비 화면 이름/사용 상태를 기록·갱신(마지막 승).
    name/use 는 넘어온 것만 갱신한다. 반환: 목록이 바뀌었는가. orig 가 비면 무시."""
    orig = engine._s(orig).strip()
    if not orig:
        return False
    name = engine._s(name).strip() if name is not None else None
    use_s = _use_str(use) if use is not None else None
    k = _key(alg, orig)
    for r in rows:
        if _key(r.get("Alg"), r.get("원본항목")) == k:
            changed = False
            if name and engine._s(r.get("장비화면이름")).strip() != name:
                r["장비화면이름"] = name
                changed = True
            if use_s is not None and engine._s(r.get("사용")).strip().upper() != use_s:
                r["사용"] = use_s
                changed = True
            if engine._s(r.get("Alg")).strip() == "" and engine._s(alg).strip():
                r["Alg"] = engine._s(alg).strip()
            return changed
    rows.append({"Alg": engine._s(alg).strip(), "원본항목": orig,
                 "장비화면이름": name or "", "사용": use_s or "", "비고": ""})
    return True


def apply_records(rows: list[dict], records: list[dict], extracts: list[dict]) -> int:
    """(하위호환) 양식 확정 결과에서 (Alg, 원본키) → 표시 이름만 기억한다(이름을 실제로
    바꾼 것만). 사용 상태까지 기억하려면 `apply_selected` 를 쓴다. 반환: 바뀐 행 수."""
    changed = 0
    for rec, ext in zip(records, extracts):
        alg = rec.get("Alg")
        orig = (ext or {}).get("key")
        name = rec.get("Parameter")
        if not engine._s(orig).strip() or not engine._s(name).strip():
            continue
        if _norm(name) == _norm(orig):      # 이름을 실제로 바꾼 것만 기억(잡음 방지)
            continue
        if upsert(rows, alg, orig, name=name):
            changed += 1
    return changed


def apply_selected(rows: list[dict], selected: list[dict]) -> int:
    """양식 편집기의 **전체 항목**(체크/미체크 모두)에서 (Alg, 원본키) →
    (장비 화면 이름, 사용 상태)를 기억한다. 새 양식에서 같은 항목의 이름·체크를
    자동으로 맞추는 근거가 된다. 반환: 바뀐 행 수.

    selected 각 항목: {alg, ext(원본키 'key'), name(표시 이름), reco(표시명 폴백), use}."""
    changed = 0
    for s in selected:
        alg = s.get("alg")
        orig = (s.get("ext") or {}).get("key")
        if not engine._s(orig).strip():
            continue
        name = engine._s(s.get("name")).strip() or engine._s(s.get("reco")).strip()
        if upsert(rows, alg, orig, name=name or None, use=bool(s.get("use"))):
            changed += 1
    return changed
