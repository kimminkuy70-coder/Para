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


def local_root(root, sources=()):
    raw = str(root)
    resolved = Path(root).resolve()
    if raw.startswith(("\\\\", "//")) or str(resolved).startswith(("\\\\", "//")) or localdirs.is_under_onedrive(resolved):
        raise ValueError("배치 분석 결과는 OneDrive/네트워크 공유가 아닌 로컬 폴더에 저장해야 합니다")
    if os.name == "nt":
        import ctypes
        if ctypes.windll.kernel32.GetDriveTypeW(str(resolved.anchor)) == 4:
            raise ValueError("네트워크 드라이브에는 분석 결과를 저장할 수 없습니다")
    for source in sources:
        origin = Path(source).resolve()
        if resolved == origin or origin in resolved.parents or resolved in origin.parents:
            raise ValueError("분석 저장 위치와 장비 원본 폴더는 분리해야 합니다")
    return resolved


def dates(target):
    start = date.fromisoformat(target["start"]) if target.get("start") else None
    end = date.fromisoformat(target["end"]) if target.get("end") else None
    if start and end and start > end:
        raise ValueError("시작일이 종료일보다 늦습니다")
    return start, end


def collect(root, targets, progress=None, host_gap=2.0):
    base = local_root(root, [t["folder"] for t in targets]) / "배치분석" / "누적"
    base.mkdir(parents=True, exist_ok=True)
    records, errors, notices = [], [], []
    parsed, reused = 0, 0
    dedup = set()
    filenames = {}
    for index, target in enumerate(targets):
        if index and host_gap:
            time.sleep(host_gap)  # sequential hosts; same security pacing as watcher
        machine, folder = target["machine"], Path(target["folder"])
        source_id = hashlib.sha256((machine + "\0" + os.path.normcase(str(folder.resolve()))).encode()).hexdigest()
        cachefile = base / (source_id + ".json")
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
        for n, name in enumerate(current, 1):
            if progress:
                progress(n, len(current), f"{machine}: {name}")
            path = folder / name
            try:
                before = path.stat()
                signature = [before.st_mtime_ns, before.st_size]
                saved = entries.get(name)
                if saved and saved.get("signature") == signature:
                    reused += 1
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
            except Exception as exc:
                invalid.add(name)
                errors.append({"machine": machine, "source_file": name, "error": str(exc)})
        state.update(machine=machine, folder=str(folder))
        # Local writes only, old snapshot survives a failed replacement.
        write_json(cachefile, state)
        for name, entry in entries.items():
            if not matches(name) or name in invalid:
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
    return {"records": records, "errors": errors, "notices": notices,
            "parsed": parsed, "reused": reused,
            "cached_only": sum(r["cached_only"] for r in records)}
