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


def test_no_netuse_calls_anywhere():
    """전체 소스에서 net use 접속을 호출하는 코드가 없어야 한다."""
    for name in ("equip_app.py", "collector.py", "watcher.py", "cmwatcher.py"):
        src = _src(name)
        assert "connect_admin_share(" not in src, f"{name}: connect_admin_share 호출 남음"
        assert "use_net_use=" not in src, f"{name}: use_net_use 인자 사용 남음"
    print("  connect_admin_share/use_net_use 호출 없음 OK")


def test_collect_dialog_has_no_password_ui():
    """수동 수집창(양식 만들기)에 ID·비밀번호 입력칸과 net use 체크가 없어야 한다."""
    src = _src("equip_app.py")
    m = re.search(r"def _collect_dialog.*?(?=\n    def )", src, re.S)
    assert m, "_collect_dialog 를 찾지 못함"
    body = m.group(0)
    assert 'show="*"' not in body and 'show="•"' not in body, "비밀번호 입력칸이 남아 있음"
    assert "net_var" not in body, "net use 체크박스가 남아 있음"
    assert "login_id_for" not in body and "set_login_id" not in body, \
        "접속 ID 처리가 남아 있음"
    print("  수동 수집창: 비밀번호/net use/접속ID UI 없음 OK")


def test_watch_collect_uses_session_only():
    """무인 수집이 net use 없이 탐색기 세션만 쓰는지(자격증명 미취급)."""
    src = _src("equip_app.py")
    m = re.search(r"def _watch_collect.*?(?=\n    def )", src, re.S)
    assert m, "_watch_collect 를 찾지 못함"
    body = m.group(0)
    for gone in ("all_creds", "netuse_mode", "use_netuse", "_watch_cred"):
        assert gone not in body, f"무인 수집에 net use 흔적 남음: {gone}"
    print("  무인 수집: 세션 전용(net use 흔적 없음) OK")


def test_no_credentials_on_disk():
    """비밀번호를 config·감시설정 등 어디에도 저장/취급하지 않는다."""
    app = _src("equip_app.py")
    assert "password" not in _src("watcher.py").lower(), "watcher 에 비밀번호 흔적"
    assert "_watch_cred" not in app, "메모리 접속 정보(_watch_cred) 가 아직 남아 있음"
    assert not re.search(r'_cfg\[[^\]]*(pw|pass|비밀번호)', app, re.I), \
        "config 에 비밀번호를 저장하고 있음"
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
    """무인 수집도 장비 사이에 간격을 둔다(측면 이동 스캔 오탐 방지)."""
    src = _src("equip_app.py")
    gap = re.search(r"^HOST_GAP_SEC\s*=\s*([\d.]+)", src, re.M)
    assert gap and float(gap.group(1)) > 0, "HOST_GAP_SEC 상수가 없거나 0"
    m = re.search(r"def _watch_collect.*?(?=\n    def )", src, re.S)
    assert m and "HOST_GAP_SEC" in m.group(0), "_watch_collect 에 장비 간 간격 없음"
    print(f"  무인 수집 장비 간 간격 {gap.group(1)}s OK")


def test_manual_install_path_exists():
    """자동 교체(백신 행위탐지 대상)를 피하고 싶을 때 직접 설치 경로가 있어야 한다."""
    src = _src("equip_app.py")
    assert "_open_program_dir" in src, "직접 설치(게시 폴더 열기) 경로가 없음"
    assert "askyesnocancel" in src, "자동 교체 외 선택지가 없음"
    print("  업데이트: 자동 교체 / 직접 설치 선택 가능 OK")


if __name__ == "__main__":
    for t in [test_no_net_use_functions_in_collector,
              test_no_netuse_calls_anywhere,
              test_collect_dialog_has_no_password_ui,
              test_watch_collect_uses_session_only,
              test_no_credentials_on_disk,
              test_probe_has_gap_between_hosts,
              test_unattended_collect_has_gap_between_machines,
              test_manual_install_path_exists]:
        run(t)
    print(f"==== {PASS}/{PASS + FAIL} passed ====")
    sys.exit(1 if FAIL else 0)
