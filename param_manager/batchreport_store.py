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


# 같은 앱 실행 중 캐시 JSON 을 다시 읽어 해석하지 않도록 메모리에 둔다(이슈 #12).
# 키 = 캐시 파일 경로, 값 = (mtime_ns, size, state). 디스크 파일이 바뀌면(서명 불일치) 다시 읽는다.
_MEMO = {}


def _load_state(cachefile):
    try:
        st = cachefile.stat()
    except FileNotFoundError:
        return {"schema": SCHEMA, "entries": {}}
    memo = _MEMO.get(str(cachefile))
    if memo and memo[0] == st.st_mtime_ns and memo[1] == st.st_size:
        state = memo[2]
    else:
        # Corrupt/unknown cache is never silently overwritten.
        state = json.loads(cachefile.read_text(encoding="utf-8"))
        if state.get("schema") != SCHEMA or not isinstance(state.get("entries"), dict):
            raise ValueError("분석 캐시 형식 확인 필요: " + str(cachefile))
        _MEMO[str(cachefile)] = (st.st_mtime_ns, st.st_size, state)
    # 얕은 복사: 이번 조사에서 더하는 항목이 쓰기 실패 시 메모리 사본에 남지 않게.
    return dict(state, entries=dict(state["entries"]))


def _save_state(cachefile, state):
    write_json(cachefile, state)
    st = cachefile.stat()
    _MEMO[str(cachefile)] = (st.st_mtime_ns, st.st_size, state)


def _scan(folder, matches):
    """폴더 목록 1번으로 대상 파일과 그 (수정시각, 크기)를 얻는다(이슈 #12 — 파일마다 장비에 다시 묻지 않기).

    Windows 의 os.scandir 는 목록에 수정시각 · 크기가 같이 와서 추가 네트워크 왕복이 없다.
    연결(심볼릭 링크) 파일만 따로 표시해 두고, 그 파일은 예전처럼 경로를 풀어 폴더 밖인지 확인한다."""
    out = {}
    with os.scandir(folder) as items:
        for entry in items:
            name = entry.name
            if not wph.is_report_file(name) or not matches(name):
                continue
            try:
                link = entry.is_symlink()
                if not entry.is_file():
                    continue
                st = entry.stat(follow_symlinks=False)
                out[name] = (None if link else [st.st_mtime_ns, st.st_size])
            except OSError:
                out[name] = None                     # 아래에서 예전 방식으로 확인 · 오류 기록
    return dict(sorted(out.items(), key=lambda kv: kv[0].lower()))


def collect(root, targets, progress=None, host_gap=2.0, cancel=None, reuse=True):
    """reuse=False: 캐시 서명(수정시각·크기)이 같아도 고른 범위를 전부 다시 연다
    (화면 '이미 읽은 Batch Report는 다시 읽지 않기'를 끈 경우).

    이미 조사한 것은 그대로 두고 새 Batch Report만 빠르게 찾는다(이슈 #12, 병렬 읽기 없음 — 한 폴더씩 순서대로):
    폴더 목록 1번으로 서명이 같은 파일은 장비에 다시 묻지 않고 캐시를 쓰며, 새로 읽은 것이 없으면 캐시 파일도
    다시 쓰지 않는다. 호기 사이 간격(host_gap)은 앞 호기에서 Report 파일을 실제로 연 경우에만 두고,
    같은 호기의 추가 폴더 사이에는 두지 않는다."""
    base = local_root(root, [t["folder"] for t in targets]) / "배치분석" / "누적"
    base.mkdir(parents=True, exist_ok=True)
    base_real = base.resolve()
    records, errors, notices = [], [], []
    parsed, reused = 0, 0
    by_machine = {}
    dedup = set()
    filenames = {}
    prev_machine, prev_opened = None, False
    for index, target in enumerate(targets):
        checkpoint(cancel)
        machine, folder = target["machine"], Path(target["folder"])
        if machine != prev_machine:
            if index and host_gap and prev_opened:
                time.sleep(host_gap)  # sequential hosts; same security pacing as watcher
            prev_machine, prev_opened = machine, False
        stat = by_machine.setdefault(machine, {"parsed": 0, "reused": 0, "records": 0, "offline": False})
        folder_real = folder.resolve()
        source_id = hashlib.sha256((machine + "\0" + os.path.normcase(str(folder_real))).encode()).hexdigest()
        cachefile = base / (source_id + ".json")
        if cachefile.is_symlink() or cachefile.resolve().parent != base_real:
            raise ValueError("분석 캐시 연결 경로를 사용할 수 없습니다")
        state = _load_state(cachefile)
        entries = state["entries"]
        stat_parsed_before = stat["parsed"]
        start, end = dates(target)
        requested = target.get("names")
        if requested is not None:
            for name in requested:
                if not isinstance(name, str) or any(c in name for c in "/\\:") or not wph.is_report_file(name):
                    raise ValueError("선택 Report는 파일 이름이어야 합니다")
            requested = set(requested)

        def matches(name):
            return (requested is None or name in requested) and wph._matches(name, target.get("query", ""), start, end)

        invalid, listed = set(), {}
        online = folder.is_dir()
        if online:
            # Include all dates so late-arriving old files are not lost to a watermark.
            try:
                listed = _scan(folder, matches)
            except OSError as exc:
                online = False
                errors.append({"machine": machine, "source_file": str(folder), "error": f"목록 읽기 실패 — 저장된 자료만 표시 ({exc})"})
                stat["offline"] = True
        else:
            errors.append({"machine": machine, "source_file": str(folder), "error": "원본 폴더 접근 불가 — 저장된 자료만 표시"})
            stat["offline"] = True
        current = list(listed)
        # 캐시와 서명이 같은 파일은 목록 정보만으로 끝(장비에 다시 묻지 않음). 진행 표시는 새로 열 파일만.
        todo = []
        for name, quick in listed.items():
            saved = entries.get(name)
            if reuse and quick is not None and saved and saved.get("signature") == quick:
                reused += 1
                stat["reused"] += 1
            else:
                todo.append(name)
        if progress and current and not todo:
            progress(len(current), len(current), f"{machine}: 새 Batch Report 없음 (캐시 {len(current)}개)")
        for n, name in enumerate(todo, 1):
            checkpoint(cancel)
            if progress:
                progress(n, len(todo), f"{machine}: {name}")
            path = folder / name
            try:
                if path.resolve().parent != folder_real:
                    raise ValueError("Report 연결 경로가 지정 폴더 밖을 가리킵니다")
                before = path.stat()
                signature = [before.st_mtime_ns, before.st_size]
                saved = entries.get(name)
                if reuse and saved and saved.get("signature") == signature:
                    reused += 1
                    stat["reused"] += 1
                    continue
                prev_opened = True
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
        checkpoint(cancel)
        if stat_parsed_before != stat["parsed"] or state.get("machine") != machine or state.get("folder") != str(folder) \
                or not cachefile.exists():
            state.update(machine=machine, folder=str(folder))
            # Local writes only, old snapshot survives a failed replacement.
            _save_state(cachefile, state)
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
                        "source_folder": str(folder), "report": entry["report"], "cached_only": name not in current,
                        "digest": entry["digest"]})
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
