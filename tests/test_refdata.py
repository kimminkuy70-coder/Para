"""refdata 테스트 — 장비 IP/참고자료(자유형)/특이사항 파일 + 셀 색상."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from param_manager import refdata  # noqa: E402


def test_ip_roundtrip_and_machines():
    with tempfile.TemporaryDirectory() as d:
        p = refdata.ip_path(d)
        refdata.create_blank_ip(p)
        assert refdata.load_ip(p) == []
        rows = [{"호기": "AOI-24", "IP": "10.0.0.24"},
                {"호기": "AOI-25", "IP": "10.0.0.25"}]
        refdata.save_ip(p, rows)
        back = refdata.load_ip(p)
        assert refdata.machines(back) == ["AOI-24", "AOI-25"]
        assert refdata.ip_for(back, "AOI-25") == "10.0.0.25"
        assert refdata.add_machine(back, "AOI-26", "10.0.0.26") is True
        assert refdata.add_machine(back, "AOI-24", "10.9.9.9") is False
        assert refdata.ip_for(back, "AOI-24") == "10.9.9.9"
        refdata.save_ip(p, back)
        assert refdata.machines(refdata.load_ip(p)) == ["AOI-24", "AOI-25", "AOI-26"]
    print("  refdata OK: 장비 IP 왕복 + 호기목록 + IP매칭 + 추가/갱신")


def test_reference_freeform_with_colors():
    with tempfile.TemporaryDirectory() as d:
        p = refdata.ref_path(d)
        refdata.create_blank_reference(p)
        grid, colors = refdata.load_reference(p)
        assert grid and grid[0] == refdata.REF_DEFAULT_HEADERS
        grid = [["구분", "내용", "비고"], ["점검", "노즐 상태 확인", "메모"]]
        refdata.save_reference(p, grid, colors={(1, 1): "#FFF24D"})
        g2, c2 = refdata.load_reference(p)
        assert g2[1][1] == "노즐 상태 확인"
        assert c2.get((1, 1)) == "#FFF24D"        # 색상 보존
    print("  refdata OK: 참고자료 자유형 그리드 + 셀 색상 저장/복원")


def test_special_with_colors():
    with tempfile.TemporaryDirectory() as d:
        p = refdata.special_path(d)
        refdata.create_blank_special(p)
        rows0, _ = refdata.load_special(p)
        assert rows0 == []
        rec = {h: None for h in refdata.SPECIAL_HEADERS}
        rec["호기"] = "AOI-24"
        rec["특이사항"] = "노즐 교체"
        rec[refdata.SPECIAL_BOOL_COL] = True
        refdata.save_special(p, [rec], colors={(0, 8): "#D9EAD3"})
        back, colors = refdata.load_special(p)
        assert len(back) == 1 and back[0]["호기"] == "AOI-24"
        assert back[0][refdata.SPECIAL_BOOL_COL] is True
        assert colors.get((0, 8)) == "#D9EAD3"
    print("  refdata OK: 특이사항 왕복(불리언) + 셀 색상")


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
