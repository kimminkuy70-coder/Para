"""refdata 테스트 — 참고자료/특이사항 독립 파일 I/O + 호기·IP 연동."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from param_manager import refdata  # noqa: E402


def test_reference_roundtrip_and_machines():
    with tempfile.TemporaryDirectory() as d:
        p = refdata.ref_path(d)
        refdata.create_blank_reference(p)
        rows = refdata.load_reference(p)
        assert rows == []
        rows = [{"호기": "AOI-24", "IP": "10.1.1.24", "비고": "메인"},
                {"호기": "AOI-25", "IP": "10.1.1.25", "비고": ""}]
        refdata.save_reference(p, rows)
        back = refdata.load_reference(p)
        assert refdata.machines(back) == ["AOI-24", "AOI-25"]
        assert refdata.ip_for(back, "AOI-25") == "10.1.1.25"

        # 호기 추가(신규) + 기존 IP 갱신
        assert refdata.add_machine(back, "AOI-26", "10.1.1.26") is True
        assert refdata.add_machine(back, "AOI-24", "10.9.9.9") is False   # 기존 → IP만
        assert refdata.ip_for(back, "AOI-24") == "10.9.9.9"
        refdata.save_reference(p, back)
        assert refdata.machines(refdata.load_reference(p)) == \
            ["AOI-24", "AOI-25", "AOI-26"]
    print("  refdata OK: 참고자료 왕복 + 호기목록 + IP매칭 + 호기추가/갱신")


def test_reference_freeform_fallback():
    """헤더가 없거나 다른 자유 양식도 첫 셀=호기, 둘째=IP 폴백."""
    import openpyxl
    with tempfile.TemporaryDirectory() as d:
        p = refdata.ref_path(d)
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["장비", "주소", "설명"])          # 비표준 헤더
        ws.append(["AOI-30", "10.2.2.30", "라인A"])
        wb.save(p)
        rows = refdata.load_reference(p)
        assert rows and rows[0]["호기"] == "AOI-30" and rows[0]["IP"] == "10.2.2.30"
    print("  refdata OK: 자유 양식(비표준 헤더) 폴백")


def test_special_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        p = refdata.special_path(d)
        refdata.create_blank_special(p)
        assert refdata.load_special(p) == []
        rec = {h: None for h in refdata.SPECIAL_HEADERS}
        rec["호기"] = "AOI-24"
        rec["특이사항"] = "노즐 교체"
        rec[refdata.SPECIAL_BOOL_COL] = True
        refdata.save_special(p, [rec])
        back = refdata.load_special(p)
        assert len(back) == 1
        assert back[0]["호기"] == "AOI-24"
        assert back[0][refdata.SPECIAL_BOOL_COL] is True
    print("  refdata OK: 특이사항 왕복(불리언 포함)")


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
