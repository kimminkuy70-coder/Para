"""v13 Windows-native parts that the Tauri shell used to do (stdlib ctypes only, no packages).

- folder / file chooser = the standard Windows dialog (IFileOpenDialog, the same one Explorer uses)
- the app window       = Microsoft Edge in app mode (``--app=URL``, no address bar), own profile folder
- tray residency        = `tray.TrayIcon` (Shell_NotifyIconW), shown while a watch keeps the app running

Off Windows every call is a quiet no-op (dialogs return None), so the Linux test runs work.
Edge is started without any debugging-port switch: that switch is how cookie stealers drive a
browser and security products watch for it (docs/V13_계획.md 11-2 ④).
"""
from __future__ import annotations

import os
import subprocess
import threading
import uuid
import webbrowser
from pathlib import Path

from . import tray
from .webserver import Natives

FILTERS = {"excel": [("Excel 파일", "*.xlsx;*.xlsm")], "zip": [("zip 파일", "*.zip")]}
TITLES = {"folder": "폴더 선택", "excel": "Excel 파일 선택", "zip": "zip 파일 선택"}
WINDOW_SIZE = "1440,960"
ICON = Path(__file__).resolve().parent / "data" / "para_icon.ico"


def is_windows() -> bool:
    return os.name == "nt"


# ---------------------------------------------------------------- Edge app window
def edge_candidates(env=None) -> list[Path]:
    env = os.environ if env is None else env
    out = []
    for var in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
        base = env.get(var)
        if base:
            out.append(Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe")
    return out


def edge_path() -> Path | None:
    for p in edge_candidates():
        if p.is_file():
            return p
    if is_windows():
        try:
            import winreg
            for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                try:
                    with winreg.OpenKey(hive, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe") as k:
                        p = Path(winreg.QueryValue(k, None))
                        if p.is_file():
                            return p
                except OSError:
                    continue
        except ImportError:
            pass
    return None


def app_window_cmd(edge: Path, url: str, profile: Path) -> list[str]:
    """Edge app-mode command. Only these switches — never a debugging port."""
    return [str(edge), f"--app={url}", f"--user-data-dir={profile}", f"--window-size={WINDOW_SIZE}",
            "--no-first-run", "--no-default-browser-check"]


def open_app_window(url: str, profile: Path) -> bool:
    """Show the screen. Edge app window if found, else the default browser. True if started."""
    edge = edge_path()
    if edge is None:
        return bool(webbrowser.open(url))
    profile.mkdir(parents=True, exist_ok=True)
    flags = 0
    if is_windows():
        flags = getattr(subprocess, "DETACHED_PROCESS", 0x8) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200)
    subprocess.Popen(app_window_cmd(edge, url, profile), close_fds=True, creationflags=flags,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True


# ---------------------------------------------------------------- file dialogs (IFileOpenDialog)
CLSID_FILE_OPEN = "DC1C5A9C-E88A-4DDE-A5A1-60F82A20AEF7"
IID_IFILE_OPEN = "D57C7288-D4AD-4768-BE02-9D969532D960"
FOS_PICKFOLDERS, FOS_FORCEFILESYSTEM, FOS_PATHMUSTEXIST, FOS_FILEMUSTEXIST = 0x20, 0x40, 0x800, 0x1000
SIGDN_FILESYSPATH = 0x80058000 - (1 << 32)      # as a signed 32-bit int
# vtable slots: IUnknown 0-2, IModalWindow.Show 3, IFileDialog SetFileTypes 4 … GetResult 20
SHOW, SET_FILE_TYPES, SET_OPTIONS, GET_OPTIONS, SET_TITLE, GET_RESULT, RELEASE = 3, 4, 9, 10, 17, 20, 2
GET_DISPLAY_NAME = 5                              # IShellItem
_dialog_lock = threading.Lock()


def dialog_options(kind: str, current: int = 0) -> int:
    base = current | FOS_FORCEFILESYSTEM | FOS_PATHMUSTEXIST
    return base | (FOS_PICKFOLDERS if kind == "folder" else FOS_FILEMUSTEXIST)


def _choose(kind: str) -> str | None:
    if not is_windows():
        return None
    import ctypes
    from ctypes import POINTER, byref, c_uint, c_void_p, c_wchar_p, wintypes

    class GUID(ctypes.Structure):
        _fields_ = [("a", ctypes.c_ulong), ("b", ctypes.c_ushort), ("c", ctypes.c_ushort), ("d", ctypes.c_ubyte * 8)]

    class Spec(ctypes.Structure):
        _fields_ = [("name", c_wchar_p), ("spec", c_wchar_p)]

    def guid(text):
        u = uuid.UUID(text)
        g = GUID(u.time_low, u.time_mid, u.time_hi_version)
        for i, byte in enumerate(u.bytes[8:]):
            g.d[i] = byte
        return g

    def method(obj, slot, *argtypes):
        table = ctypes.cast(obj, POINTER(POINTER(c_void_p))).contents
        fn = ctypes.WINFUNCTYPE(ctypes.HRESULT, c_void_p, *argtypes)(table[slot])
        return lambda *args: fn(obj, *args)

    ole32 = ctypes.windll.ole32
    initialized = ole32.CoInitializeEx(None, 0x2) in (0, 1)        # apartment thread
    dlg, item = c_void_p(), c_void_p()
    try:
        clsid, iid = guid(CLSID_FILE_OPEN), guid(IID_IFILE_OPEN)
        if ole32.CoCreateInstance(byref(clsid), None, 1, byref(iid), byref(dlg)) != 0:
            return None
        opts = c_uint()
        method(dlg, GET_OPTIONS, POINTER(c_uint))(byref(opts))
        method(dlg, SET_OPTIONS, c_uint)(dialog_options(kind, opts.value))
        filters = FILTERS.get(kind)
        if filters:
            arr = (Spec * len(filters))(*[Spec(n, s) for n, s in filters])
            method(dlg, SET_FILE_TYPES, c_uint, c_void_p)(len(filters), ctypes.cast(arr, c_void_p))
        method(dlg, SET_TITLE, c_wchar_p)(TITLES.get(kind, "선택"))
        owner = ctypes.windll.user32.GetForegroundWindow()
        try:
            method(dlg, SHOW, wintypes.HWND)(owner)
        except OSError:
            return None                                             # cancelled
        method(dlg, GET_RESULT, POINTER(c_void_p))(byref(item))
        raw = c_void_p()
        method(item, GET_DISPLAY_NAME, ctypes.c_int, POINTER(c_void_p))(SIGDN_FILESYSPATH, byref(raw))
        try:
            return ctypes.wstring_at(raw.value) if raw.value else None
        finally:
            ole32.CoTaskMemFree(raw)
    except OSError:
        return None
    finally:
        for obj in (item, dlg):
            if obj.value:
                try:
                    method(obj, RELEASE)()
                except OSError:
                    pass
        if initialized:
            ole32.CoUninitialize()


def pick(kind: str) -> str | None:
    with _dialog_lock:                       # one dialog at a time
        return _choose(kind)


# ---------------------------------------------------------------- desktop shortcut (IShellLinkW)
CLSID_SHELL_LINK = "00021401-0000-0000-C000-000000000046"
IID_SHELL_LINK_W = "000214F9-0000-0000-C000-000000000046"
IID_PERSIST_FILE = "0000010B-0000-0000-C000-000000000046"
# IShellLinkW slots: SetDescription 7, SetWorkingDirectory 9, SetArguments 11, SetIconLocation 17, SetPath 20
# IPersistFile slots: Save 6
SL_DESC, SL_WORKDIR, SL_ARGS, SL_ICON, SL_PATH, PF_SAVE, QUERY = 7, 9, 11, 17, 20, 6, 0
SHORTCUT_NAME = "Camtek AOI Manager.lnk"


def desktop_dir() -> Path | None:
    if not is_windows():
        return None
    import ctypes
    buf = ctypes.create_unicode_buffer(260)
    if ctypes.windll.shell32.SHGetFolderPathW(None, 0x10, None, 0, buf) != 0:   # CSIDL_DESKTOPDIRECTORY
        return None
    return Path(buf.value)


def shortcut_spec(home: Path) -> dict:
    """What the desktop shortcut points to: python.org pythonw.exe running our start file."""
    return dict(target=str(home / "python" / "pythonw.exe"), args=f'"{home / "Camtek_AOI_manager.pyw"}"',
                workdir=str(home), icon=str(home / "app" / "param_manager" / "data" / "para_icon.ico"),
                description="Camtek AOI Manager (Para v13)")


def create_shortcut(lnk: Path, spec: dict) -> bool:
    """Write a .lnk with the Windows shell API (what Explorer itself uses). Windows only."""
    if not is_windows():
        return False
    import ctypes
    from ctypes import POINTER, byref, c_int, c_void_p, c_wchar_p

    class GUID(ctypes.Structure):
        _fields_ = [("a", ctypes.c_ulong), ("b", ctypes.c_ushort), ("c", ctypes.c_ushort), ("d", ctypes.c_ubyte * 8)]

    def guid(text):
        u = uuid.UUID(text)
        g = GUID(u.time_low, u.time_mid, u.time_hi_version)
        for i, byte in enumerate(u.bytes[8:]):
            g.d[i] = byte
        return g

    def method(obj, slot, *argtypes):
        table = ctypes.cast(obj, POINTER(POINTER(c_void_p))).contents
        return lambda *a: ctypes.WINFUNCTYPE(ctypes.HRESULT, c_void_p, *argtypes)(table[slot])(obj, *a)

    ole32 = ctypes.windll.ole32
    initialized = ole32.CoInitializeEx(None, 0x2) in (0, 1)
    link, pf = c_void_p(), c_void_p()
    try:
        if ole32.CoCreateInstance(byref(guid(CLSID_SHELL_LINK)), None, 1, byref(guid(IID_SHELL_LINK_W)), byref(link)) != 0:
            return False
        method(link, SL_PATH, c_wchar_p)(spec["target"])
        method(link, SL_ARGS, c_wchar_p)(spec["args"])
        method(link, SL_WORKDIR, c_wchar_p)(spec["workdir"])
        method(link, SL_DESC, c_wchar_p)(spec["description"])
        if Path(spec["icon"]).is_file():
            method(link, SL_ICON, c_wchar_p, c_int)(spec["icon"], 0)
        method(link, QUERY, POINTER(GUID), POINTER(c_void_p))(byref(guid(IID_PERSIST_FILE)), byref(pf))
        method(pf, PF_SAVE, c_wchar_p, c_int)(str(lnk), 1)
        return True
    except OSError:
        return False
    finally:
        for obj in (pf, link):
            if obj.value:
                try:
                    method(obj, RELEASE)()
                except OSError:
                    pass
        if initialized:
            ole32.CoUninitialize()


def ensure_desktop_shortcut(home: Path | None) -> bool:
    """Installed copy only: make the desktop shortcut once (the first start is the starter .bat in the install folder)."""
    if home is None or not is_windows() or not (home / "python" / "pythonw.exe").is_file():
        return False
    desk = desktop_dir()
    if desk is None or (desk / SHORTCUT_NAME).exists():
        return False
    return create_shortcut(desk / SHORTCUT_NAME, shortcut_spec(home))


# ---------------------------------------------------------------- natives for the web server
class WinNatives(Natives):
    def __init__(self, server, profile: Path | None = None):
        super().__init__(server)
        self.profile = profile or Path(os.environ.get("LOCALAPPDATA", Path.home())) / "CamtekAOI" / "EdgeProfile"
        self._tray: tray.TrayIcon | None = None
        server.bridge.on_unheard = self.unheard

    def open_window(self):
        open_app_window(self.server.url, self.profile)

    def pick_folder(self, args):
        return pick("folder")

    def pick_file(self, args):
        kind = args.get("kind") if args.get("kind") in FILTERS else "excel"
        return pick(kind)

    def set_background(self, args):
        super().set_background(args)
        on, tip = self.background["enabled"], self.background["tooltip"] or "Para"
        if on and self._tray is None and tray.available():
            run = lambda fn: threading.Thread(target=fn, daemon=True).start()   # noqa: E731
            icon = tray.TrayIcon(tip, on_open=self.open_window, on_exit=self.server.request_exit,
                                 schedule=run, icon_path=str(ICON) if ICON.is_file() else None,
                                 on_balloon=self.open_window)
            if icon.start():
                self._tray = icon
        elif on and self._tray is not None:
            self._tray.set_tooltip(tip)
        elif not on and self._tray is not None:
            self._tray.stop()
            self._tray = None
        return None

    def unheard(self, message: dict):
        """A watch notice while no window is open: show it as a tray balloon."""
        if self._tray is not None and message.get("event") == "notice":
            n = message.get("notice") or {}
            if not n.get("quiet") and not n.get("live"):
                self._tray.notify(str(n.get("title", "Para"))[:63], str(n.get("summary", ""))[:255])

    def stop(self):
        if self._tray is not None:
            self._tray.stop()
            self._tray = None
