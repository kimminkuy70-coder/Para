"""Fixed PyInstaller entrypoint, not a command or file-path interpreter."""
import sys
import time

STARTED = time.perf_counter()          # before the heavy imports: start-up timing


def main():
    from param_manager.singleinst import SingleInstance
    from param_manager.desktop_ipc import serve, encoded
    imported = time.perf_counter()
    instance = SingleInstance()
    # A relaunch right after closing: the previous engine may still be finishing its
    # last save. Wait for it briefly instead of refusing to start at once.
    if not instance.acquire(wait_sec=15):
        sys.stdout.buffer.write(encoded(dict(version=1,id=None,event='error',code='already_running')))
        sys.stdout.buffer.flush()
        return 1
    waited = time.perf_counter() - imported
    try:
        serve(sys.stdin.buffer, sys.stdout.buffer,
              startup=f"엔진 시작 — 모듈 로딩 {imported - STARTED:.1f}s · 이전 엔진 종료 대기 {waited:.1f}s")
    finally:
        instance.release()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
