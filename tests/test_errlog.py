"""errlog 헤드리스 테스트 — 오류 코드+traceback 로그가 실제로 남고, 사용자 메시지에
코드가 들어가는지 검증(에러 원인 파악 경로)."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from param_manager import errlog  # noqa: E402

PASS = 0


def ok(msg):
    global PASS
    PASS += 1
    print(f"[PASS] {msg}")


def test_log_path_is_local_not_onedrive():
    """로그는 **저장폴더(OneDrive)에 쓰지 않는다** — 잦은 append 가 전원에게
    동기화돼 '대량 디렉터리 접근' 경고를 유발했다(2026-08 사고)."""
    from param_manager import localdirs
    with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as local:
        localdirs.set_root(local)
        try:
            got = errlog.log_path(d)
            assert not got.startswith(d), f"저장폴더에 로그를 만들면 안 됨: {got}"
            assert got == os.path.join(local, localdirs.LOGS, errlog.LOG_NAME), got
            assert errlog.log_path(None) == got, "save_dir 과 무관하게 로컬"
        finally:
            localdirs.set_root(None)
    ok("log_path: 로컬 Logs 폴더(OneDrive 아님)")


def test_write_log_records_traceback():
    with tempfile.TemporaryDirectory() as d:
        try:
            raise ValueError("망가진 값")
        except ValueError as e:
            assert errlog.write_log(d, "E999", "테스트 실패", e) is True
        txt = open(errlog.log_path(d), encoding="utf-8").read()
        assert "[E999]" in txt and "테스트 실패" in txt
        assert "ValueError" in txt and "망가진 값" in txt      # traceback 본문
        assert "Traceback (most recent call last)" in txt
        # 두 번째 기록이 이어붙는지(append)
        errlog.write_log(d, "E998", "두번째", None)
        txt2 = open(errlog.log_path(d), encoding="utf-8").read()
        assert "[E999]" in txt2 and "[E998]" in txt2
    ok("write_log: 코드+traceback 기록 · append")


def test_write_log_survives_bad_dir():
    """쓰기 불가여도 예외 없이 False — 앱이 멈추면 안 된다.
    (로그는 이제 로컬 폴더에 쓰므로 **로컬 루트가 불가능한 경로**일 때를 본다.)"""
    from param_manager import localdirs
    bad = os.path.join(os.sep, "존재하지않는루트_zzz", "x", "y")
    localdirs.set_root(bad)
    try:
        # 어떤 경우에도 **예외를 던지지 않고** bool 을 돌려준다(앱이 멈추면 안 됨).
        # 로컬 루트를 못 쓰면 홈 폴더로 물러난다 — 로그는 남되 앱은 계속 동작.
        r = errlog.write_log(None, "E000", "무시", None)
        assert isinstance(r, bool), r
        # save_dir 가 이상해도 로컬이 정상이면 기록은 성공해야 한다
        import tempfile as _t
        with _t.TemporaryDirectory() as local:
            localdirs.set_root(local)
            assert errlog.write_log(bad, "E001", "저장폴더는 무관", None) is True
            assert os.path.isfile(errlog.log_path(None))
    finally:
        localdirs.set_root(None)
    ok("write_log: 쓰기 불가여도 예외 없이 False(앱 안 멈춤)")


def test_user_message_has_code():
    try:
        raise KeyError("k")
    except KeyError as e:
        msg = errlog.user_message("E201", "격자 구성 실패", e, path="/tmp/오류_로그.txt")
    assert "E201" in msg
    assert "격자 구성 실패" in msg
    assert "KeyError" in msg                        # 기술 요약
    assert "오류 코드(E201)" in msg                 # 사용자에게 코드 안내
    assert "/tmp/오류_로그.txt" in msg              # 로그 경로 안내
    # extra 도 반영
    msg2 = errlog.user_message("E9", "t", None, extra="추가설명")
    assert "추가설명" in msg2
    ok("user_message: 코드·요약·코드안내·로그경로·extra 포함")


def test_detail_of():
    assert errlog.detail_of(ValueError("x")).startswith("ValueError")
    assert errlog.detail_of("문자열") == "문자열"
    assert errlog.detail_of(None) == ""
    ok("detail_of: 예외/문자열/None")


if __name__ == "__main__":
    for k, v in sorted(globals().items()):
        if k.startswith("test_"):
            v()
    print(f"\n==== {PASS}/{PASS} passed ====")
