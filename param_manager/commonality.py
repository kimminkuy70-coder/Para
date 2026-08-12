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
  조사할 웨이퍼(슬롯) 폴더는 **사람이 고른다**(기본 = 이름순 1번째).
  여러 개 고르면 `expand_wafers` 가 슬롯마다 별도 조사 대상으로 펼친다.

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
from dataclasses import dataclass, field, replace
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill

from . import collate, downloader, engine, ini_parser

# --------------------------------------------------------------------------
# Lot 계획 엑셀 (디바이스명 / 공정번호 / S/M / AOI호기)
# --------------------------------------------------------------------------
# 조사할 Lot 목록(사람이 채우는 파일). '감시 대상 계획'(cmwatcher.WATCH_PLAN_*) 과
# 헷갈리지 않게 파일 이름을 구분한다 — 이건 **무엇을 조사할지**, 저건 **무엇을 감시할지**.
PLAN_FILENAME = "Commonality_Lot계획.xlsx"
# '생성일자' = 자동 감시가 새 S/M 을 찾아 넣을 때 그 폴더가 언제 생겼는지(사람 입력 아님).
PLAN_HEADERS = ["디바이스명", "공정번호", "S/M", "AOI호기", "fail여부", "생성일자"]
# 구 템플릿(LOT번호) 하위호환 — 읽을 때 공정번호로 통일.
_HEADER_ALIASES = {"LOT번호": "공정번호", "LOT": "공정번호", "공정 번호": "공정번호",
                   "공정 Number": "공정번호", "Fail": "fail여부", "FAIL": "fail여부",
                   "fail": "fail여부", "fail 여부": "fail여부"}
_YES = {"y", "yes", "1", "true", "o", "예", "fail", "ng", "불량"}

# 취합 비교에서 값이 과반수와 다를 때 칠하는 색(연한 주황).
MISMATCH_FILL = "FFF2CC"
# fail=Y 인 S/M 을 표시하는 노란색(엑셀·뷰어 공통).
FAIL_FILL = "FFF176"
# 양식과 매칭이 적은 S/M(자동 감시가 조사했지만 양식이 잘 안 맞음) — 연한 빨강.
# **열은 남기되** 색으로 구분한다(사용자 확정 2026-08): 지워 버리면 그런 S/M 이
# 있었다는 사실 자체가 사라져, 왜 비었는지 나중에 알 수 없다.
LOWMATCH_FILL = "F4CCCC"
_HDR_FILL = "1F4E78"


def _is_yes(v) -> bool:
    return _norm(v) in _YES


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
    for col, w in zip("ABCDEF", (28, 18, 12, 12, 10, 18)):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A2"
    info = wb.create_sheet("사용법")
    for line in [
        ["Lot 계획 — 작성 방법"],
        ["1) 디바이스명: Scanresult 아래 '2D@..' 폴더명에 포함된 디바이스명"],
        ["   예) 2D@R3-S6WH11001-00001_... → 디바이스명 'S6WH11001-00001'"],
        ["2) 공정번호: 디바이스 폴더 아래 공정 폴더명(예: 6412)"],
        ["3) S/M: 공정 폴더 아래 폴더명(예: HPG / TVS / HCH). 변형 이름"
         "(CFG X20, CFG #14 REWORK 등)도 자동으로 찾아 후보로 올립니다."],
        ["4) AOI호기: 이 공정이 검사된 호기(예: AOI-6). 선택한 호기 행만 조사합니다."],
        ["5) fail여부: 이 S/M 이 fail 이면 Y(비교표·뷰어에서 노란색으로 표시). 아니면 비움/N."],
        ["6) 생성일자: 비워 두세요. 자동 감시가 새 S/M 을 찾아 넣을 때 그 폴더가"],
        ["   언제 생겼는지 자동으로 채웁니다."],
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
    heads = [_HEADER_ALIASES.get(h, h) for h in heads]   # 구 'LOT번호' → '공정번호'
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


def _machine_ids(text) -> set:
    """호기 셀에서 호기 번호 집합 추출. 'AOI-09'→{9}, 'AOI-4,6,9'→{4,6,9}."""
    return {int(n) for n in re.findall(r"\d+", str(text or ""))}


def filter_plan_for_machine(plan_rows: list[dict], machine: str) -> list[dict]:
    """선택한 호기 행만 필터. 0패딩(AOI-9==AOI-09)·여러 호기 한 칸(AOI-4,6,9) 지원."""
    want = _machine_ids(machine)
    if not want:
        return []
    wnum = next(iter(want))               # 선택 호기는 1개
    return [r for r in plan_rows if wnum in _machine_ids(r.get("AOI호기"))]


# --------------------------------------------------------------------------
# 폴더 해석 (디바이스명 + 공정번호 + S/M → 실제 웨이퍼 폴더)
# --------------------------------------------------------------------------
def _norm(s) -> str:
    """매칭용 정규화 — 소문자화 + 영숫자/한글만(구분자 -,_,공백,@ 제거)."""
    return re.sub(r"[^0-9a-z가-힣]", "", str(s or "").lower())


def _tokens(s) -> list[str]:
    """'SUA RETURN PG8E10' → ['sua','return','pg8e10'] (매칭용 단어 분해)."""
    return [_norm(t) for t in re.split(r"[^0-9A-Za-z가-힣]+", str(s or "")) if _norm(t)]


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
    label: str                        # 취합 열/식별용 = 실제 S/M 폴더명(변형 포함)
    wafer_dir: Path | None = None     # 조사 대상 웨이퍼(슬롯) 폴더 — 기본은 이름순 첫
    wafer_choices: list = field(default_factory=list)   # 고를 수 있는 슬롯 폴더 전부
    wafer_picks: list = field(default_factory=list)     # 사람이 고른 슬롯(여러 개 가능)
    scan_time: str = ""               # S/M 폴더 수정시각 = Scan 일자(언제 스캔됐는지)
    exists: bool = False
    has_zones: bool = False
    has_rtp: bool = False
    has_optic: bool = False
    reason: str = ""                  # 실패 사유(폴더 없음 등)
    fail: bool = False                # 계획의 fail여부=Y (노란색 표시)


def _is_scanresult_name(name: str) -> bool:
    """'Scanresult' 및 변형(Scanresult_260401 등) 인식."""
    return _norm(name).startswith("scanresult")


def _find_scanresult_dirs(parent: Path) -> list[Path]:
    """parent 바로 아래 'Scanresult*' 폴더 **전부**(백업본 포함, 이름순)."""
    if not parent.is_dir():
        return []
    try:
        return sorted((p for p in parent.iterdir()
                       if p.is_dir() and _is_scanresult_name(p.name)),
                      key=lambda x: x.name.lower())
    except OSError:
        return []


def _find_scanresult_dir(parent: Path) -> Path | None:
    """parent 바로 아래 'Scanresult*' 폴더 하나(이름순 첫, 하위호환)."""
    hits = _find_scanresult_dirs(parent)
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


def scanresult_roots(root_base: str, machine: str) -> list[Path]:
    """호기 폴더만 지정하면 그 아래 **Scanresult 폴더 전부**(백업본 포함) 반환.

    예: W:\\AOI-9 아래 Scanresult / Scanresult_260402 / SCANRESULT_BACKUP_260805 가
    있으면 **모두** 반환해 Lot 을 여기저기서 찾는다.
    base 는 W:\\ 같은 상위, W:\\AOI-9(호기폴더), 또는 Scanresult 폴더 자체 모두 허용:
      - base 가 Scanresult* 자체 → [base]
      - base 아래에 Scanresult* 들 → 그 전부
      - base 아래 호기 폴더(AOI-9==AOI-09) → 그 아래 Scanresult* 전부
    실제 폴더 변형(이름·0패딩)에 견고. 아무것도 없으면 기본 경로 1개."""
    base = Path(root_base)
    if _is_scanresult_name(base.name):        # base 가 Scanresult* 자체
        return [base]
    here = _find_scanresult_dirs(base)        # base 가 호기 폴더 → 바로 아래 전부
    if here:
        return here
    mdir = _find_machine_dir(base, machine)   # base 아래 호기 폴더(0패딩 흡수)
    if mdir is None and (base / machine).is_dir():
        mdir = base / machine
    if mdir is not None:
        sub = _find_scanresult_dirs(mdir)
        return sub or [mdir / "Scanresult"]
    return [base / machine / "Scanresult"]


def scanresult_root(root_base: str, machine: str) -> Path:
    """단일 Scanresult 경로(하위호환) — 첫 번째."""
    return scanresult_roots(root_base, machine)[0]


def _find_children(parent: Path, name: str, *, contains: bool = True) -> list[Path]:
    """parent 아래에서 name 과 맞는 폴더 **후보 전부**(정확일치 먼저, 그 뒤 이름순).

    **정확일치가 있어도 포함 매칭 후보를 함께 돌려준다(2026-08 수정).** 종전에는
    정확일치가 하나라도 있으면 거기서 끝냈는데, 그러면 `ASD` 를 찾을 때 `ASD` 만
    나오고 `ASD X20`·`ASD REWORK`·`ASD-RW_0517S` 같은 **변형이 통째로 숨었다**.
    어느 것을 조사할지는 사람이 골라야 하므로 후보를 다 올린다.

    · `contains=False`(공정번호처럼 숫자라 포함매칭이 위험할 때)는 **정확일치만**.
      6412 가 64120/16412 에 걸리면 안 되기 때문.
    · 정확·포함이 하나도 없을 때만 **토큰(단어) 겹침**으로 한 번 더 찾는다
      ('SUA RERURN PG8E10' 처럼 오타·군더더기가 붙은 폴더 흡수). 이 단계는 느슨해서
      정상 후보가 있을 때는 쓰지 않는다.
    """
    if not parent.is_dir():
        return []
    try:
        dirs = sorted((p for p in parent.iterdir() if p.is_dir()),
                      key=lambda x: x.name.lower())
    except OSError:
        return []
    nk = _norm(name)
    if not nk:
        return []
    exact = [p for p in dirs if _norm(p.name) == nk]
    if not contains:
        return exact
    part = [p for p in dirs
            if p not in exact and (nk in _norm(p.name) or _norm(p.name) in nk)]
    if exact or part:
        return exact + part          # 정확일치를 앞에 두어 기본 선택이 되게 한다
    # 실제 폴더는 'SUA RERURN PG8E10' 처럼 오타·군더더기가 붙는다. 정확·포함
    # 매칭이 **둘 다** 실패했을 때만 토큰 겹침으로 한 번 더 찾는다.
    toks = [t for t in _tokens(name) if len(t) >= 2]
    if not toks:
        return []
    return [p for p in dirs if any(t in _norm(p.name) for t in toks)]


def _find_child(parent: Path, name: str, *, contains: bool = True) -> Path | None:
    """후보 중 첫 번째(하위호환)."""
    hits = _find_children(parent, name, contains=contains)
    return hits[0] if hits else None


def _bfs_exact(parent: Path, name: str, max_depth: int = 3) -> list[Path]:
    """parent 이하 max_depth 단계까지 **정규화 정확일치** 폴더(가장 얕은 깊이 우선).
    공정번호처럼 숫자라 포함매칭이 위험할 때, 중간 폴더가 한 단계 더 있어도 찾는다."""
    nk = _norm(name)
    if not parent.is_dir() or not nk:
        return []
    level = [parent]
    for _ in range(max_depth):
        found, nxt = [], []
        for d in level:
            try:
                kids = [p for p in d.iterdir() if p.is_dir()]
            except OSError:
                kids = []
            for k in kids:
                if _norm(k.name) == nk:
                    found.append(k)
                nxt.append(k)
        if found:
            return sorted(found, key=lambda x: x.name.lower())
        level = nxt
    return []


def folder_mtime(path) -> str:
    """폴더 수정시각 'YYYY-MM-DD HH:MM'. 못 읽으면 빈 문자열.
    S/M 폴더의 수정시각을 **Scan 일자**(언제 스캔된 자료인지)로 쓴다."""
    try:
        from datetime import datetime as _dt
        return _dt.fromtimestamp(Path(path).stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    except (OSError, ValueError, OverflowError):
        return ""


def list_wafers(sm_dir: Path) -> list[Path]:
    """S/M 폴더 아래 웨이퍼(슬롯) 폴더 **전부** — 이름순.

    한 Lot 에 슬롯이 여러 개 있어도 파라미터를 보는 데는 1개면 되므로 기본은
    이름순 첫 번째지만, **어느 슬롯을 볼지 사람이 고를 수 있어야 한다**
    (슬롯마다 스캔이 다르게 남아 있을 수 있음).
    """
    if not sm_dir.is_dir():
        return []
    try:
        return sorted((p for p in sm_dir.iterdir() if p.is_dir()),
                      key=lambda x: x.name.lower())
    except OSError:
        return []


def _first_wafer(sm_dir: Path) -> Path | None:
    """S/M 폴더 아래 **이름순 첫** 웨이퍼(슬롯) 폴더."""
    wafers = list_wafers(sm_dir)
    return wafers[0] if wafers else None


def set_wafer(lot: LotFolder, wafer) -> LotFolder:
    """조사할 웨이퍼(슬롯) 폴더를 바꾼다 — 대상 파일(Zones/RTP/Optic) 유무도 다시 판정.
    선택창에서 다른 슬롯을 고르면 호출된다(같은 객체를 갱신)."""
    w = Path(wafer)
    lot.wafer_dir = w
    lot.has_zones = (w / downloader.TARGET_FOLDER_NAME).is_dir()
    lot.has_rtp = (w / "RTP.txt").is_file()
    lot.has_optic = (w / "OpticPreset.ini").is_file()
    lot.exists = w.is_dir()
    lot.reason = "" if (lot.has_zones or lot.has_rtp or lot.has_optic) else \
        "웨이퍼 폴더에 대상 파일(Zones/RTP/Optic) 없음"
    return lot


def expand_wafers(lot: LotFolder) -> list[LotFolder]:
    """고른 슬롯마다 조사 대상 LotFolder 를 만든다(**슬롯 다중 선택**).

    한 Lot 에서 슬롯을 여러 개 고르면 슬롯마다 값이 다를 수 있으므로 각각을
    별도 조사 대상으로 펼친다. 취합 열(라벨)이 겹치면 안 되므로 2개 이상일 때만
    라벨 뒤에 슬롯명을 붙인다(1개면 기존과 똑같은 라벨 = 이전 결과와 비교 가능).
    고른 것이 없으면 지금 대상(wafer_dir) 하나만 돌려준다.
    """
    picks = [Path(p) for p in (lot.wafer_picks or [])]
    if not picks:
        return [lot]
    if len(picks) == 1 and picks[0] == lot.wafer_dir:
        return [lot]
    out: list[LotFolder] = []
    for w in picks:
        clone = replace(lot, wafer_choices=list(lot.wafer_choices), wafer_picks=[w])
        set_wafer(clone, w)
        if len(picks) > 1:
            clone.label = f"{lot.label}·{w.name}"
        out.append(clone)
    return out


def expand_all(lots: list[LotFolder]) -> list[LotFolder]:
    """선택된 Lot 목록을 슬롯 선택까지 펼친다(조사 직전에 한 번 호출)."""
    out: list[LotFolder] = []
    for l in lots or []:
        out.extend(expand_wafers(l))
    return out


def _make_lotfolder(device, lot, sm, machine, sm_dir: Path, wafer: Path,
                    fail: bool, wafers: list | None = None) -> LotFolder:
    """찾은 S/M 폴더 → LotFolder. 라벨 = 실제 S/M 폴더명(변형 포함).
    wafers 를 주면 폴더를 다시 훑지 않는다(네트워크 폴더라 목록 조회가 비싸다)."""
    label = sm_dir.name if sm else (engine._s(lot).strip() or device or "lot")
    lf = LotFolder(device=device, lot=lot, sm=sm_dir.name if sm else sm,
                   machine=machine, label=label, fail=fail,
                   scan_time=folder_mtime(sm_dir),      # S/M 폴더 수정시각 = Scan 일자
                   wafer_choices=list(wafers if wafers is not None
                                      else list_wafers(sm_dir)))
    return set_wafer(lf, wafer)


def _as_roots(scan_roots) -> list[Path]:
    """단일 Path/str 또는 리스트를 Scanresult 루트 목록으로 정규화."""
    if isinstance(scan_roots, (list, tuple, set)):
        return [Path(p) for p in scan_roots]
    return [Path(scan_roots)]


def resolve_lot_variants(scan_roots, device: str, lot: str, sm: str,
                         machine: str = "", fail: bool = False) -> list[LotFolder]:
    """디바이스+공정+S/M → **찾은 S/M 폴더마다** LotFolder(변형 이름 다중 지원).

    scan_roots 는 Scanresult 루트 **하나 또는 여러 개**(백업본 포함) — 전부 탐색한다.
    S/M 폴더는 정확 일치가 있으면 그것만, 없으면 **포함 매칭 후보 전부**
    (예: 'CFG' → 'CFG X20' / 'CFG #14 REWORK' / 'CFG-RW_0517S'). 못 찾으면
    사유가 담긴 LotFolder 1개를 돌려준다(exists=False)."""
    fallback = LotFolder(device=device, lot=lot, sm=sm, machine=machine,
                         label=(engine._s(sm).strip() or engine._s(lot).strip()
                                or device or "lot"), fail=fail)
    out: list[LotFolder] = []
    seen: set = set()
    dev_found = reached_lot = reached_sm = False
    for scan_root in _as_roots(scan_roots):        # 백업 포함 모든 Scanresult 탐색
        dev_dirs = _find_children(scan_root, device)
        if not dev_dirs:
            continue
        dev_found = True
        for dev_dir in dev_dirs:
            # 공정번호는 숫자 → 정확일치만(6412 가 64120/16412 에 오매칭 방지) + BFS 폴백.
            lot_dirs = _find_children(dev_dir, lot, contains=False) \
                or _bfs_exact(dev_dir, lot, max_depth=3)
            for lot_dir in lot_dirs:
                reached_lot = True
                # S/M: ①정확 일치 → ②포함(양방향) → ③토큰 겹침(+BFS) 3단계.
                # 못 찾으면 그대로 '폴더 없음' — 관계없는 폴더를 후보로 올리지 않는다.
                sm_dirs = (_find_children(lot_dir, sm) or _bfs_exact(lot_dir, sm, 2)) \
                    if sm else [lot_dir]
                for sm_dir in sm_dirs:
                    reached_sm = True
                    wafers = list_wafers(sm_dir)      # 슬롯 선택 후보(기본 = 첫 번째)
                    if not wafers:
                        continue
                    wafer = wafers[0]
                    key = str(wafer.resolve()) if wafer else str(sm_dir)
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append(_make_lotfolder(device, lot, sm, machine, sm_dir,
                                               wafer, fail, wafers))
    if out:
        return sorted(out, key=lambda l: l.label.lower())
    if not dev_found:
        fallback.reason = f"디바이스 폴더 없음: {device}"
    elif not reached_lot:
        fallback.reason = f"공정 폴더 없음: {lot}"
    elif not reached_sm:
        fallback.reason = f"S/M 폴더 없음: {sm}"
    else:
        fallback.reason = "웨이퍼 폴더 없음"
    return [fallback]


def resolve_lot(scan_roots, device: str, lot: str, sm: str,
                machine: str = "") -> LotFolder:
    """단일 반환(하위호환) — 변형 후보 중 첫 번째."""
    return resolve_lot_variants(scan_roots, device, lot, sm, machine)[0]


def resolve_plan(scan_roots, plan_rows: list[dict]) -> list[LotFolder]:
    """계획 행들 → LotFolder 목록. S/M 변형은 각각 별도 항목으로 펼친다.
    scan_roots 는 Scanresult 루트 하나 또는 여러 개(백업본 포함). fail여부(Y) 반영."""
    out = []
    for r in plan_rows:
        fail = _is_yes(r.get("fail여부"))
        out.extend(resolve_lot_variants(
            scan_roots, r.get("디바이스명", ""), r.get("공정번호", ""),
            r.get("S/M", ""), r.get("AOI호기", ""), fail))
    return out


# --------------------------------------------------------------------------
# 안전 복사 (원본 read-only) — downloader 재사용
# --------------------------------------------------------------------------
def copy_lot(lot: LotFolder, dest_root: str, verify: bool = True) -> dict:
    """Lot 웨이퍼 폴더의 대상(Zones/RTP/Optic)만 dest_root/{label}/ 로 안전 복사."""
    if not lot.exists or lot.wafer_dir is None:
        raise RuntimeError(f"복사할 웨이퍼 폴더가 없습니다: {lot.label} ({lot.reason})")
    dst_base = Path(dest_root) / downloader.safe_name(lot.label)
    _zones, files = downloader.collect_target_items(lot.wafer_dir)
    rows = []
    for src in files:
        # 전부 wafer_dir 하위 → 상대구조 보존(Zones/·Recipe*-Zones/ 유지)
        dst = dst_base / src.relative_to(lot.wafer_dir)
        rows.append(downloader.copy_one_file(src, dst, overwrite=False, verify=verify))
    return {"label": lot.label, "dest": str(dst_base), "files": rows, "count": len(rows)}


# --------------------------------------------------------------------------
# Lot 파싱 → 통합 피벗(값=Lot별) + 구조 diff
# --------------------------------------------------------------------------
def detect_recipes(lot_dirs: list[tuple[str, Path]]) -> list[dict] | None:
    """Lot 들의 config 폴더에서 RecipesInfo.ini 를 찾아 다중 레시피 목록을 돌려준다.
    [{index, name, prefix}] (2개 이상일 때만) / 단일·없음이면 None.
    첫 번째로 발견되는 config 폴더 기준(모든 Lot 이 같은 레시피 구성이라고 가정)."""
    for _label, cdir in lot_dirs:
        for cfg_dir in ini_parser.find_config_dirs(Path(cdir)):
            recs = ini_parser.read_recipes_info(cfg_dir)
            if recs:
                return recs
    return None


def form_preflight(lot_dirs: list[tuple[str, Path]]) -> dict:
    """양식 만들기 전에 사용자에게 확인시켜 줄 정보(첫 config 폴더 기준).

    반환: {"config_dir": str, "recipes": [...], "active": {...}, "files": {...}}
    - recipes: RecipesInfo.ini 로 감지한 하위 레시피 목록(2개+일 때만, 아니면 []).
    - active:  ActiveScenarioOptics.ini(레시피별 접두 포함) 파일 존재/유효 Scan2d 여부.
    - files:   `{레시피명: {global, optic, zones, count, thin}}` — **그 레시피 접두로
      실제로 파싱될 파일이 무엇인지**. 다중 레시피인데 `RecipeN-OpticPreset.ini` /
      `RecipeN-Zones/` 가 없으면 GlobalRTP 만 남아(공유본 폴백) **양식에 GlobalRTP
      항목만 들어간다**. 그 상태를 미리 잡아내려고 `thin` 으로 표시한다.
    """
    recipes = detect_recipes(lot_dirs) or []
    cfg = None
    for _label, cdir in lot_dirs:
        dirs = ini_parser.find_config_dirs(Path(cdir))
        if dirs:
            cfg = dirs[0]
            break
    active: dict = {}
    files: dict = {}
    if cfg is not None:
        targets = ([(r["name"], r["prefix"]) for r in recipes] if recipes
                   else [("", "")])
        for name, prefix in targets:
            fname = f"{prefix}{ini_parser.ACTIVE_SCENARIO_FILE}"
            fpath = Path(cfg) / fname
            exists = fpath.is_file() or (Path(cfg) / fname.lower()).is_file()
            has_scan2d = (ini_parser.read_active_scan2d(cfg, prefix) is not None
                          if exists else False)
            active[name] = {"file": bool(exists), "scan2d": bool(has_scan2d)}
            # 이 접두로 **실제 파싱될** 파일 목록 — 파서와 같은 함수를 쓴다.
            got = ini_parser.config_ini_files(Path(cfg), prefix)
            zones = sum(1 for p in got
                        if p.parent.name.lower().endswith("zones"))
            optic = any("opticpreset" in p.name.lower() for p in got)
            files[name] = {
                "global": any("globalrtp" in p.name.lower() for p in got),
                "optic": optic, "zones": zones, "count": len(got),
                # GlobalRTP 만 남은 상태 = 양식에 그 항목만 들어간다(접두 불일치 의심)
                "thin": bool(not optic and not zones)}
    return {"config_dir": str(cfg) if cfg else "", "recipes": recipes,
            "active": active, "files": files}


def _lot_configs(config_dir: Path, lot_label: str, level: str,
                 scales: dict | None, coef_lookup=None,
                 recipe_prefix: str = "") -> list[ini_parser.ParsedConfig]:
    """Lot 1개의 config 폴더 → ParsedConfig 목록(equipment=lot_label 로 태깅).
    recipe_prefix 를 주면 그 레시피(RecipeN-) 파일만 파싱(다중 레시피)."""
    # folder_variant=False: 여기서 config 폴더는 Lot 의 **슬롯 폴더**(CX01 …)다.
    # 폴더명을 변형 라벨로 쓰면 Lot 마다 변형이 달라져 값이 한 줄로 모이지 않는다.
    return ini_parser.scan_tree(config_dir, default_level=level,
                                default_equipment=lot_label, scales=scales,
                                coef_lookup=coef_lookup, recipe_prefix=recipe_prefix,
                                folder_variant=False)


def parse_lots(lot_dirs: list[tuple[str, Path]], level: str = "",
               scales: dict | None = None, coef_lookup=None,
               recipe_prefix: str = "") -> tuple[list[dict], list[str]]:
    """[(lot_label, config_dir)] → (통합 피벗, lot_label 목록).

    build_pivot 이 값을 equipment(=lot_label) 별로 모아주므로, 그대로
    collate.collate_recipe(machines_all=lot_labels) 에 넘길 수 있다.
    변환계수는 조사 호기 1대 기준이므로 coef_lookup 은 **호기 고정** 콜백을 넘긴다."""
    all_cfgs: list[ini_parser.ParsedConfig] = []
    labels: list[str] = []
    for label, cdir in lot_dirs:
        if label not in labels:
            labels.append(label)
        all_cfgs += _lot_configs(Path(cdir), label, level, scales, coef_lookup,
                                 recipe_prefix)
    pivot_rows, _ = ini_parser.build_pivot(all_cfgs)
    return pivot_rows, labels


def structure_diff(lot_dirs: list[tuple[str, Path]], level: str = "",
                   scales: dict | None = None, recipe_prefix: str = "") -> dict:
    """Lot 간 파라미터 **구조**(zone/alg/param 집합) 비교.

    반환: {"baseline_count": N, "lots": {label: {"missing":[...], "extra":[...]}},
           "identical": bool}. 대표(합집합) 대비 빠진/추가 항목을 알린다.
    """
    per_lot: dict[str, set] = {}
    for label, cdir in lot_dirs:
        keys = per_lot.setdefault(label, set())
        for cfg in _lot_configs(Path(cdir), label, level, scales,
                                recipe_prefix=recipe_prefix):
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
# 조사 결과 엑셀에서 **파라미터 목록의 맨 첫 행**으로 넣는 Scan 일자 행.
# (헤더 아래 첫 줄 = 각 S/M 열이 언제 스캔된 자료인지)
SCAN_ROW_LABEL = "Scan일자"
# 자동 감시가 채우는 정보 행 — Scan일자 바로 밑에 순서대로 들어간다(사용자 지정).
#   생성일자 = 그 S/M 폴더가 언제 생겼는지
#   조사슬롯 = 무인 회차가 **어느 슬롯을 읽었는지**(이름순 첫 슬롯 하나만 읽으므로
#              나중에 "그때 뭘 본 거지?" 를 되짚을 수 있어야 한다)
CREATED_ROW_LABEL = "생성일자"
SLOT_ROW_LABEL = "조사슬롯"
INFO_ROW_LABELS = (SCAN_ROW_LABEL, CREATED_ROW_LABEL, SLOT_ROW_LABEL)


def collate_lots(recipe: str, form_path: str, pivot_rows: list[dict],
                 lot_labels: list[str], coef_lookup=None) -> collate.CollateRecipe:
    """확정 양식 + 통합 피벗 → Lot 열 채운 CollateRecipe(collate 재사용).
    값은 양식 변환방식 재적용. coef_lookup(lot라벨, MAG)→계수(commonality 는 호기 고정)."""
    return collate.collate_recipe(recipe, form_path, pivot_rows, lot_labels,
                                  coef_lookup=coef_lookup)


def write_lot_result(dest_xlsx: str, recipe: str, machine: str,
                     res: collate.CollateRecipe, lot_labels: list[str],
                     fail_labels: list[str] | None = None,
                     coef_note: list[str] | None = None,
                     scan_times: dict | None = None,
                     created: dict | None = None,
                     slots: dict | None = None,
                     low_labels: list[str] | None = None) -> str:
    """호기 1대 결과: 시트=레시피, 헤더=META + S/M들. 호기명·fail 은 '_정보' 시트에.

    값은 **양식의 변환방식대로 계수를 적용한 값**(collate.collate_recipe)이다.
    coef_note 를 주면 어떤 계수를 썼는지 '_정보' 시트에 함께 남긴다.
    """
    headers = list(engine.META_FIELDS) + list(lot_labels)   # 내부 키(데이터 접근용)
    # 1행은 표시용 헤더(PI→상위 Recipe, Recipe→하위 Recipe). Lot 열은 그대로.
    disp_headers = [engine.display_header(h) for h in headers]
    fail_labels = list(fail_labels or [])
    scan_times = dict(scan_times or {})
    created = dict(created or {})
    slots = dict(slots or {})
    low_labels = list(low_labels or [])
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = collate._safe_sheet(recipe)
    ws.append(disp_headers)                        # 1행 = 헤더(종전과 동일)
    # 헤더 바로 아래 **파라미터 첫 행 = Scan 일자**. 각 S/M 열 밑에 그 폴더가
    # 언제 스캔됐는지가 들어가 값과 같은 자리에서 바로 대조된다.
    # 정보 행(Scan일자 → 생성일자 → 조사슬롯). 값이 하나도 없는 행은 만들지 않는다
    # (수동 조사에는 생성일자·조사슬롯이 없으므로 파일이 종전과 같게 유지된다).
    info_rows = 0
    for label, src in ((SCAN_ROW_LABEL, scan_times), (CREATED_ROW_LABEL, created),
                       (SLOT_ROW_LABEL, slots)):
        if label != SCAN_ROW_LABEL and not any(
                engine._s(src.get(l)).strip() for l in lot_labels):
            continue
        row = {"Parameter": label}
        row.update({l: engine._s(src.get(l)) for l in lot_labels})
        ws.append([row.get(h, "") for h in headers])
        info_rows += 1
    for rec in res.records:
        ws.append([rec.get(h) for h in headers])
    fill = PatternFill("solid", fgColor=_HDR_FILL)
    white = Font(color="FFFFFF", bold=True)
    yellow = PatternFill("solid", fgColor=FAIL_FILL)
    lowred = PatternFill("solid", fgColor=LOWMATCH_FILL)
    scan_fill = PatternFill("solid", fgColor="E8EEF7")
    for j, h in enumerate(headers, start=1):
        c = ws.cell(row=1, column=j)               # 헤더 행
        # fail(노랑)이 우선, 그다음 양식 매칭 미달(연한 빨강)
        c.fill = (yellow if h in fail_labels
                  else lowred if h in low_labels else fill)
        c.font = (Font(bold=True) if h in fail_labels or h in low_labels else white)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        for r in range(2, 2 + info_rows):          # 정보 행(눈에 띄게)
            c2 = ws.cell(row=r, column=j)
            c2.fill = scan_fill
            c2.font = Font(bold=True, color="1F4E78")
    ws.freeze_panes = f"A{2 + info_rows}"          # 헤더 + 정보 줄 고정
    meta = wb.create_sheet("_정보")
    meta.append(["호기", machine])
    meta.append(["레시피", recipe])
    meta.append(["Lot수", len(lot_labels)])
    for line in (coef_note or []):
        meta.append(["변환계수", line])
    for label in lot_labels:
        meta.append(["Lot", label])
    for label in fail_labels:
        meta.append(["Fail", label])
    for label in low_labels:
        meta.append(["LowMatch", label])           # 양식 매칭이 적었던 S/M
    wb.save(dest_xlsx)
    return dest_xlsx


def read_lot_result(path: str) -> dict:
    """호기 결과 엑셀 → {machine, recipe, lots, records, fails}. fails=fail S/M 집합."""
    wb = openpyxl.load_workbook(path, data_only=True)
    machine = recipe = ""
    fails: set = set()
    lows: set = set()
    if "_정보" in wb.sheetnames:
        for row in wb["_정보"].iter_rows(values_only=True):
            if not row:
                continue
            if row[0] == "호기":
                machine = engine._s(row[1])
            elif row[0] == "레시피":
                recipe = engine._s(row[1])
            elif row[0] == "Fail":
                fails.add(engine._s(row[1]))
            elif row[0] == "LowMatch":
                lows.add(engine._s(row[1]))
    data_ws = next((ws for ws in wb.worksheets if ws.title != "_정보"), None)
    records, lots = [], []
    info: dict = {}
    if data_ws is not None:
        if not recipe:
            recipe = data_ws.title
        # 표시용 헤더(상위/하위 Recipe)를 내부 키(PI/Recipe)로 되돌린다.
        heads = [engine.internal_header(engine._s(c.value).strip()) for c in data_ws[1]]
        meta = set(engine.META_FIELDS)
        lots = [h for h in heads if h and h not in meta]
        for row in data_ws.iter_rows(min_row=2, values_only=True):
            if row is None or all(v in (None, "") for v in row):
                continue
            rec = {heads[i]: row[i] for i in range(len(heads)) if i < len(row)}
            # 위쪽 정보 행(Scan일자/생성일자/조사슬롯)은 파라미터가 아니라 메타 —
            # 따로 빼서 돌려준다(비교표 파라미터 열에 섞이면 안 된다).
            pname = engine._s(rec.get("Parameter")).strip()
            if pname in INFO_ROW_LABELS:
                info[pname] = {l: engine._s(rec.get(l)).strip() for l in lots}
                continue
            records.append(rec)
    wb.close()
    return {"machine": machine, "recipe": recipe, "lots": lots,
            "records": records, "fails": fails, "lows": lows,
            "scan_times": info.get(SCAN_ROW_LABEL, {}),
            "created": info.get(CREATED_ROW_LABEL, {}),
            "slots": info.get(SLOT_ROW_LABEL, {})}


# --------------------------------------------------------------------------
# Step 6: 호기 취합·비교 (행=S/M/호기, 열=파라미터[Zone 그룹 정렬], 과반수 이탈 색칠)
# --------------------------------------------------------------------------
def _param_label(rec: dict) -> str:
    """비교 표의 파라미터 열 이름 — Zone/Alg/Parameter 조합(중복 회피)."""
    parts = [engine._s(rec.get("Zone")), engine._s(rec.get("Alg")),
             engine._s(rec.get("Parameter"))]
    return " / ".join(p for p in parts if p) or engine._s(rec.get("Parameter"))


def _zone_sort_key(param_label: str) -> tuple:
    """비슷한 Zone 을 인접시키는 정렬 키. Zone 의 **마지막 단어**로 그룹핑해
    'AL PAD' 와 'PAD'(둘 다 'pad')가 붙어 나오게 한다."""
    zone = param_label.split(" / ", 1)[0]
    words = re.findall(r"[0-9A-Za-z]+", zone)
    tail = words[-1].lower() if words else zone.lower()
    return (tail, zone.lower(), param_label.lower())


def merge_lot_result(dest_xlsx: str, recipe: str, machine: str,
                     res: collate.CollateRecipe, lot_labels: list[str],
                     fail_labels: list[str] | None = None,
                     coef_note: list[str] | None = None,
                     scan_times: dict | None = None,
                     created: dict | None = None,
                     slots: dict | None = None,
                     low_labels: list[str] | None = None) -> dict:
    """**하나의 결과 파일에 S/M 열을 누적**한다(자동 감시용, 사용자 확정 2026-08).

    회차마다 새 결과 파일을 만들면 파일이 수십 개로 불어나고, `build_comparison`
    이 중복을 걸러 주지 않아 **같은 S/M 이 여러 행으로 중복**된다. 그래서 감시는
    (호기, 레시피)마다 결과 파일 하나를 두고 새 S/M 을 열로 붙인다.

    · 이미 있는 S/M 이면 **값을 갱신**한다(다시 조사한 경우).
    · 파일이 없으면 `write_lot_result` 와 같은 모양으로 새로 만든다.
    · 파라미터 행은 **기존 것과 합집합**(양식이 조금 달라도 열이 어긋나지 않게).
    반환: {"path", "added": 새 S/M 수, "updated": 갱신 수, "lots": 전체 S/M 수}
    """
    scan_times, created, slots = dict(scan_times or {}), dict(created or {}), dict(slots or {})
    old = {"lots": [], "records": [], "fails": set(), "lows": set(),
           "scan_times": {}, "created": {}, "slots": {}}
    if Path(dest_xlsx).is_file():
        try:
            old = read_lot_result(dest_xlsx)
        except Exception:  # noqa: BLE001
            pass                                   # 깨진 파일이면 새로 만든다
    # ── S/M 열 = 기존 + 새것(순서 유지, 중복 제거)
    lots = list(old.get("lots") or [])
    added = updated = 0
    for l in lot_labels:
        if l in lots:
            updated += 1
        else:
            lots.append(l)
            added += 1
    # ── 파라미터 행 = 기존 ∪ 새것. 행 키는 META_FIELDS(값 열 제외).
    meta = list(engine.META_FIELDS)

    def rkey(rec):
        return tuple(engine._s(rec.get(h)).strip() for h in meta if h != "비고")

    merged: dict = {}
    order: list = []
    for rec in (old.get("records") or []):
        k = rkey(rec)
        if k not in merged:
            order.append(k)
        merged[k] = dict(rec)
    for rec in res.records:
        k = rkey(rec)
        if k not in merged:
            order.append(k)
            merged[k] = {h: rec.get(h) for h in meta}
        for l in lot_labels:                       # 이번에 조사한 열만 덮어쓴다
            merged[k][l] = rec.get(l)
    records = [merged[k] for k in order]

    info_old = {SCAN_ROW_LABEL: dict(old.get("scan_times") or {}),
                CREATED_ROW_LABEL: dict(old.get("created") or {}),
                SLOT_ROW_LABEL: dict(old.get("slots") or {})}
    info_old[SCAN_ROW_LABEL].update(scan_times)
    info_old[CREATED_ROW_LABEL].update(created)
    info_old[SLOT_ROW_LABEL].update(slots)
    fails = set(old.get("fails") or set()) | set(fail_labels or [])
    # 매칭 미달 표시 — 이번에 제대로 매칭된 S/M 은 표시를 **해제**한다
    # (양식을 고치고 다시 조사하면 정상으로 돌아와야 하므로).
    lows = set(old.get("lows") or set()) | set(low_labels or [])
    lows -= {l for l in lot_labels if l not in set(low_labels or [])}

    class _Res:                                    # write_lot_result 가 쓰는 모양
        pass
    holder = _Res()
    holder.records = records
    write_lot_result(dest_xlsx, recipe or old.get("recipe") or "", machine,
                     holder, lots, sorted(fails), coef_note=coef_note,
                     scan_times=info_old[SCAN_ROW_LABEL],
                     created=info_old[CREATED_ROW_LABEL],
                     slots=info_old[SLOT_ROW_LABEL],
                     low_labels=sorted(lows))
    return {"path": dest_xlsx, "added": added, "updated": updated,
            "lots": len(lots), "lows": sorted(lows)}


def build_comparison(result_files: list[str]) -> dict:
    """여러 호기 결과 엑셀 → 비교 표.

    반환:
      {"columns": ["S/M","호기", param1, param2, ...],
       "rows": [{"S/M","호기", param: value, ...}, ...],
       "outliers": {(row_idx, param), ...},   # 과반수와 다른 셀
       "fail_rows": {row_idx, ...},           # fail여부=Y 인 S/M 행(노란색)
       "changed_params": [param, ...]}        # 값이 갈리는 파라미터만
    각 (호기, S/M) 조합이 한 행. 파라미터 열은 **비슷한 Zone 끼리 묶어** 정렬
    (AL PAD/PAD 인접). 1열=S/M, 2열=호기.
    """
    params: list[str] = []
    param_seen: set = set()
    rows: list[dict] = []
    fail_rows: set = set()
    low_rows: set = set()
    for path in result_files:
        data = read_lot_result(path)
        machine = data["machine"] or Path(path).stem
        fails = data.get("fails") or set()
        lows = data.get("lows") or set()
        # 파라미터 열 및 S/M별 값 맵
        by_param_value: dict[str, dict[str, object]] = {}
        for rec in data["records"]:
            pl = _param_label(rec)
            if pl not in param_seen:
                param_seen.add(pl)
                params.append(pl)
            by_param_value[pl] = {lot: rec.get(lot) for lot in data["lots"]}
        scan_times = data.get("scan_times") or {}
        for lot in data["lots"]:
            if lot in fails:
                fail_rows.add(len(rows))
            if lot in lows:
                low_rows.add(len(rows))
            row = {"S/M": lot, "호기": machine,
                   SCAN_ROW_LABEL: scan_times.get(lot, "")}
            for pl in by_param_value:
                row[pl] = by_param_value[pl].get(lot)
            rows.append(row)

    # 비슷한 Zone 끼리 인접하도록 파라미터 열 정렬(엑셀/뷰어 공통)
    params.sort(key=_zone_sort_key)

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
    return {"columns": ["S/M", "호기", SCAN_ROW_LABEL] + params, "rows": rows,
            "low_rows": low_rows,
            "outliers": outliers, "fail_rows": fail_rows, "changed_params": changed}


def write_comparison(dest_xlsx: str, comparison: dict,
                     changed_only: bool = False) -> str:
    """비교 표 → 엑셀(과반수 이탈 셀 색칠). changed_only=True 면 변경 파라미터만."""
    # 앞 3개(S/M · 호기 · Scan일자)는 식별 열, 그 뒤가 파라미터 열
    head_n = 3
    params = (comparison["changed_params"] if changed_only
              else comparison["columns"][head_n:])
    columns = list(comparison["columns"][:head_n]) + list(params)
    rows = comparison["rows"]
    outliers = comparison["outliers"]
    fail_rows = comparison.get("fail_rows") or set()

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
    fail_fill = PatternFill("solid", fgColor=FAIL_FILL)
    low_fill = PatternFill("solid", fgColor=LOWMATCH_FILL)
    low_rows = comparison.get("low_rows") or set()
    for i, r in enumerate(rows):
        ws.append([r.get(col) for col in columns])
        excel_row = i + 2
        # fail=Y S/M 은 식별칸(S/M·호기)을 노란색으로.
        # 양식 매칭이 적었던 S/M 은 연한 빨강 — 값이 비어 보여도 '조사는 했는데
        # 양식이 안 맞았다'는 뜻이라 다른 이유와 구분돼야 한다.
        if i in fail_rows:
            for c in range(1, head_n + 1):
                ws.cell(row=excel_row, column=c).fill = fail_fill
        elif i in low_rows:
            for c in range(1, head_n + 1):
                ws.cell(row=excel_row, column=c).fill = low_fill
        for j, col in enumerate(columns[head_n:], start=head_n + 1):
            if (i, col) in outliers:
                ws.cell(row=excel_row, column=j).fill = mismatch
    ws.freeze_panes = "D2"
    ws.column_dimensions["A"].width = 16
    ws.column_dimensions["B"].width = 10
    ws.column_dimensions["C"].width = 17
    wb.save(dest_xlsx)
    return dest_xlsx
