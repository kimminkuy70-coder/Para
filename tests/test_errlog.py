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


def test_log_path():
    with tempfile.TemporaryDirectory() as d:
        assert errlog.log_path(d) == os.path.join(d, errlog.LOG_NAME)
    # 저장폴더 없으면 홈
    assert errlog.log_path(None).endswith(errlog.LOG_NAME)
    ok("log_path: 저장폴더 안 / 홈 폴백")


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
    # 존재할 수 없는 경로 → 예외 없이 False
    bad = os.path.join(os.sep, "존재하지않는루트_zzz", "x", "y")
    assert errlog.write_log(bad, "E000", "무시", None) is False
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
