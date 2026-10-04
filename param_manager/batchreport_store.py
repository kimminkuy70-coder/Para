"""Read-only equipment collection, atomic local raw-report cache.

One atomic JSON transaction per source contains metadata AND full reports. This
avoids divergent batch/wafer JSONL files after power loss. Failed files are not
marked seen. Selection is applied again on every run, including cached records.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import date
from pathlib import Path

from . import localdirs, wph
from .atomicfile import write_json

SCHEMA = 1


class Cancelled(Exception):
    """Cooperative interruption at a safe read/transaction boundary."""


def checkpoint(cancel):
    if cancel is not None and cancel():
        raise Cancelled()


def local_root(root, sources=()):
    raw = str(root)
    resolved = Path(root).resolve()
    if raw.startswith(("\\\\", "//")) or str(resolved).startswith(("\\\\", "//")) or localdirs.is_under_onedrive(resolved):
        raise ValueError("배치 분석 결과는 OneDrive/네트워크 공유가 아닌 로컬 폴더에 저장해야 합니다")
    if os.name == "nt":
        import ctypes
        if ctypes.windll.kernel32.GetDriveTypeW(str(resolved.anchor)) == 4:
            raise ValueError("네트워크 드라이브에는 분석 결과를 저장할 수 없습니다")
    # Lexical check only. Path.resolve() on an equipment share (a mapped P: drive or a
    # UNC path) opens it, and a disconnected share blocks for the SMB timeout (tens of
    # seconds). This runs on nearly every request, so with a team config listing many
    # machines the whole engine looked frozen ("불러오는 중" forever).
    def key(p):
        return os.path.normcase(os.path.normpath(os.path.abspath(str(p))))
    mine = key(resolved)
    for source in sources:
        raw_source = str(source or "")
        if not raw_source or raw_source.startswith(("\\\\", "//")):
            continue                           # a network share can never contain the local root
        origin = key(raw_source)
        if mine == origin or mine.startswith(origin.rstrip(os.sep) + os.sep) or origin.startswith(mine.rstrip(os.sep) + os.sep):
            raise ValueError("분석 저장 위치와 장비 원본 폴더는 분리해야 합니다")
    return resolved


def dates(target):
    start = date.fromisoformat(target["start"]) if target.get("start") else None
    end = date.fromisoformat(target["end"]) if target.get("end") else None
    if start and end and start > end:
        raise ValueError("시작일이 종료일보다 늦습니다")
    return start, end


def collect(root, targets, progress=None, host_gap=2.0, cancel=None, reuse=True):
    """reuse=False: 캐시 서명(수정시각·크기)이 같아도 고른 범위를 전부 다시 연다
    (화면 '이미 읽은 Batch Report는 다시 읽지 않기'를 끈 경우)."""
    base = local_root(root, [t["folder"] for t in targets]) / "배치분석" / "누적"
    base.mkdir(parents=True, exist_ok=True)
    records, errors, notices = [], [], []
    parsed, reused = 0, 0
    by_machine = {}
    dedup = set()
    filenames = {}
    for index, target in enumerate(targets):
        checkpoint(cancel)
        if index and host_gap:
            time.sleep(host_gap)  # sequential hosts; same security pacing as watcher
        machine, folder = target["machine"], Path(target["folder"])
        stat = by_machine.setdefault(machine, {"parsed": 0, "reused": 0, "records": 0, "offline": False})
        source_id = hashlib.sha256((machine + "\0" + os.path.normcase(str(folder.resolve()))).encode()).hexdigest()
        cachefile = base / (source_id + ".json")
        if cachefile.is_symlink() or cachefile.resolve().parent != base.resolve():
            raise ValueError("분석 캐시 연결 경로를 사용할 수 없습니다")
        state = {"schema": SCHEMA, "entries": {}}
        if cachefile.exists():
            # Corrupt/unknown cache is never silently overwritten.
            state = json.loads(cachefile.read_text(encoding="utf-8"))
            if state.get("schema") != SCHEMA or not isinstance(state.get("entries"), dict):
                raise ValueError("분석 캐시 형식 확인 필요: " + str(cachefile))
        entries = state["entries"]
        start, end = dates(target)
        requested = target.get("names")
        if requested is not None:
            for name in requested:
                if not isinstance(name, str) or any(c in name for c in "/\\:") or not wph.is_report_file(name):
                    raise ValueError("선택 Report는 파일 이름이어야 합니다")
            requested = set(requested)

        def matches(name):
            return (requested is None or name in requested) and wph._matches(name, target.get("query", ""), start, end)

        invalid, current = set(), []
        online = folder.is_dir()
        if online:
            # Include all dates so late-arriving old files are not lost to a watermark.
            current = [n for n in wph.list_reports(folder, target.get("query", ""), start, end) if matches(n)]
        else:
            errors.append({"machine": machine, "source_file": str(folder), "error": "원본 폴더 접근 불가 — 저장된 자료만 표시"})
            stat["offline"] = True
        for n, name in enumerate(current, 1):
            checkpoint(cancel)
            if progress:
                progress(n, len(current), f"{machine}: {name}")
            path = folder / name
            try:
                if path.resolve().parent != folder.resolve():
                    raise ValueError("Report 연결 경로가 지정 폴더 밖을 가리킵니다")
                before = path.stat()
                signature = [before.st_mtime_ns, before.st_size]
                saved = entries.get(name)
                if reuse and saved and saved.get("signature") == signature:
                    reused += 1
                    stat["reused"] += 1
                    continue
                # Reuse the established parser exactly once per changed source.
                report = wph.parse_report(path)
                after = path.stat()
                if signature != [after.st_mtime_ns, after.st_size]:
                    raise ValueError("읽는 중 변경됨 — 다음 조사에서 재시도")
                meta = {wph.normalize_key(k): v for k, v in report.get("metadata", [])}
                if not meta.get("batchend") or wph.parse_batch_datetime(meta["batchend"]) is None or not report.get("wafers"):
                    raise ValueError("완료 Batch End / Wafer 표 누락 — 다음 조사에서 재시도")
                # Ignore filename for identical backup-content deduplication.
                content = {k: v for k, v in report.items() if k != "file_name"}
                digest = hashlib.sha256(json.dumps(content, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
                entries[name] = {"signature": signature, "digest": digest, "report": report}
                parsed += 1
                stat["parsed"] += 1
            except Exception as exc:
                invalid.add(name)
                errors.append({"machine": machine, "source_file": name, "error": str(exc)})
        state.update(machine=machine, folder=str(folder))
        checkpoint(cancel)
        # Local writes only, old snapshot survives a failed replacement.
        write_json(cachefile, state)
        added = _emit(records, notices, dedup, filenames, source_id, machine, folder, entries,
                      lambda name: matches(name) and name not in invalid, set(current))
        stat["records"] += added
    return {"records": records, "errors": errors, "notices": notices,
            "parsed": parsed, "reused": reused, "by_machine": by_machine,
            "cached_only": sum(r["cached_only"] for r in records)}


def _emit(records, notices, dedup, filenames, source_id, machine, folder, entries, keep, current):
    added = 0
    for name, entry in entries.items():
        if not keep(name):
            continue
        key = (machine, entry["digest"])
        if key in dedup:
            notices.append(f"{machine} / {name}: 동일 내용 백업 중복 제외")
            continue
        dedup.add(key)
        name_key = (machine, name)
        if name_key in filenames and filenames[name_key] != entry['digest']:
            notices.append(f"{machine} / {name}: 같은 이름의 다른 내용 보존 — Batches 원본 폴더 열 참조")
        filenames[name_key] = entry['digest']
        records.append({"id": source_id + ":" + name, "machine": machine,
                        "source_folder": str(folder), "report": entry["report"], "cached_only": name not in current})
        added += 1
    return added


def load_cached(root, targets):
    """지난 조사 범위를 **로컬 캐시에서만** 다시 읽는다(장비 폴더 접근 없음 — 화면을 열 때 지난 결과 표시용).

    캐시 파일 이름은 원본 폴더 경로로 만든 해시라 그 경로를 다시 풀면(resolve) 장비 공유에 접속하게
    된다. 그래서 캐시 파일 안에 적어 둔 (호기, 폴더) 문자열로 짝을 찾는다."""
    base = local_root(root, [t["folder"] for t in targets]) / "배치분석" / "누적"
    records, notices, dedup, filenames, by_machine = [], [], set(), {}, {}
    if not base.is_dir():
        return {"records": records, "errors": [], "notices": notices, "parsed": 0, "reused": 0,
                "by_machine": by_machine, "cached_only": 0}
    states = {}
    for cachefile in sorted(base.glob("*.json")):
        if cachefile.is_symlink():
            continue
        try:
            state = json.loads(cachefile.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if state.get("schema") == SCHEMA and isinstance(state.get("entries"), dict):
            states[(state.get("machine"), os.path.normcase(str(state.get("folder", ""))))] = (cachefile.stem, state)
    for target in targets:
        machine = target["machine"]
        stat = by_machine.setdefault(machine, {"parsed": 0, "reused": 0, "records": 0, "offline": False})
        found = states.get((machine, os.path.normcase(str(Path(target["folder"])))))
        if not found:
            continue
        source_id, state = found
        start, end = dates(target)
        requested = set(target["names"]) if target.get("names") is not None else None

        def keep(name, target=target, start=start, end=end, requested=requested):
            return (requested is None or name in requested) and wph._matches(name, target.get("query", ""), start, end)
        stat["records"] += _emit(records, notices, dedup, filenames, source_id, machine, target["folder"],
                                 state["entries"], keep, set())
    return {"records": records, "errors": [], "notices": notices, "parsed": 0, "reused": len(records),
            "by_machine": by_machine, "cached_only": len(records)}
