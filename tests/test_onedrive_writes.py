"""저장폴더(OneDrive)에 **쓰기를 최소화**하는 규칙 회귀 테스트.

배경(2026-08 실사고): 저장폴더가 OneDrive 라 파일 하나를 쓸 때마다 전원 PC로
동기화된다. 임시파일·중간 산물을 저장폴더에 만들었다가
'Unusual High-Volume Directory Access' 보안 경고를 받았다.

여기서는 그 재발을 막는 규칙을 코드 수준에서 고정한다.
  ① 양식 폴더는 **실제로 파일을 쓸 때만** 만든다(취소하면 빈 폴더가 남지 않게)
  ② 이미 내가 쥔 편집 잠금은 화면을 다시 그릴 때마다 다시 쓰지 않는다
  ③ 장비에서 긁어온 원본 ini(수십~수백 개)는 저장폴더에 복사하지 않는다
"""

import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from param_manager import locking, workdirs  # noqa: E402

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


# --------------------------------------------------------------------------
def test_form_dirs_not_created_until_write():
    """양식 만들기를 열었다가 취소해도 저장폴더에 빈 폴더가 생기면 안 된다."""
    with tempfile.TemporaryDirectory() as save_dir:
        run_dir = workdirs.form_run_dir(save_dir, "PI3", "20260806_1200", create=False)
        related = workdirs.related_dir(run_dir, create=False)
        assert not os.path.exists(os.path.join(save_dir, workdirs.FORM_DIR)), \
            "경로만 계산했는데 '양식' 폴더가 만들어짐"
        assert not os.path.exists(run_dir) and not os.path.exists(related)

        # 실제로 쓸 때(create=True)는 만들어져야 한다
        run_dir2 = workdirs.form_run_dir(save_dir, "PI3", "20260806_1200")
        assert os.path.isdir(run_dir2) and run_dir2 == run_dir
        assert os.path.isdir(workdirs.related_dir(run_dir2))
    print("  양식 폴더 지연 생성(취소 시 빈 폴더 없음) OK")


def test_repeat_acquire_does_not_rewrite_lock():
    """같은 화면을 다시 그릴 때마다 잠금 파일을 다시 쓰면 안 된다
    (쓰기 1회 = 전원 동기화 1회)."""
    import param_manager.engine as engine
    with tempfile.TemporaryDirectory() as tmp:
        doc = os.path.join(tmp, "특이사항.xlsx")
        open(doc, "w").close()
        st = locking.acquire(doc, "나")
        assert st.editable
        lock = engine.lock_path_for(doc)
        first = os.stat(lock).st_mtime_ns

        for _ in range(5):                       # 탭을 5번 다시 열어도
            st = locking.acquire(doc, "나")
            assert st.editable and st.status == "mine"
        assert os.stat(lock).st_mtime_ns == first, \
            "내 잠금인데 다시 기록됨(불필요한 OneDrive 쓰기)"

        # 만료가 가까우면(force) 당연히 갱신된다
        assert locking.refresh(doc, "나", force=True) is True
        assert os.stat(lock).st_mtime_ns != first
        locking.release(doc, "나")
    print("  내 잠금 반복 획득 시 재기록 없음 OK")


def _src(name: str) -> str:
    with open(os.path.join(SRC_DIR, name), encoding="utf-8") as fh:
        return fh.read()


if __name__ == "__main__":
    for t in [test_form_dirs_not_created_until_write,
              test_repeat_acquire_does_not_rewrite_lock]:
        run(t)
    print(f"==== {PASS}/{PASS + FAIL} passed ====")
    sys.exit(1 if FAIL else 0)
