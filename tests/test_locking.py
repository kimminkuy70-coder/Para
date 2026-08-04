"""locking.py 검증 — 문서 편집 잠금 + 접속자 세션(GUI 비의존).

'다른 사용자'는 잠금 파일을 직접 써서 흉내낸다(다른 host/pid).
"""

import json
import os
import socket
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from param_manager import engine, locking  # noqa: E402

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


def _write_other_lock(path, user="타인", host="PC-OTHER", pid=999999, when=None):
    """다른 사람이 잡은 잠금을 파일로 직접 생성."""
    payload = {"user": user, "host": host, "time": when or engine.now_str(), "pid": pid}
    with open(engine.lock_path_for(path), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)


def _doc(tmp, name="특이사항.xlsx"):
    p = os.path.join(tmp, name)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("dummy")
    return p


# --------------------------------------------------------------------------
def test_acquire_free_and_release():
    with tempfile.TemporaryDirectory() as tmp:
        doc = _doc(tmp)
        st = locking.acquire(doc, "홍길동")
        assert st.status == "mine" and st.editable, st
        assert os.path.exists(engine.lock_path_for(doc))
        # 같은 사람이 다시 획득해도 mine(갱신)
        st2 = locking.acquire(doc, "홍길동")
        assert st2.status == "mine" and st2.editable
        locking.release(doc, "홍길동")
        assert not os.path.exists(engine.lock_path_for(doc))
    print("  잠금 획득→갱신→해제 OK")


def test_other_holder_is_read_only():
    with tempfile.TemporaryDirectory() as tmp:
        doc = _doc(tmp)
        _write_other_lock(doc, user="김철수", host="PC-07")
        st = locking.acquire(doc, "홍길동")
        assert st.status == "other" and not st.editable, st
        assert st.held_by_other
        msg = locking.holder_message(st, "특이사항")
        assert "김철수" in msg and "읽기 전용" in msg, msg
        # 타인 잠금은 해제되지 않아야 한다
        locking.release(doc, "홍길동")
        assert os.path.exists(engine.lock_path_for(doc))
    print("  타인 보유 → 읽기 전용 + 안내문 + 남의 잠금 해제 안 함 OK")


def test_stale_lock_needs_takeover():
    with tempfile.TemporaryDirectory() as tmp:
        doc = _doc(tmp)
        old = "2000-01-01 00:00:00"                 # 아주 오래된 잠금
        _write_other_lock(doc, user="김철수", host="PC-07", when=old)
        st = locking.acquire(doc, "홍길동")          # takeover 없이
        assert st.status == "stale" and not st.editable, st
        assert "이어받" in locking.holder_message(st, "특이사항")
        st2 = locking.acquire(doc, "홍길동", takeover=True)
        assert st2.status == "mine" and st2.editable, st2
    print("  만료 잠금: 기본은 읽기전용, takeover=True 로 인수 OK")


def test_self_other_process_reclaims():
    """같은 사람·같은 PC의 죽은 프로세스 잠금은 바로 이어받는다.
    (안 그러면 비정상 종료 후 30분간 자기 문서에 못 들어간다.)"""
    with tempfile.TemporaryDirectory() as tmp:
        doc = _doc(tmp)
        _write_other_lock(doc, user="홍길동", host=socket.gethostname(),
                          pid=os.getpid() + 12345)   # 같은 사람, 다른 프로세스
        st = locking.status(doc, "홍길동")
        assert st.status == "self", st
        got = locking.acquire(doc, "홍길동")          # takeover 없이도 획득
        assert got.status == "mine" and got.editable, got
    print("  같은 사람·다른 프로세스 잠금 자동 인수 OK")


def test_refresh_only_when_mine():
    with tempfile.TemporaryDirectory() as tmp:
        doc = _doc(tmp)
        locking.acquire(doc, "홍길동")
        assert locking.refresh(doc, "홍길동") is True
        _write_other_lock(doc, user="김철수", host="PC-07")
        assert locking.refresh(doc, "홍길동") is False   # 남의 잠금은 갱신 못함
    print("  잠금 갱신은 내 것일 때만 OK")


def test_check_before_save_detects_external_change():
    with tempfile.TemporaryDirectory() as tmp:
        doc = _doc(tmp)
        locking.acquire(doc, "홍길동")
        stamp = locking.file_stamp(doc)
        chk = locking.check_before_save(doc, "홍길동", stamp)
        assert chk["ok"] and not chk["changed"], chk
        # 다른 사람이 먼저 저장한 상황
        time.sleep(0.01)
        with open(doc, "w", encoding="utf-8") as fh:
            fh.write("다른 사람이 저장한 내용")
        chk2 = locking.check_before_save(doc, "홍길동", stamp)
        assert chk2["changed"] and not chk2["ok"], chk2
        assert "먼저 저장" in chk2["reason"], chk2["reason"]
    print("  저장 직전 재검증: 외부 변경 감지 OK(덮어쓰기 손실 방어)")


def test_check_before_save_detects_lock_takeover():
    with tempfile.TemporaryDirectory() as tmp:
        doc = _doc(tmp)
        locking.acquire(doc, "홍길동")
        stamp = locking.file_stamp(doc)
        _write_other_lock(doc, user="김철수", host="PC-07")   # 잠금이 넘어감
        chk = locking.check_before_save(doc, "홍길동", stamp)
        assert not chk["ok"] and "김철수" in chk["reason"], chk
    print("  저장 직전 재검증: 잠금 탈취 감지 OK")


def test_global_lock_single_runner():
    """자동 감시는 여러 PC 동시 실행 금지 — 전역 잠금."""
    with tempfile.TemporaryDirectory() as tmp:
        st = locking.acquire_global(tmp, locking.GLOBAL_WATCHER, "홍길동")
        assert st.status == "mine" and st.editable, st
        gp = locking.global_lock_path(tmp, locking.GLOBAL_WATCHER)
        _write_other_lock(gp, user="김철수", host="PC-07")
        st2 = locking.acquire_global(tmp, locking.GLOBAL_WATCHER, "홍길동")
        assert st2.status == "other" and not st2.editable, st2
        assert "김철수" in locking.holder_message(st2, "자동 감시")
    print("  전역 감시 잠금: 2번째 PC 실행 차단 OK")


def test_sessions_list_and_prune():
    with tempfile.TemporaryDirectory() as tmp:
        locking.touch_session(tmp, "홍길동", screen="특이사항")
        got = locking.list_sessions(tmp)
        assert len(got) == 1 and got[0].user == "홍길동", got
        assert got[0].screen == "특이사항"
        # 만료 세션(오래된 last_seen) 추가 → 목록에서 빠지고 prune 으로 삭제
        d = locking.sessions_dir(tmp)
        with open(os.path.join(d, "old@PC-9#1.json"), "w", encoding="utf-8") as fh:
            json.dump({"user": "옛사람", "host": "PC-9", "pid": 1,
                       "started": "2000-01-01 00:00:00",
                       "last_seen": "2000-01-01 00:00:00"}, fh, ensure_ascii=False)
        assert len(locking.list_sessions(tmp)) == 1                  # 만료 제외
        assert len(locking.list_sessions(tmp, include_stale=True)) == 2
        assert locking.prune_sessions(tmp) == 1
        assert len(locking.list_sessions(tmp, include_stale=True)) == 1
        locking.end_session(tmp, "홍길동")
        assert locking.list_sessions(tmp, include_stale=True) == []
    print("  접속자 세션: 등록·목록·만료제외·정리·종료 OK")


def test_others_message_excludes_me():
    with tempfile.TemporaryDirectory() as tmp:
        locking.touch_session(tmp, "홍길동")
        assert locking.others_message(tmp, "홍길동") == ""     # 나뿐이면 빈 문자열
        d = locking.sessions_dir(tmp)
        with open(os.path.join(d, "kim@PC-07#5.json"), "w", encoding="utf-8") as fh:
            json.dump({"user": "김철수", "host": "PC-07", "pid": 5,
                       "started": engine.now_str(),
                       "last_seen": engine.now_str()}, fh, ensure_ascii=False)
        msg = locking.others_message(tmp, "홍길동")
        assert "김철수(PC-07)" in msg and "홍길동" not in msg, msg
    print("  접속자 요약: 나 제외 표기 OK")


def test_release_all_is_forgiving():
    """앱 종료 시 일괄 해제 — 없는 경로가 섞여도 예외 없이 나머지를 해제."""
    with tempfile.TemporaryDirectory() as tmp:
        a, b = _doc(tmp, "a.xlsx"), _doc(tmp, "b.xlsx")
        locking.acquire(a, "홍길동")
        locking.acquire(b, "홍길동")
        locking.release_all([a, os.path.join(tmp, "없는파일.xlsx"), b], "홍길동")
        assert not os.path.exists(engine.lock_path_for(a))
        assert not os.path.exists(engine.lock_path_for(b))
    print("  종료 시 일괄 해제(예외 없음) OK")


if __name__ == "__main__":
    for t in [test_acquire_free_and_release, test_other_holder_is_read_only,
              test_stale_lock_needs_takeover, test_self_other_process_reclaims,
              test_refresh_only_when_mine,
              test_check_before_save_detects_external_change,
              test_check_before_save_detects_lock_takeover,
              test_global_lock_single_runner, test_sessions_list_and_prune,
              test_others_message_excludes_me, test_release_all_is_forgiving]:
        run(t)
    print(f"==== {PASS}/{PASS + FAIL} passed ====")
    sys.exit(1 if FAIL else 0)
