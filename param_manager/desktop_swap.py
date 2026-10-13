"""Folder swap for the web app self-update, done by the engine exe itself (Para #31).

Until v12.7.16 the swap was a hidden, self-deleting `web_update.bat` in Temp
(`ping` as a sleep, `rmdir /s /q`, `start`, `del "%~f0"`). Windows Defender's
cloud ML flagged exactly that shape as `Trojan:Script/Wacatac.F!ml` and blocked
the update. Now no script file is written at all: `desktop_appupdate.prepare`
copies the *new* engine folder to the update's Temp folder and writes
`swap.json` next to it; `launch` starts that copy as
`Camtek_AOI_engine.exe --apply-update`, and this module does what the script did.

Not a path interpreter: there is no path argument. The plan is read only from
`<folder of the running engine>/../swap.json`, and only the fixed rename pattern
`<install>` → `<install>.prev`, `<install>.new` → `<install>` is accepted.
stdlib only.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

FLAG = "--apply-update"
PLAN = "swap.json"
APP_EXE = "Camtek_AOI_manager.exe"
WAIT_SECONDS = 120


def plan_path() -> Path:
    """`<temp run>/swap.json` for the engine copy `<temp run>/swapper/Camtek_AOI_engine.exe`."""
    return Path(sys.executable).resolve().parent.parent / PLAN


def write_plan(folder, install, staged, prev, wait=WAIT_SECONDS) -> str:
    path = Path(folder) / PLAN
    path.write_text(json.dumps(dict(install=str(install), staged=str(staged), prev=str(prev), wait=int(wait)),
                               ensure_ascii=False), encoding="utf-8")
    return str(path)


def read_plan(path) -> dict:
    """The plan, checked against the only shape `prepare` writes. ValueError otherwise."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) != {"install", "staged", "prev", "wait"}:
        raise ValueError("bad plan")
    install, staged, prev = (Path(str(data[k])) for k in ("install", "staged", "prev"))
    if not install.is_absolute() or not install.name \
            or staged != install.parent / f"{install.name}.new" or prev != install.parent / f"{install.name}.prev":
        raise ValueError("bad plan paths")
    if not (staged / APP_EXE).is_file():
        raise ValueError("staged package missing")
    wait = data["wait"]
    if not isinstance(wait, int) or not 1 <= wait <= 600:
        raise ValueError("bad wait")
    return dict(install=install, staged=staged, prev=prev, wait=wait)


def _start(exe: Path) -> None:
    flags = 0x00000008 | 0x00000200 if os.name == "nt" else 0   # DETACHED | NEW_PROCESS_GROUP
    subprocess.Popen([str(exe)], cwd=str(exe.parent), close_fds=True, creationflags=flags,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def swap(plan: dict, sleep=time.sleep, start=_start) -> int:
    """Wait until the install folder can be renamed (a folder with a running exe
    inside cannot be — that *is* the "app has exited" signal), put the new folder
    in place, keep one `.prev`, start the app. Failure → old folder back."""
    install, staged, prev = plan["install"], plan["staged"], plan["prev"]
    held = Path(f"{prev}.tmp")
    for _ in range(plan["wait"]):
        try:
            os.rename(install, held)
            break
        except OSError:
            sleep(1)
    else:
        shutil.rmtree(staged, ignore_errors=True)    # app never exited: drop the staged copy
        return 2
    try:
        os.rename(staged, install)
    except OSError:
        os.rename(held, install)
        start(install / APP_EXE)
        return 3
    if prev.exists():
        shutil.rmtree(prev, ignore_errors=True)
    try:
        os.rename(held, prev)
    except OSError:
        pass
    start(install / APP_EXE)
    return 0


def main() -> int:
    try:
        plan = read_plan(plan_path())
    except (OSError, ValueError):
        return 1
    return swap(plan)
