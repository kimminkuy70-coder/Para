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


def test_device_type_and_legacy_login_id_ignored():
    """장비종류는 공유 파일에 저장·조회되고, 구 파일의 '접속ID' 열은 **무시**된다
    (2026-09, net use 접속 삭제 — 프로그램이 계정 정보를 읽지 않는다)."""
    with tempfile.TemporaryDirectory() as d:
        p = refdata.ip_path(d)
        rows = [{"호기": "AOI-24", "IP": "10.0.0.24", "장비종류": "Camtek"},
                {"호기": "K1", "IP": "10.0.0.31", "장비종류": "KLA"}]
        assert refdata.device_type_for(rows, "AOI-24") == "Camtek"
        assert refdata.device_type_for(rows, "K1") == "KLA"
        # KLA 숨김
        assert refdata.machines(rows, hide_types=["KLA"]) == ["AOI-24"]
        # 저장 → 다시 읽어도 장비종류 유지, 접속ID 는 파일에 쓰지 않는다
        refdata.save_ip(p, rows)
        back = refdata.load_ip(p)
        assert refdata.device_type_for(back, "AOI-24") == "Camtek"
        assert refdata.ip_for(back, "AOI-24") == "10.0.0.24", "IP 가 밀리면 안 됨"
        assert "접속ID" not in back[0], "접속ID 를 다시 읽어들이면 안 됨"
        assert not hasattr(refdata, "login_id_for"), "login_id_for 가 남아 있음"
        # '접속ID' 열이 들어 있는 구 파일도 그대로 읽히되 그 값은 무시된다
        old = refdata.ip_path(os.path.join(d, "old"))
        os.makedirs(os.path.dirname(old), exist_ok=True)
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = refdata.IP_SHEET
        ws.append(["호기", "IP", "접속ID"])
        ws.append(["AOI-30", "10.0.0.30", "camtek"])
        wb.save(old)
        rows_old = refdata.load_ip(old)
        assert rows_old[0]["IP"] == "10.0.0.30"
        assert "접속ID" not in rows_old[0], "구 파일의 접속ID 를 읽어들이면 안 됨"
    print("  refdata OK: 장비종류 공유 + 접속ID(구 파일) 무시")


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
