"""KLA 자재 찾기 — KLA 장비 스캔 결과 폴더에서 Lot 이름으로 자재를 찾는다(이슈 #30).

KLA 장비는 Camtek 과 폴더 구조가 다르다. 사용자가 알려 준 구조:

    {장비 폴더}\\{날짜 YYYY-MM-DD}\\{Lot 이름}\\{스캔 시각 YYYY-MM-DD-HH-MM}_{슬롯}\\
        *.jpg (Defect 이미지) · {Recipe}_{Lot}_{Wafer}.001 · {Recipe}_{Lot}_{Wafer}.pass

예 `J:\\2.K2\\2025-05-21\\RINT63@6324\\2025-05-21-09-08_16` = 장비 `2.K2`, 날짜 2025-05-21,
Lot `RINT63@6324`, 슬롯 16.

찾기는 **폴더 이름만** 본다(파일은 열지도 세지도 않는다): 장비 폴더 → 날짜 폴더 목록 →
그 날짜의 Lot 폴더 목록(키워드에 맞는 것만) → 맞은 Lot 의 슬롯 폴더 목록. 장비 원본은
읽기 전용이고 아무것도 쓰지 않는다. 등록한 폴더(설정 `kla_roots` = {이름: 경로})는
로컬 설정 파일(`~/.pi_param_manager.json`)에만 저장한다.

등록 폴더가 장비 폴더(바로 아래가 날짜 폴더)가 아니면 한 단계 아래 폴더들을 장비 폴더로
본다(예 `J:\\` 하나만 등록 → `1.K1`, `2.K2` … 를 모두 찾음).

**Defect 이미지 백업본(이슈 #32)**: Camtek 의 'Scanresult 백업본'에 해당하는 KLA 설정. KLA 는 Scanresult 폴더가
없고 장비 폴더 바로 아래 날짜 폴더에 Defect 이미지(.jpg)와 결과 파일을 저장하므로, 날짜 폴더째 옮겨 둔 보관 폴더를
장비마다 등록한다(`kla_backups` = {장비 이름: [경로]}). 켜기/끄기 = `kla_backup`(기본 켬). 켜면 찾기가 원본 장비
폴더와 백업 폴더를 함께 보고, 끄면 원본만 본다. 백업 폴더도 구조는 원본과 같다(바로 아래 날짜 폴더, 또는 한 단계 아래
장비 폴더들).

**KLA 캐시(이슈 Para #40)**: Camtek Batch Report 캐시(#29 · #39)와 같은 방식. 개발자 PC 가 [캐시 갱신]으로 등록한 장비(+ 백업본)의
폴더 이름(날짜 · Lot · 슬롯)만 읽어 로컬 `KLA캐시/KLA색인.json` 에 모으고, [OneDrive 에 게시]로 저장 폴더 옆 `캐시공유/` 에
`KLA_캐시_YYYYMMDD_HHMMSS.zip` + `KLA캐시정보.json`(Camtek 의 `BatchReport_캐시_*.zip` · `캐시정보.json` 과 이름으로 구분)을 올린다.
다른 PC 는 [OneDrive 에서 불러오기]로 받아(로컬 Temp 복사 · 크기 · SHA-256 확인 → 로컬 색인에 합침, OneDrive 에 쓰지 않음)
장비에 연결하지 않고 [캐시에서 찾기]로 찾는다. 갱신은 날짜 폴더 수정시각이 같고 오늘 기준 `KLA_REREAD_DAYS` 일보다 오래된 날짜는
다시 읽지 않는다(새 슬롯 폴더는 Lot 폴더에 생겨 날짜 폴더 수정시각이 안 바뀌므로 최근 날짜는 늘 다시 읽음).
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import json
from datetime import datetime, timedelta

from . import atomicfile, desktop_progress
from .desktop_batch import DesktopBatch, _name_key, read_json

MAX_PATH = 4096
MAX_NAME = 64
MAX_ROOTS = 50
MAX_BACKUPS = 20         # 장비 하나의 백업 폴더 수 한도
MAX_QUERY = 200
MAX_HITS = 2000          # Lot 폴더 수 한도(넘으면 앞의 것만 + 안내)
MAX_SLOTS = 200          # Lot 하나의 슬롯 폴더 표시 한도
DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
# KLA 캐시(이슈 Para #40)
KLA_CACHE_DIR = "KLA캐시"
KLA_CACHE_FILE = "KLA색인.json"
KLA_CACHE_SCHEMA = 1
KLA_SHARE_INDEX = "KLA캐시정보.json"
KLA_SHARE_KEEP = 3
KLA_SHARE_NAME = re.compile(r"KLA_캐시_\d{8}_\d{6}\.zip")
KLA_ZIP_MEMBER = "KLA색인.json"
KLA_REREAD_DAYS = 3              # 오늘 기준 이 날수 안의 날짜 폴더는 갱신 때마다 다시 읽는다
KLA_CACHE_MAX_LOTS = 300000      # 색인 전체 Lot 폴더 수 한도
KLA_CACHE_MAX_SLOTS = 500        # Lot 하나에 적는 슬롯 폴더 이름 한도
KLA_ZIP_MAX = 512 * 1024 ** 2    # 불러올 zip 안 색인 크기 한도
SLOT_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-(\d{2})-(\d{2})(?:-(\d{2}))?_(\d+)$")


def _dirs(path):
    """하위 폴더 이름 목록(링크/정션은 따라가지 않음). 못 읽으면 OSError."""
    out = []
    with os.scandir(path) as it:
        for e in it:
            try:
                if e.is_dir(follow_symlinks=False) and not e.is_symlink():
                    out.append(e.name)
            except OSError:
                continue
    return out


def _keywords(query):
    return [t for t in str(query or "").lower().split() if t]


def _match(name, words):
    low = name.lower()
    return all(w in low for w in words)


def slot_info(name):
    """슬롯 폴더 이름 → (슬롯 번호, 스캔 시각 'YYYY-MM-DD HH:MM'). 형식이 다르면 ('', '')."""
    m = SLOT_RE.match(name)
    if not m:
        tail = name.rsplit("_", 1)
        return (str(int(tail[1])) if len(tail) == 2 and tail[1].isdigit() else ""), ""
    day, hh, mm, ss, slot = m.groups()
    return str(int(slot)), f"{day} {hh}:{mm}" + (f":{ss}" if ss else "")


def _text(v, limit=MAX_PATH):
    return isinstance(v, str) and 0 < len(v) <= limit and "\0" not in v


def clean_index(data):
    """KLA 색인(로컬 · zip 안) 검사 — 모양이 틀린 항목은 버리고, 틀이 틀리면 ValueError."""
    if not isinstance(data, dict) or data.get("schema") != KLA_CACHE_SCHEMA or not isinstance(data.get("sources"), list):
        raise ValueError("KLA 캐시 형식(버전)이 이 프로그램과 다릅니다")
    sources, lots_total = [], 0
    for src in data["sources"]:
        if not isinstance(src, dict) or not _text(src.get("machine"), 200) or not _text(src.get("path")) \
                or not isinstance(src.get("dates"), dict):
            continue
        dates = {}
        for day, entry in src["dates"].items():
            if not isinstance(day, str) or not DATE_RE.match(day) or not isinstance(entry, dict) or not isinstance(entry.get("lots"), dict):
                continue
            lots = {}
            for lot, slots in entry["lots"].items():
                if lots_total >= KLA_CACHE_MAX_LOTS:
                    break
                if not _text(lot, 260) or any(c in lot for c in "\\/") or not isinstance(slots, list):
                    continue
                lots[lot] = [x for x in slots[:KLA_CACHE_MAX_SLOTS] if _text(x, 260) and not any(c in x for c in "\\/")]
                lots_total += 1
            mtime = entry.get("mtime")
            dates[day] = dict(mtime=mtime if type(mtime) is int else 0,
                              read_at=entry.get("read_at") if isinstance(entry.get("read_at"), str) else "", lots=lots)
        sources.append(dict(machine=src["machine"], path=src["path"], backup=src.get("backup") is True, dates=dates))
    return dict(schema=KLA_CACHE_SCHEMA, updated_at=data.get("updated_at") if isinstance(data.get("updated_at"), str) else "",
                sources=sources)


def merge_index(mine, incoming):
    """불러온 색인을 로컬 색인에 합친다 — (장비, 폴더, 날짜)가 겹치면 read_at 이 더 나중인 쪽."""
    table = {(s["machine"], s["path"]): dict(s, dates=dict(s["dates"])) for s in mine["sources"]}
    for src in incoming["sources"]:
        key = (src["machine"], src["path"])
        if key not in table:
            table[key] = dict(src, dates=dict(src["dates"]))
            continue
        dates = table[key]["dates"]
        for day, entry in src["dates"].items():
            if day not in dates or entry["read_at"] >= dates[day]["read_at"]:
                dates[day] = entry
    sources = sorted(table.values(), key=lambda x: (_name_key(x["machine"]), x["backup"], x["path"]))
    return dict(schema=KLA_CACHE_SCHEMA, updated_at=max(mine["updated_at"], incoming["updated_at"]), sources=sources)


def index_summary(data):
    machines = sorted({s["machine"] for s in data["sources"]}, key=_name_key)
    days = [d for s in data["sources"] for d in s["dates"]]
    return dict(updated_at=data["updated_at"], machines=machines,
                lots=sum(len(e["lots"]) for s in data["sources"] for e in s["dates"].values()),
                dates=len(days), first=min(days) if days else "", last=max(days) if days else "")


class DesktopKla:
    def __init__(self, config_path=None):
        self.config_path = Path(config_path) if config_path else Path.home() / ".pi_param_manager.json"

    # ---- 등록 폴더 -------------------------------------------------------------
    def _read(self):
        return read_json(self.config_path)

    def roots(self, cfg=None):
        cfg = self._read() if cfg is None else cfg
        table = cfg.get("kla_roots")
        if not isinstance(table, dict):
            return []
        backups = cfg.get("kla_backups") if isinstance(cfg.get("kla_backups"), dict) else {}
        out = []
        for n, p in table.items():
            if isinstance(n, str) and isinstance(p, str) and n.strip() and p.strip():
                extra = backups.get(n) if isinstance(backups.get(n), list) else []
                out.append(dict(name=n, path=p, backups=[b for b in extra if isinstance(b, str) and b.strip()]))
        return out

    @staticmethod
    def backup_on(cfg):
        """설정 'Defect 이미지 백업본 포함'(`kla_backup`, 기본 켬)."""
        return cfg.get("kla_backup", True) is not False

    def state(self):
        cfg = self._read()
        return dict(roots=self.roots(cfg), backup=self.backup_on(cfg), cache=self._cache_summary())

    @staticmethod
    def _check_path(name, path, what="폴더"):
        if not isinstance(path, str):
            raise ValueError("KLA 장비 폴더 목록을 확인하세요")
        path = path.strip()
        if not path or len(path) > MAX_PATH or "\0" in path or not Path(path).is_absolute():
            raise ValueError(f"{name}: {what} 경로는 드라이브(J:\\…) 또는 \\\\서버\\… 로 시작하는 전체 경로여야 합니다")
        return path

    def set_roots(self, params):
        """roots = [{name, path, backups?}]. backups 를 빼고 보내면 그 장비의 기존 백업 폴더를 그대로 둔다."""
        if set(params) != {"roots"} or not isinstance(params["roots"], list) or len(params["roots"]) > MAX_ROOTS:
            raise ValueError("KLA 장비 폴더 목록을 확인하세요")
        cfg = self._read()
        old = cfg.get("kla_backups") if isinstance(cfg.get("kla_backups"), dict) else {}
        table, backups = {}, {}
        for item in params["roots"]:
            if not isinstance(item, dict) or not {"name", "path"} <= set(item) <= {"name", "path", "backups"}:
                raise ValueError("KLA 장비 폴더 목록을 확인하세요")
            name = item["name"]
            if not isinstance(name, str):
                raise ValueError("KLA 장비 폴더 목록을 확인하세요")
            name = name.strip()
            if not name or len(name) > MAX_NAME or any(c in name for c in "\\/\0"):
                raise ValueError("장비 이름은 1~64자로, \\ / 없이 적으세요")
            path = self._check_path(name, item["path"])
            if name in table:
                raise ValueError(f"같은 장비 이름이 두 번 있습니다: {name}")
            table[name] = path
            extra = item["backups"] if "backups" in item else (old.get(name) if isinstance(old.get(name), list) else [])
            if not isinstance(extra, list) or len(extra) > MAX_BACKUPS:
                raise ValueError(f"{name}: 백업 폴더는 {MAX_BACKUPS}개까지 등록할 수 있습니다")
            seen = []
            for b in extra:
                b = self._check_path(name, b, "백업 폴더")
                if b != path and b not in seen:
                    seen.append(b)
            if seen:
                backups[name] = seen
        cfg["kla_roots"] = table
        cfg["kla_backups"] = backups
        atomicfile.write_json(str(self.config_path), cfg)
        return self.state()

    def set_backup(self, params):
        """찾기에서 Defect 이미지 백업본(장비마다 등록한 백업 폴더)까지 볼지."""
        if set(params) != {"enabled"} or type(params["enabled"]) is not bool:
            raise ValueError("Defect 이미지 백업본 포함 설정을 확인하세요")
        cfg = self._read()
        cfg["kla_backup"] = params["enabled"]
        atomicfile.write_json(str(self.config_path), cfg)
        return self.state()

    # ---- 찾기 ------------------------------------------------------------------
    def _machine_dirs(self, name, root):
        """등록 폴더 → [(장비 이름, 장비 폴더, 날짜 폴더 이름들)]. 바로 아래에 날짜 폴더가 없으면
        한 단계 아래 폴더들을 장비 폴더로 본다."""
        names = _dirs(root)
        dates = [n for n in names if DATE_RE.match(n)]
        if dates or not names:
            return [(name, root, dates)]
        out = []
        for sub in sorted(names):
            path = os.path.join(root, sub)
            try:
                sub_dates = [n for n in _dirs(path) if DATE_RE.match(n)]
            except OSError:
                continue
            if sub_dates:
                out.append((f"{name} › {sub}", path, sub_dates))
        return out or [(name, root, [])]

    def search(self, params):
        if set(params) - {"query", "machines", "start", "end", "source"}:
            raise ValueError("찾기 요청을 확인하세요")
        source = params.get("source", "equipment")
        if source not in ("equipment", "cache"):
            raise ValueError("찾을 곳을 확인하세요")
        query = params.get("query", "")
        if not isinstance(query, str) or len(query) > MAX_QUERY:
            raise ValueError("검색어를 확인하세요")
        words = _keywords(query)
        if not words:
            raise ValueError("Lot 이름(또는 그 일부)을 입력하세요")
        start, end = params.get("start", ""), params.get("end", "")
        for v in (start, end):
            if not isinstance(v, str) or (v and not DATE_RE.match(v)):
                raise ValueError("기간은 YYYY-MM-DD 로 적으세요")
        if start and end and start > end:
            start, end = end, start
        machines = params.get("machines")
        if machines is not None and (not isinstance(machines, list) or not all(isinstance(m, str) for m in machines)):
            raise ValueError("장비 선택을 확인하세요")
        if source == "cache":
            return self._search_cache(query, words, start, end, machines)
        cfg = self._read()
        roots = self.roots(cfg)
        backup = self.backup_on(cfg)
        if machines is not None:
            roots = [r for r in roots if r["name"] in set(machines)]
        if not roots:
            raise ValueError("찾을 KLA 장비 폴더가 없습니다. 위 [KLA 장비 폴더]에서 먼저 등록하세요")

        hits, failed, machines_seen = [], [], []
        dates_seen = 0
        truncated = False
        sources = []
        for r in roots:
            sources.append((r["name"], r["path"], False))
            if backup:
                sources.extend((r["name"], b, True) for b in r["backups"])
        for name, root, is_backup in sources:
            label = f"{name} 백업본" if is_backup else name
            desktop_progress.report(f"{label}: 날짜 폴더 목록 확인 중…")
            try:
                groups = self._machine_dirs(name, root)
            except OSError as exc:
                failed.append(dict(machine=name, path=root, backup=is_backup, reason=exc.strerror or type(exc).__name__))
                continue
            for machine, mpath, dates in groups:
                if machine not in machines_seen:
                    machines_seen.append(machine)
                picked = sorted((d for d in dates if (not start or d >= start) and (not end or d <= end)), reverse=True)
                for i, day in enumerate(picked):
                    if truncated:
                        break
                    if i % 20 == 0:
                        desktop_progress.report(f"{machine}: 날짜 폴더 {i + 1}/{len(picked)} 확인 중 (찾은 Lot {len(hits)})")
                    dpath = os.path.join(mpath, day)
                    try:
                        lots = _dirs(dpath)
                    except OSError:
                        continue
                    dates_seen += 1
                    for lot in sorted(lots):
                        if not _match(lot, words):
                            continue
                        if len(hits) >= MAX_HITS:
                            truncated = True
                            break
                        lpath = os.path.join(dpath, lot)
                        try:
                            names = _dirs(lpath)
                        except OSError:
                            names = []
                        slots = []
                        for s in sorted(names)[:MAX_SLOTS]:
                            no, at = slot_info(s)
                            slots.append(dict(name=s, slot=no, time=at, path=os.path.join(lpath, s)))
                        slots.sort(key=lambda x: (x["time"], int(x["slot"]) if x["slot"].isdigit() else 0))
                        hits.append(dict(machine=machine, date=day, lot=lot, path=lpath, slots=slots,
                                         more=max(0, len(names) - MAX_SLOTS), backup=is_backup))
        # 최근 날짜 먼저, 같은 Lot 이면 원본이 백업본보다 위.
        hits.sort(key=lambda h: (h["date"], h["machine"], h["lot"], not h["backup"]), reverse=True)
        return dict(query=query, start=start, end=end, hits=hits, truncated=truncated, max_hits=MAX_HITS,
                    machines=machines_seen, dates=dates_seen, failed=failed, backup=backup,
                    backup_folders=sum(len(r["backups"]) for r in roots) if backup else 0, source="equipment")

    # ---- KLA 캐시(이슈 Para #40) ------------------------------------------------
    def _local(self):
        """로컬 작업 폴더(Camtek 캐시와 같은 곳) — OneDrive 밖."""
        return DesktopBatch(self.config_path).configuration()[2]

    def _cache_path(self, root=None):
        return (root or self._local()) / KLA_CACHE_DIR / KLA_CACHE_FILE

    def _load_cache(self, root=None):
        path = self._cache_path(root)
        try:
            with path.open(encoding="utf-8") as stream:
                data = json.load(stream)
        except FileNotFoundError:
            return dict(schema=KLA_CACHE_SCHEMA, updated_at="", sources=[])
        except (OSError, ValueError) as exc:
            raise ValueError("로컬 KLA 캐시 파일을 읽지 못했습니다 — [캐시 갱신] 또는 [OneDrive 에서 불러오기]로 다시 만드세요") from exc
        return clean_index(data)

    def _save_cache(self, data, root=None):
        path = self._cache_path(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        atomicfile.write_json(str(path), data)

    def _cache_summary(self):
        """화면 요약 — 로컬 작업 폴더를 못 정하면(설정 오류) 캐시 없음으로 본다."""
        try:
            data = self._load_cache()
        except (OSError, ValueError):
            return dict(updated_at="", machines=[], lots=0, dates=0, error=True)
        return index_summary(data)

    def cache_build(self, params):
        """개발자: 등록한 KLA 장비(+ 백업본 설정)의 날짜 · Lot · 슬롯 폴더 이름을 읽어 로컬 KLA 색인을 갱신한다.
        파일은 열지 않고 장비에는 쓰지 않는다. 읽지 못한 폴더의 예전 색인은 지우지 않고 그대로 둔다."""
        if params:
            raise ValueError("요청을 확인하세요")
        cfg = self._read()
        roots = self.roots(cfg)
        if not roots:
            raise ValueError("캐시를 만들 KLA 장비 폴더가 없습니다. 설정 › AOI 장비 호기 루트 › KLA 에서 먼저 등록하세요")
        backup = self.backup_on(cfg)
        local = self._local()
        data = self._load_cache(local)
        old = {(x["machine"], x["path"]): x for x in data["sources"]}
        recent = (datetime.now() - timedelta(days=KLA_REREAD_DAYS)).strftime("%Y-%m-%d")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sources = []
        for r in roots:
            sources.append((r["name"], r["path"], False))
            if backup:
                sources.extend((r["name"], b, True) for b in r["backups"])
        fresh, failed = {}, []
        read_dates = reused = 0
        total_lots = 0
        for name, root, is_backup in sources:
            label = f"{name} 백업본" if is_backup else name
            desktop_progress.report(f"{label}: 날짜 폴더 목록 확인 중…")
            try:
                groups = self._machine_dirs(name, root)
            except OSError as exc:
                failed.append(dict(machine=name, path=root, backup=is_backup, reason=exc.strerror or type(exc).__name__))
                continue
            for machine, mpath, dates in groups:
                prev = old.get((machine, mpath), {}).get("dates", {})
                out = {}
                for i, day in enumerate(sorted(dates, reverse=True)):
                    if i % 20 == 0:
                        desktop_progress.report(f"{machine}: 날짜 폴더 {i + 1}/{len(dates)} 확인 중")
                    dpath = os.path.join(mpath, day)
                    try:
                        mtime = os.stat(dpath).st_mtime_ns
                    except OSError:
                        if day in prev:
                            out[day] = prev[day]
                        continue
                    if day in prev and prev[day]["mtime"] == mtime and day < recent:
                        out[day] = prev[day]
                        reused += 1
                        total_lots += len(prev[day]["lots"])
                        continue
                    try:
                        lot_names = _dirs(dpath)
                    except OSError:
                        if day in prev:
                            out[day] = prev[day]
                        continue
                    lots = {}
                    for lot in sorted(lot_names):
                        if total_lots >= KLA_CACHE_MAX_LOTS:
                            break
                        try:
                            slots = sorted(_dirs(os.path.join(dpath, lot)))[:KLA_CACHE_MAX_SLOTS]
                        except OSError:
                            slots = []
                        lots[lot] = slots
                        total_lots += 1
                    out[day] = dict(mtime=mtime, read_at=now, lots=lots)
                    read_dates += 1
                fresh[(machine, mpath)] = dict(machine=machine, path=mpath, backup=is_backup, dates=out)
        if not fresh and failed:
            raise ValueError("KLA 장비 폴더를 하나도 읽지 못했습니다: "
                             + ", ".join(f"{f['machine']}({f['path']})" for f in failed[:5]) + " — 연결을 확인하세요")
        # 이번에 읽지 못한 장비 · 다른 PC 에서 불러온 장비의 예전 색인은 그대로 둔다.
        merged = [fresh.pop(k) if k in fresh else v for k, v in old.items()] + list(fresh.values())
        merged.sort(key=lambda x: (_name_key(x["machine"]), x["backup"], x["path"]))
        data = dict(schema=KLA_CACHE_SCHEMA, updated_at=now, sources=merged)
        self._save_cache(data, local)
        return dict(index_summary(data), read_dates=read_dates, reused_dates=reused, failed=failed,
                    path=str(self._cache_path(local)))

    def _search_cache(self, query, words, start, end, machines):
        """[캐시에서 찾기] — 로컬 KLA 색인만 본다(장비 접근 없음). 결과 모양은 장비 찾기와 같다."""
        data = self._load_cache()
        if not data["sources"]:
            raise ValueError("KLA 캐시가 없습니다. [OneDrive 에서 불러오기]로 캐시를 받거나, 장비가 연결된 PC 에서 [캐시 갱신]을 하세요")
        pick = set(machines) if machines is not None else None
        hits, seen = [], []
        dates = 0
        truncated = False
        for src in data["sources"]:
            base = src["machine"].split(" › ", 1)[0]
            if pick is not None and base not in pick and src["machine"] not in pick:
                continue
            if src["machine"] not in seen:
                seen.append(src["machine"])
            for day in sorted(src["dates"], reverse=True):
                if (start and day < start) or (end and day > end):
                    continue
                dates += 1
                for lot, names in sorted(src["dates"][day]["lots"].items()):
                    if not _match(lot, words):
                        continue
                    if len(hits) >= MAX_HITS:
                        truncated = True
                        break
                    lpath = os.path.join(src["path"], day, lot)
                    slots = []
                    for s in names[:MAX_SLOTS]:
                        no, at = slot_info(s)
                        slots.append(dict(name=s, slot=no, time=at, path=os.path.join(lpath, s)))
                    slots.sort(key=lambda x: (x["time"], int(x["slot"]) if x["slot"].isdigit() else 0))
                    hits.append(dict(machine=src["machine"], date=day, lot=lot, path=lpath, slots=slots,
                                     more=max(0, len(names) - MAX_SLOTS), backup=src["backup"]))
                if truncated:
                    break
        hits.sort(key=lambda h: (h["date"], h["machine"], h["lot"], not h["backup"]), reverse=True)
        return dict(query=query, start=start, end=end, hits=hits, truncated=truncated, max_hits=MAX_HITS,
                    machines=seen, dates=dates, failed=[], backup=any(s["backup"] for s in data["sources"]),
                    backup_folders=0, source="cache", cache_at=data["updated_at"])

    def cache_publish(self, params):
        """개발자: 로컬 KLA 색인 → 로컬 Temp 에서 zip → OneDrive `캐시공유/` 에 1번 복사 + `KLA캐시정보.json`(Camtek #39 와 같은 원칙).
        Camtek 캐시(`BatchReport_캐시_*.zip` · `캐시정보.json`)는 건드리지 않는다."""
        import shutil
        import zipfile
        from . import __version__
        if params:
            raise ValueError("요청을 확인하세요")
        batch = DesktopBatch(self.config_path)
        local = self._local()
        data = self._load_cache(local)
        if not data["sources"]:
            raise ValueError("게시할 KLA 캐시가 없습니다. 먼저 [캐시 갱신]을 하세요")
        folder = batch._share()
        stamp = datetime.now()
        name = f"KLA_캐시_{stamp:%Y%m%d_%H%M%S}.zip"
        summary = index_summary(data)
        manifest = dict(schema=1, kind="kla", exported_at=stamp.strftime("%Y-%m-%d %H:%M:%S"), app_version=__version__,
                        cache_schema=KLA_CACHE_SCHEMA, updated_at=data["updated_at"], machines=summary["machines"],
                        lots=summary["lots"], dates=summary["dates"], file=KLA_ZIP_MEMBER)
        work = local / "Temp" / f"KLA캐시게시_{stamp:%Y%m%d_%H%M%S_%f}"
        try:
            work.mkdir(parents=True)
            zpath = work / name
            desktop_progress.report("KLA 캐시 압축 중…")
            with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr(KLA_ZIP_MEMBER, json.dumps(data, ensure_ascii=False))
                zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=1))
            folder.mkdir(parents=True, exist_ok=True)
            target = folder / name
            if target.exists():
                raise ValueError("같은 이름의 KLA 캐시 zip 이 이미 있습니다. 잠시 뒤 다시 게시하세요.")
            try:
                size, sha = DesktopBatch._copy_hashed(zpath, target, "OneDrive 에 복사 중")
            except BaseException:
                try:
                    target.unlink()
                except OSError:
                    pass
                raise
        finally:
            shutil.rmtree(work, ignore_errors=True)
        item = dict(name=name, exported_at=manifest["exported_at"], app_version=__version__, cache_schema=KLA_CACHE_SCHEMA,
                    updated_at=data["updated_at"], size=size, sha256=sha, machines=summary["machines"], lots=summary["lots"])
        items = [item] + [i for i in self._share_index(folder) if i["name"] != name]
        keep, drop = items[:KLA_SHARE_KEEP], items[KLA_SHARE_KEEP:]
        listed = {i["name"] for i in keep}
        for path in folder.glob("KLA_캐시_*.zip"):
            if KLA_SHARE_NAME.fullmatch(path.name) and path.name not in listed and not path.is_symlink():
                try:
                    path.unlink()
                except OSError:
                    pass
        index = folder / KLA_SHARE_INDEX
        if index.is_symlink():
            raise ValueError("캐시 공유 폴더의 연결 경로는 사용할 수 없습니다")
        index.write_text(json.dumps(dict(schema=1, kind="kla", items=keep), ensure_ascii=False, indent=1), encoding="utf-8")
        return dict(item, path=str(target), folder=str(folder), kept=len(keep), removed=len(drop))

    @staticmethod
    def _share_index(folder):
        try:
            data = read_json(folder / KLA_SHARE_INDEX)
        except (OSError, ValueError):
            return []
        items = data.get("items") if data.get("schema") == 1 else None
        if not isinstance(items, list):
            return []
        return [i for i in items if isinstance(i, dict) and isinstance(i.get("name"), str) and KLA_SHARE_NAME.fullmatch(i["name"])
                and type(i.get("size")) is int and isinstance(i.get("sha256"), str) and len(i["sha256"]) == 64]

    def cache_share_list(self, params):
        """사용자: `캐시공유/KLA캐시정보.json` 하나만 읽어 게시된 KLA 캐시 목록을 돌려준다(누를 때만, 쓰기 없음)."""
        if params:
            raise ValueError("요청을 확인하세요")
        folder = DesktopBatch(self.config_path)._share()
        items = []
        for item in self._share_index(folder) if folder.is_dir() else []:
            path = folder / item["name"]
            try:
                present = path.is_file() and not path.is_symlink()
            except OSError:
                present = False
            items.append(dict(name=item["name"], exported_at=str(item.get("exported_at") or ""),
                              updated_at=str(item.get("updated_at") or ""), app_version=str(item.get("app_version") or ""),
                              size=item["size"], machines=[m for m in item.get("machines") or [] if isinstance(m, str)],
                              lots=item.get("lots") if type(item.get("lots")) is int else 0,
                              compatible=item.get("cache_schema") == KLA_CACHE_SCHEMA, present=present))
        items.sort(key=lambda i: i["name"], reverse=True)
        return dict(folder=str(folder), exists=folder.is_dir(), items=items)

    def cache_share_import(self, params):
        """사용자: 고른 KLA 캐시 zip → 로컬 Temp 복사 → 크기 · SHA-256 확인 → zip 안 색인을 로컬 색인에 합친다.
        같은 (장비, 폴더, 날짜)는 더 나중에 읽은 쪽을 남긴다. OneDrive 에는 쓰지 않고 zip 은 풀지 않는다."""
        import shutil
        import zipfile
        name = params.get("name") if isinstance(params, dict) and set(params) == {"name"} else None
        if not isinstance(name, str) or not KLA_SHARE_NAME.fullmatch(name):
            raise ValueError("불러올 KLA 캐시 zip 을 목록에서 고르세요")
        folder = DesktopBatch(self.config_path)._share()
        item = next((i for i in self._share_index(folder) if i["name"] == name), None)
        if item is None:
            raise ValueError("KLA캐시정보.json 에 없는 zip 입니다. 목록을 새로 고친 뒤 다시 고르세요.")
        if item.get("cache_schema") != KLA_CACHE_SCHEMA:
            raise ValueError("KLA 캐시 형식(버전)이 이 프로그램과 다릅니다 — 개발자에게 같은 버전 프로그램으로 다시 게시해 달라고 하세요.")
        source = folder / name
        if source.is_symlink() or not source.is_file():
            raise ValueError("OneDrive 에 그 zip 이 아직 없습니다. 동기화가 끝난 뒤 다시 누르세요.")
        local = self._local()
        work = local / "Temp" / f"KLA캐시불러오기_{datetime.now():%Y%m%d_%H%M%S_%f}"
        try:
            work.mkdir(parents=True)
            copy = work / name
            size, sha = DesktopBatch._copy_hashed(source, copy, "OneDrive 에서 받는 중")
            if size != item["size"] or sha != item["sha256"]:
                raise ValueError("받은 zip 이 게시된 내용과 다릅니다(OneDrive 동기화가 아직 끝나지 않았을 수 있습니다). 잠시 뒤 다시 누르세요.")
            try:
                with zipfile.ZipFile(copy) as zf:
                    info = zf.getinfo(KLA_ZIP_MEMBER)
                    if info.file_size > KLA_ZIP_MAX:
                        raise ValueError("KLA 캐시가 너무 큽니다")
                    incoming = clean_index(json.loads(zf.read(info).decode("utf-8")))
            except (KeyError, OSError, zipfile.BadZipFile, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("KLA 캐시 zip 이 아닙니다 — [OneDrive 에 게시]로 만든 zip 인지 확인하세요") from exc
        finally:
            shutil.rmtree(work, ignore_errors=True)
        data = self._load_cache(local)
        merged = merge_index(data, incoming)
        self._save_cache(merged, local)
        return dict(index_summary(merged), source=name, exported_at=str(item.get("exported_at") or ""),
                    app_version=str(item.get("app_version") or ""), imported=index_summary(incoming))

    # ---- 열기 허용 범위(desktop_open) ------------------------------------------
    def allows(self, path):
        """등록한 KLA 장비 폴더 · 백업 폴더 **안의 폴더**인지(글자로만 비교 — 끊긴 공유에서 멈추지 않게)."""
        def key(p):
            return os.path.normcase(os.path.normpath(os.path.abspath(str(p))))
        target = key(path)
        for base_path in (p for r in self.roots() for p in [r["path"], *r["backups"]]):
            if not Path(base_path).is_absolute():
                continue
            base = key(base_path)
            if target == base or target.startswith(base.rstrip(os.sep) + os.sep):
                return True
        return False
