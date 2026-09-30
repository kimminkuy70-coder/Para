"""Detailed start-up / request timing log for "why was it slow on this PC" questions.

Stdlib only and imported *first* by the engine entry, before the heavy modules,
so the import phase itself can be measured. Lines are buffered in memory until
the local Logs folder is known (`attach`), then appended to
`상세_진단_로그.txt` there (never the OneDrive save folder).

What is recorded (no file contents, no credentials):
* process creation → Python entry (PyInstaller bootloader + interpreter start),
* every module import that took >= IMPORT_MS (inclusive time, nesting depth),
* engine set-up steps (config read, local folder check, scheduler),
* every request: when the frame was read, queue wait, duration, background steps,
* the web UI's own timeline (page load, engine connect, request send/complete),
* PC facts that explain variance: uptime since boot, CPU count, free memory.

The file is rotated at MAX_BYTES (one previous copy kept).
"""
from __future__ import annotations

import builtins
import os
import sys
import threading
import time
from contextlib import contextmanager
from datetime import datetime

FILENAME = "상세_진단_로그.txt"
MAX_BYTES = 5 * 1024 * 1024
IMPORT_MS = 30.0
T0 = time.time()                 # wall clock when this module was imported
_P0 = time.perf_counter()

_lock = threading.RLock()
_buffer: list[str] = []
_path = ""
_import_stats = {"count": 0, "seconds": 0.0}
_original_import = None


def elapsed() -> float:
    """Seconds since the engine's Python code started."""
    return time.perf_counter() - _P0


def _line(text: str) -> str:
    now = time.time()
    stamp = datetime.fromtimestamp(now).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    return f"{stamp}\t+{elapsed():8.3f}s\t{threading.current_thread().name[:12]}\t{text}\n"


def event(text: str) -> None:
    line = _line(str(text)[:2000])
    with _lock:
        if not _path:
            if len(_buffer) < 5000:
                _buffer.append(line)
            return
        _write([line])


def _write(lines) -> None:
    try:
        if os.path.exists(_path) and os.path.getsize(_path) > MAX_BYTES:
            old = _path + ".1"
            if os.path.exists(old):
                os.remove(old)
            os.replace(_path, old)
        with open(_path, "a", encoding="utf-8") as fh:
            fh.writelines(lines)
    except OSError:
        pass                     # diagnostics must never break the engine


def attach(folder: str) -> str:
    """Start writing to `folder/상세_진단_로그.txt` and flush what was buffered."""
    global _path
    if not folder:
        return ""
    try:
        os.makedirs(folder, exist_ok=True)
    except OSError:
        return ""
    with _lock:
        first = not _path
        _path = os.path.join(folder, FILENAME)
        if first:
            _write([_line("로그 파일 연결 — 아래 줄은 그 전(메모리에 모아 둔) 기록부터 시작")] + _buffer)
            _buffer.clear()
    return _path


def path() -> str:
    return _path


@contextmanager
def timed(label: str, min_ms: float = 0.0):
    """Log how long a block took (and whether it failed)."""
    started = time.perf_counter()
    failed = ""
    try:
        yield
    except BaseException as exc:
        failed = f" — 실패 {type(exc).__name__}: {str(exc)[:200]}"
        raise
    finally:
        ms = (time.perf_counter() - started) * 1000
        if ms >= min_ms or failed:
            event(f"{label} {ms:.0f}ms{failed}")


# ---------------------------------------------------------------- import timing
_depth = threading.local()


def _timed_import(name, globals=None, locals=None, fromlist=(), level=0):
    if level or name in sys.modules:
        return _original_import(name, globals, locals, fromlist, level)
    depth = getattr(_depth, "n", 0)
    _depth.n = depth + 1
    started = time.perf_counter()
    try:
        return _original_import(name, globals, locals, fromlist, level)
    finally:
        _depth.n = depth
        ms = (time.perf_counter() - started) * 1000
        if depth == 0:
            _import_stats["count"] += 1
            _import_stats["seconds"] += ms / 1000
        if ms >= IMPORT_MS:
            event(f"import {'  ' * depth}{name} {ms:.0f}ms")


def start_import_timer() -> None:
    global _original_import
    if _original_import is None:
        _original_import = builtins.__import__
        builtins.__import__ = _timed_import


def stop_import_timer() -> None:
    global _original_import
    if _original_import is not None:
        builtins.__import__ = _original_import
        _original_import = None
        event(f"모듈 로딩 합계 — 최상위 import {_import_stats['count']}개 · {_import_stats['seconds']:.2f}s")


# ---------------------------------------------------------------- PC facts
def _process_age() -> float | None:
    """Seconds from this process's creation to T0 (bootloader + interpreter start)."""
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.windll.kernel32
        ft = [wintypes.FILETIME() for _ in range(4)]
        if not k32.GetProcessTimes(k32.GetCurrentProcess(), *[ctypes.byref(f) for f in ft]):
            return None
        created = (ft[0].dwHighDateTime << 32 | ft[0].dwLowDateTime) / 1e7 - 11644473600
        return T0 - created
    except Exception:  # noqa: BLE001
        return None


def system_facts() -> str:
    parts = [f"Python {sys.version.split()[0]}", f"frozen={bool(getattr(sys, 'frozen', False))}",
             f"CPU {os.cpu_count()}", f"exe={sys.executable}"]
    if os.name == "nt":
        try:
            import ctypes
            k32 = ctypes.windll.kernel32
            k32.GetTickCount64.restype = ctypes.c_ulonglong
            parts.append(f"부팅 후 {k32.GetTickCount64() / 60000:.0f}분")

            class MEM(ctypes.Structure):
                _fields_ = [("len", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
                    (n, ctypes.c_ulonglong) for n in ("tot", "avail", "ptot", "pavail", "vtot", "vavail", "ext")]
            m = MEM()
            m.len = ctypes.sizeof(MEM)
            if k32.GlobalMemoryStatusEx(ctypes.byref(m)):
                parts.append(f"메모리 사용 {m.load}% (여유 {m.avail / 2**30:.1f}GB / {m.tot / 2**30:.1f}GB)")
        except Exception:  # noqa: BLE001
            pass
    return " · ".join(parts)


def engine_started() -> None:
    age = _process_age()
    event("==================== 엔진 시작 ====================")
    event(("프로세스 생성 → Python 시작 " + (f"{age:.1f}s" if age is not None else "(측정 불가)"))
          + " (실행파일 풀기·백신 검사·인터프리터 준비)")
    event(system_facts())


def client_events(params) -> dict:
    """The web UI's own timeline (its clock), logged next to the engine's lines."""
    events = params.get("events") if isinstance(params, dict) else None
    if set(params or {}) != {"events"} or not isinstance(events, list) or len(events) > 200:
        raise ValueError("진단 기록을 확인하세요")
    for item in events:
        if not isinstance(item, dict) or not isinstance(item.get("t"), (int, float)) \
                or not isinstance(item.get("text"), str):
            continue
        stamp = datetime.fromtimestamp(item["t"] / 1000).strftime("%H:%M:%S.%f")[:-3]
        event(f"[화면 {stamp}] {item['text'][:300]}")
    return dict(logged=True)


def bundle(folder: str) -> str:
    """Zip every log in the local Logs folder so the user can hand it over as one file."""
    import zipfile
    if not folder or not os.path.isdir(folder):
        raise ValueError("로그 폴더를 찾을 수 없습니다")
    event("진단 로그 묶기 — " + system_facts())
    target = os.path.join(folder, f"진단로그_{datetime.now():%Y%m%d_%H%M%S}.zip")
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in sorted(os.listdir(folder)):
            full = os.path.join(folder, name)
            if os.path.isfile(full) and name.lower().endswith((".txt", ".txt.1", ".log")):
                zf.write(full, name)
    # Keep only the latest 3 bundles.
    bundles = sorted(n for n in os.listdir(folder) if n.startswith("진단로그_") and n.endswith(".zip"))
    for old in bundles[:-3]:
        try:
            os.remove(os.path.join(folder, old))
        except OSError:
            pass
    return target
