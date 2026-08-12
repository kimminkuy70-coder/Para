"""Commonality 자동 감시 — **새로 생긴 S/M 폴더**를 찾아 조사 계획에 넣는다.

무엇을 보는가
-------------
    {호기폴더}/Scanresult*/{2D@디바이스}/{공정번호}/{S/M}/{슬롯}/
                                              ↑ 여기(4단계)가 감시 지점

새 S/M 폴더 = 새 검사 건. 슬롯 아래로는 내려가지 않는다.

왜 이렇게 짰는가
----------------
· **감시 범위 = '감시 대상 Lot 계획'의 (디바이스, 공정번호)** (사용자 확정 2026-08).
  트리 전체를 훑으면 호기당 폴더 수천 개를 매 회차 stat 해야 해서 느리고, 파일서버
  접근 패턴도 좋지 않다. 계획에 적힌 조합만 보면 회차당 접근이 **계획 행 수**로 끝난다.
· **공정 폴더 mtime 이 지난 회차와 같으면 통째로 건너뛴다.** 디렉터리 mtime 은 자식이
  추가/삭제될 때 바뀌므로, 안 바뀌었으면 새 S/M 이 없다는 뜻이다.
· **기억 키는 경로가 아니라 (디바이스, 공정, S/M) 정규화 키**다. `scanresult_roots` 가
  백업본(`Scanresult_260402` 등)까지 훑기 때문에, 경로로 기억하면 백업 폴더가 하나
  생길 때마다 그 안의 S/M 수백 개가 전부 '신규'로 잡혀 알림이 폭주한다.
· **첫 회차는 기준선만 기록하고 알리지 않는다**(기존 폴더 전부를 신규라고 하면 안 됨).
· **아직 쓰는 중인 폴더는 미룬다**: 스캔이 끝나기 전에 폴더가 먼저 생기므로, 폴더
  수정시각이 `settle_minutes` 이상 지났고 슬롯에 설정 파일이 있어야 '신규 확정'.
· 삭제는 보지 않는다(추가만).

파일 이름 구분(사용자 지정)
---------------------------
  · `감시대상_Lot계획.xlsx`      — **무엇을 감시할지**(디바이스/공정/호기)
  · `Commonality_Lot계획.xlsx`   — **무엇을 조사할지**(commonality.PLAN_FILENAME)
새로 찾은 S/M 은 조사 계획 쪽에 **생성일자와 함께** 덧붙인다.

설정·상태는 **로컬**(`CamtekAOI/Cache/commonality_감시.json`) — Scanresult 루트 경로
자체가 로컬 설정이고 commonality 산출물도 로컬이라 그쪽에 맞춘다.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill

from . import commonality as cm
from . import engine, localdirs

SETTINGS_FILENAME = "commonality_감시.json"
LOG_FILENAME = "commonality_감시로그.txt"

# 감시 대상 계획 — '무엇을 조사할지'(commonality.PLAN_FILENAME)와 이름을 구분한다.
WATCH_PLAN_FILENAME = "감시대상_Lot계획.xlsx"
WATCH_PLAN_SHEET = "감시대상"
WATCH_PLAN_HEADERS = ["디바이스명", "공정번호", "AOI호기", "비고"]

# 폴더가 만들어진 뒤 이 시간이 지나야 '신규 확정'. 스캔이 끝나기 전에 폴더가 먼저
# 생기므로, 바로 잡으면 반쪽 데이터를 조사 계획에 넣게 된다.
DEFAULT_SETTLE_MINUTES = 10.0
_HDR_FILL = "1F4E78"


# --------------------------------------------------------------------------
# 감시 대상 계획 엑셀
# --------------------------------------------------------------------------
def create_watch_plan_template(path: str, rows: list[dict] | None = None) -> str:
    """감시 대상 계획 템플릿 — 어떤 (디바이스, 공정번호) 아래를 감시할지.

    S/M 칸이 없다. 그 아래 **모든 S/M** 이 감시 대상이고, 새로 생긴 것을 찾는 게
    이 파일의 목적이기 때문이다.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = WATCH_PLAN_SHEET
    ws.append(WATCH_PLAN_HEADERS)
    for r in rows or []:
        ws.append([engine._s(r.get(h)) for h in WATCH_PLAN_HEADERS])
    fill = PatternFill("solid", fgColor=_HDR_FILL)
    white = Font(color="FFFFFF", bold=True)
    for c in ws[1]:
        c.fill = fill
        c.font = white
        c.alignment = Alignment(horizontal="center", vertical="center")
    for col, w in zip("ABCD", (28, 18, 12, 30)):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A2"
    info = wb.create_sheet("사용법")
    for line in [
        ["감시 대상 Lot 계획 — 작성 방법"],
        [""],
        ["이 파일은 '무엇을 감시할지'만 적습니다."],
        [f"조사할 대상을 적는 파일({cm.PLAN_FILENAME})과 다른 파일이니 헷갈리지 마세요."],
        [""],
        ["1) 디바이스명: Scanresult 아래 '2D@..' 폴더명에 포함된 디바이스명"],
        ["   예) 2D@R3-S6WH11001-00001_... → 디바이스명 'S6WH11001-00001'"],
        ["2) 공정번호: 디바이스 폴더 아래 공정 폴더명(예: 6412)"],
        ["3) AOI호기: 감시할 호기(예: AOI-6). 여러 호기면 'AOI-4,6,9' 처럼 적어도 됩니다."],
        ["4) 비고: 자유 메모(감시에는 쓰이지 않습니다)."],
        [""],
        ["※ S/M 칸이 없는 이유: 그 공정 아래 **모든 S/M** 을 감시하고,"],
        [f"   새로 생긴 S/M 을 찾아 '{cm.PLAN_FILENAME}' 에 생성일자와 함께 넣어 줍니다."],
    ]:
        info.append(line)
    info.column_dimensions["A"].width = 78
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    wb.save(path)
    return path


def read_watch_plan(path: str) -> list[dict]:
    """감시 대상 계획 엑셀 → dict 목록(헤더명 기준, 위치 변동 허용)."""
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = (wb[WATCH_PLAN_SHEET] if WATCH_PLAN_SHEET in wb.sheetnames
          else wb[wb.sheetnames[0]])
    heads = [engine._s(c.value).strip() for c in ws[1]]
    heads = [cm._HEADER_ALIASES.get(h, h) for h in heads]     # 구 'LOT번호' 흡수
    hidx = {h: i for i, h in enumerate(heads) if h}
    out = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row is None or all(v in (None, "") for v in row):
            continue
        rec = {h: engine._s(row[i]).strip() if i < len(row) else ""
               for h, i in hidx.items()}
        if rec.get("디바이스명") or rec.get("공정번호"):
            out.append(rec)
    wb.close()
    return out


def targets_for_machine(plan_rows: list[dict], machine: str) -> list[tuple]:
    """감시 대상 계획 + 호기 → [(디바이스, 공정번호)] (중복 제거, 순서 유지)."""
    out, seen = [], set()
    for r in cm.filter_plan_for_machine(plan_rows, machine):
        dev = engine._s(r.get("디바이스명")).strip()
        lot = engine._s(r.get("공정번호")).strip()
        if not (dev or lot):
            continue
        k = (cm._norm(dev), cm._norm(lot))
        if k in seen:
            continue
        seen.add(k)
        out.append((dev, lot))
    return out


# --------------------------------------------------------------------------
# 설정 / 상태 (로컬 JSON)
# --------------------------------------------------------------------------
@dataclass
class CmWatchSettings:
    enabled: bool = False
    interval_hours: float = 6.0
    window_start: int = 0                 # watcher.in_window 와 같은 규칙
    window_end: int = 0
    machines: list = field(default_factory=list)      # 감시할 호기
    settle_minutes: float = DEFAULT_SETTLE_MINUTES
    watch_plan: str = ""                  # 감시 대상 계획 엑셀 경로
    cm_plan: str = ""                     # 조사 계획 엑셀 경로(새 S/M 을 여기에 추가)
    roots: dict = field(default_factory=dict)         # {호기: Scanresult 루트}
    # 감시 대상마다 쓸 양식 — {survey_key: {"form","recipe","sm"}}.
    #   form   = 확정 양식 경로(감시 켤 때 대표 S/M 으로 만든 것)
    #   recipe = 조사 제목(결과 파일 이름·시트명)
    #   sm     = 그 양식을 만든 대표 S/M(어느 것으로 만들었는지 기록)
    # 없으면 그 대상은 조사하지 않고 계획 추가·알림까지만 한다.
    forms: dict = field(default_factory=dict)
    min_match: float = 0.5                # 양식 매칭이 이 비율 미만이면 결과 제외


@dataclass
class CmWatchState:
    last_run: str = ""
    last_result: str = ""
    fail_count: int = 0
    baseline: bool = False                # 기준선을 세웠는가(첫 회차 무알림)
    seen: dict = field(default_factory=dict)      # {호기: [키…]}
    mtimes: dict = field(default_factory=dict)    # {호기: {공정폴더: mtime}} — 건너뛰기용
    pending: dict = field(default_factory=dict)   # {호기: [키…]} 안정화 대기 중


def settings_path(local_root: str) -> str:
    return os.path.join(localdirs.cache_dir(local_root), SETTINGS_FILENAME)


def log_path(local_root: str) -> str:
    return os.path.join(localdirs.logs_dir(local_root), LOG_FILENAME)


def load_settings(local_root: str) -> tuple[CmWatchSettings, CmWatchState]:
    """설정·상태 읽기. 파일이 없거나 깨졌으면 기본값(예외 없음)."""
    p = settings_path(local_root)
    data: dict = {}
    try:
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh) or {}
    except (OSError, ValueError):
        data = {}
    s, st = CmWatchSettings(), CmWatchState()
    for k, v in (data.get("settings") or {}).items():
        if hasattr(s, k):
            setattr(s, k, v)
    for k, v in (data.get("state") or {}).items():
        if hasattr(st, k):
            setattr(st, k, v)
    s.machines = list(s.machines or [])
    s.roots = dict(s.roots or {})
    s.forms = dict(s.forms or {})
    st.seen = {m: list(v or []) for m, v in (st.seen or {}).items()}
    st.mtimes = {m: dict(v or {}) for m, v in (st.mtimes or {}).items()}
    st.pending = {m: list(v or []) for m, v in (st.pending or {}).items()}
    return s, st


def save_settings(local_root: str, s: CmWatchSettings, st: CmWatchState) -> str:
    p = settings_path(local_root)
    payload = {"settings": {k: getattr(s, k) for k in s.__dataclass_fields__},
               "state": {k: getattr(st, k) for k in st.__dataclass_fields__}}
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, p)
    return p


def append_log(local_root: str, text: str) -> bool:
    """감시 로그 한 줄. 실패해도 예외를 내지 않는다(로그 때문에 회차가 죽으면 안 됨)."""
    try:
        with open(log_path(local_root), "a", encoding="utf-8") as fh:
            fh.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {text}\n")
        return True
    except OSError:
        return False


# --------------------------------------------------------------------------
# 폴더 스캔
# --------------------------------------------------------------------------
def sm_key(device: str, lot: str, sm: str) -> str:
    """기억 키 — **경로가 아니라 (디바이스, 공정, S/M) 정규화 값**.

    백업본(Scanresult_260402 …)에도 같은 S/M 이 있으므로 경로로 기억하면 백업 폴더가
    생길 때마다 전부 '신규'로 잡힌다. 내용 기준 키라야 중복이 걸러진다.
    """
    return "|".join((cm._norm(device), cm._norm(lot), cm._norm(sm)))


def folder_created(path) -> str:
    """폴더 **생성일시** 'YYYY-MM-DD HH:MM'. 못 읽으면 빈 문자열.

    Windows 는 `st_ctime` 이 생성 시각이다. macOS 등은 `st_birthtime`.
    생성 시각 개념이 없는 OS(리눅스)에서는 `st_mtime` 으로 물러난다.
    """
    try:
        stt = Path(path).stat()
    except OSError:
        return ""
    ts = getattr(stt, "st_birthtime", None)
    if ts is None:
        ts = stt.st_ctime if os.name == "nt" else stt.st_mtime
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except (OSError, OverflowError, ValueError):
        return ""


def _dir_mtime(path) -> float:
    try:
        return Path(path).stat().st_mtime
    except OSError:
        return 0.0


def lot_dirs_for(scan_roots, device: str, lot: str) -> list[Path]:
    """(디바이스, 공정번호) → 실제 공정 폴더들. commonality 의 경로 해석 재사용.

    디바이스는 포함 매칭(레시피 접미사가 붙음), 공정번호는 숫자라 **정확일치만**
    (6412 가 64120/16412 에 오매칭되지 않게) + 중간 폴더가 한 단계 더 있는 구조를
    위한 BFS 폴백.
    """
    out: list[Path] = []
    for root in cm._as_roots(scan_roots):
        for dev_dir in cm._find_children(root, device):
            hits = (cm._find_children(dev_dir, lot, contains=False)
                    or cm._bfs_exact(dev_dir, lot, max_depth=3))
            out += [h for h in hits if h.is_dir()]
    return out


def scan_new(scan_roots, targets: list[tuple], seen: set, mtimes: dict,
             *, now: float | None = None,
             settle_minutes: float = DEFAULT_SETTLE_MINUTES) -> dict:
    """새로 생긴 S/M 폴더를 찾는다.

    targets  = [(디바이스, 공정번호)] — 감시 대상 계획에서 온 조합
    seen     = 이미 아는 `sm_key` 집합
    mtimes   = {공정폴더 경로: 지난 회차 mtime} — 안 바뀐 폴더는 통째로 건너뛴다
    반환: {"new": [item…], "pending": [key…], "mtimes": {…}, "scanned": n, "skipped": n}
      item = {key, device, lot, sm, path, created, machine_hint}
    """
    now = time.time() if now is None else now
    settle = max(0.0, float(settle_minutes)) * 60.0
    new_items, pending, out_mtimes = [], [], {}
    scanned = skipped = 0
    for device, lot in targets:
        for lot_dir in lot_dirs_for(scan_roots, device, lot):
            key_path = str(lot_dir)
            mt = _dir_mtime(lot_dir)
            out_mtimes[key_path] = mt
            # 자식이 추가/삭제되지 않았으면 새 S/M 도 없다 → iterdir 생략
            if key_path in mtimes and mtimes[key_path] == mt:
                skipped += 1
                continue
            scanned += 1
            try:
                subs = sorted((p for p in lot_dir.iterdir() if p.is_dir()),
                              key=lambda x: x.name.lower())
            except OSError:
                continue
            for sm_dir in subs:
                k = sm_key(device, lot, sm_dir.name)
                if k in seen:
                    continue
                # 아직 쓰는 중일 수 있다 — 조용해질 때까지 미룬다
                if settle and (now - _dir_mtime(sm_dir)) < settle:
                    pending.append(k)
                    continue
                if not _has_config(sm_dir):
                    pending.append(k)
                    continue
                seen.add(k)                    # 같은 회차에서 백업본 중복 방지
                new_items.append({
                    "key": k, "device": device, "lot": lot, "sm": sm_dir.name,
                    "path": str(sm_dir), "created": folder_created(sm_dir)})
    return {"new": new_items, "pending": pending, "mtimes": out_mtimes,
            "scanned": scanned, "skipped": skipped}


def apply_scan(state: CmWatchState, machine: str, result: dict) -> list:
    """스캔 결과를 상태에 반영하고 **알릴 항목**을 돌려준다.

    **첫 회차(기준선)는 알리지 않는다** — 이미 있던 폴더 전부를 '신규'라고 하면
    안 되므로, 기억만 하고 빈 목록을 돌려준다. 이 판단을 GUI 에 맡기면 틀리기
    쉬워서 여기서 처리한다.
    """
    keys = [i["key"] for i in result.get("new") or []]
    seen = list(state.seen.get(machine) or [])
    seen += [k for k in keys if k not in seen]
    state.seen[machine] = seen
    state.mtimes[machine] = dict(result.get("mtimes") or {})
    state.pending[machine] = list(result.get("pending") or [])
    if not state.baseline:
        state.baseline = True
        return []
    return list(result.get("new") or [])


def seen_set(state: CmWatchState, machine: str) -> set:
    return set(state.seen.get(machine) or [])


def slot_has_config(wafer_dir: Path) -> bool:
    """이 슬롯에 **실제로 읽을 설정이 있는가**.

    폴더만 있고 안이 빈 슬롯이 흔하다(스캔이 아직 안 끝났거나 실패한 것).
    `Zones/` 가 있어도 안에 .ini 가 없으면 읽을 게 없으므로 내용을 본다.
    """
    w = Path(wafer_dir)
    if any((w / n).is_file() for n in ("OpticPreset.ini", "GlobalRTP.ini")):
        return True
    z = w / "Zones"
    return z.is_dir() and any(p.is_file() for p in z.glob("*.ini"))


def usable_slots(sm_dir: Path) -> list:
    """읽을 설정이 있는 슬롯만(이름순). 무인 조사는 이 중 **첫 번째**를 쓴다."""
    return [w for w in cm.list_wafers(sm_dir) if slot_has_config(w)]


def _has_config(sm_dir: Path) -> bool:
    """S/M 아래에 조사할 설정 파일이 하나라도 있는가(아직 쓰는 중이면 없다)."""
    return bool(usable_slots(sm_dir))


# --------------------------------------------------------------------------
# 조사 계획에 추가
# --------------------------------------------------------------------------
def plan_backup_path(plan_path: str) -> str:
    return f"{os.path.splitext(plan_path)[0]}_백업_" \
           f"{datetime.now():%Y%m%d_%H%M%S}.xlsx"


def append_cm_plan(plan_path: str, items: list[dict], machine: str = "") -> dict:
    """찾은 S/M 을 **조사 계획 엑셀**에 덧붙인다(생성일자 포함).

    · 사람이 관리하는 파일이므로 **쓰기 전에 백업 1부**를 같은 폴더에 남긴다.
    · 이미 같은 (디바이스, 공정, S/M) 행이 있으면 넣지 않는다.
    · 파일이 없으면 템플릿을 만들어 시작한다.
    반환: {"added": n, "backup": 경로 or "", "skipped": n}
    """
    if not items:
        return {"added": 0, "backup": "", "skipped": 0}
    if not os.path.isfile(plan_path):
        cm.create_plan_template(plan_path)
        backup = ""
    else:
        backup = plan_backup_path(plan_path)
        shutil.copy2(plan_path, backup)

    wb = openpyxl.load_workbook(plan_path)
    ws = wb["Lot목록"] if "Lot목록" in wb.sheetnames else wb[wb.sheetnames[0]]
    heads = [engine._s(c.value).strip() for c in ws[1]]
    heads = [cm._HEADER_ALIASES.get(h, h) for h in heads]
    # 구 파일에 '생성일자' 열이 없으면 뒤에 만들어 준다
    if "생성일자" not in heads:
        ws.cell(1, len(heads) + 1).value = "생성일자"
        if ws[1][0].fill is not None:
            c = ws.cell(1, len(heads) + 1)
            c.fill = PatternFill("solid", fgColor=_HDR_FILL)
            c.font = Font(color="FFFFFF", bold=True)
            c.alignment = Alignment(horizontal="center", vertical="center")
        heads.append("생성일자")
    hidx = {h: i for i, h in enumerate(heads) if h}

    have = set()
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row is None or all(v in (None, "") for v in row):
            continue

        def g(name):
            i = hidx.get(name)
            return engine._s(row[i]) if i is not None and i < len(row) else ""
        have.add(sm_key(g("디바이스명"), g("공정번호"), g("S/M")))

    added = skipped = 0
    for it in items:
        if it["key"] in have:
            skipped += 1
            continue
        have.add(it["key"])
        vals = {"디바이스명": it["device"], "공정번호": it["lot"], "S/M": it["sm"],
                "AOI호기": machine or it.get("machine", ""), "fail여부": "",
                "생성일자": it.get("created", "")}
        line = [""] * len(heads)
        for h, i in hidx.items():
            line[i] = vals.get(h, "")
        ws.append(line)
        added += 1
    wb.save(plan_path)
    wb.close()
    return {"added": added, "backup": backup, "skipped": skipped}


# --------------------------------------------------------------------------
# 감시용 양식 · 자동 조사
# --------------------------------------------------------------------------
def survey_key(machine: str, device: str, lot: str) -> str:
    """양식/결과를 묶는 키 — (호기, 디바이스, 공정번호) 정규화.

    **감시 대상마다 양식을 따로 지정한다**(사용자 확정 2026-08). 디바이스가 다르면
    파라미터 구성이 달라, 양식 하나를 전부에 물리면 엉뚱한 항목으로 조사하게 된다.
    """
    return "|".join((cm._aoi_norm(machine), cm._norm(device), cm._norm(lot)))


def form_for(settings: CmWatchSettings, machine: str, device: str, lot: str) -> dict:
    """이 감시 대상에 지정된 양식 정보. 없으면 빈 dict(=조사하지 않음)."""
    return dict((settings.forms or {}).get(survey_key(machine, device, lot)) or {})


def set_form(settings: CmWatchSettings, machine: str, device: str, lot: str,
             form_path: str, recipe: str, sm: str = "") -> None:
    """감시 대상에 양식을 묶는다(감시 켤 때 대표 S/M 으로 만든 확정 양식)."""
    settings.forms = dict(settings.forms or {})
    settings.forms[survey_key(machine, device, lot)] = {
        "form": str(form_path or ""), "recipe": str(recipe or ""), "sm": str(sm or "")}


def missing_forms(settings: CmWatchSettings, machine: str,
                  targets: list[tuple]) -> list[tuple]:
    """양식이 아직 없는 (디바이스, 공정) — 설정창에서 빨갛게 표시할 것."""
    out = []
    for device, lot in targets:
        info = form_for(settings, machine, device, lot)
        if not (info.get("form") and os.path.isfile(info["form"])):
            out.append((device, lot))
    return out


def sm_candidates(scan_roots, device: str, lot: str) -> list[dict]:
    """(디바이스, 공정) 아래 S/M 후보 — **생성일자 최신순**(사용자 확정).

    감시를 켤 때 '대표 S/M'(양식을 만들 기준)을 사람이 고르는데, 최근에 스캔된
    것부터 보여 줘야 고르기 쉽다. 반환: [{sm, path, created, scan, slots}]
    """
    out: list[dict] = []
    seen: set = set()
    for lot_dir in lot_dirs_for(scan_roots, device, lot):
        try:
            subs = [p for p in lot_dir.iterdir() if p.is_dir()]
        except OSError:
            continue
        for sm_dir in subs:
            k = sm_key(device, lot, sm_dir.name)
            if k in seen:
                continue                       # 백업본의 같은 S/M 은 한 번만
            seen.add(k)
            out.append({"sm": sm_dir.name, "path": str(sm_dir),
                        "created": folder_created(sm_dir),
                        "scan": cm.folder_mtime(sm_dir),
                        "slots": len(cm.list_wafers(sm_dir))})
    # 생성일자 문자열은 'YYYY-MM-DD HH:MM' 이라 사전식 정렬 = 시간순
    out.sort(key=lambda d: (d["created"] or d["scan"] or "", d["sm"]), reverse=True)
    return out


def result_path(local_root: str, machine: str, recipe: str) -> str:
    """(호기, 레시피)마다 **결과 파일 하나** — 회차마다 S/M 열이 누적된다."""
    from . import workdirs
    d = os.path.join(workdirs.commonality_root(local_root), cm.downloader.safe_name(machine),
                     "자동감시")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"감시조사_{cm.downloader.safe_name(machine)}_"
                           f"{cm.downloader.safe_name(recipe)}.xlsx")


def copy_root(local_root: str, machine: str) -> str:
    """무인 회차가 안전복사본을 두는 곳(로컬). 원본은 언제나 읽기 전용."""
    from . import workdirs
    d = os.path.join(workdirs.commonality_root(local_root),
                     cm.downloader.safe_name(machine), "자동감시", "복사본")
    os.makedirs(d, exist_ok=True)
    return d


def lot_for_item(item: dict, machine: str):
    """감지 항목 → 조사용 LotFolder. 슬롯은 **이름순 첫 하나**(무인이라 못 고름).
    반환: (LotFolder, 슬롯이름) / 슬롯이 없으면 (None, '')."""
    sm_dir = Path(item["path"])
    # **읽을 게 있는** 슬롯 중 이름순 첫 번째. 빈 슬롯이 이름순으로 앞에 있으면
    # 그걸 읽고 0건이 되므로(실제로 겪음), 내용이 있는 것만 후보로 본다.
    wafers = usable_slots(sm_dir)
    if not wafers:
        return None, ""
    lot = cm.LotFolder(device=item["device"], lot=item["lot"], sm=item["sm"],
                       machine=machine, label=item["sm"],
                       scan_time=cm.folder_mtime(sm_dir))
    cm.set_wafer(lot, wafers[0])
    return lot, wafers[0].name


def survey_items(items: list[dict], *, machine: str, form_path: str, recipe: str,
                 dest_xlsx: str, copy_dir: str, coef_lookup=None,
                 min_match: float = 0.5) -> dict:
    """새 S/M 들을 **안전복사 → 저장된 양식으로 값 조사 → 결과 파일에 누적**.

    · 슬롯은 이름순 첫 하나만 읽고, **어느 슬롯을 읽었는지 결과에 남긴다**
      (`조사슬롯` 행 — 나중에 되짚을 수 있어야 한다).
    · 양식과 매칭된 파라미터 비율이 `min_match` 미만이면 **열은 남기되 연한 빨강
      으로 표시**한다(`low_labels`). 빼 버리면 그런 S/M 이 있었다는 사실이 사라져
      "왜 이건 조사가 안 됐지?" 를 알 수 없다.
    반환: {"done": [라벨], "low": [매칭 적은 라벨], "skipped": [(라벨, 못 읽은 사유)],
           "flagged": [(라벨, 매칭 사유)], "merged": {…} or None}
    """
    skipped, flagged = [], []      # skipped=아예 못 읽음 / flagged=조사했지만 매칭 적음
    lot_dirs, labels = [], []
    scan_times, created, slots = {}, {}, {}
    for it in items:
        lot, slot_name = lot_for_item(it, machine)
        if lot is None or not lot.exists:
            skipped.append((it["sm"], "슬롯(웨이퍼) 폴더 없음"))
            continue
        if not (lot.has_zones or lot.has_optic):
            skipped.append((it["sm"], "설정 파일 없음"))
            continue
        try:
            got = cm.copy_lot(lot, copy_dir)
        except Exception as e:  # noqa: BLE001
            skipped.append((it["sm"], f"복사 실패: {e}"))
            continue
        lot_dirs.append((lot.label, Path(got["dest"])))
        labels.append(lot.label)
        scan_times[lot.label] = lot.scan_time
        created[lot.label] = it.get("created", "")
        slots[lot.label] = slot_name
    if not lot_dirs:
        return {"done": [], "low": [], "skipped": skipped, "flagged": [],
                "merged": None}

    pivot, plabels = cm.parse_lots(lot_dirs, level=recipe, coef_lookup=coef_lookup)
    res = cm.collate_lots(recipe, form_path, pivot, plabels, coef_lookup=coef_lookup)
    # 양식과 얼마나 맞았는지 — 적게 맞은 S/M 도 **열은 남기고 색으로 표시**한다
    # (사용자 확정 2026-08). 빼 버리면 그런 S/M 이 있었다는 사실 자체가 사라져
    # 나중에 "왜 이건 조사가 안 됐지?" 를 알 수 없다.
    total = len(res.records) or 1
    low = []
    for label in plabels:
        filled = sum(1 for r in res.records if engine._s(r.get(label)).strip() != "")
        if filled / total < max(0.0, min(1.0, min_match)):
            low.append(label)
            flagged.append((label, f"양식과 매칭 {filled}/{total} — 표시만"))

    merged = cm.merge_lot_result(
        dest_xlsx, recipe, machine, res, plabels,
        scan_times={k: scan_times.get(k, "") for k in plabels},
        created={k: created.get(k, "") for k in plabels},
        slots={k: slots.get(k, "") for k in plabels},
        low_labels=low)
    return {"done": list(plabels), "low": low, "skipped": skipped,
            "flagged": flagged, "merged": merged}


def summary(items: list[dict]) -> str:
    """알림용 한 줄 요약."""
    if not items:
        return "새 S/M 없음"
    head = ", ".join(f"{i['device']}/{i['lot']}/{i['sm']}" for i in items[:3])
    more = f" 외 {len(items) - 3}건" if len(items) > 3 else ""
    return f"새 S/M {len(items)}건 — {head}{more}"
