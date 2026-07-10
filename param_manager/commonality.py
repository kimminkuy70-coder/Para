"""Commonality 조사 — 헤드리스 코어.

Scanresult 아래 여러 **Lot**(웨이퍼 로트)의 파라미터 값을 조사해 바뀐 부분(공통성)을
찾는다. 기존 양식 만들기/값 확인 흐름과 모듈을 최대한 재사용한다.

절대 안전 규칙(원본 보호): Scanresult 원본은 **읽기/복사만** 한다(수정/삭제/이동 금지).
복사는 downloader 의 안전 복사(.part→replace, 해시 검증)를 재사용한다.

경로 구조:
  {루트}/{AOI-호기}/Scanresult/{2D@디바이스_레시피}/{공정번호}/{S/M}/{웨이퍼번호}/
      ├─ Zones/*        (하위 ini 전체)
      ├─ RTP.txt        (표시값 — 변환계수 추정)
      └─ OpticPreset.ini
  웨이퍼 폴더는 **이름순 1번째** 1개만 조사한다.

흐름(GUI 가 호출):
  1) 호기 선택 → scanresult_root()
  2) Lot 계획 엑셀(디바이스명/공정번호/S·M/AOI호기) → read_plan()/filter_plan_for_machine()
     → resolve_plan()(폴더 실재 확인)
  3) copy_lot()(안전 복사)
  4) parse_lots()(대표 Lot 양식 만들기 소스) + structure_diff()(Lot 간 구조 확인)
  5) collate_lots()(양식 기준 Lot별 값) → write_lot_result()
  6) build_comparison()/write_comparison()(호기 취합·비교, 과반수 이탈 색칠)
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill

from . import collate, downloader, engine, ini_parser

# --------------------------------------------------------------------------
# Lot 계획 엑셀 (디바이스명 / 공정번호 / S/M / AOI호기)
# --------------------------------------------------------------------------
PLAN_HEADERS = ["디바이스명", "공정번호", "S/M", "AOI호기"]

# 취합 비교에서 값이 과반수와 다를 때 칠하는 색(연한 주황).
MISMATCH_FILL = "FFF2CC"
_HDR_FILL = "1F4E78"


def create_plan_template(path: str, rows: list[dict] | None = None) -> str:
    """Lot 계획 엑셀 템플릿 생성(사용자가 채워서 다시 업로드)."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Lot목록"
    ws.append(PLAN_HEADERS)
    for r in rows or []:
        ws.append([engine._s(r.get(h)) for h in PLAN_HEADERS])
    fill = PatternFill("solid", fgColor=_HDR_FILL)
    white = Font(color="FFFFFF", bold=True)
    for c in ws[1]:
        c.fill = fill
        c.font = white
        c.alignment = Alignment(horizontal="center", vertical="center")
    for col, w in zip("ABCD", (28, 18, 10, 12)):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A2"
    info = wb.create_sheet("사용법")
    for line in [
        ["Lot 계획 — 작성 방법"],
        ["1) 디바이스명: Scanresult 아래 '2D@..' 폴더명에 포함된 디바이스명"],
        ["   예) 2D@R3-S6WH11001-00001_... → 디바이스명 'S6WH11001-00001'"],
        ["2) 공정번호: 디바이스 폴더 아래 공정 폴더명(예: 6412)"],
        ["3) S/M: 공정 폴더 아래 폴더명(예: HPG / TVS / HCH)"],
        ["4) AOI호기: 이 공정이 검사된 호기(예: AOI-6). 선택한 호기 행만 조사합니다."],
    ]:
        info.append(line)
    info.column_dimensions["A"].width = 70
    wb.save(path)
    return path


def read_plan(path: str) -> list[dict]:
    """작성된 Lot 계획 엑셀 → dict 목록(헤더명 기준, 위치 변동 허용)."""
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["Lot목록"] if "Lot목록" in wb.sheetnames else wb[wb.sheetnames[0]]
    heads = [engine._s(c.value).strip() for c in ws[1]]
    hidx = {h: i for i, h in enumerate(heads) if h}
    out = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row is None or all(v in (None, "") for v in row):
            continue
        rec = {h: engine._s(row[i]).strip() if i < len(row) else ""
               for h, i in hidx.items()}
        # 디바이스명/공정번호 중 하나라도 있으면 유효 행
        if rec.get("디바이스명") or rec.get("공정번호"):
            out.append(rec)
    wb.close()
    return out


def filter_plan_for_machine(plan_rows: list[dict], machine: str) -> list[dict]:
    """선택한 호기(AOI호기) 행만 필터. 호기 정규화 비교(AOI-9 == AOI-09)."""
    mk = _aoi_norm(machine)
    return [r for r in plan_rows if _aoi_norm(r.get("AOI호기")) == mk]


# --------------------------------------------------------------------------
# 폴더 해석 (디바이스명 + 공정번호 + S/M → 실제 웨이퍼 폴더)
# --------------------------------------------------------------------------
def _norm(s) -> str:
    """매칭용 정규화 — 소문자화 + 영숫자/한글만(구분자 -,_,공백,@ 제거)."""
    return re.sub(r"[^0-9a-z가-힣]", "", str(s or "").lower())


def _aoi_norm(s) -> str:
    """호기 식별용 정규화 — 숫자의 앞 0 무시(AOI-9 == AOI-09 == AOI_9)."""
    s = str(s or "")
    letters = re.sub(r"[^a-z]", "", s.lower())
    m = re.search(r"(\d+)", s)
    num = str(int(m.group(1))) if m else ""
    return letters + num


@dataclass
class LotFolder:
    device: str
    lot: str
    sm: str
    machine: str
    label: str                        # 취합 열/식별용(예: '6321_HPG')
    wafer_dir: Path | None = None     # 이름순 첫 웨이퍼 폴더(조사 대상)
    exists: bool = False
    has_zones: bool = False
    has_rtp: bool = False
    has_optic: bool = False
    reason: str = ""                  # 실패 사유(폴더 없음 등)


def _is_scanresult_name(name: str) -> bool:
    """'Scanresult' 및 변형(Scanresult_260401 등) 인식."""
    return _norm(name).startswith("scanresult")


def _find_scanresult_dir(parent: Path) -> Path | None:
    """parent 바로 아래에서 'Scanresult*' 폴더(이름순 첫)."""
    if not parent.is_dir():
        return None
    try:
        hits = sorted((p for p in parent.iterdir()
                       if p.is_dir() and _is_scanresult_name(p.name)),
                      key=lambda x: x.name.lower())
    except OSError:
        return None
    return hits[0] if hits else None


def _find_machine_dir(parent: Path, machine: str) -> Path | None:
    """parent 아래에서 호기 폴더(AOI 번호 정규화 — AOI-9 == AOI-09)."""
    if not parent.is_dir():
        return None
    mk = _aoi_norm(machine)
    if not mk:
        return None
    try:
        for p in parent.iterdir():
            if p.is_dir() and _aoi_norm(p.name) == mk:
                return p
    except OSError:
        return None
    return None


def scanresult_root(root_base: str, machine: str) -> Path:
    """호기 루트 base → Scanresult 폴더. 실제 폴더 변형에 견고하게:
      - Scanresult 폴더명 변형(Scanresult_260401 등) 인식,
      - 호기 폴더 AOI 번호 0 패딩 차이(AOI-9 == AOI-09) 흡수.
    base 는 W:\\ 같은 상위, W:\\AOI-9(호기폴더), 또는 Scanresult 폴더 자체 모두 허용."""
    base = Path(root_base)
    if _is_scanresult_name(base.name):        # base 가 Scanresult* 자체
        return base
    sr = _find_scanresult_dir(base)           # base 가 호기 폴더 → 바로 아래 Scanresult*
    if sr:
        return sr
    mdir = _find_machine_dir(base, machine)   # base 아래 호기 폴더 탐색(0패딩 흡수)
    if mdir is None and (base / machine).is_dir():
        mdir = base / machine
    if mdir is not None:
        sr = _find_scanresult_dir(mdir)
        if sr:
            return sr
        return mdir / "Scanresult"
    return base / machine / "Scanresult"


def _find_child(parent: Path, name: str, *, contains: bool = True) -> Path | None:
    """parent 아래에서 name 과 일치(정규화)하는 폴더. 정확 일치 우선, 없으면 포함."""
    if not parent.is_dir():
        return None
    try:
        dirs = [p for p in parent.iterdir() if p.is_dir()]
    except OSError:
        return None
    nk = _norm(name)
    if not nk:
        return None
    for p in dirs:                       # 1) 정규화 정확 일치
        if _norm(p.name) == nk:
            return p
    if contains:                         # 2) 정규화 포함(디바이스명이 폴더명 일부)
        hits = [p for p in dirs if nk in _norm(p.name)]
        if len(hits) == 1:
            return hits[0]
        if hits:                         # 여러 개면 이름순 첫 번째(결정적)
            return sorted(hits, key=lambda x: x.name.lower())[0]
    return None


def _first_wafer(sm_dir: Path) -> Path | None:
    """S/M 폴더 아래 **이름순 첫** 웨이퍼 폴더."""
    if not sm_dir.is_dir():
        return None
    try:
        dirs = sorted((p for p in sm_dir.iterdir() if p.is_dir()),
                      key=lambda x: x.name.lower())
    except OSError:
        return None
    return dirs[0] if dirs else None


def resolve_lot(scan_root: Path, device: str, lot: str, sm: str,
                machine: str = "") -> LotFolder:
    """디바이스명 + 공정번호 + S/M → LotFolder(웨이퍼 폴더 확정 + 대상파일 확인).
    lot 인자 = 공정번호(폴더 레벨)."""
    label = "_".join(x for x in (lot, sm) if x) or device or "lot"
    lf = LotFolder(device=device, lot=lot, sm=sm, machine=machine, label=label)
    dev_dir = _find_child(scan_root, device)
    if dev_dir is None:
        lf.reason = f"디바이스 폴더 없음: {device}"
        return lf
    lot_dir = _find_child(dev_dir, lot)
    if lot_dir is None:
        lf.reason = f"공정 폴더 없음: {lot}"
        return lf
    sm_dir = _find_child(lot_dir, sm) if sm else lot_dir
    if sm_dir is None:
        lf.reason = f"S/M 폴더 없음: {sm}"
        return lf
    wafer = _first_wafer(sm_dir)
    if wafer is None:
        lf.reason = "웨이퍼 폴더 없음"
        return lf
    z = (wafer / downloader.TARGET_FOLDER_NAME).is_dir()
    r = (wafer / "RTP.txt").is_file()
    o = (wafer / "OpticPreset.ini").is_file()
    lf.wafer_dir, lf.exists = wafer, True
    lf.has_zones, lf.has_rtp, lf.has_optic = z, r, o
    if not (z or r or o):
        lf.reason = "웨이퍼 폴더에 대상 파일(Zones/RTP/Optic) 없음"
    return lf


def resolve_plan(scan_root: Path, plan_rows: list[dict]) -> list[LotFolder]:
    """계획 행들 → LotFolder 목록(실재/사유 포함). 순서 보존."""
    out = []
    for r in plan_rows:
        out.append(resolve_lot(scan_root, r.get("디바이스명", ""),
                               r.get("공정번호", ""), r.get("S/M", ""),
                               r.get("AOI호기", "")))
    return out


# --------------------------------------------------------------------------
# 안전 복사 (원본 read-only) — downloader 재사용
# --------------------------------------------------------------------------
def copy_lot(lot: LotFolder, dest_root: str, verify: bool = True) -> dict:
    """Lot 웨이퍼 폴더의 대상(Zones/RTP/Optic)만 dest_root/{label}/ 로 안전 복사."""
    if not lot.exists or lot.wafer_dir is None:
        raise RuntimeError(f"복사할 웨이퍼 폴더가 없습니다: {lot.label} ({lot.reason})")
    dst_base = Path(dest_root) / downloader.safe_name(lot.label)
    zones, files = downloader.collect_target_items(lot.wafer_dir)
    rows = []
    for src in files:
        if zones.is_dir() and zones in src.parents:
            dst = dst_base / src.relative_to(lot.wafer_dir)
        else:
            dst = dst_base / src.name
        rows.append(downloader.copy_one_file(src, dst, overwrite=False, verify=verify))
    return {"label": lot.label, "dest": str(dst_base), "files": rows, "count": len(rows)}


# --------------------------------------------------------------------------
# Lot 파싱 → 통합 피벗(값=Lot별) + 구조 diff
# --------------------------------------------------------------------------
def _lot_configs(config_dir: Path, lot_label: str, level: str,
                 scales: dict | None) -> list[ini_parser.ParsedConfig]:
    """Lot 1개의 config 폴더 → ParsedConfig 목록(equipment=lot_label 로 태깅)."""
    return ini_parser.scan_tree(config_dir, default_level=level,
                                default_equipment=lot_label, scales=scales)


def parse_lots(lot_dirs: list[tuple[str, Path]], level: str = "",
               scales: dict | None = None) -> tuple[list[dict], list[str]]:
    """[(lot_label, config_dir)] → (통합 피벗, lot_label 목록).

    build_pivot 이 값을 equipment(=lot_label) 별로 모아주므로, 그대로
    collate.collate_recipe(machines_all=lot_labels) 에 넘길 수 있다.
    """
    all_cfgs: list[ini_parser.ParsedConfig] = []
    labels: list[str] = []
    for label, cdir in lot_dirs:
        if label not in labels:
            labels.append(label)
        all_cfgs += _lot_configs(Path(cdir), label, level, scales)
    pivot_rows, _ = ini_parser.build_pivot(all_cfgs)
    return pivot_rows, labels


def structure_diff(lot_dirs: list[tuple[str, Path]], level: str = "",
                   scales: dict | None = None) -> dict:
    """Lot 간 파라미터 **구조**(zone/alg/param 집합) 비교.

    반환: {"baseline_count": N, "lots": {label: {"missing":[...], "extra":[...]}},
           "identical": bool}. 대표(합집합) 대비 빠진/추가 항목을 알린다.
    """
    per_lot: dict[str, set] = {}
    for label, cdir in lot_dirs:
        keys = per_lot.setdefault(label, set())
        for cfg in _lot_configs(Path(cdir), label, level, scales):
            for r in cfg.rows:
                keys.add((r.zone, r.alg, r.param))
    union: set = set()
    for s in per_lot.values():
        union |= s
    lots = {}
    identical = True
    for label, s in per_lot.items():
        missing = sorted(union - s)
        if missing:
            identical = False
        lots[label] = {
            "missing": [f"{z}/{a}/{p}" for z, a, p in missing],
            "count": len(s),
        }
    return {"baseline_count": len(union), "lots": lots, "identical": identical}


# --------------------------------------------------------------------------
# Step 5: 양식 기준 Lot별 값 → 호기 결과 엑셀
# --------------------------------------------------------------------------
def collate_lots(recipe: str, form_path: str, pivot_rows: list[dict],
                 lot_labels: list[str]) -> collate.CollateRecipe:
    """확정 양식 + 통합 피벗 → Lot 열 채운 CollateRecipe(collate 재사용)."""
    return collate.collate_recipe(recipe, form_path, pivot_rows, lot_labels)


def write_lot_result(dest_xlsx: str, recipe: str, machine: str,
                     res: collate.CollateRecipe, lot_labels: list[str]) -> str:
    """호기 1대 결과: 시트=레시피, 헤더=META + Lot들. 호기명은 '_정보' 시트에 기록."""
    headers = list(engine.META_FIELDS) + list(lot_labels)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = collate._safe_sheet(recipe)
    ws.append(headers)
    for rec in res.records:
        ws.append([rec.get(h) for h in headers])
    fill = PatternFill("solid", fgColor=_HDR_FILL)
    white = Font(color="FFFFFF", bold=True)
    for c in ws[1]:
        c.fill = fill
        c.font = white
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.freeze_panes = "A2"
    meta = wb.create_sheet("_정보")
    meta.append(["호기", machine])
    meta.append(["레시피", recipe])
    meta.append(["Lot수", len(lot_labels)])
    for label in lot_labels:
        meta.append(["Lot", label])
    wb.save(dest_xlsx)
    return dest_xlsx


def read_lot_result(path: str) -> dict:
    """호기 결과 엑셀 → {machine, recipe, lots, records}. records=행dict(META+Lot값)."""
    wb = openpyxl.load_workbook(path, data_only=True)
    machine = recipe = ""
    if "_정보" in wb.sheetnames:
        for row in wb["_정보"].iter_rows(values_only=True):
            if not row:
                continue
            if row[0] == "호기":
                machine = engine._s(row[1])
            elif row[0] == "레시피":
                recipe = engine._s(row[1])
    data_ws = next((ws for ws in wb.worksheets if ws.title != "_정보"), None)
    records, lots = [], []
    if data_ws is not None:
        if not recipe:
            recipe = data_ws.title
        heads = [engine._s(c.value).strip() for c in data_ws[1]]
        meta = set(engine.META_FIELDS)
        lots = [h for h in heads if h and h not in meta]
        for row in data_ws.iter_rows(min_row=2, values_only=True):
            if row is None or all(v in (None, "") for v in row):
                continue
            records.append({heads[i]: row[i] for i in range(len(heads)) if i < len(row)})
    wb.close()
    return {"machine": machine, "recipe": recipe, "lots": lots, "records": records}


# --------------------------------------------------------------------------
# Step 6: 호기 취합·비교 (행=공정번호/호기, 열=파라미터, 과반수 이탈 색칠)
# --------------------------------------------------------------------------
def _param_label(rec: dict) -> str:
    """비교 표의 파라미터 열 이름 — Zone/Alg/Parameter 조합(중복 회피)."""
    parts = [engine._s(rec.get("Zone")), engine._s(rec.get("Alg")),
             engine._s(rec.get("Parameter"))]
    return " / ".join(p for p in parts if p) or engine._s(rec.get("Parameter"))


def build_comparison(result_files: list[str]) -> dict:
    """여러 호기 결과 엑셀 → 비교 표.

    반환:
      {"columns": ["공정번호","호기", param1, param2, ...],
       "rows": [{"공정번호","호기", param: value, ...}, ...],
       "outliers": {(row_idx, param), ...},   # 과반수와 다른 셀
       "changed_params": [param, ...]}        # 값이 갈리는 파라미터만
    각 (호기, 공정) 조합이 한 행. 파라미터 열은 모든 파일의 합집합(순서 보존).
    """
    params: list[str] = []
    param_seen: set = set()
    rows: list[dict] = []
    for path in result_files:
        data = read_lot_result(path)
        machine = data["machine"] or Path(path).stem
        # 파라미터 열(순서 보존) 및 Lot별 값 맵
        by_param_value: dict[str, dict[str, object]] = {}
        for rec in data["records"]:
            pl = _param_label(rec)
            if pl not in param_seen:
                param_seen.add(pl)
                params.append(pl)
            by_param_value[pl] = {lot: rec.get(lot) for lot in data["lots"]}
        for lot in data["lots"]:
            row = {"공정번호": lot, "호기": machine}
            for pl in by_param_value:
                row[pl] = by_param_value[pl].get(lot)
            rows.append(row)

    # 과반수(mode) 대비 이탈 셀 + 값이 갈리는 파라미터
    outliers: set = set()
    changed: list[str] = []
    for pl in params:
        vals = [engine._s(r.get(pl)) for r in rows if engine._s(r.get(pl)) != ""]
        if not vals:
            continue
        common, _ = Counter(vals).most_common(1)[0]
        distinct = set(vals)
        if len(distinct) > 1:
            changed.append(pl)
        for i, r in enumerate(rows):
            v = engine._s(r.get(pl))
            if v != "" and v != common:
                outliers.add((i, pl))
    return {"columns": ["공정번호", "호기"] + params, "rows": rows,
            "outliers": outliers, "changed_params": changed}


def write_comparison(dest_xlsx: str, comparison: dict,
                     changed_only: bool = False) -> str:
    """비교 표 → 엑셀(과반수 이탈 셀 색칠). changed_only=True 면 변경 파라미터만."""
    params = (comparison["changed_params"] if changed_only
              else comparison["columns"][2:])
    columns = ["공정번호", "호기"] + list(params)
    rows = comparison["rows"]
    outliers = comparison["outliers"]

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "취합비교"
    ws.append(columns)
    hdr = PatternFill("solid", fgColor=_HDR_FILL)
    white = Font(color="FFFFFF", bold=True)
    for c in ws[1]:
        c.fill = hdr
        c.font = white
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    mismatch = PatternFill("solid", fgColor=MISMATCH_FILL)
    for i, r in enumerate(rows):
        ws.append([r.get(col) for col in columns])
        excel_row = i + 2
        for j, col in enumerate(columns[2:], start=3):
            if (i, col) in outliers:
                ws.cell(row=excel_row, column=j).fill = mismatch
    ws.freeze_panes = "C2"
    ws.column_dimensions["A"].width = 16
    ws.column_dimensions["B"].width = 10
    wb.save(dest_xlsx)
    return dest_xlsx
