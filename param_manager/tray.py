"""작업표시줄 알림영역(트레이) 아이콘 — 창을 닫아도 자동 감시를 계속하기 위한 상주.

왜 직접 만드는가
----------------
트레이 아이콘 라이브러리(pystray 등)는 **추가 패키지 금지** 제약에 걸린다.
그래서 표준 라이브러리 `ctypes` 로 Win32 `Shell_NotifyIconW` 를 직접 호출한다.

동작
----
  · 창을 닫아도(X) 감시가 켜져 있으면 **프로세스는 살아 있고 창만 숨긴다**.
    tkinter mainloop 이 계속 돌기 때문에 `after` 로 도는 감시 주기도 그대로 동작한다.
  · 트레이 아이콘 **좌클릭/더블클릭 → 창 다시 열기**, **우클릭 → 메뉴(열기 / 종료)**.
  · 종료를 누르면 그때 진짜로 끝난다(잠금·세션 반납 후).

스레드 규칙 (중요)
------------------
아이콘 메시지를 받으려면 창과 메시지 루프가 필요하다. tkinter 루프를 건드리지
않도록 **별도 스레드에서 숨은 창 + 메시지 루프**를 돌리고, 사용자가 아이콘을
누르면 `schedule`(=root.after) 로 **GUI 스레드에 넘겨서** 콜백을 실행한다.
ctypes 콜백 객체는 GC 되면 프로세스가 죽으므로 반드시 참조를 유지한다.

Windows 가 아니거나 API 호출이 실패하면 `available()` 이 False 가 되고, 모든
메서드는 조용한 no-op 이 된다(개발환경/타 OS 에서 앱이 깨지지 않도록).
"""

from __future__ import annotations

import os
import sys
import threading

# ── Win32 상수 ─────────────────────────────────────────────────────────────
WM_DESTROY = 0x0002
WM_COMMAND = 0x0111
WM_LBUTTONUP = 0x0202
WM_RBUTTONUP = 0x0205
WM_LBUTTONDBLCLK = 0x0203
WM_TRAY = 0x0400 + 20          # WM_USER+20 — 우리 아이콘 콜백 메시지
NIN_BALLOONUSERCLICK = 0x0405  # 풍선 알림 본문을 사용자가 클릭

NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_INFO = 0x01, 0x02, 0x04, 0x10
IDI_APPLICATION = 32512
IMAGE_ICON = 1
LR_LOADFROMFILE, LR_DEFAULTSIZE = 0x0010, 0x0040

TPM_RIGHTBUTTON = 0x0002
MF_STRING, MF_SEPARATOR = 0x0000, 0x0800
CS_DBLCLKS = 0x0008

ID_OPEN, ID_EXIT = 1001, 1002


def available() -> bool:
    """이 환경에서 트레이 아이콘을 쓸 수 있는가(Windows 전용)."""
    return os.name == "nt" and sys.platform.startswith("win")


def should_stay_resident(watch_enabled: bool, tray_ok: bool | None = None) -> bool:
    """창을 닫을 때 **상주할지**(True) 진짜 종료할지(False).

    감시가 켜져 있고 트레이를 쓸 수 있을 때만 상주한다. 감시가 꺼져 있으면
    남아 있을 이유가 없으므로 그냥 종료한다. (GUI 비의존 — 테스트 대상)
    """
    return bool(watch_enabled) and bool(available() if tray_ok is None else tray_ok)


class TrayIcon:
    """트레이 아이콘 1개. Windows 가 아니면 아무것도 하지 않는다.

    on_open()  — 아이콘 좌클릭/더블클릭, 또는 메뉴 '열기'
    on_exit()  — 메뉴 '종료'
    schedule(fn) — 콜백을 GUI 스레드에서 실행해 주는 함수(root.after(0, fn) 등)
    """

    def __init__(self, title: str, on_open=None, on_exit=None, schedule=None,
                 icon_path: str | None = None, on_balloon=None):
        self.title = title[:127]
        self._on_open = on_open
        self._on_exit = on_exit
        self._on_balloon = on_balloon      # 풍선 알림 본문 클릭
        self._schedule = schedule or (lambda fn: fn())
        self._icon_path = icon_path
        self._hwnd = None
        self._thread = None
        self._ready = threading.Event()
        self._alive = False
        self._refs: list = []          # ctypes 콜백/구조체 참조 유지(GC 방지)

    # ── 공개 API (실패해도 앱이 죽지 않도록 전부 방어) ──────────────────
    def start(self) -> bool:
        """트레이 아이콘 표시. 성공하면 True."""
        if not available() or self._alive:
            return False
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="tray")
        self._thread.start()
        self._ready.wait(timeout=3.0)
        return self._alive

    def stop(self) -> None:
        """아이콘 제거 + 메시지 루프 종료."""
        if not self._alive:
            return
        self._alive = False
        try:
            import ctypes
            self._notify(NIM_DELETE)
            if self._hwnd:
                ctypes.windll.user32.PostMessageW(self._hwnd, WM_DESTROY, 0, 0)
        except Exception:  # noqa: BLE001
            pass

    def notify(self, title: str, message: str) -> None:
        """풍선 알림(변경 감지 등). 실패해도 무시."""
        if not self._alive:
            return
        try:
            self._notify(NIM_MODIFY, info=message[:255], info_title=title[:63])
        except Exception:  # noqa: BLE001
            pass

    def set_tooltip(self, text: str) -> None:
        if not self._alive:
            return
        try:
            self.title = text[:127]
            self._notify(NIM_MODIFY)
        except Exception:  # noqa: BLE001
            pass

    # ── 내부 구현 ──────────────────────────────────────────────────────
    def _run(self):
        try:
            self._create()
            self._alive = True
        except Exception:  # noqa: BLE001
            self._alive = False
        finally:
            self._ready.set()
        if not self._alive:
            return
        try:
            self._pump()
        except Exception:  # noqa: BLE001
            pass

    def _create(self):
        import ctypes
        from ctypes import wintypes

        user32, shell32, kernel32 = (ctypes.windll.user32, ctypes.windll.shell32,
                                     ctypes.windll.kernel32)

        # 반환형/인자형을 명시하지 않으면 ctypes 가 int(32bit)로 가정해 **64비트에서
        # 핸들 값이 잘려** 크래시한다. 핸들을 돌려주는 함수는 반드시 지정할 것.
        LRESULT = ctypes.c_ssize_t          # LONG_PTR — 포인터 크기
        WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT,
                                     wintypes.WPARAM, wintypes.LPARAM)
        user32.DefWindowProcW.restype = LRESULT
        user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT,
                                          wintypes.WPARAM, wintypes.LPARAM]
        user32.CreateWindowExW.restype = wintypes.HWND
        user32.LoadIconW.restype = wintypes.HICON
        user32.LoadImageW.restype = wintypes.HANDLE
        user32.CreatePopupMenu.restype = wintypes.HMENU
        user32.GetMessageW.argtypes = [ctypes.c_void_p, wintypes.HWND,
                                       wintypes.UINT, wintypes.UINT]
        shell32.Shell_NotifyIconW.restype = wintypes.BOOL

        class WNDCLASS(ctypes.Structure):
            _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC),
                        ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                        ("hInstance", wintypes.HINSTANCE),
                        ("hIcon", wintypes.HICON), ("hCursor", wintypes.HANDLE),
                        ("hbrBackground", wintypes.HBRUSH),
                        ("lpszMenuName", wintypes.LPCWSTR),
                        ("lpszClassName", wintypes.LPCWSTR)]

        class NOTIFYICONDATA(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND),
                        ("uID", wintypes.UINT), ("uFlags", wintypes.UINT),
                        ("uCallbackMessage", wintypes.UINT),
                        ("hIcon", wintypes.HICON), ("szTip", wintypes.WCHAR * 128),
                        ("dwState", wintypes.DWORD),
                        ("dwStateMask", wintypes.DWORD),
                        ("szInfo", wintypes.WCHAR * 256),
                        ("uTimeout", wintypes.UINT),
                        ("szInfoTitle", wintypes.WCHAR * 64),
                        ("dwInfoFlags", wintypes.DWORD),
                        ("guidItem", ctypes.c_byte * 16),
                        ("hBalloonIcon", wintypes.HICON)]

        self._NOTIFYICONDATA = NOTIFYICONDATA
        self._shell32 = shell32
        self._user32 = user32

        def wndproc(hwnd, msg, wparam, lparam):
            if msg == WM_TRAY:
                low = lparam & 0xFFFF
                if low == NIN_BALLOONUSERCLICK:
                    # 풍선 알림 본문 클릭 → 창 열고 해당 내용(보고서)까지 보여준다
                    self._fire(self._on_balloon or self._on_open)
                elif low in (WM_LBUTTONUP, WM_LBUTTONDBLCLK):
                    self._fire(self._on_open)
                elif low == WM_RBUTTONUP:
                    self._menu(hwnd)
                return 0
            if msg == WM_COMMAND:
                cmd = wparam & 0xFFFF
                if cmd == ID_OPEN:
                    self._fire(self._on_open)
                elif cmd == ID_EXIT:
                    self._fire(self._on_exit)
                return 0
            if msg == WM_DESTROY:
                user32.PostQuitMessage(0)
                return 0
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        proc = WNDPROC(wndproc)
        self._refs.append(proc)          # GC 되면 크래시 — 반드시 유지

        hinst = kernel32.GetModuleHandleW(None)
        cls = WNDCLASS()
        cls.style = CS_DBLCLKS
        cls.lpfnWndProc = proc
        cls.hInstance = hinst
        cls.lpszClassName = f"ParaTray{os.getpid()}"
        self._refs.append(cls)
        if not user32.RegisterClassW(ctypes.byref(cls)):
            raise OSError("트레이 창 클래스 등록 실패")

        self._hwnd = user32.CreateWindowExW(0, cls.lpszClassName, "Para", 0,
                                            0, 0, 0, 0, None, None, hinst, None)
        if not self._hwnd:
            raise OSError("트레이 창 생성 실패")

        # 아이콘: 지정 .ico 가 있으면 사용, 없으면 시스템 기본.
        # IDI_APPLICATION 은 문자열이 아니라 **정수 리소스 ID**(MAKEINTRESOURCE)라
        # 문자열 포인터로 넘기면 안 되고, 정수를 포인터 값으로 캐스팅해 전달한다.
        hicon = None
        if self._icon_path and os.path.isfile(self._icon_path):
            hicon = user32.LoadImageW(None, str(self._icon_path), IMAGE_ICON,
                                      0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE)
        if not hicon:
            hicon = user32.LoadIconW(
                None, ctypes.cast(ctypes.c_void_p(IDI_APPLICATION),
                                  ctypes.c_wchar_p))
        self._hicon = hicon
        self._notify(NIM_ADD)

    def _notify(self, action, info="", info_title=""):
        import ctypes
        nid = self._NOTIFYICONDATA()
        nid.cbSize = ctypes.sizeof(self._NOTIFYICONDATA)
        nid.hWnd = self._hwnd
        nid.uID = 1
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = WM_TRAY
        nid.hIcon = self._hicon
        nid.szTip = self.title
        if info:
            nid.uFlags |= NIF_INFO
            nid.szInfo = info
            nid.szInfoTitle = info_title or "Para"
            nid.uTimeout = 10000
        if not self._shell32.Shell_NotifyIconW(action, ctypes.byref(nid)) \
                and action == NIM_ADD:
            raise OSError("트레이 아이콘 등록 실패")

    def _menu(self, hwnd):
        """우클릭 메뉴 — 열기 / 종료."""
        import ctypes
        from ctypes import wintypes
        user32 = self._user32
        menu = user32.CreatePopupMenu()
        user32.AppendMenuW(menu, MF_STRING, ID_OPEN, "프로그램 열기")
        user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(menu, MF_STRING, ID_EXIT, "자동 감시 종료")
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        # 메뉴가 바깥 클릭으로 닫히게 하려면 포그라운드로 올려야 한다(Win32 관례)
        user32.SetForegroundWindow(hwnd)
        user32.TrackPopupMenu(menu, TPM_RIGHTBUTTON, pt.x, pt.y, 0, hwnd, None)
        user32.PostMessageW(hwnd, 0, 0, 0)
        user32.DestroyMenu(menu)

    def _pump(self):
        import ctypes
        from ctypes import wintypes
        user32 = self._user32
        msg = wintypes.MSG()
        while self._alive and user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def _fire(self, cb):
        """아이콘 조작 콜백을 GUI 스레드로 넘긴다(위젯을 여기서 만지면 안 됨)."""
        if cb is None:
            return
        try:
            self._schedule(cb)
        except Exception:  # noqa: BLE001
            pass
