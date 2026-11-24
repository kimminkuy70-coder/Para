"""TB500 Review 조회 (v14.4.2, 소유자 2026-11-23) — 맨 위 탭 `TB500 Review 조회`(KLA 와 설정 사이, Mini 포함).

리뷰 전용 HTML(`TB500_Review.html`, 브랜치 `version_TB500_review` — 앱이 없는 PC 용으로 그대로 유지)의 조회를 앱 안으로
옮긴 것이다. 판정 규칙은 HTML 과 같다(Para #40 ~ #85):

- Lot 폴더 = Conder Scan 폴더 바로 아래에서 Lot 이름 정확 일치 → 단어 경계 일치 → 포함. 괄호 안 = S/M.
- Lot 폴더 바로 아래 하위 폴더 = 실제 이름 그대로 한 줄씩(이름 순). 이름으로 Layer(STAGES) · 종류(재리뷰 · Skip · 재스캔 · 기본).
  `★` 로 시작하는 폴더 = 리뷰 대상 아님(이름만). Layer 상태 = 재리뷰 폴더가 있으면 '재리뷰 완료', Skip 폴더가 있으면 'Skip',
  아니면 '재리뷰 필요'. 장비 · 호기는 재리뷰 필요 · 재리뷰 완료 Layer 의 기본 · 재스캔 폴더에만(#85).
- 장비 판정 = 폴더 아래 이미지 파일 이름(`TB500_…` · ` - Multi_` = Camtek, `영문숫자_숫자×4 이상` = KLA). 파일은 열지 않는다.
- Camtek 호기 · 스캔 시각 = 로컬 Batch Report 캐시(배치분석/누적)에서 S/M 의 Lot 코드가 같고 Job 이름에 그 Layer 가 있는 Batch Report.
  wafer 판정은 `lotmodel.attempt` 그대로(HTML 의 waferCells 는 그 JS 복사본이었다).
- KLA 장비 · 시각 = 로컬 KLA 캐시(KLA캐시/KLA색인.json)에서 `{Lot}@{공정번호}` 폴더(공정번호 → Layer).

HTML 과 다른 점 — 브라우저 권한 · 폴더 접근 문제(#76 · #77 · 2026-11-23 '허용 창이 안 뜸')가 생기지 않는 구조:
- 파일은 브라우저가 아니라 이 엔진(Python)이 Windows 파일 기능으로 읽는다. 허용 창 · 사용자 동작 · 브라우저 설정 · 정책과 무관하고,
  OneDrive 온라인 전용 파일도 다른 프로그램처럼 Windows 가 내려받는다. 폴더는 전체 경로 문자열로 이 PC 설정에 둔다.
- 캐시는 앱의 로컬 캐시를 쓴다. 갱신 = 기존 [OneDrive 에서 불러오기](Camtek `batch_cache_share_import` · KLA
  `kla_cache_share_import`, 로컬 Temp 복사 · 크기 · SHA-256 확인)를 한 번에(`cache_update`).

읽기 전용: Conder Scan 폴더는 이름 목록(scandir)만 읽고 아무것도 쓰지 않는다. OneDrive 에도 쓰지 않는다.
쓰기 = 이 PC 설정 파일의 `tb500_conder`(Conder Scan 폴더) · `tb500_imported`(마지막으로 불러온 캐시 zip 이름 · 시각)뿐.
"""
from __future__ import annotations

import os
import re
import threading
import time
from datetime import datetime
from pathlib import Path

from . import atomicfile, batchreport_store, desktop_progress, lotmodel, wph
from .desktop_batch import DesktopBatch, read_json

DEFAULT_CONDER = r"\\k5cifsn2\k5tsvdata$\1. Conder Scan\531. NVIDIA INT\129. 4DT-TB500-H-M1"
MAX_LOTS = 500
MAX_LOT_LEN = 200
MAX_PATH = 4096
WALK_ENTRIES, WALK_SEC = 3000, 2.5      # 장비 판정: 폴더 아래를 이만큼만 본다(HTML 과 같음)
TXT_ENTRIES, TXT_SEC = 5000, 2.5        # 재리뷰 맵(.txt) 세기
SHOW_HITS = 3                           # 결과 표 한 칸에 보이는 스캔 수(나머지는 Lot History)


def _stage(key, keys, aoi, aoi_name, rev, rev_name):
    return dict(key=key, keys=[re.compile(k, re.I) for k in keys], aoi=aoi, aoi_name=aoi_name, rev=rev, rev_name=rev_name)


# Layer = 원본 HTML 의 순서 · 공정번호(AOI / Review). keys = Conder 폴더 이름과 Job 이름에서 찾는 표기.
# FS UBM: Camtek Job 이름에 UBM 이 없을 수 있어(예: R_TB500 LIVE_FS_6324_LSD-FS) 앞뒤가 영문자가 아닌 'FS' 낱말로도 찾는다(Para #45).
STAGES = [
    _stage("RDL4", [r"RDL[ _.-]*4(?!\d)"], "6305", "AOI", "6412", "2D/RE"),
    _stage("PIDS3", [r"PIDS[ _.-]*3(?!\d)", r"(?:^|[^A-Z])PI[ _.-]*4(?!\d)"], "6311", "AOI2", "6321", "2D/R2"),
    _stage("RDL3", [r"RDL[ _.-]*3(?!\d)"], "6312", "AOI3", "6322", "2D/R3"),
    _stage("PIDS5", [r"PIDS[ _.-]*5(?!\d)", r"(?:^|[^A-Z])PI[ _.-]*3(?!\d)"], "6313", "AOI4", "6323", "2D/R4"),
    _stage("RDL2", [r"RDL[ _.-]*2(?!\d)"], "6314", "AOI5", "6324", "2D/R5"),
    _stage("PIDS7", [r"PIDS[ _.-]*7(?!\d)", r"(?:^|[^A-Z])PI[ _.-]*2(?!\d)"], "6315", "AOI6", "6325", "2D/R6"),
    _stage("RDL1", [r"RDL[ _.-]*1(?!\d)"], "6316", "AOI7", "6326", "2D/R7"),
    _stage("FS UBM", [r"FS[ _.-]*UBM", r"FSUBM", r"(?:^|[^A-Z])FS(?![A-Z])"], "6317", "AOI8", "6327", "2D/R8"),
]
PROC = {}
for _s in STAGES:
    PROC[_s["aoi"]] = _s
    PROC[_s["rev"]] = _s
ORDER = {s["key"]: i for i, s in enumerate(STAGES)}

STATUS_DONE, STATUS_NEED, STATUS_SKIP, STATUS_REREVIEW = "done", "need", "skip", "rereview"
SCAN_SHOWN = {STATUS_NEED, STATUS_DONE}        # 장비 · 호기를 보이는 줄(#85)
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp")
CAMTEK_IMG = [re.compile(r"^TB500_", re.I), re.compile(r"\s-\sMulti_", re.I)]
KLA_IMG = re.compile(r"^[A-Z0-9]+(?:_\d+){4,}$", re.I)
SLOT_ONLY = re.compile(r"(?:slot\s*)?\d{1,2}", re.I)           # `Slot 14` · `25` = 진짜 Wafer ID 아님
FILE_TIME = re.compile(r"_(\d{2})-([A-Za-z]{3})-(\d{2})_\((\d{2})\.(\d{2})\.(\d{2})\)_")
KLA_SLOT_TIME = re.compile(r"^(\d{4}-\d{2}-\d{2})-(\d{2})-(\d{2})")
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


class Stopped(Exception):
    """[중단] — 하던 Lot 은 버리고 끝난 Lot 만 돌려준다."""


# ---------------------------------------------------------------------------
#  이름 규칙(HTML 과 같음)
# ---------------------------------------------------------------------------
def stage_of(text):
    """이름에서 가장 앞에 나온 Layer 표기(같은 자리면 STAGES 앞쪽)."""
    best, pos = None, None
    for s in STAGES:
        for rx in s["keys"]:
            m = rx.search(str(text or ""))
            if m and (pos is None or m.start() < pos):
                best, pos = s, m.start()
    return best


def kind_of(name):
    """하위 폴더 종류: 재리뷰(rereview) · Skip(skip) · 재스캔(rescan) · 기본(base). 괄호 안(메모)은 보지 않는다."""
    head = name.split("(")[0]
    if "재리뷰" in head:
        return "rereview"
    if "skip" in head.lower():
        return "skip"
    if "재스캔" in head:
        return "rescan"
    return "base"


def is_star(name):
    return name.lstrip().startswith("★")


def classify_image(file_name):
    base = re.sub(r"\.[^.]+$", "", str(file_name or "")).strip()
    if any(rx.search(base) for rx in CAMTEK_IMG):
        return "Camtek"
    if KLA_IMG.match(base):
        return "KLA"
    return "Unknown"


_PUNCT = "_-,;:!?.'\"()[]{}@*/\\&#%`^+<=>|~$"


def ko_key(name):
    """화면 순서 = HTML 의 localeCompare('ko', {numeric:true}) 에 가깝게: 공백 < 문장 부호 < 기호(★) < 숫자(값) < 영문 < 한글."""
    out = []
    for m in re.finditer(r"[0-9]+|.", str(name), re.S):
        t = m.group(0)
        if t[0] in "0123456789":
            out.append((3, int(t), ""))
        elif t.isspace():
            out.append((0, 0, ""))
        elif t in _PUNCT:
            out.append((1, _PUNCT.index(t), ""))
        elif t.isascii() and t.isalpha():
            out.append((4, 0, t.lower()))
        elif t.isalpha():
            out.append((5, 0, t))
        else:
            out.append((2, ord(t), ""))
    return out


def find_lot(lot, names):
    """Conder Scan 바로 아래 폴더 이름 중 Lot 폴더: 정확 일치 → 앞뒤가 영숫자가 아닌 일치 → 포함(대소문자 무시)."""
    low = lot.lower()
    for n in names:
        if n.lower() == low:
            return n
    rx = re.compile(r"(?:^|[^A-Za-z0-9.])" + re.escape(low) + r"(?![A-Za-z0-9])", re.I)
    for n in names:
        if rx.search(n):
            return n
    for n in names:
        if low in n.lower():
            return n
    return None


def sm_of_folder(folder):
    m = re.search(r"\(([^()]*)\)\s*$", folder)
    return m.group(1).strip() if m else ""


def file_time(name):
    m = FILE_TIME.search(str(name or ""))
    if not m or m.group(2).lower() not in MONTHS:
        return ""
    yy, mon, dd, hh, mi, ss = m.groups()
    return f"20{yy}-{MONTHS[mon.lower()]:02d}-{dd} {hh}:{mi}:{ss}"


def _dirs(path):
    """바로 아래 폴더 이름(링크 · 정션은 따라가지 않음). 못 읽으면 OSError."""
    out = []
    with os.scandir(path) as it:
        for e in it:
            try:
                if e.is_dir(follow_symlinks=False) and not e.is_symlink():
                    out.append(e.name)
            except OSError:
                continue
    return out


def _walk(path, entries, seconds, on_file, cancel):
    """폴더 아래를 이름만 훑는다(정해 둔 개수 · 시간까지). on_file 이 True 면 그만. 끝까지 봤으면 True."""
    started, stack, seen = time.monotonic(), [path], 0
    while stack:
        if cancel.is_set():
            raise Stopped()
        folder = stack.pop()
        try:
            it = os.scandir(folder)
        except OSError:
            continue
        with it:
            for e in it:
                seen += 1
                if seen > entries or time.monotonic() - started > seconds:
                    return False
                try:
                    is_dir = e.is_dir(follow_symlinks=False) and not e.is_symlink()
                except OSError:
                    continue
                if is_dir:
                    stack.append(e.path)
                elif on_file(e.name) is True:
                    return True
    return True


def equipment_of(path, cancel):
    found = []

    def look(name):
        if name.lower().endswith(IMAGE_EXT):
            kind = classify_image(name)
            if kind != "Unknown":
                found.append(kind)
                return True
        return False
    _walk(path, WALK_ENTRIES, WALK_SEC, look, cancel)
    return found[0] if found else "Unknown"


def count_txt(path, cancel):
    n = [0]

    def look(name):
        if name.lower().endswith(".txt"):
            n[0] += 1
    done = _walk(path, TXT_ENTRIES, TXT_SEC, look, cancel)
    return dict(count=n[0], partial=not done)


# ---------------------------------------------------------------------------
#  로컬 캐시 색인(Camtek Batch Report · KLA) — 파일 서명이 같으면 다시 만들지 않는다
# ---------------------------------------------------------------------------
class CamtekIndex:
    """로컬 Batch Report 캐시(배치분석/누적/*.json) → Lot 코드별 Batch Report 목록. wafer 판정은 필요할 때만(detail)."""

    def __init__(self, base):
        self.base = base
        self.refs = []          # [(cachefile, file name, machine, job, setup, sm, code)]
        self.by_code = {}
        self.machines = set()
        self.bad_files = 0
        self._detail = {}
        files = []
        if base.is_dir():
            files = sorted(p for p in base.glob("*.json") if not p.is_symlink())
        sig = []
        seen = set()
        for cachefile in files:
            try:
                st = cachefile.stat()
                state = batchreport_store._load_state(cachefile)
            except (OSError, ValueError):
                self.bad_files += 1
                continue
            sig.append((cachefile.name, st.st_mtime_ns, st.st_size))
            machine = state.get("machine") if isinstance(state.get("machine"), str) else ""
            for fname, entry in state["entries"].items():
                report = entry.get("report") if isinstance(entry, dict) else None
                if not isinstance(report, dict):
                    continue
                name = str(report.get("file_name") or fname)
                if (machine, name) in seen:            # 같은 Report 가 캐시 파일 둘에(#29 가져온 이름 · resolve 한 이름)
                    continue
                seen.add((machine, name))
                job_setup = ""
                for pair in report.get("metadata") or []:
                    if isinstance(pair, (list, tuple)) and len(pair) >= 2 and wph.normalize_key(pair[0]) == "jobsetup":
                        job_setup = wph.clean_text(pair[1])
                        break
                job, _, setup = job_setup.partition("/")
                job, setup = job.strip(), setup.strip()
                sm = lotmodel.sm_of(name, job, setup)
                if not sm:
                    sm = lotmodel.sm_of(name, job, setup, [wph.safe_field(w, "Lot") for w in report.get("wafers") or []
                                                           if isinstance(w, dict)])
                code = lotmodel.lot_code(sm)
                if not code:
                    continue                            # 점검 스캔(Lot 코드 없음)은 어느 Lot 과도 맞지 않는다
                self.by_code.setdefault(code, []).append(len(self.refs))
                self.refs.append((str(cachefile), fname, machine, job, setup, sm, code))
                if machine:
                    self.machines.add(machine)
        self.signature = tuple(sig)

    @property
    def reports(self):
        return len(self.refs)

    def detail(self, ref):
        """Batch Report 1장의 시각 · wafer 판정(lotmodel.attempt). 칸 = [슬롯, Wafer ID, 종류 P/E/A/S, 원문]."""
        if ref in self._detail:
            return self._detail[ref]
        cachefile, fname, machine, job, setup, sm, code = self.refs[ref]
        state = batchreport_store._load_state(Path(cachefile))
        report = dict(state["entries"][fname]["report"])
        report.setdefault("file_name", fname)
        a = lotmodel.attempt({"id": str(ref), "machine": machine, "report": report})
        cells, n = [], dict(P=0, E=0, A=0, S=0)
        for row in a["rows"]:
            if row["pass"]:
                k = "P"
            elif row["kind"] == lotmodel.SKIP:
                k = "S"
            elif row["kind"] == lotmodel.STOP:
                k = "A"
            else:
                k = "E"
            n[k] += 1
            cells.append([row["slot"], row["wafer_id"], k, "" if row["pass"] else (wph.clean_text(row["status"]) or "(빈 칸)")])
        at = a["start"].strftime("%Y-%m-%d %H:%M:%S") if a["start"] else file_time(report["file_name"])
        scan = dict(total=len(cells), n=n, outcome="Error" if n["E"] else "작업자 중단" if n["A"] else "정상")
        out = dict(id=ref, vendor="Camtek", machine=machine, job=job, setup=setup, sm=sm, code=code, at=at,
                   file=report["file_name"], scan=scan, cells=cells)
        self._detail[ref] = out
        return out

    def report(self, ref):
        """Batch Report 보기: 캐시에 든 머리 정보 · wafer 표(원문 그대로) — 원본 파일은 열지 않는다."""
        d = self.detail(ref)
        cachefile, fname = self.refs[ref][:2]
        report = batchreport_store._load_state(Path(cachefile))["entries"][fname]["report"]
        meta = [[str(p[0]), str(p[1])] for p in report.get("metadata") or [] if isinstance(p, (list, tuple)) and len(p) >= 2]
        cols = []
        for w in report.get("wafers") or []:
            for k in (w if isinstance(w, dict) else {}):
                if k not in cols:
                    cols.append(k)
        vals = [[("" if not isinstance(w, dict) or w.get(k) is None else str(w.get(k))) for k in cols] for w in report.get("wafers") or []]
        return dict(id=ref, machine=d["machine"], at=d["at"], file=d["file"], scan=d["scan"], meta=meta, cols=cols, vals=vals,
                    cells=[[c[0], c[2]] for c in d["cells"]])


class KlaIndex:
    """로컬 KLA 캐시 → Lot 이름(소문자, @ 앞)별 폴더 목록."""

    def __init__(self, data):
        self.updated_at = data.get("updated_at", "")
        self.by_lot = {}
        self.lots = 0
        machines = set()
        for src in data.get("sources", []):
            base = str(src["path"]).rstrip("\\/")
            for day, entry in src["dates"].items():
                for lot, slots in entry["lots"].items():
                    at = lot.find("@")
                    if at < 1:
                        continue
                    m = re.match(r"\d{4}", lot[at + 1:])
                    times = sorted(t.group(1) + " " + t.group(2) + ":" + t.group(3) for t in (KLA_SLOT_TIME.match(s) for s in slots) if t)
                    self.by_lot.setdefault(lot[:at].lower(), []).append(dict(
                        machine=src["machine"], day=day, lot=lot, proc=m.group(0) if m else "", slots=len(slots),
                        at=times[0] if times else day, path=base + "\\" + day + "\\" + lot))
                    self.lots += 1
                    machines.add(src["machine"])
        self.machines = machines


_CACHE = {}       # 'camtek' → CamtekIndex, 'kla' → (서명, KlaIndex)


def _camtek_index(local):
    base = batchreport_store.local_root(local) / "배치분석" / "누적"
    old = _CACHE.get("camtek")
    if old is not None and old.base == base:
        files = sorted(p for p in base.glob("*.json") if not p.is_symlink()) if base.is_dir() else []
        try:
            sig = tuple((p.name, p.stat().st_mtime_ns, p.stat().st_size) for p in files)
        except OSError:
            sig = None
        if sig == old.signature and not old.bad_files:
            return old
    index = CamtekIndex(base)
    _CACHE["camtek"] = index
    return index


def _kla_index(config_path):
    from .desktop_kla import DesktopKla
    kla = DesktopKla(config_path)
    path = kla._cache_path()
    try:
        st = path.stat()
        sig = (str(path), st.st_mtime_ns, st.st_size)
    except OSError:
        sig = (str(path), 0, 0)
    old = _CACHE.get("kla")
    if old and old[0] == sig:
        return old[1]
    index = KlaIndex(kla._load_cache())
    _CACHE["kla"] = (sig, index)
    return index


# ---------------------------------------------------------------------------
#  wafer 판정(Layer 마다) — HTML verdictGroups 와 같은 규칙(lotmodel.resolve 와 같은 말)
# ---------------------------------------------------------------------------
def verdict_groups(scans):
    """Camtek 스캔(시간순)을 Layer(· 3D 스캔)마다 모아 wafer(슬롯)마다 판정한다. 스캔 안 한 슬롯(S)은 세지 않는다."""
    groups = {}
    for x in sorted(scans, key=lambda s: s["at"]):
        name = (x.get("layer") or "?") + (" · 3D 스캔" if lotmodel.scan_kind(x["sm"]) == lotmodel.SCAN_3D else "")
        groups.setdefault(name, []).append(x)
    out = []
    for name, items in groups.items():
        id_slot = {}
        for x in items:
            for c in x["cells"]:
                if c[0] is not None and c[1] and not SLOT_ONLY.fullmatch(c[1]):
                    id_slot[c[1]] = c[0]
        wafers = {}
        for pos, x in enumerate(items):
            for c in x["cells"]:
                if c[2] == "S":
                    continue
                slot = c[0] if c[0] is not None else id_slot.get(c[1])
                key = f"S{slot:02d}" if slot is not None else "ID:" + str(c[1])
                w = wafers.setdefault(key, dict(key=key, slot=slot, wid=c[1], items=[]))
                if c[1] and not SLOT_ONLY.fullmatch(c[1]):
                    w["wid"] = c[1]
                w["items"].append(dict(pos=pos, k=c[2], t=c[3]))
        rows = sorted(wafers.values(), key=lambda w: (w["slot"] is None, -(w["slot"] or 0), w["key"]))
        counts = {v: 0 for v in (lotmodel.OK, lotmodel.RECOVERED, lotmodel.DUPLICATE, lotmodel.UNRESOLVED)}
        for w in rows:
            passes = sum(1 for i in w["items"] if i["k"] == "P")
            bad = any(i["k"] != "P" for i in w["items"])
            w["verdict"] = (lotmodel.UNRESOLVED if not passes else lotmodel.DUPLICATE if passes > 1
                            else lotmodel.RECOVERED if bad else lotmodel.OK)
            counts[w["verdict"]] += 1
        state = (lotmodel.LOT_OPEN if counts[lotmodel.UNRESOLVED] else lotmodel.LOT_RESCANNED if counts[lotmodel.RECOVERED]
                 else lotmodel.LOT_DONE)
        out.append(dict(name=name, layer=items[0].get("layer") or "?", scans=[x["id"] for x in items], wafers=rows,
                        counts=counts, state=state))
    return out


def _hit_public(d, layer):
    return dict(vendor="Camtek", id=d["id"], machine=d["machine"], at=d["at"], sm=d["sm"], file=d["file"], scan=d["scan"],
                layer=layer)


# ---------------------------------------------------------------------------
class DesktopTb500:
    def __init__(self, config_path=None, batch=None, kla=None):
        self.config_path = Path(config_path) if config_path else Path.home() / ".pi_param_manager.json"
        self.batch = batch
        self.kla = kla
        self.cancel = threading.Event()
        self._last = None       # 마지막 조회(Lot History · Batch Report 보기용)

    # ---- 설정 ---------------------------------------------------------------
    def _read(self):
        return read_json(self.config_path)

    def conder(self, cfg=None):
        cfg = self._read() if cfg is None else cfg
        value = cfg.get("tb500_conder")
        return value if isinstance(value, str) and value.strip() else DEFAULT_CONDER

    def _local(self):
        return DesktopBatch(self.config_path).configuration()[2]

    def state(self):
        cfg = self._read()
        imported = cfg.get("tb500_imported") if isinstance(cfg.get("tb500_imported"), dict) else {}
        out = dict(conder=self.conder(cfg), default_conder=DEFAULT_CONDER, is_default=not cfg.get("tb500_conder"),
                   imported=dict(camtek=str(imported.get("camtek") or ""), kla=str(imported.get("kla") or ""),
                                 at=str(imported.get("at") or "")))
        # 화면 요약: 파일 이름 · 크기만 본다(캐시 JSON 을 열지 않음 — 큰 캐시에서도 바로 응답).
        try:
            base = batchreport_store.local_root(self._local()) / "배치분석" / "누적"
            files = [p for p in base.glob("*.json") if not p.is_symlink()] if base.is_dir() else []
            out["camtek"] = dict(files=len(files), size=sum(p.stat().st_size for p in files))
        except (OSError, ValueError):
            out["camtek"] = dict(files=0, size=0, error=True)
        try:
            from .desktop_kla import DesktopKla
            path = DesktopKla(self.config_path)._cache_path()
            out["kla"] = dict(present=path.is_file(), size=path.stat().st_size if path.is_file() else 0)
        except (OSError, ValueError):
            out["kla"] = dict(present=False, size=0, error=True)
        index = _CACHE.get("camtek")
        if index is not None and out["camtek"]["files"]:
            out["camtek"].update(reports=index.reports, machines=sorted(index.machines, key=ko_key))
        return out

    def set_conder(self, params):
        """Conder Scan 폴더(Lot 폴더들이 바로 아래 있는 폴더). 빈 값 = 기본 경로. 글자로만 확인한다(네트워크에서 멈추지 않게)."""
        if set(params) != {"path"} or not isinstance(params["path"], str):
            raise ValueError("Conder Scan 폴더를 확인하세요")
        path = params["path"].strip().strip('"').strip()
        if len(path) > 3:
            path = path.rstrip("\\/")          # 드라이브 루트(P:\)는 그대로
        if path and (len(path) > MAX_PATH or "\0" in path or not (Path(path).is_absolute() or path.startswith("\\\\"))):
            raise ValueError("Conder Scan 폴더는 전체 경로로 적으세요(예: \\\\서버\\공유\\폴더 또는 P:\\폴더)")
        cfg = self._read()
        if path and path != DEFAULT_CONDER:
            cfg["tb500_conder"] = path
        else:
            cfg.pop("tb500_conder", None)
        atomicfile.write_json(str(self.config_path), cfg)
        self._last = None
        return self.state()

    def allows(self, path):
        """[폴더 열기] — 설정한 Conder Scan 폴더 안의 폴더만(글자로만 비교, 네트워크 경로를 풀지 않음)."""
        def key(p):
            return os.path.normcase(os.path.normpath(str(p)))
        base, target = key(self.conder()), key(path)
        return target == base or target.startswith(base.rstrip("\\/") + os.sep)

    # ---- 조회 ---------------------------------------------------------------
    def stop(self):
        self.cancel.set()
        return dict(stopping=True)

    def lookup(self, params):
        if set(params) != {"lots"} or not isinstance(params["lots"], list):
            raise ValueError("조회할 Lot 목록을 확인하세요")
        lots = []
        for raw in params["lots"]:
            if not isinstance(raw, str):
                raise ValueError("조회할 Lot 목록을 확인하세요")
            lot = raw.strip()
            if lot and len(lot) <= MAX_LOT_LEN and "\0" not in lot and lot.lower() not in (x.lower() for x in lots):
                lots.append(lot)
        if not lots:
            raise ValueError("조회할 Lot 을 입력하세요")
        if len(lots) > MAX_LOTS:
            raise ValueError(f"한 번에 {MAX_LOTS}개까지 조회할 수 있습니다")
        self.cancel.clear()
        conder = self.conder()
        started = time.monotonic()
        desktop_progress.report("Conder Scan 폴더 목록 읽는 중…")
        try:
            names = _dirs(conder)
        except OSError as exc:
            raise ValueError(f"Conder Scan 폴더를 열지 못했습니다 — {conder} ({exc.strerror or exc}). "
                             "파일 탐색기에서 이 폴더가 열리는지 확인하고, 다르면 [폴더 고르기]로 다시 고르세요.") from exc
        desktop_progress.report("캐시 읽는 중…")
        local = self._local()
        camtek = _camtek_index(local)
        try:
            kla = _kla_index(self.config_path)
            kla_error = ""
        except (OSError, ValueError) as exc:
            kla, kla_error = KlaIndex(dict(sources=[])), str(exc)
        results, stopped = [], False
        for i, lot in enumerate(lots):
            if self.cancel.is_set():
                stopped = True
                break
            desktop_progress.report(f"{i + 1} / {len(lots)} 조회 중… {lot}")
            try:
                results.append(self._look(lot, conder, names, camtek, kla))
            except Stopped:
                stopped = True
                break
        self._last = dict(results=results, camtek=camtek, kla=kla)
        layers = [ly for r in results for ly in r["layers"]]
        return dict(conder=conder, lots=len(lots), done=len(results), stopped=stopped, results=results,
                    elapsed=round(time.monotonic() - started, 1),
                    summary=dict(lots=len(results), missing=sum(1 for r in results if r["missing"]), layers=len(layers),
                                 done=sum(1 for ly in layers if ly["status"] == STATUS_DONE),
                                 need=sum(1 for ly in layers if ly["status"] == STATUS_NEED),
                                 skip=sum(1 for ly in layers if ly["status"] == STATUS_SKIP)),
                    cache=dict(camtek_reports=camtek.reports, camtek_machines=len(camtek.machines), camtek_bad=camtek.bad_files,
                               kla_lots=kla.lots, kla_machines=len(kla.machines), kla_at=kla.updated_at, kla_error=kla_error))

    def _look(self, lot, conder, names, camtek, kla):
        folder = find_lot(lot, names)
        if not folder:
            return dict(lot=lot, folder="", sm="", code="", missing=True, subs=[], layers=[], error="")
        sm = sm_of_folder(folder)
        code = lotmodel.lot_code(sm) or ""
        lot_path = os.path.join(conder, folder)
        try:
            sub_names = sorted(_dirs(lot_path), key=ko_key)
        except OSError as exc:
            return dict(lot=lot, folder=folder, sm=sm, code=code, missing=False, subs=[], layers=[],
                        error=f"하위 폴더를 읽지 못했습니다({exc.strerror or exc})")
        subs = []
        for name in sub_names:
            star = is_star(name)
            st = None if star else (stage_of(name.split("(")[0]) or stage_of(name))
            subs.append(dict(name=name, star=star, stage=st, kind="base" if star else kind_of(name)))
        status = {}
        for st in STAGES:
            group = [s for s in subs if s["stage"] is st]
            if group:
                status[st["key"]] = (STATUS_DONE if any(s["kind"] == "rereview" for s in group)
                                     else STATUS_SKIP if any(s["kind"] == "skip" for s in group) else STATUS_NEED)
        out = []
        for s in subs:
            if self.cancel.is_set():
                raise Stopped()
            st = s["stage"]
            row = dict(name=s["name"], kind=s["kind"], star=s["star"], path=os.path.join(lot_path, s["name"]),
                       stage=None if st is None else {k: st[k] for k in ("key", "aoi", "aoi_name", "rev", "rev_name")},
                       status="", txt=None, equipment="", hits=[], total=0, machines=0, verdicts=[])
            if st is not None:
                if s["kind"] == "rereview":
                    row["status"] = STATUS_REREVIEW
                    row["txt"] = count_txt(row["path"], self.cancel)
                elif s["kind"] == "skip":
                    row["status"] = STATUS_SKIP
                else:
                    row["status"] = status[st["key"]]
                    if row["status"] in SCAN_SHOWN:
                        row["equipment"] = equipment_of(row["path"], self.cancel)
                        hits = []
                        if row["equipment"] != "KLA" and code:
                            details = [camtek.detail(ref) for ref in camtek.by_code.get(code, [])
                                       if any(rx.search(camtek.refs[ref][3]) for rx in st["keys"])]
                            hits += [_hit_public(d, st["key"]) for d in details]
                            row["verdicts"] = [dict(name=g["name"], state=g["state"], counts=g["counts"], wafers=len(g["wafers"]))
                                               for g in verdict_groups([dict(d, layer=st["key"]) for d in details])]
                        if row["equipment"] != "Camtek":
                            hits += [dict(vendor="KLA", machine=k["machine"], at=k["at"], lot=k["lot"], slots=k["slots"],
                                          path=k["path"], review=k["proc"] == st["rev"], layer=st["key"])
                                     for k in kla.by_lot.get(lot.lower(), []) if PROC.get(k["proc"]) is st]
                        hits.sort(key=lambda h: h["at"], reverse=True)
                        row["total"] = len(hits)
                        row["machines"] = len({h["machine"] for h in hits})
                        row["hits"] = hits[:SHOW_HITS]
            out.append(row)
        layers = [dict(key=st["key"], status=status[st["key"]]) for st in STAGES if st["key"] in status]
        return dict(lot=lot, folder=folder, sm=sm, code=code, missing=False, subs=out, layers=layers, error="")

    # ---- Lot History · Batch Report 보기 -------------------------------------
    def _result(self, params):
        if self._last is None:
            raise ValueError("먼저 [조회]를 누르세요")
        i = params.get("lot")
        if type(i) is not int or not 0 <= i < len(self._last["results"]):
            raise ValueError("Lot 을 다시 고르세요")
        return self._last["results"][i]

    def history(self, params):
        """이 Lot 의 모든 스캔(Camtek: S/M 코드가 같은 Batch Report, KLA: Lot 이름@공정번호 폴더)을 시간순으로 + wafer 판정."""
        if set(params) != {"lot"}:
            raise ValueError("요청을 확인하세요")
        r = self._result(params)
        camtek, kla = self._last["camtek"], self._last["kla"]
        rows = []
        for ref in camtek.by_code.get(r["code"], []) if r["code"] else []:
            d = camtek.detail(ref)
            st = stage_of(d["job"])
            rows.append(dict(vendor="Camtek", id=d["id"], machine=d["machine"], at=d["at"], layer=st["key"] if st else "?",
                             what=f"{d['job']} / {d['setup']} · S/M {d['sm']}", sm=d["sm"], scan=d["scan"], src=d["file"],
                             cells=d["cells"]))
        for k in kla.by_lot.get(r["lot"].lower(), []):
            st = PROC.get(k["proc"])
            kind = (("Review " if k["proc"] == st["rev"] else "AOI ") + k["proc"]) if st else "공정 " + (k["proc"] or "?")
            rows.append(dict(vendor="KLA", machine=k["machine"], at=k["at"] if st else k["day"], layer=st["key"] if st else "?",
                             what=f"{k['lot']} · {kind} · 슬롯 {k['slots']}개", src=k["path"]))
        rows.sort(key=lambda h: h["at"])
        groups = verdict_groups([h for h in rows if h["vendor"] == "Camtek"])
        for h in rows:
            h.pop("cells", None)
        layers = sorted({h["layer"] for h in rows}, key=lambda k: ORDER.get(k, len(ORDER)))
        return dict(lot=r["lot"], folder=r["folder"], sm=r["sm"], code=r["code"], rows=rows, groups=groups, layers=layers)

    def report(self, params):
        if set(params) != {"id"} or type(params["id"]) is not int:
            raise ValueError("요청을 확인하세요")
        if self._last is None or not 0 <= params["id"] < self._last["camtek"].reports:
            raise ValueError("먼저 [조회]를 누르세요")
        return self._last["camtek"].report(params["id"])

    # ---- 캐시 갱신 = OneDrive 에서 최신 캐시 불러오기(Camtek · KLA) ----------
    def _has_local(self, kind):
        try:
            if kind == "camtek":
                base = batchreport_store.local_root(self._local()) / "배치분석" / "누적"
                return base.is_dir() and any(base.glob("*.json"))
            from .desktop_kla import DesktopKla
            return DesktopKla(self.config_path)._cache_path().is_file()
        except (OSError, ValueError):
            return False

    def cache_update(self, params):
        """OneDrive 캐시공유/ 에서 Camtek · KLA 각각 받을 수 있는 가장 최근 zip 을 기존 [OneDrive 에서 불러오기]로 받는다.
        지난번에 받은 zip 과 같고 로컬 캐시가 있으면 다시 받지 않는다(이미 최신). OneDrive 에는 쓰지 않는다."""
        if params:
            raise ValueError("요청을 확인하세요")
        from .desktop_kla import DesktopKla
        batch = self.batch or DesktopBatch(self.config_path)
        kla = self.kla or DesktopKla(self.config_path)
        cfg = self._read()
        imported = dict(cfg.get("tb500_imported")) if isinstance(cfg.get("tb500_imported"), dict) else {}
        out = {}
        for kind, label, lister, importer in (("camtek", "Camtek", batch.cache_share_list, batch.cache_share_import),
                                              ("kla", "KLA", kla.cache_share_list, kla.cache_share_import)):
            desktop_progress.report(f"{label} 캐시 목록 읽는 중…")
            try:
                listing = lister({})
                ready = [i for i in listing["items"] if i["present"] and i["compatible"]]
                if not listing["items"]:
                    res = dict(status="none", message="OneDrive 에 게시된 캐시가 없습니다")
                elif not ready:
                    res = dict(status="wait", message="받을 수 있는 캐시가 없습니다 — OneDrive 동기화가 끝나지 않았거나 형식(버전)이 다릅니다")
                else:
                    item = ready[0]
                    if imported.get(kind) == item["name"] and self._has_local(kind):
                        res = dict(status="latest", name=item["name"], exported_at=item["exported_at"])
                    else:
                        desktop_progress.report(f"{label} 캐시 받는 중… {item['name']}")
                        importer({"name": item["name"]})
                        imported[kind] = item["name"]
                        res = dict(status="imported", name=item["name"], exported_at=item["exported_at"])
            except ValueError as exc:
                res = dict(status="error", message=str(exc))
            out[kind] = res
        if all(out[k]["status"] in ("imported", "latest") for k in out):
            imported["at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")   # 둘 다 받았을 때만(24시간 알림이 계속 나오게)
        cfg = self._read()
        cfg["tb500_imported"] = imported
        atomicfile.write_json(str(self.config_path), cfg)
        self._last = None
        return dict(out, state=self.state())
