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
NAME_HEADERS = ["Alg", "원본항목", "장비화면이름", "사용", "비고", "색상코드"]
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


_COL_W = (22, 26, 30, 8, 20, 14)


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
    for col, w in zip("ABCDEF", _COL_W):
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
                    "사용": g("사용"), "비고": g("비고"), "색상코드": g("색상코드")})
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
    for col, w in zip("ABCDEF", _COL_W):
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


def upsert(rows: list[dict], alg, orig, name=None, use=None, color=None) -> bool:
    """(alg, 원본항목) 행에 장비 화면 이름/사용 상태를 기록·갱신(마지막 승).
    name/use 는 넘어온 것만 갱신한다. 반환: 목록이 바뀌었는가. orig 가 비면 무시."""
    orig = engine._s(orig).strip()
    if not orig:
        return False
    name = engine._s(name).strip() if name is not None else None
    use_s = _use_str(use) if use is not None else None
    color = normalize_color(color) if color is not None else None
    k = _key(alg, orig)
    for r in rows:
        if _key(r.get("Alg"), r.get("원본항목")) == k:
            changed = False
            if color is not None and r.get("색상코드", "") != color:
                r["색상코드"] = color
                changed = True
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
                 "장비화면이름": name or "", "사용": use_s or "", "비고": "",
                 "색상코드": color or ""})
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
        if upsert(rows, alg, orig, name=name or None,
                  use=bool(s["use"]) if "use" in s else None,
                  color=s.get("color")):
            changed += 1
    return changed


def normalize_color(value):
    """Empty means automatic; otherwise store a portable RGB hex code."""
    value = engine._s(value).strip().upper()
    if not value:
        return ""
    if not value.startswith('#'):
        value = '#' + value
    if not re.fullmatch(r'#[0-9A-F]{6}', value):
        raise ValueError("색상은 #RRGGBB 형식으로 입력하세요. 예: #FFFF80 (빈칸=자동)")
    return value


def default_color(alg, parameter):
    """Reference-inspired defaults, not an assertion about equipment metadata."""
    name = _norm(parameter)
    if 'rich' in name:
        return '#FF7D88'
    if 'elong' in name or ('adaptive' in name and 'bright' in name):
        return '#FF8900'
    if 'adaptive' in name and 'dark' in name:
        return '#9080FF'
    if 'cluster' in name or 'adaptiveactivation' in name or 'edgeuncertainty' in name:
        return '#80F58A'
    if 'dark' in name:
        return '#F080F4'
    if 'bright' in name:
        return '#FFFF80'
    return '#C9D0D2'


def contrast_text(color):
    try:
        hx = normalize_color(color).lstrip('#')
        r, g, b = (int(hx[i:i+2], 16) for i in (0, 2, 4))
        return '#202020' if (299*r + 587*g + 114*b) >= 140000 else '#FFFFFF'
    except (ValueError, TypeError):
        return '#EEEEEE'


def make_color_lookup(rows):
    # Build once per screen/editor, never scan the workbook for every painted cell.
    index = {}
    for row in rows:
        try:
            color = normalize_color(row.get('색상코드'))
        except ValueError:
            continue
        if color:
            for field in ('원본항목', '장비화면이름'):
                if row.get(field):
                    index[_key(row.get('Alg'), row[field])] = color
    return lambda alg, orig: index.get(_key(alg, orig), '')


def resolve_original(rows, alg, display):
    """Resolve a view label without silently editing an ambiguous mapping."""
    candidates = {r['원본항목'] for r in rows
                  if _norm(r.get('Alg')) == _norm(alg)
                  and _norm(display) in (_norm(r.get('장비화면이름')), _norm(r.get('원본항목')))}
    if not candidates:
        from .ini_parser import KNOWN_DISPLAY_MAP
        candidates = {key[-1] for key, info in KNOWN_DISPLAY_MAP.items()
                      if _norm(info[0]) == _norm(alg) and _norm(info[1]) == _norm(display)}
    if len(candidates) > 1:
        raise ValueError("같은 표시 이름의 원본 항목이 여러 개입니다. 양식 만들기에서 색상을 지정하세요.")
    return next(iter(candidates), display)


def save_selected(path, selected, user, opened_stamp=None):
    """One explicit user action, latest-file merge, existing soft-lock safeguards."""
    from . import locking
    previous = locking.status(path, user)
    state = locking.acquire(path, user)
    if not state.editable:
        raise ValueError(locking.holder_message(state, '장비 화면 이름/색상'))
    try:
        stamp = locking.file_stamp(path)
        if opened_stamp is not None and (stamp or (0, 0)) != opened_stamp:
            raise ValueError('장비화면이름.xlsx가 변경되었습니다. 창을 다시 열어 최신 값을 확인하세요.')
        rows = load(path)
        changed = apply_selected(rows, selected)
        if changed:
            check = locking.check_before_save(path, user, stamp)
            if not check['ok'] or locking.file_stamp(path) != stamp:
                raise ValueError(check['reason'] or '저장 직전 파일이 변경되었습니다.')
            save(path, rows)
        return changed, rows
    finally:
        if previous.status != 'mine':
            locking.release(path, user)


def resolve_color_edits(entries, initial, current):
    """One shared key may appear in many variants; do not undo one edited row."""
    normalized = {r: normalize_color(value) for r, value in current.items()}
    overrides = {}
    for r, color in normalized.items():
        if color != initial[r]:
            e = entries[r]
            key = _key(e['alg'], e['orig'])
            if key in overrides and overrides[key] != color:
                raise ValueError(f"{e['orig']}: 같은 Alg·원본 항목에 서로 다른 색상을 지정했습니다.")
            overrides[key] = color
    return {r: overrides.get(_key(entries[r]['alg'], entries[r]['orig']), color)
            for r, color in normalized.items()}
