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
    use = "Y" if r.get("use", True) else "N"     # OpticPreset 비-통일 항목은 N(검토용)
    return [
        use, engine._s(r.get("recipe")), engine._s(r.get("mag")),
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


def rename_level(xlsx: str, old: str, new: str) -> int:
    """양식(초안/확정) 엑셀 안의 레시피 레벨 이름을 old→new 로 바꾼다.

    바꾸는 곳: 모든 시트의 'PI' 헤더 열에서 값이 old 인 셀,
    사용법 시트의 '레시피 레벨: old' 줄, 추출_요약 시트의 ('레시피 레벨', old) 행.
    반환: 바뀐 셀 수. (파일 제목/폴더명 변경은 호출측 담당.)
    """
    old_s, new_s = engine._s(old).strip(), engine._s(new).strip()
    if not new_s or old_s == new_s:
        return 0
    wb = openpyxl.load_workbook(xlsx)
    changed = 0
    for ws in wb.worksheets:
        heads = [engine._s(c.value).strip() for c in ws[1]]
        if "PI" in heads:
            ci = heads.index("PI") + 1
            for r in range(2, ws.max_row + 1):
                c = ws.cell(row=r, column=ci)
                if engine._s(c.value).strip() == old_s:
                    c.value = new_s
                    changed += 1
        # 요약형: ('레시피 레벨', old) 두 칸 행 (추출_요약)
        if heads[:2] == ["항목", "값"]:
            for r in range(2, ws.max_row + 1):
                if engine._s(ws.cell(row=r, column=1).value) == "레시피 레벨" and \
                        engine._s(ws.cell(row=r, column=2).value).strip() == old_s:
                    ws.cell(row=r, column=2).value = new_s
                    changed += 1
        # 안내문형: '레시피 레벨: old' 한 칸 줄 (사용법)
        for r in range(1, ws.max_row + 1):
            c = ws.cell(row=r, column=1)
            if engine._s(c.value) == f"레시피 레벨: {old_s}":
                c.value = f"레시피 레벨: {new_s}"
                changed += 1
    wb.save(xlsx)
    return changed


def force_level(xlsx: str, new: str) -> int:
    """양식(초안/확정) 엑셀의 레시피 레벨을 **현재 값과 무관하게** new 로 통일한다.
    (rename_level 은 old 값이 폴더명과 달라 매칭 실패할 수 있어, 이름 변경 확정 시
    이 함수로 PI 열 전체를 new 로 강제한다. 한 양식=한 레벨 전제.)
    반환: 바뀐 셀 수.
    """
    new_s = engine._s(new).strip()
    if not new_s:
        return 0
    wb = openpyxl.load_workbook(xlsx)
    changed = 0
    for ws in wb.worksheets:
        heads = [engine._s(c.value).strip() for c in ws[1]]
        if "PI" in heads:
            ci = heads.index("PI") + 1
            for r in range(2, ws.max_row + 1):
                c = ws.cell(row=r, column=ci)
                if engine._s(c.value).strip() and engine._s(c.value).strip() != new_s:
                    c.value = new_s
                    changed += 1
        if heads[:2] == ["항목", "값"]:
            for r in range(2, ws.max_row + 1):
                if engine._s(ws.cell(row=r, column=1).value) == "레시피 레벨":
                    ws.cell(row=r, column=2).value = new_s
                    changed += 1
        for r in range(1, ws.max_row + 1):
            c = ws.cell(row=r, column=1)
            if engine._s(c.value).startswith("레시피 레벨:"):
                c.value = f"레시피 레벨: {new_s}"
                changed += 1
    wb.save(xlsx)
    return changed


def form_params(xlsx: str) -> set[tuple]:
    """양식(확정 PI_ALL/RDL_ALL)의 파라미터 키 집합 — (Zone, Alg, Parameter) 정규화.
    두 양식 비교(신규 파라미터 검출)용."""
    import re
    def _n(s):
        return re.sub(r"[^0-9a-z가-힣µ]", "", engine._s(s).lower())
    out = set()
    try:
        wb = openpyxl.load_workbook(xlsx, data_only=True)
    except Exception:  # noqa: BLE001
        return out
    for ws in wb.worksheets:
        heads = [engine._s(c.value).strip() for c in ws[1]]
        if not ({"Zone", "Alg", "Parameter"} <= set(heads)) or heads[:1] != ["PI"]:
            continue
        iz, ia, ip = heads.index("Zone"), heads.index("Alg"), heads.index("Parameter")
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row and any(v not in (None, "") for v in row):
                p = row[ip] if ip < len(row) else ""
                if engine._s(p).strip():
                    out.add((_n(row[iz] if iz < len(row) else ""),
                             _n(row[ia] if ia < len(row) else ""), _n(p)))
    wb.close()
    return out


def _norm_key3(zone, alg, param) -> tuple:
    import re
    def _n(s):
        return re.sub(r"[^0-9a-z가-힣µ]", "", engine._s(s).lower())
    return (_n(zone), _n(alg), _n(param))


def pivot_param_keys(rows: list[dict]) -> set[tuple]:
    """파싱 피벗 행들 → (Zone, Alg, Parameter) 정규화 키 집합(양식 비교용)."""
    out = set()
    for r in rows:
        p = engine._s(r.get("param")).strip()
        if p:
            out.add(_norm_key3(r.get("zone"), r.get("alg"), p))
    return out


def form_to_pivot(xlsx: str) -> tuple[list[dict], dict]:
    """확정 양식(PI_ALL/RDL_ALL + _EXTRACT_MAP + 계수) → 편집기용 (rows, scales).
    rows = 파싱 피벗과 같은 형식(zone/alg/param/mag/raws/extract/use=True),
    scales = {변형: 계수}(추출_요약 우선, 없으면 변환방식 라벨에서 역추출).
    '기존 양식 수정하기'에서 엑셀 대신 프로그램 편집기로 불러올 때 사용.
    """
    from . import ini_parser
    repo = engine.ParamRepository(xlsx)
    repo.load()
    emap = extract_io.read_extract_map(xlsx)
    scales = dict(extract_io.read_scales(xlsx) or {})
    rows, label_coefs = [], {}
    for pr in repo.rows:
        level = engine._s(pr.get("PI"))
        variant = engine._s(pr.get("Recipe"))
        zone = engine._s(pr.get("Zone"))
        alg = engine._s(pr.get("Alg"))
        param = engine._s(pr.get("Parameter"))
        meta = emap.get(pr.row_id, {})
        transform = engine._s(meta.get("transform")) or "RAW"
        rows.append({
            "layer": level, "recipe": level, "mag": variant, "zone": zone,
            "alg": alg, "param": param, "values": {}, "unit": meta.get("unit", ""),
            "raws": {"양식": meta.get("raw")}, "use": True,
            "extract": {"src_file": meta.get("src_file", ""),
                        "section": meta.get("section", ""),
                        "key": meta.get("key", ""), "transform": transform,
                        "source_path": meta.get("source_path", "")}})
        c = ini_parser.scale_from_label(transform)
        if c is not None:
            label_coefs.setdefault(variant, c)
    for v, c in label_coefs.items():
        scales.setdefault(v, c)
    return rows, scales


def ext_key(variant, src_file, section, key) -> tuple:
    """설정키 = (변형, 설정파일, Section, 설정 Parameter) 정규화.

    후보 초안과 확정 양식을 이어붙일 때 **이름이 아니라 이 키로 맞춘다**
    (collate 가 값을 채울 때 쓰는 원칙과 같다). 사람이 양식에서 '최종
    Parameter' 이름을 바꿔 놨으면 이름으로는 매칭이 깨져 멀쩡한 항목이
    '새 항목'으로 튀어나온다.
    """
    import re

    def _n(s):
        return re.sub(r"[^0-9a-z가-힣µ]", "", engine._s(s).lower())
    return (_n(variant), _n(src_file), _n(section), _n(key))


def initial_to_pivot(xlsx: str) -> tuple[list[dict], set, set]:
    """편집용 초안(`관련파일/…_원본_….xlsx`) → (전체 후보 rows, 사용키, 이름키).

    확정 양식과 달리 초안에는 **체크하지 않은 파라미터까지 전부** 들어 있다.
    '기존 양식 수정하기'에서 빠져 있던 항목을 다시 넣을 수 있게 하는 소스다.
    반환 rows 는 파싱 피벗과 같은 형식이라 편집기에 그대로 넘길 수 있다.
      · 사용키 = 초안에서 사용=Y 였던 행의 `ext_key`
      · 이름키 = 모든 행의 `_norm_key3`(설정키가 비었을 때의 폴백 매칭용)
    """
    recs = read_initial_rows(xlsx)
    rows, used, names = [], set(), set()
    for r in recs:
        param = engine._s(r.get("최종 Parameter")).strip() or \
            engine._s(r.get("추천 Parameter")).strip()
        if not param:
            continue
        level = engine._s(r.get("PI")).strip()
        variant = engine._s(r.get("Recipe")).strip()
        zone = engine._s(r.get("Zone")).strip()
        alg = engine._s(r.get("Alg")).strip()
        ext = {"src_file": engine._s(r.get("설정파일")),
               "section": engine._s(r.get("설정 Section")),
               "key": engine._s(r.get("설정 Parameter")),
               "transform": engine._s(r.get("변환방식")) or "RAW",
               "source_path": ""}
        rows.append({
            "layer": level, "recipe": level, "mag": variant, "zone": zone,
            "alg": alg, "param": param, "values": {}, "unit": "",
            "raws": {"양식": r.get("Raw Value")},
            "use": _is_used(r.get("사용")), "extract": ext})
        names.add(_norm_key3(zone, alg, param))
        if _is_used(r.get("사용")):
            used.add(ext_key(variant, ext["src_file"], ext["section"], ext["key"]))
    return rows, used, names


def form_ext_keys(xlsx: str) -> set:
    """확정 양식의 설정키 집합 — `_EXTRACT_MAP` + Recipe(변형) 기준.

    '지금 이 양식이 실제로 쓰고 있는 항목'을 초안 후보에 표시하기 위한 것.
    """
    out = set()
    try:
        repo = engine.ParamRepository(xlsx)
        repo.load()
        emap = extract_io.read_extract_map(xlsx)
    except Exception:  # noqa: BLE001
        return out
    for pr in repo.rows:
        meta = emap.get(pr.row_id, {})
        out.add(ext_key(pr.get("Recipe"), meta.get("src_file", ""),
                        meta.get("section", ""), meta.get("key", "")))
    return out


def form_overlay(xlsx: str) -> dict:
    """확정 양식의 **사람이 고친 내용**을 설정키로 뽑는다.

    {설정키: {"param": 최종이름, "transform": 변환방식, "비고": …}}
    초안 후보 위에 덮어써서 이름·변환방식·비고를 잃지 않게 한다.
    """
    out = {}
    try:
        repo = engine.ParamRepository(xlsx)
        repo.load()
        emap = extract_io.read_extract_map(xlsx)
    except Exception:  # noqa: BLE001
        return out
    for pr in repo.rows:
        meta = emap.get(pr.row_id, {})
        k = ext_key(pr.get("Recipe"), meta.get("src_file", ""),
                    meta.get("section", ""), meta.get("key", ""))
        out[k] = {"param": engine._s(pr.get("Parameter")),
                  "zone": engine._s(pr.get("Zone")),
                  "alg": engine._s(pr.get("Alg")),
                  "level": engine._s(pr.get("PI")),
                  "variant": engine._s(pr.get("Recipe")),
                  "transform": engine._s(meta.get("transform")) or "RAW",
                  "raw": meta.get("raw"),
                  "src_file": engine._s(meta.get("src_file")),
                  "section": engine._s(meta.get("section")),
                  "key": engine._s(meta.get("key")),
                  "비고": engine._s(pr.get("비고")),
                  "unit": engine._s(meta.get("unit"))}
    return out


def merge_form_into_candidates(rows: list[dict], final_xlsx: str) -> tuple[list[dict], int]:
    """후보 rows(초안 전체) + 확정 양식 → 편집기에 넘길 rows.

    · 확정 양식에 있는 항목은 `use=True` 로 켜고, 사람이 고친 이름·변환방식·
      비고를 덮어쓴다(설정키 매칭, 없으면 Zone/Alg/Parameter 이름 폴백).
    · 확정 양식에만 있고 초안에 없는 항목(중간에 손으로 추가한 행 등)은
      **잃어버리면 안 되므로** 뒤에 덧붙인다.
    반환: (rows, 확정 양식과 매칭된 개수)
    """
    overlay = form_overlay(final_xlsx)
    by_name = {}
    for k, v in overlay.items():
        by_name.setdefault(_norm_key3(v["zone"], v["alg"], v["param"]), k)
    matched = set()
    for r in rows:
        ext = r.get("extract") or {}
        k = ext_key(r.get("mag"), ext.get("src_file"), ext.get("section"),
                    ext.get("key"))
        if k not in overlay:
            k = by_name.get(_norm_key3(r.get("zone"), r.get("alg"), r.get("param")))
        if k is None or k not in overlay:
            r["use"] = False              # 양식에 없던 항목 = 후보로만 보여 준다
            continue
        v = overlay[k]
        r["use"] = True
        r["param"] = v["param"] or r.get("param")
        r["unit"] = v["unit"] or r.get("unit", "")
        ext["transform"] = v["transform"] or ext.get("transform") or "RAW"
        r["extract"] = ext
        matched.add(k)
    for k, v in overlay.items():          # 초안에 없는 확정 항목은 살려서 덧붙인다
        if k in matched:
            continue
        rows.append({
            "layer": v["level"], "recipe": v["level"], "mag": v["variant"],
            "zone": v["zone"], "alg": v["alg"], "param": v["param"],
            "values": {}, "unit": v["unit"], "raws": {"양식": v["raw"]},
            "use": True,
            "extract": {"src_file": v["src_file"], "section": v["section"],
                        "key": v["key"], "transform": v["transform"],
                        "source_path": ""}})
    return rows, len(matched)


def rank_similar_forms(parsed_keys: set, forms: dict[str, set]) -> list[tuple]:
    """새 레시피(parsed_keys)와 기존 양식들(forms={레시피:키집합})의 겹치는 파라미터
    수로 정렬. 반환: [(레시피, 일치수, 기존항목수)] — 일치 많은 순(동률은 이름순)."""
    out = []
    for recipe, keys in forms.items():
        out.append((recipe, len(parsed_keys & keys), len(keys)))
    out.sort(key=lambda t: (-t[1], t[0]))
    return out


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
