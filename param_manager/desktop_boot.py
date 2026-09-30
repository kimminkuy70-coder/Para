"""Engine start-up: load the heavy modules in the background and keep the UI informed.

The web UI sends its first requests (settings read, …) the moment the engine
process exists, but the engine can only answer after `desktop_ipc` and everything
it imports (openpyxl, …) is loaded. On PCs where a security scanner slows file
access that took minutes and the screen showed only "기존 설정 읽기 N초".

Here the import runs on a worker thread while this module
* reads request frames from stdin into a queue (nothing is lost or reordered;
  `serve` later reads them from the queue exactly as it would from stdin), and
* every PROGRESS_SEC sends a `progress` event to each request still waiting, so
  the progress panel shows "엔진 준비 중 — 모듈 N개 불러옴 · 경과 T초".

Stdlib only (json/queue/threading), imported before the heavy modules.
"""
from __future__ import annotations

import json
import queue
import re
import sys
import threading
import time

PROGRESS_SEC = 2.0
_ID = re.compile(rb'"id"\s*:\s*(\d{1,16})')


class FrameQueue:
    """stdin frames read by a thread; `readline()` mimics the stream `serve` expects."""

    def __init__(self, source, max_frame):
        self._q: queue.Queue = queue.Queue()
        self._source, self._max = source, max_frame
        self.waiting: list[int] = []          # request ids seen before the engine was ready
        self.ready = False
        self._lock = threading.Lock()
        threading.Thread(target=self._read, name="stdin", daemon=True).start()

    def _read(self):
        while True:
            try:
                frame = self._source.readline(self._max + 1)
            except (OSError, ValueError):
                frame = b""
            if frame and not self.ready:
                found = _ID.search(frame[:200])
                if found:
                    with self._lock:
                        self.waiting.append(int(found.group(1)))
            self._q.put(frame)
            if not frame:
                return                         # EOF: the UI closed the pipe

    def pending(self) -> list[int]:
        with self._lock:
            return list(self.waiting)

    def readline(self, _limit=-1):
        return self._q.get()


def _emit(output, rid, message):
    payload = json.dumps(dict(version=1, id=rid, event="progress", message=message), ensure_ascii=False)
    output.write((payload + "\n").encode("utf-8"))
    output.flush()


def load_with_progress(loader, frames: FrameQueue, output, diag=None):
    """Run `loader()` on a thread; while it runs, tell waiting requests how far it got.
    Returns loader's result (re-raises its exception)."""
    box: dict = {}

    def work():
        try:
            box["value"] = loader()
        except BaseException as exc:  # noqa: BLE001 - re-raised on the main thread
            box["error"] = exc

    started = time.monotonic()
    worker = threading.Thread(target=work, name="import", daemon=True)
    worker.start()
    told = False
    while worker.is_alive():
        worker.join(PROGRESS_SEC)
        if not worker.is_alive():
            break
        waiting = frames.pending()
        if not waiting:
            continue
        sec = time.monotonic() - started
        message = (f"엔진 준비 중 — 프로그램 모듈 {len(sys.modules)}개 불러옴 · {sec:.0f}초 경과"
                   + (" (보안 검사로 느려질 수 있습니다)" if sec >= 20 else ""))
        for rid in waiting:
            try:
                _emit(output, rid, message)
            except (OSError, ValueError):
                pass
        if diag is not None and not told and sec >= 20:
            told = True
            diag.event(f"모듈 로딩이 {sec:.0f}초째 — 대기 중인 화면 요청 {len(waiting)}건에 진행 상황을 보내는 중")
    frames.ready = True
    if "error" in box:
        raise box["error"]
    return box.get("value")
