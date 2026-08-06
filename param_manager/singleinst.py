"""프로그램 중복 실행 방지(단일 인스턴스) — Windows 명명 뮤텍스, stdlib 만.

왜 필요한가
------------
  · **트레이 상주**: 자동 감시가 켜진 상태로 창을 닫으면 프로그램은 종료되지 않고
    트레이로 숨는다. 이때 사용자가 아이콘을 다시 실행하면 **두 번째 인스턴스**가
    떠서 창이 2개 열린 것처럼 보인다(실제 신고된 증상). 숨어 있던 창을 다시
    보여주는 것이 올바른 동작이다.
  · **자동 업데이트 직후**: 교체 스크립트가 새 exe 를 실행하는 시점과 구 프로세스가
    종료되는 시점이 겹치면 잠깐 2개가 될 수 있다. 잠깐 기다렸다가 진입한다.
  · 감시가 두 벌 돌면 장비에 **배수로 접속**하게 되므로 기능적으로도 막아야 한다.

추가 패키지 금지 제약 때문에 `ctypes` 로 Win32 를 직접 호출한다. 비Windows 에서는
전부 no-op(항상 획득 성공)이라 개발환경에서도 앱이 그대로 동작한다.
"""

from __future__ import annotations

import os
import time

# 같은 사용자 세션 안에서만 유일하면 된다(Local\). 다른 사용자가 각자 쓰는 것은 정상.
MUTEX_NAME = r"Local\CamtekAOI_Para_SingleInstance"
ERROR_ALREADY_EXISTS = 183

# 업데이트 직후 구 프로세스가 사라지기를 기다리는 시간(초).
WAIT_FOR_PREVIOUS_SEC = 12.0
WAIT_STEP_SEC = 0.5


def available() -> bool:
    return os.name == "nt"


class SingleInstance:
    """뮤텍스 보유자. `acquire()` 가 True 면 이 프로세스가 유일한 인스턴스다.

    핸들은 프로세스가 살아 있는 동안 유지해야 하므로 인스턴스를 앱에 보관할 것.
    """

    def __init__(self, name: str = MUTEX_NAME):
        self.name = name
        self._handle = None

    def acquire(self, wait_sec: float = 0.0) -> bool:
        """뮤텍스 획득. 이미 다른 인스턴스가 있으면 False.

        wait_sec > 0 이면 그동안 재시도한다(업데이트 직후 구 프로세스 종료 대기).
        """
        if not available():
            return True
        deadline = time.monotonic() + max(0.0, wait_sec)
        while True:
            if self._try_once():
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(WAIT_STEP_SEC)

    def _try_once(self) -> bool:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
        k32.CreateMutexW.restype = wintypes.HANDLE      # x64: 잘림 방지 필수
        handle = k32.CreateMutexW(None, True, self.name)
        err = ctypes.get_last_error()
        if not handle:
            return True                                 # 뮤텍스 자체 실패 → 막지 않는다
        if err == ERROR_ALREADY_EXISTS:
            k32.CloseHandle(handle)
            return False
        self._handle = handle
        return True

    def release(self) -> None:
        if self._handle and available():
            try:
                import ctypes
                ctypes.WinDLL("kernel32").CloseHandle(self._handle)
            except Exception:  # noqa: BLE001
                pass
        self._handle = None


def activate_existing(window_title: str) -> bool:
    """이미 떠 있는(또는 트레이에 숨은) 창을 찾아 앞으로 가져온다. 성공하면 True.

    숨겨진 창은 `ShowWindow(SW_RESTORE)` 로 다시 보이게 한다 — 사용자가 아이콘을
    다시 눌렀을 때 '아무 일도 일어나지 않는' 것처럼 보이면 안 되기 때문이다.
    """
    if not available():
        return False
    try:
        import ctypes
        from ctypes import wintypes
        u32 = ctypes.WinDLL("user32", use_last_error=True)
        u32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        u32.FindWindowW.restype = wintypes.HWND
        hwnd = u32.FindWindowW(None, window_title)
        if not hwnd:
            return False
        u32.ShowWindow(hwnd, 9)                 # SW_RESTORE
        u32.SetForegroundWindow(hwnd)
        return True
    except Exception:  # noqa: BLE001
        return False
