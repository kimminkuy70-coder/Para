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


def test_equipment_staging_never_targets_save_dir():
    """수집(staging)은 반드시 로컬(localdirs) 로만 간다.

    `_collect_dialog(staging_root, ...)` 의 첫 인자가 저장폴더 경로
    (`related`/`workdirs.*`)이면 장비의 ini 수십~수백 개가 OneDrive 로 복사돼
    사고가 재발한다. 소스 수준에서 고정한다.
    """
    src = _src("equip_app.py")
    # 정의부(def _collect_dialog(self, …))가 아니라 **호출부**만 본다
    calls = re.findall(r"self\._collect_dialog\(\s*\n?\s*([A-Za-z_][\w\.\[\]\"']*)", src)
    assert calls, "_collect_dialog 호출을 찾지 못함(테스트가 낡음)"
    for arg in calls:
        assert not arg.startswith("workdirs."), \
            f"수집 staging 이 저장폴더 경로: {arg}"
        assert arg not in ("related", "run_dir", "self.save_dir"), \
            f"수집 staging 이 저장폴더 경로: {arg}"
    # 실제로 로컬 임시폴더를 쓰는 호출이 있어야 한다
    assert re.search(r"staging\s*=\s*localdirs\.new_temp_run", src), \
        "로컬 임시 staging 사용 흔적이 없음"
    print(f"  수집 staging = 로컬 전용 OK (호출 {len(calls)}곳 확인: {calls})")


def test_commonality_outputs_stay_local():
    """Commonality 산출물(Lot 안전복사본 다수)은 저장폴더에 두지 않는다."""
    src = _src("equip_app.py")
    for m in re.finditer(r"workdirs\.commonality_\w+\(\s*([^,\)]+)", src):
        arg = m.group(1).strip()
        assert "save_dir" not in arg, f"Commonality 경로가 저장폴더 기준: {arg}"
    print("  Commonality 산출물 = 로컬 전용 OK")


def test_watch_cycle_writes_collation_only_on_change():
    """무인 회차는 하루 몇 번씩 돈다 — 변경이 없으면 취합 엑셀을 저장폴더에
    새로 만들지 않는다(같은 내용 파일이 쌓이는 것 = 순수 동기화 낭비)."""
    src = _src("equip_app.py")
    m = re.search(r"def _watch_cycle_work.*?(?=\n    def )", src, re.S)
    assert m, "_watch_cycle_work 를 찾지 못함"
    body = m.group(0)
    assert "localdirs.new_temp_run" in body, "회차 취합본을 로컬에 먼저 쓰지 않음"
    assert re.search(r"if res\.has_change or not prev", body), \
        "변경이 있을 때만 저장폴더로 옮기는 분기가 없음"
    print("  무인 회차: 변경 있을 때만 저장폴더에 취합본 생성 OK")


if __name__ == "__main__":
    for t in [test_form_dirs_not_created_until_write,
              test_repeat_acquire_does_not_rewrite_lock,
              test_equipment_staging_never_targets_save_dir,
              test_commonality_outputs_stay_local,
              test_watch_cycle_writes_collation_only_on_change]:
        run(t)
    print(f"==== {PASS}/{PASS + FAIL} passed ====")
    sys.exit(1 if FAIL else 0)
