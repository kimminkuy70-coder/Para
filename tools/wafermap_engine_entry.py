"""Wafer Map 전용판 엔진의 고정 PyInstaller 진입점(명령 · 파일 경로 해석기 아님).

본 앱 진입점(`desktop_engine_entry.py`)과 같은 순서(진단 시작 → 중복 실행 확인 → 모듈 로딩 중
요청 대기열)로 돌지만, 불러오는 프로토콜은 `param_manager.wafermap_ipc`(Wafer Map 요청만)이고
중복 실행 뮤텍스 이름도 따로라 본 앱과 동시에 켜도 서로 막지 않는다.
"""
import sys
import time

STARTED = time.perf_counter()          # before the heavy imports: start-up timing
from param_manager import desktop_diag  # noqa: E402 - stdlib-only; must time the imports below
desktop_diag.engine_started()
desktop_diag.start_import_timer()

MAX_FRAME = 4 * 1024 * 1024            # same limit as wafermap_ipc.MAX_FRAME (checked by a test)
MUTEX_NAME = r"Local\CamtekAOI_WaferMap_SingleInstance"   # not the main app's mutex


def _load_ipc():
    from param_manager import wafermap_ipc
    return wafermap_ipc


def main():
    from param_manager.singleinst import SingleInstance
    from param_manager.desktop_boot import FrameQueue, load_with_progress
    instance = SingleInstance(MUTEX_NAME)
    before = time.perf_counter()
    if not instance.acquire(wait_sec=15):
        sys.stdout.buffer.write(b'{"version": 1, "id": null, "event": "error", "code": "already_running"}\n')
        sys.stdout.buffer.flush()
        return 1
    waited = time.perf_counter() - before
    desktop_diag.event(f"중복 실행 확인(이전 엔진 종료 대기) {waited:.1f}s")
    frames = FrameQueue(sys.stdin.buffer, MAX_FRAME)
    ipc = load_with_progress(_load_ipc, frames, sys.stdout.buffer, desktop_diag)
    imported = time.perf_counter()
    desktop_diag.stop_import_timer()
    try:
        ipc.serve(frames, sys.stdout.buffer,
                  startup=f"Wafer Map 엔진 시작 — 모듈 로딩 {imported - STARTED - waited:.1f}s · 이전 엔진 종료 대기 {waited:.1f}s")
    finally:
        instance.release()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
