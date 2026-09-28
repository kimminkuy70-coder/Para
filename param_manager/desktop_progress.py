"""Step messages from slow engine work to the web UI's progress panel.

A background job sets a per-thread reporter; domain code calls `report("...")`
at its slow steps (reading a big workbook on OneDrive, one machine of a
collection, ...). Outside a job `report` does nothing, so the adapters stay
usable headless and in tests.

Slow requests are also written to a local timing log (never the save folder), so
when a PC is slow the user can hand over which step took how long.
"""
from __future__ import annotations

import os
import threading
from datetime import datetime

_local = threading.local()
SLOW_SEC = 3.0


def set_reporter(fn) -> None:
    _local.fn = fn


def report(message: str) -> None:
    fn = getattr(_local, "fn", None)
    if fn is not None:
        try:
            fn(str(message)[:300])
        except Exception:  # noqa: BLE001 - progress must never break the work
            pass


def log_slow(method: str, seconds: float, steps=()) -> None:
    """Append one line for a request that took SLOW_SEC or longer (local Logs/).
    Method names and step texts only — no file contents."""
    if seconds < SLOW_SEC:
        return
    try:
        from . import localdirs
        root = localdirs.active_root()
        folder = localdirs.logs_dir(root) if root else ""
        if not folder:
            return
        os.makedirs(folder, exist_ok=True)
        trail = " > ".join(f"{t:.1f}s {s}" for t, s in steps)[-600:]
        with open(os.path.join(folder, "작업시간_로그.txt"), "a", encoding="utf-8") as fh:
            fh.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}\t{method}\t{seconds:.1f}s\t{trail}\n")
    except Exception:  # noqa: BLE001 - logging is best effort
        pass


def log_event(text: str) -> None:
    """One line per engine start/stop in the same local timing log (start-up speed)."""
    try:
        from . import localdirs
        root = localdirs.active_root()
        folder = localdirs.logs_dir(root) if root else ""
        if not folder:
            return
        with open(os.path.join(folder, "작업시간_로그.txt"), "a", encoding="utf-8") as fh:
            fh.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}\t{text}\n")
    except Exception:  # noqa: BLE001 - logging is best effort
        pass
