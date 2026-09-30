"""Fixed PyInstaller entrypoint, not a command or file-path interpreter."""
import sys
import time

STARTED = time.perf_counter()          # before the heavy imports: start-up timing
from param_manager import desktop_diag  # noqa: E402 - stdlib-only; must time the imports below
desktop_diag.engine_started()
desktop_diag.start_import_timer()

MAX_FRAME = 4 * 1024 * 1024            # same limit as desktop_ipc.MAX_FRAME (checked by a test)


def _load_ipc():
    from param_manager import desktop_ipc
    return desktop_ipc


def main():
    from param_manager.singleinst import SingleInstance
    from param_manager.desktop_boot import FrameQueue, load_with_progress
    instance = SingleInstance()
    # A relaunch right after closing: the previous engine may still be finishing its
    # last save. Wait for it briefly instead of refusing to start at once.
    before = time.perf_counter()
    if not instance.acquire(wait_sec=15):
        sys.stdout.buffer.write(b'{"version": 1, "id": null, "event": "error", "code": "already_running"}\n')
        sys.stdout.buffer.flush()
        return 1
    waited = time.perf_counter() - before
    desktop_diag.event(f"중복 실행 확인(이전 엔진 종료 대기) {waited:.1f}s")
    # Requests arriving while the heavy modules load are queued and told how far
    # loading got, instead of sitting silently in the pipe.
    frames = FrameQueue(sys.stdin.buffer, MAX_FRAME)
    ipc = load_with_progress(_load_ipc, frames, sys.stdout.buffer, desktop_diag)
    imported = time.perf_counter()
    desktop_diag.stop_import_timer()
    try:
        ipc.serve(frames, sys.stdout.buffer,
                  startup=f"엔진 시작 — 모듈 로딩 {imported - STARTED - waited:.1f}s · 이전 엔진 종료 대기 {waited:.1f}s")
    finally:
        instance.release()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
