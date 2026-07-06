"""versioning 모듈 테스트 — 항상 새 버전 저장/목록/최신/라벨."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from param_manager import versioning  # noqa: E402


def _touch(path, text="x"):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def test_version_flow():
    with tempfile.TemporaryDirectory() as d:
        canon = os.path.join(d, "TB500_PI.xlsx")
        _touch(canon, "v0")
        assert versioning.list_versions(canon) == []
        assert versioning.latest_version(canon) is None
        assert versioning.next_version_number(canon) == 1

        p1 = versioning.save_new_version(canon, stamp="20260706_143000")
        assert os.path.isfile(p1)
        assert "_v001_" in os.path.basename(p1)
        assert versioning.next_version_number(canon) == 2

        _touch(canon, "v1")
        p2 = versioning.save_new_version(canon, stamp="20260706_143500")
        assert "_v002_" in os.path.basename(p2)

        vs = versioning.list_versions(canon)
        assert vs == [p1, p2]                       # 오래된→최신
        assert versioning.latest_version(canon) == p2

        # 같은 stamp 로 또 저장 → 충돌 회피 접미사
        p3 = versioning.save_new_version(canon, stamp="20260706_143500")
        assert p3 != p2 and os.path.isfile(p3)
        assert versioning.next_version_number(canon) == 4

        lbl = versioning.label_for(canon, p1)
        assert lbl.startswith("v001") and "2026-07-06 14:30:00" in lbl
    print("  versioning OK: 새버전 저장/번호증가/목록순서/충돌회피/라벨")


def test_isolation_between_stems():
    with tempfile.TemporaryDirectory() as d:
        pi = os.path.join(d, "TB500_PI.xlsx")
        rdl = os.path.join(d, "TB500_RDL.xlsx")
        _touch(pi); _touch(rdl)
        versioning.save_new_version(pi, stamp="20260706_143000")
        versioning.save_new_version(pi, stamp="20260706_143001")
        versioning.save_new_version(rdl, stamp="20260706_143002")
        assert len(versioning.list_versions(pi)) == 2
        assert len(versioning.list_versions(rdl)) == 1   # 서로 안 섞임
    print("  versioning OK: PI/RDL 버전 폴더 분리")


if __name__ == "__main__":
    fails = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(f"[RUN] {name}")
            try:
                fn()
                print(f"[PASS] {name}\n")
            except Exception as e:  # noqa: BLE001
                fails += 1
                print(f"[FAIL] {name}: {e}\n")
    total = sum(1 for n in globals() if n.startswith("test_"))
    print(f"==== {total - fails}/{total} passed ====")
    sys.exit(1 if fails else 0)
