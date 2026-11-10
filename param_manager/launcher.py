"""v13 program start (called by the root `Camtek_AOI_manager.pyw`, run by python.org pythonw.exe).

1. one copy only: if Para already runs, open its window again and stop here.
2. start the 127.0.0.1 web server (stdlib, fast) and remember its address in a local file
   so a second start can find it (`%LOCALAPPDATA%\\CamtekAOI\\Cache\\server.json`, same user only).
3. open the Edge app window, load the engine on a worker thread and serve until the user quits
   (or the window is closed and no watch keeps the app in the tray).

No console, no script files, nothing written next to the program (docs/V13_계획.md 11).
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

APP_TITLE = "Camtek AOI Manager"


def state_file() -> Path:
    from . import localdirs
    return Path(localdirs.appdata_root()) / "Cache" / "server.json"


def write_state(server) -> None:
    p = state_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps({"port": server.port, "token": server.token, "pid": os.getpid(),
                               "started": time.strftime("%Y-%m-%d %H:%M:%S")}), encoding="utf-8")
    os.replace(tmp, p)


def read_state() -> dict | None:
    try:
        data = json.loads(state_file().read_text(encoding="utf-8"))
        return data if isinstance(data.get("port"), int) and data.get("token") else None
    except (OSError, ValueError, AttributeError):
        return None


def clear_state(server) -> None:
    data = read_state()
    if data and data.get("token") == server.token:
        try:
            state_file().unlink()
        except OSError:
            pass


def message_box(text: str, title: str = APP_TITLE) -> None:
    """pythonw has no console: errors before the window exists go to a Windows message box."""
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, text, title, 0x10)
            return
        except Exception:  # noqa: BLE001
            pass
    print(text, file=sys.stderr)


def onedrive_refusal(app_home: str | None) -> str | None:
    """The program folder must not be synced (2026-08 'High-Volume Directory Access' alert)."""
    from . import localdirs
    if app_home and localdirs.is_under_onedrive(app_home):
        return ("프로그램 폴더가 OneDrive 안에 있습니다.\n\n" + app_home + "\n\n"
                "이 위치에서는 실행하지 않습니다(파일이 많아 동기화 경고가 납니다).\n"
                "설치 안내대로 %LOCALAPPDATA%\\CamtekAOI\\app 에 풀고 그 바로가기로 실행하십시오.")
    return None


def main(argv=None) -> int:
    started = time.perf_counter()
    from . import desktop_diag            # stdlib only; times everything below
    desktop_diag.engine_started()
    desktop_diag.start_import_timer()
    from . import webserver, winnative
    from .singleinst import SingleInstance

    refusal = onedrive_refusal(os.environ.get("PARA_APP_HOME"))
    if refusal:
        message_box(refusal)
        return 2
    profile = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "CamtekAOI" / "EdgeProfile"

    instance = SingleInstance()
    if not instance.acquire(wait_sec=15):            # a just-closed copy may still be saving
        state = read_state()
        if state:
            winnative.open_app_window(f"http://127.0.0.1:{state['port']}/?t={state['token']}", profile)
            return 0
        message_box("Camtek AOI Manager(또는 v12 프로그램)가 이미 실행 중입니다.\n"
                    "작업 표시줄 알림 영역의 아이콘에서 열거나, 종료한 뒤 다시 실행하십시오.")
        return 1

    natives = lambda s: winnative.WinNatives(s, profile=profile)   # noqa: E731
    server = webserver.WebServer(natives_factory=natives)
    server.start()
    try:
        write_state(server)
        winnative.open_app_window(server.url, profile)
        home = os.environ.get("PARA_APP_HOME")
        try:
            winnative.ensure_desktop_shortcut(Path(home) if home else None)
        except Exception:  # noqa: BLE001 - a missing shortcut must not stop the program
            pass
        def loader():
            from . import desktop_ipc as ipc
            return ipc
        webserver.run_engine(server, loader, diag=desktop_diag,
                             startup_prefix=f"엔진 시작(v13 · 서버 준비 {time.perf_counter() - started:.1f}s)")
    except Exception as exc:  # noqa: BLE001 - show it; pythonw would hide it
        message_box(f"프로그램을 시작하지 못했습니다.\n\n{type(exc).__name__}: {exc}")
        return 1
    finally:
        clear_state(server)
        stop = getattr(server.natives, "stop", None)
        if stop:
            stop()
        instance.release()
    return 0

