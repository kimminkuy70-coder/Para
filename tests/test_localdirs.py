"""localdirs.py 검증 — 임시/로그를 OneDrive 밖에 두기 위한 로컬 작업 폴더.

배경: 저장폴더(OneDrive) 안에 임시파일을 만들자 동기화가 폭주해 보안 시스템이
'Unusual High-Volume Directory Access' 로 탐지한 사고가 있었다(2026-08).
"""

import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from param_manager import localdirs as L  # noqa: E402

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
def test_structure_created():
    """폴더 구조는 한 곳에서만 만든다 — Temp/Logs/Cache."""
    with tempfile.TemporaryDirectory() as tmp:
        root = L.ensure(os.path.join(tmp, "CamtekAOI"))
        assert sorted(os.listdir(root)) == ["Cache", "Logs", "Temp"]
        assert L.temp_dir(root).endswith(L.TEMP)
        assert L.logs_dir(root).endswith(L.LOGS)
        L.ensure(root)                       # 반복 호출해도 안전
        assert sorted(os.listdir(root)) == ["Cache", "Logs", "Temp"]
    print("  Temp/Logs/Cache 생성(멱등) OK")


def test_default_root_is_not_synced():
    """기본 위치는 동기화 대상이 아닌 로컬 앱 폴더."""
    root = L.default_root()
    assert root.endswith(L.APP_DIRNAME), root
    assert not L.is_under_onedrive(root), root
    print(f"  기본 위치 OK ({root})")


def test_onedrive_detection():
    """로컬 폴더를 실수로 OneDrive 안에 잡으면 경고할 수 있어야 한다."""
    assert L.is_under_onedrive(r"C:\\Users\\a\\OneDrive\\취합") is True
    assert L.is_under_onedrive(r"C:\\Users\\a\\OneDrive - Amkor\\x") is True
    assert L.is_under_onedrive(r"C:\\Users\\a\\AppData\\Local\\CamtekAOI") is False
    assert L.is_under_onedrive("") is False
    print("  OneDrive 경로 판정 OK")


def test_temp_run_and_drop():
    """회차 폴더를 만들고, 끝나면 지운다(누적 방지)."""
    with tempfile.TemporaryDirectory() as tmp:
        root = L.ensure(os.path.join(tmp, "CamtekAOI"))
        run_dir = L.new_temp_run(root, "감시")
        assert os.path.isdir(run_dir)
        assert os.path.basename(run_dir).startswith("감시_")
        with open(os.path.join(run_dir, "GlobalRTP.ini"), "w", encoding="utf-8") as fh:
            fh.write("[A]\nx=1\n")
        assert L.drop(run_dir) is True
        assert not os.path.isdir(run_dir)
    print("  회차 폴더 생성·삭제 OK")


def test_drop_refuses_outside_temp():
    """Temp 밖 경로는 절대 지우지 않는다(실수로 저장폴더를 지우면 큰일)."""
    with tempfile.TemporaryDirectory() as tmp:
        root = L.ensure(os.path.join(tmp, "CamtekAOI"))
        logs = L.logs_dir(root)
        assert L.drop(logs) is False and os.path.isdir(logs)
        assert L.drop(root) is False and os.path.isdir(root)
        outside = os.path.join(tmp, "저장폴더")
        os.makedirs(outside, exist_ok=True)
        assert L.drop(outside) is False and os.path.isdir(outside)
        assert L.drop("") is False
    print("  Temp 밖 삭제 거부 OK")


def test_cleanup_keeps_recent():
    """비정상 종료로 남은 오래된 회차만 지우고, 작업 중인 최근 것은 남긴다."""
    with tempfile.TemporaryDirectory() as tmp:
        root = L.ensure(os.path.join(tmp, "CamtekAOI"))
        fresh = L.new_temp_run(root, "수집")
        old = os.path.join(L.temp_dir(root), "수집_20200101_000000")
        os.makedirs(old, exist_ok=True)
        past = time.time() - 24 * 3600
        os.utime(old, (past, past))
        assert L.cleanup_temp(root, keep_hours=6) == 1
        assert not os.path.isdir(old), "오래된 회차는 지워야 함"
        assert os.path.isdir(fresh), "최근(작업 중) 회차는 남겨야 함"
        # keep_hours=0 이면 전부 정리(사용자가 '비우기' 누른 경우)
        assert L.cleanup_temp(root, keep_hours=0) == 1
        assert not os.path.isdir(fresh)
    print("  오래된 회차만 정리 / 전체 비우기 OK")


def test_active_root_override():
    """앱이 설정한 위치를 다른 모듈(errlog 등)도 같이 쓴다."""
    try:
        assert L.active_root() == L.default_root()
        L.set_root("/tmp/여기")
        assert L.active_root() == "/tmp/여기"
    finally:
        L.set_root(None)
    assert L.active_root() == L.default_root()
    print("  활성 루트 등록/복원 OK")


def test_describe():
    with tempfile.TemporaryDirectory() as tmp:
        root = L.ensure(os.path.join(tmp, "CamtekAOI"))
        assert "0개" in L.describe(root)
        d = L.new_temp_run(root, "감시")
        with open(os.path.join(d, "a.ini"), "wb") as fh:
            fh.write(b"x" * 2048)
        assert "1개" in L.describe(root)
    print("  용량·개수 요약 OK")


if __name__ == "__main__":
    for t in [test_structure_created, test_default_root_is_not_synced,
              test_onedrive_detection, test_temp_run_and_drop,
              test_drop_refuses_outside_temp, test_cleanup_keeps_recent,
              test_active_root_override, test_describe]:
        run(t)
    print(f"==== {PASS}/{PASS + FAIL} passed ====")
    sys.exit(1 if FAIL else 0)
