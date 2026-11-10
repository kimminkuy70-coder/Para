"""사내 보안 모니터링(EDR/SIEM/네트워크 장비)에 오탐되지 않기 위한 규칙.

장비 접속은 `\\IP\\c$`(관리공유)라 원래 감시 대상이다. **net use 접속 기능은
2026-09 에 전면 삭제**되었다 — 프로그램이 자격증명으로 관리공유에 로그온하는
동작 자체가 없어야 트로이/측면이동 오탐이 재발하지 않는다.

  ① net use 접속 기능(connect_admin_share 등)이 코드에 없어야 한다.
  ② 접속 UI 에 ID·비밀번호 입력칸이 없어야 한다(탐색기 세션만 사용).
  ③ 445 포트를 여러 대에 몰아서 두드리지 않는다(수평 포트 스캔 오탐).
  ④ 무인 수집에서 장비 사이에 간격을 둔다(측면 이동 스캔 오탐).
  ⑤ 비밀번호는 어디에도 저장/취급하지 않는다.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from param_manager import watcher  # noqa: E402

PASS = FAIL = 0
SRC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "param_manager")


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


def _src(name: str) -> str:
    with open(os.path.join(SRC_DIR, name), encoding="utf-8") as fh:
        return fh.read()


# --------------------------------------------------------------------------
def test_no_net_use_functions_in_collector():
    """collector 에 net use 접속 함수·명령이 남아 있지 않아야 한다."""
    src = _src("collector.py")
    assert "def connect_admin_share" not in src, "connect_admin_share 가 남아 있음"
    assert "def disconnect_admin_share" not in src, "disconnect_admin_share 가 남아 있음"
    assert '"net", "use"' not in src and '"net","use"' not in src, \
        "net use subprocess 호출이 남아 있음"
    print("  collector: net use 접속 함수/명령 없음 OK")


def _engine_sources():
    """v13: 웹 엔진(param_manager 전체) — tkinter 판은 삭제됨."""
    return {n: _src(n) for n in sorted(os.listdir(SRC_DIR)) if n.endswith(".py")}


def test_no_netuse_calls_anywhere():
    """전체 소스에서 net use 접속을 호출하는 코드가 없어야 한다."""
    for name, src in _engine_sources().items():
        assert "connect_admin_share(" not in src, f"{name}: connect_admin_share 호출 남음"
        assert "use_net_use=" not in src, f"{name}: use_net_use 인자 사용 남음"
        assert '"net", "use"' not in src and '"net","use"' not in src, f"{name}: net use 명령 남음"
    print("  connect_admin_share/use_net_use 호출 없음 OK")


def test_no_credentials_on_disk():
    """비밀번호를 config·감시설정 등 어디에도 저장/취급하지 않는다."""
    assert "password" not in _src("watcher.py").lower(), "watcher 에 비밀번호 흔적"
    assert "password" not in _src("desktop_watch.py").lower(), "desktop_watch 에 비밀번호 흔적"
    assert "password" not in _src("desktop_config.py").lower(), "desktop_config 에 비밀번호 흔적"
    print("  비밀번호 저장/취급 없음 OK")


def test_probe_has_gap_between_hosts():
    """445 포트를 연속으로 두드리지 않는다(포트 스캔 오탐 방지)."""
    assert watcher.PROBE_GAP_SEC > 0, "호스트 간 간격이 없음"
    src = _src("watcher.py")
    m = re.search(r"def check_connections.*?(?=\ndef )", src, re.S)
    assert m and "PROBE_GAP_SEC" in m.group(0) and "time.sleep" in m.group(0), \
        "check_connections 가 호스트 사이에 쉬지 않음"
    print(f"  연결 점검 호스트 간 간격 {watcher.PROBE_GAP_SEC}s OK")


def test_unattended_collect_has_gap_between_machines():
    """무인 수집(웹 엔진 자동 감시)도 장비 사이에 간격을 둔다(측면 이동 스캔 오탐 방지)."""
    from param_manager import desktop_watch
    assert desktop_watch.HOST_GAP_SEC > 0, "HOST_GAP_SEC 가 0"
    assert _src("desktop_watch.py").count("self.sleep(HOST_GAP_SEC)") >= 2, "장비 간 간격 호출이 빠짐"
    print(f"  무인 수집 장비 간 간격 {desktop_watch.HOST_GAP_SEC}s OK")


if __name__ == "__main__":
    for t in [test_no_net_use_functions_in_collector,
              test_no_netuse_calls_anywhere,
              test_no_credentials_on_disk,
              test_probe_has_gap_between_hosts,
              test_unattended_collect_has_gap_between_machines]:
        run(t)
    print(f"==== {PASS}/{PASS + FAIL} passed ====")
    sys.exit(1 if FAIL else 0)
