"""tray.py 검증 — 상주 판단 규칙 + 비Windows 안전 degradation.

Win32 API 자체는 개발환경(Linux)에서 호출할 수 없으므로, 여기서는
 · '창을 닫을 때 상주할지' 판단 규칙(GUI 비의존)
 · Windows 가 아닐 때 **앱을 깨뜨리지 않고 조용히 no-op** 이 되는지
를 검증한다. 실제 아이콘 표시·클릭은 Windows 실기 확인 대상.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from param_manager import tray  # noqa: E402

PASS = FAIL = 0


def run(fn):
    global PASS, FAIL
    print(f"[RUN] {fn.__name__}")
    try:
        fn()
        PASS += 1
        print(f"[PASS] {fn.__name__}\n")
    except Exception as e:  # noqa: BLE001
        FAIL += 1
        import traceback
        print(f"[FAIL] {fn.__name__}: {e}")
        traceback.print_exc()
        print()


# --------------------------------------------------------------------------
def test_stay_resident_rule():
    """감시가 켜져 있을 때만 상주. 꺼져 있으면 남아 있을 이유가 없다."""
    assert tray.should_stay_resident(True, tray_ok=True) is True
    assert tray.should_stay_resident(False, tray_ok=True) is False, \
        "감시 꺼짐 → 그냥 종료"
    assert tray.should_stay_resident(True, tray_ok=False) is False, \
        "트레이를 못 쓰면(비Windows) 상주하지 않는다 — 숨은 채 남으면 안 됨"
    assert tray.should_stay_resident(False, tray_ok=False) is False
    print("  상주 판단 규칙(감시 ON + 트레이 가능일 때만) OK")


def test_available_matches_platform():
    assert tray.available() == (os.name == "nt")
    if os.name != "nt":
        assert tray.available() is False, "개발환경(Linux)에서는 사용 불가"
    print(f"  플랫폼 판정 OK (available={tray.available()})")


def test_icon_is_safe_noop_off_windows():
    """비Windows 에서 start/notify/stop 이 예외 없이 조용히 무시되어야 한다."""
    calls = []
    icon = tray.TrayIcon("Para 테스트",
                         on_open=lambda: calls.append("open"),
                         on_exit=lambda: calls.append("exit"),
                         schedule=lambda fn: fn())
    started = icon.start()
    if os.name != "nt":
        assert started is False, "비Windows 에서는 start() 가 False"
    # 어떤 순서로 불러도 예외가 나면 안 된다(앱 종료 경로에서 호출되므로)
    icon.notify("제목", "내용")
    icon.set_tooltip("툴팁")
    icon.stop()
    icon.stop()                      # 중복 호출도 안전해야 함
    print("  비Windows 안전 no-op(예외 없음) OK")


def test_menu_command_ids_are_distinct():
    """우클릭 메뉴: '열기'와 '종료'가 서로 다른 명령이어야 한다."""
    assert tray.ID_OPEN != tray.ID_EXIT
    assert tray.WM_TRAY > 0x0400, "WM_USER 이상이어야 시스템 메시지와 겹치지 않음"
    print("  트레이 메뉴 명령 ID 분리 OK")


def test_single_instance_is_noop_off_windows():
    """중복 실행 방지 — 비Windows 에서는 항상 획득 성공(앱을 막지 않는다)."""
    from param_manager import singleinst
    g = singleinst.SingleInstance("Local\\CamtekAOI_test")
    assert g.acquire() is True
    g.release()
    g.release()                                   # 중복 해제도 안전
    assert singleinst.activate_existing("없는 창") is False
    assert singleinst.available() == (os.name == "nt")
    print("  중복 실행 방지: 비Windows 안전 no-op OK")


def test_main_guards_second_instance():
    """트레이 상주 중에 아이콘을 다시 눌러도 창이 2개 열리면 안 된다 —
    main() 이 단일 인스턴스를 확인하고 기존 창을 살리는 구조여야 한다."""
    import re
    src = open(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "param_manager", "equip_app.py"),
        encoding="utf-8").read()
    m = re.search(r"\ndef main\(\):.*", src, re.S)
    assert m, "main() 을 찾지 못함"
    body = m.group(0)
    assert "singleinst.SingleInstance" in body, "중복 실행 검사가 없음"
    assert "activate_existing" in body, "기존 창을 살리지 않음"
    assert body.index("acquire") < body.index("EquipApp()"), \
        "창을 만들기 전에 검사해야 함"
    print("  main(): 두 번째 인스턴스 차단 + 기존 창 복원 OK")


if __name__ == "__main__":
    for t in [test_stay_resident_rule, test_available_matches_platform,
              test_icon_is_safe_noop_off_windows, test_menu_command_ids_are_distinct,
              test_single_instance_is_noop_off_windows,
              test_main_guards_second_instance]:
        run(t)
    print(f"==== {PASS}/{PASS + FAIL} passed ====")
    sys.exit(1 if FAIL else 0)
