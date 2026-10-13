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
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from . import atomicfile, desktop_progress
from .desktop_batch import read_json

MAX_PATH = 4096
MAX_NAME = 64
MAX_ROOTS = 50
MAX_BACKUPS = 20         # 장비 하나의 백업 폴더 수 한도
MAX_QUERY = 200
MAX_HITS = 2000          # Lot 폴더 수 한도(넘으면 앞의 것만 + 안내)
MAX_SLOTS = 200          # Lot 하나의 슬롯 폴더 표시 한도
DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
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
        return dict(roots=self.roots(cfg), backup=self.backup_on(cfg))

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
        if set(params) - {"query", "machines", "start", "end"}:
            raise ValueError("찾기 요청을 확인하세요")
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
        cfg = self._read()
        roots = self.roots(cfg)
        backup = self.backup_on(cfg)
        if machines is not None:
            if not isinstance(machines, list) or not all(isinstance(m, str) for m in machines):
                raise ValueError("장비 선택을 확인하세요")
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
                    backup_folders=sum(len(r["backups"]) for r in roots) if backup else 0)

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
