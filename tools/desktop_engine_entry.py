"""Fixed PyInstaller entrypoint, not a command or file-path interpreter."""
import sys
from param_manager.desktop_ipc import serve, encoded
from param_manager.singleinst import SingleInstance

def main():
    instance = SingleInstance()
    if not instance.acquire():
        sys.stdout.buffer.write(encoded(dict(version=1,id=None,event='error',code='already_running')))
        sys.stdout.buffer.flush()
        return 1
    try:
        serve(sys.stdin.buffer, sys.stdout.buffer)
    finally:
        instance.release()
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
