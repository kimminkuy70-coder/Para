"""collector 안전장치 회귀 테스트 — 원본(장비) 보호.

핵심 불변식(장비 레시피 에러 원인 점검 후 추가):
  1) 쓰기 대상(staging)은 반드시 로컬. 네트워크(UNC `\\\\`, `//`) 경로면 거부.
  2) copy_planned 는 원본을 읽기만 하고, 로컬 dest 에만 쓴다. 원본을 수정/삭제/이동하지 않는다.
  3) 원본과 동일 경로에 쓰려 하면(dest==src) 거부.
  4) COPY_DELAY_SEC 지연은 그대로 유지(장비망 부하 완화).
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from param_manager import collector  # noqa: E402


def test_reject_unc_staging():
    """UNC(네트워크) staging 대상은 거부 → 장비 원본 폴더에 쓰지 못하게 차단."""
    for bad in (r"\\10.0.0.1\c$\Job", "//10.0.0.1/c$/Job"):
        try:
            collector._assert_local_write_target(Path(bad))
        except RuntimeError:
            pass
        else:
            raise AssertionError(f"UNC 경로를 거부하지 않음: {bad}")
    # 로컬 경로는 통과해야 한다
    with tempfile.TemporaryDirectory() as tmp:
        collector._assert_local_write_target(Path(tmp))
    print("  collector OK: UNC staging 거부 + 로컬 통과")


def test_copy_is_read_only_on_source():
    """copy_planned: 원본은 읽기만(내용/개수/mtime 보존), 사본은 로컬에만 생성."""
    with tempfile.TemporaryDirectory() as tmp:
        src_root = Path(tmp) / "장비원본" / "PI3"
        src_root.mkdir(parents=True)
        f1 = src_root / "GlobalRTP.ini"
        f1.write_text("[G]\nA = 1\n", encoding="utf-8")
        (src_root / "Zones").mkdir()
        f2 = src_root / "Zones" / "Z.ini"
        f2.write_text("[S]\nHigh = 25\n", encoding="utf-8")

        before = {p: (p.read_bytes(), p.stat().st_mtime_ns)
                  for p in (f1, f2)}
        src_names_before = sorted(p.name for p in src_root.rglob("*"))

        planned = collector.plan_files([src_root])
        staging = Path(tmp) / "staging"
        copied, log = collector.copy_planned(planned, staging)

        assert copied == 2, f"복사 개수 {copied}"
        # 원본 불변: 내용·mtime 그대로, 추가/삭제/이름변경 없음
        for p, (content, mtime) in before.items():
            assert p.exists(), f"원본 사라짐: {p}"
            assert p.read_bytes() == content, f"원본 내용 변경됨: {p}"
            assert p.stat().st_mtime_ns == mtime, f"원본 mtime 변경됨: {p}"
        assert sorted(p.name for p in src_root.rglob("*")) == src_names_before, \
            "원본 폴더 구성이 바뀜(추가/삭제)"
        # 사본은 로컬 staging 에만
        assert log.exists() and str(log).startswith(str(staging))
        assert (staging / "PI3" / "GlobalRTP.ini").read_text(encoding="utf-8") \
            == "[G]\nA = 1\n"
    print("  collector OK: 원본 읽기전용 보존 + 사본은 로컬 staging")


def test_source_never_overwritten_even_if_staging_is_source_dir():
    """staging 을 실수로 원본 폴더로 지정해도 원본은 절대 덮어써지지 않는다.

    이중 안전장치: (a) dest 가 이미 있으면 `_N` 로 사본을 만들고,
    (b) 그래도 dest==src 면 RuntimeError. 어느 경로든 원본 내용은 보존된다.
    """
    with tempfile.TemporaryDirectory() as tmp:
        rec = Path(tmp) / "R" / "PI3"
        rec.mkdir(parents=True)
        f = rec / "GlobalRTP.ini"
        f.write_text("ORIGINAL", encoding="utf-8")
        before = (f.read_bytes(), f.stat().st_mtime_ns)
        planned = [(f, "PI3", "GlobalRTP.ini")]
        staging = Path(tmp) / "R"      # dest 후보 = R/PI3/GlobalRTP.ini == 원본
        collector.copy_planned(planned, staging)
        # 원본은 그대로여야 한다(내용·mtime 불변)
        assert f.read_bytes() == before[0], "원본 내용이 변경됨"
        assert f.stat().st_mtime_ns == before[1], "원본 mtime 이 변경됨"
    print("  collector OK: staging==원본폴더라도 원본 보존(사본만 추가)")


if __name__ == "__main__":
    fails = 0
    tests = [(n, f) for n, f in list(globals().items())
             if n.startswith("test_") and callable(f)]
    for name, fn in tests:
        print(f"[RUN] {name}")
        try:
            fn()
            print(f"[PASS] {name}\n")
        except Exception as e:  # noqa: BLE001
            fails += 1
            import traceback
            traceback.print_exc()
            print(f"[FAIL] {name}: {e}\n")
    print(f"==== {len(tests) - fails}/{len(tests)} passed ====")
    sys.exit(1 if fails else 0)
