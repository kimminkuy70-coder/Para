"""Web app (Tauri + sidecar) self-update through the shared OneDrive folder.

Same channel and rules as the tkinter updater (`updater.py`): the program
folder next to the save folder, no internet, local Temp download, SHA-256
check, a detached script that swaps after the app exits, and a way back.
What differs is the payload — the web app is a *folder* (app exe + `sidecar\\`
engine, hundreds of files), so:

* **Publish = one zip file** (`Camtek_AOI_manager_web_v{ver}.zip`) plus its own
  manifest `버전정보_web.json`. Unzipped folders on OneDrive would be exactly the
  mass-sync pattern that triggered the 2026-08 security alert, and a separate
  manifest keeps tkinter installations from treating the zip as their update.
  The latest two zips stay for rollback (`KEEP_VERSIONS`).
* **Apply = side-by-side folder swap.** The zip is copied to local Temp and
  verified, extracted next to the install folder (`<install>.new`) and checked
  file by file against its `package-manifest.json`. A script then waits until
  the install folder can be renamed — a folder with a running exe or engine
  inside cannot be, so a successful rename *is* the "app has exited" signal
  (the folder counterpart of the tkinter "old exe deleted" rule) — renames it to
  `<install>.prev` (one rollback copy), moves the new folder in place and starts
  it. The install path never changes, so shortcuts keep working. If anything
  fails the old folder is restored and started again.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime

from . import __version__, desktop_package, localdirs, updater

WEB_MANIFEST = "버전정보_web.json"
ZIP_PREFIX = "Camtek_AOI_manager_web_v"
APP_EXE = "Camtek_AOI_manager.exe"
ENGINE_DIR = "sidecar"
ENGINE_EXE = "Camtek_AOI_engine.exe"
KEEP_VERSIONS = 2
MAX_ZIP = 1024 * 1024 * 1024
WAIT_SECONDS = 120


# ---- where are we installed -----------------------------------------------------
def install_dir() -> Path | None:
    """`<install>` when running as the packaged engine `<install>\\sidecar\\engine.exe`."""
    if not getattr(sys, "frozen", False):
        return None
    exe = Path(sys.executable).resolve()
    if exe.parent.name.lower() != ENGINE_DIR or not (exe.parent.parent / APP_EXE).is_file():
        return None
    return exe.parent.parent


def default_local_root() -> str:
    """Local work folder when the config has none. The tkinter default ('next to
    the program') would be *inside* the web install folder, which an update
    renames and later deletes — so the packaged engine uses %LOCALAPPDATA%."""
    return localdirs.appdata_root() if install_dir() else localdirs.default_root()


def inside_install(path) -> bool:
    root = install_dir()
    if root is None:
        return False
    p = Path(path).resolve()
    return p == root or root in p.parents


# ---- publish (developer) -----------------------------------------------------------
def zip_name(version: str) -> str:
    return f"{ZIP_PREFIX}{version}.zip"


def manifest_path(save_dir: str) -> str:
    return os.path.join(updater.active_program_dir(save_dir), WEB_MANIFEST)


def read_manifest(save_dir: str) -> dict | None:
    try:
        with open(manifest_path(save_dir), encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:  # noqa: BLE001 - a missing/broken manifest just means "no update"
        return None
    if not isinstance(data, dict):
        return None
    ver, name = str(data.get("version") or ""), str(data.get("filename") or "")
    try:
        size = int(data.get("size") or 0)
    except (TypeError, ValueError):
        return None
    if (updater.parse_version(ver) == (0,) or name != zip_name(ver) or size <= 0
            or not re.fullmatch(r"[0-9a-f]{64}", str(data.get("sha256") or ""))):
        return None
    return data


def publish(save_dir: str, package: str, local_root: str, changelog: str = "", user: str = "") -> dict:
    """Zip a built package folder (the CI artifact / build_desktop output) into the
    program folder and update the web manifest last."""
    if not save_dir:
        raise ValueError("먼저 저장폴더를 지정하세요")
    root = Path(package)
    if not root.is_dir():
        raise ValueError("게시할 패키지 폴더를 찾을 수 없습니다")
    info = desktop_package.verify(root)          # all files present, unchanged, versioned
    version = info["version"]
    folder = updater.program_dir(save_dir)
    dest = os.path.join(folder, zip_name(version))
    ours = (root / desktop_package.MANIFEST).read_bytes()
    if os.path.exists(dest):
        # Zips are not byte-reproducible; the package manifest (all file hashes) is.
        with zipfile.ZipFile(dest) as old:
            try:
                theirs = old.read(desktop_package.MANIFEST)
            except KeyError:
                theirs = b""
        if theirs != ours:
            raise ValueError("같은 버전의 다른 패키지가 이미 게시되어 있습니다. 버전을 올려 다시 빌드하세요.")
    else:
        local = localdirs.new_temp_run(localdirs.ensure(local_root), "webpublish")
        try:
            built = os.path.join(local, zip_name(version))
            with zipfile.ZipFile(built, "w", zipfile.ZIP_DEFLATED) as zf:
                for file in sorted(root.rglob("*")):
                    if file.is_file():
                        zf.write(file, file.relative_to(root).as_posix())
            # One file event on OneDrive (no .tmp beside it). The manifest is written
            # after this copy, and clients verify size + SHA-256 before using it.
            shutil.copy2(built, dest)
        finally:
            localdirs.drop(local)
    release = dict(version=version, filename=zip_name(version), sha256=updater.file_sha256(dest),
                   size=os.path.getsize(dest), changelog=changelog or "",
                   published_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), published_by=user or "",
                   kind="web")
    with open(os.path.join(folder, WEB_MANIFEST), "w", encoding="utf-8") as fh:
        json.dump(release, fh, ensure_ascii=False, indent=2)
    prune(folder, keep=release["filename"])
    return release


def prune(folder: str, keep: str) -> list[str]:
    """Keep the newest KEEP_VERSIONS web zips (by version number, not file time)."""
    zips = [n for n in os.listdir(folder) if n.startswith(ZIP_PREFIX) and n.endswith(".zip")]
    zips.sort(key=lambda n: updater.parse_version(n[len(ZIP_PREFIX):-4]), reverse=True)
    removed = []
    for name in zips[KEEP_VERSIONS:]:
        if name == keep:
            continue
        try:
            os.remove(os.path.join(folder, name))
            removed.append(name)
        except OSError:
            pass
    return removed


# ---- check ---------------------------------------------------------------------------
def check(save_dir: str, cfg: dict) -> dict:
    current = __version__
    release = read_manifest(save_dir) if save_dir else None
    applied = str(cfg.get("web_update_applied_version") or "")
    return dict(current=current, installed=install_dir() is not None,
                available=(release or {}).get("version", ""),
                newer=bool(release and updater.is_newer(release["version"], current)),
                changelog=(release or {}).get("changelog", ""),
                published_at=(release or {}).get("published_at", ""),
                skipped=bool(release and cfg.get("web_update_skip_version") == release["version"]),
                # The last update was started but this is still the old version.
                failed=bool(applied and updater.same_version(applied, (release or {}).get("version", ""))
                            and not updater.same_version(applied, current)),
                program_dir=updater.active_program_dir(save_dir) if save_dir else "")


# ---- apply -----------------------------------------------------------------------------
def _safe_extract(zip_path: str, dest: Path) -> None:
    with zipfile.ZipFile(zip_path) as zf:
        total = 0
        for member in zf.infolist():
            name = member.filename
            target = (dest / name).resolve()
            if name.startswith(("/", "\\")) or ":" in name or not (target == dest.resolve() or dest.resolve() in target.parents):
                raise ValueError("업데이트 패키지에 허용되지 않는 경로가 있습니다")
            total += member.file_size
            if total > 4 * MAX_ZIP:
                raise ValueError("업데이트 패키지가 너무 큽니다")
        zf.extractall(dest)


def build_swap_script(install: Path, staged: Path, prev: Path) -> str:
    """Folder swap (see module doc). ASCII-only body; paths are written by
    updater._write_bat in the system ANSI code page. No `timeout` (detached
    runs have no console) — `ping` waits. No PID matching — the folder rename is
    the exit signal."""
    exe = install / APP_EXE
    lines = [
        "@echo off",
        f'set "APP={install}"',
        f'set "NEW={staged}"',
        f'set "PREV={prev}"',
        "set /a N=0",
        ':wait',
        'move "%APP%" "%PREV%.tmp" >nul 2>&1 && goto moved',
        "set /a N+=1",
        f"if %N% GEQ {WAIT_SECONDS} goto giveup",
        "ping -n 2 127.0.0.1 >nul",
        "goto wait",
        ":moved",
        'move "%NEW%" "%APP%" >nul 2>&1 || goto restore',
        'if exist "%PREV%" rmdir /s /q "%PREV%"',
        'move "%PREV%.tmp" "%PREV%" >nul 2>&1',
        f'start "" "{exe}"',
        "goto end",
        ":restore",
        'move "%PREV%.tmp" "%APP%" >nul 2>&1',
        f'start "" "{exe}"',
        "goto end",
        ":giveup",
        'rmdir /s /q "%NEW%"',
        ":end",
        '(goto) 2>nul & del "%~f0"',
    ]
    return "\n".join(lines) + "\n"


def prepare(save_dir: str, local_root: str) -> dict:
    """Download, verify and stage the new version, then write the swap script.
    Nothing in the install folder changes until the app has exited."""
    install = install_dir()
    if install is None:
        raise ValueError("개발 실행에서는 자동 업데이트를 할 수 없습니다. 설치된 앱에서 실행하세요.")
    if localdirs.is_under_onedrive(str(install)):
        raise ValueError("앱이 OneDrive 폴더 안에 설치되어 있어 자동 업데이트를 할 수 없습니다. "
                         "사용 설명서대로 로컬 폴더로 옮긴 뒤 다시 시도하세요.")
    release = read_manifest(save_dir)
    if not release or not updater.is_newer(release["version"], __version__):
        raise ValueError("설치할 새 버전이 없습니다")
    source = os.path.join(updater.active_program_dir(save_dir), release["filename"])
    if not os.path.isfile(source):
        raise ValueError("게시된 업데이트 파일이 없습니다. OneDrive 동기화가 끝났는지 확인하세요.")
    if release["size"] > MAX_ZIP:
        raise ValueError("업데이트 파일이 너무 큽니다")
    temp = localdirs.new_temp_run(localdirs.ensure(local_root), "webupdate")
    local_zip = os.path.join(temp, release["filename"])
    shutil.copy2(source, local_zip)
    if os.path.getsize(local_zip) != release["size"] or updater.file_sha256(local_zip) != release["sha256"]:
        localdirs.drop(temp)
        raise ValueError("받은 파일이 게시본과 다릅니다(OneDrive 동기화 중일 수 있음). 잠시 후 다시 시도하세요.")
    staged = install.parent / f"{install.name}.new"
    prev = install.parent / f"{install.name}.prev"
    if staged.exists():
        shutil.rmtree(staged)
    staged.mkdir()
    try:
        _safe_extract(local_zip, staged)
        info = desktop_package.verify(staged)     # every file present and unchanged
        if not updater.same_version(info["version"], release["version"]):
            raise ValueError("패키지 버전이 게시 정보와 다릅니다")
    except Exception:
        shutil.rmtree(staged, ignore_errors=True)
        localdirs.drop(temp)
        raise
    script = os.path.join(temp, "web_update.bat")
    updater._write_bat(script, build_swap_script(install, staged, prev))
    return dict(version=release["version"], script=script, temp=temp, install=str(install),
                staged=str(staged), prev=str(prev))


def launch(prepared: dict) -> None:
    """Start the swap script detached, outside the install folder, then the UI exits."""
    flags = 0
    if os.name == "nt":
        flags = 0x00000008 | 0x00000200 | 0x08000000   # DETACHED | NEW_PROCESS_GROUP | NO_WINDOW
    subprocess.Popen(["cmd.exe", "/c", prepared["script"]], cwd=prepared["temp"], close_fds=True,
                     creationflags=flags, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL)


class DesktopAppUpdate:
    """IPC adapter. Paths come from the shared config only; the publish source is
    a folder the user picked with the native chooser (same trust model as setup)."""

    def __init__(self, config_path=None):
        self.config_path = Path(config_path) if config_path else Path.home() / ".pi_param_manager.json"

    def _cfg(self):
        from .desktop_batch import read_json
        return read_json(self.config_path)

    def _local_root(self):
        from .desktop_batch import DesktopBatch
        return str(DesktopBatch(self.config_path).configuration()[2])

    def _write_cfg(self, **changes):
        from . import atomicfile
        cfg = self._cfg()
        cfg.update(changes)
        atomicfile.write_json(str(self.config_path), cfg)

    def check(self, params):
        if params:
            raise ValueError("요청을 확인하세요")
        cfg = self._cfg()
        out = check(cfg.get("save_dir") or "", cfg)
        if out["failed"]:
            self._write_cfg(web_update_applied_version="")   # report once
        return out

    def skip(self, params):
        if set(params) != {"version"} or not isinstance(params["version"], str) or len(params["version"]) > 32:
            raise ValueError("버전을 확인하세요")
        self._write_cfg(web_update_skip_version=params["version"])
        return dict(skipped=params["version"])

    def apply(self, params):
        if params:
            raise ValueError("요청을 확인하세요")
        cfg = self._cfg()
        prepared = prepare(cfg.get("save_dir") or "", self._local_root())
        self._write_cfg(web_update_applied_version=prepared["version"])
        launch(prepared)
        return dict(version=prepared["version"], restart=True)

    def publish(self, params):
        if set(params) - {"path", "notes"} or not isinstance(params.get("path"), str) \
                or not isinstance(params.get("notes", ""), str) or len(params.get("notes", "")) > 4000:
            raise ValueError("게시할 패키지 폴더와 변경 내용을 확인하세요")
        from . import engine
        cfg = self._cfg()
        return publish(cfg.get("save_dir") or "", params["path"], self._local_root(),
                       params.get("notes", ""), engine.current_user())

    def open_dir(self, params):
        """Open the program (publish) folder for the manual '직접 설치' path."""
        if params:
            raise ValueError("요청을 확인하세요")
        save = self._cfg().get("save_dir") or ""
        if not save:
            raise ValueError("먼저 저장폴더를 지정하세요")
        folder = updater.active_program_dir(save)
        if not os.path.isdir(folder):
            raise ValueError("아직 게시된 버전이 없습니다")
        if os.name == "nt":
            os.startfile(folder)  # noqa: S606 - Windows only
        return dict(opened=folder)
