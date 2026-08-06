"""사내 보안 모니터링(EDR/SIEM/네트워크 장비)에 오탐되지 않기 위한 규칙.

장비 접속은 `\\IP\\c$`(관리공유)라 원래 감시 대상이다. 기능은 그대로 두되
**패턴이 공격처럼 보이지 않게** 하는 규칙을 고정한다.

  ① 빈 비밀번호로 net use 를 시도하지 않는다
     — 장비마다 로그온 실패(4625)가 쌓이면 무차별 대입/패스워드 스프레이로
       탐지되고, 공용 계정이 잠기면 실제 운영이 멈춘다.
  ② 445 포트를 여러 대에 몰아서 두드리지 않는다(수평 포트 스캔 오탐).
  ③ 무인 수집에서 장비 사이에 간격을 둔다(측면 이동 스캔 오탐).
  ④ 비밀번호는 디스크에 저장하지 않는다.
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
def test_never_connects_with_empty_password():
    """`connect_admin_share(ip, id, "")` 처럼 **빈 비밀번호 고정 호출**이 없어야 한다."""
    src = _src("equip_app.py")
    calls = re.findall(r"connect_admin_share\(([^)]*)\)", src)
    assert calls, "connect_admin_share 호출을 찾지 못함(테스트가 낡음)"
    for args in calls:
        assert not re.search(r',\s*""\s*\)?$', args.strip()), \
            f"빈 비밀번호로 net use 시도: connect_admin_share({args})"
        assert '"amkor"' not in args or "cred" in args, \
            f"하드코딩 계정으로 접속 시도: connect_admin_share({args})"
    print(f"  빈 비밀번호/하드코딩 접속 없음 OK (호출 {len(calls)}곳)")


def test_netuse_requires_credential_in_memory():
    """접속 정보가 메모리에 없으면 net use 모드여도 시도하지 않는다."""
    src = _src("equip_app.py")
    m = re.search(r"def _watch_collect.*?(?=\n    def )", src, re.S)
    assert m, "_watch_collect 를 찾지 못함"
    body = m.group(0)
    assert re.search(r"use_netuse\s*=\s*\(s\.conn_mode == watcher\.CONN_NETUSE"
                     r"\s*and\s*bool\(cred\)\)", body), \
        "접속 정보 없이도 net use 를 켜고 있음"
    print("  net use 는 메모리 접속 정보가 있을 때만 OK")


def test_credentials_never_written_to_disk():
    """비밀번호가 설정 파일·감시설정에 저장되지 않아야 한다."""
    app = _src("equip_app.py")
    # 저장 payload 를 만드는 곳에 비밀번호 키가 없어야 한다
    for name in ("watcher.py",):
        assert "password" not in _src(name).lower(), \
            f"{name} 에 비밀번호 저장 흔적"
    assert "_watch_cred" in app, "메모리 전용 접속 정보 보관이 없음"
    assert not re.search(r'_cfg\[[^\]]*(pw|pass|비밀번호)', app, re.I), \
        "config 에 비밀번호를 저장하고 있음"
    assert not re.search(r'save_config\([^)]*(pw|password)', app, re.I)
    print("  비밀번호 디스크 저장 없음 OK")


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
    # equip_app 은 tkinter 의존이라 개발환경에서 import 할 수 없다 → 소스로 확인
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
    for t in [test_never_connects_with_empty_password,
              test_netuse_requires_credential_in_memory,
              test_credentials_never_written_to_disk,
              test_probe_has_gap_between_hosts,
              test_unattended_collect_has_gap_between_machines,
              test_manual_install_path_exists]:
        run(t)
    print(f"==== {PASS}/{PASS + FAIL} passed ====")
    sys.exit(1 if FAIL else 0)
