"""엔진 헤드리스 테스트 — GUI 없이 핵심 로직을 검증한다."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from param_manager import engine  # noqa: E402
from param_manager.engine import ParamRepository  # noqa: E402

SRC_XLSM = "/root/.claude/uploads/7851d2ae-4682-5f92-96aa-2026219c8485/52ecc345-Camtek_RTP_PI_CoreParameter_Managed_PI_ALL_IncrementalSync_VBA.xlsm"


def _new_repo_from_sample(tmp):
    dest = os.path.join(tmp, "shared.xlsx")
    repo = engine.import_from_xlsm(SRC_XLSM, dest)
    return dest, repo


def test_import():
    with tempfile.TemporaryDirectory() as tmp:
        dest, repo = _new_repo_from_sample(tmp)
        assert os.path.exists(dest)
        assert len(repo.rows) == 132, f"파라미터 행 수 132 기대, 실제 {len(repo.rows)}"
        assert len(repo.history) == 1948, f"이력 1948 기대, 실제 {len(repo.history)}"
        assert all(pr.row_id for pr in repo.rows), "모든 행에 Row_ID"
        assert repo.aoi_ip.get("AOI-19") == "10.142.80.84"
        print(f"  import OK: rows={len(repo.rows)} history={len(repo.history)} aoi_ip={len(repo.aoi_ip)}")


def test_reload_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        dest, repo = _new_repo_from_sample(tmp)
        repo2 = ParamRepository(dest)
        repo2.load()
        assert len(repo2.rows) == 132
        assert len(repo2.history) == 1948
        print("  reload roundtrip OK")


def test_edit_and_change_detection():
    with tempfile.TemporaryDirectory() as tmp:
        dest, repo = _new_repo_from_sample(tmp)
        # AOI 값 1개 + 메타 1개 수정
        target = repo.rows[2]
        target.set("AOI-3", "999")
        target.set("비고", "테스트 변경")
        changes = repo.detect_changes()
        fields = sorted(c.field for c in changes)
        assert fields == ["AOI-3", "비고"], fields
        aoi_change = [c for c in changes if c.field == "AOI-3"][0]
        assert aoi_change.is_aoi is True
        assert engine._s(aoi_change.new) == "999"
        print(f"  change detection OK: {[(c.field, c.is_aoi) for c in changes]}")


def test_save_appends_history_and_merges():
    with tempfile.TemporaryDirectory() as tmp:
        dest, repo = _new_repo_from_sample(tmp)
        hist_before = len(repo.history)
        repo.rows[5].set("AOI-20", "42")
        stats = repo.save(user="tester")
        assert stats["changes"] == 1, stats
        # 재로드해서 반영 확인
        r2 = ParamRepository(dest)
        r2.load()
        assert len(r2.history) == hist_before + 1
        # 값이 실제 기록됐는지
        row = next(p for p in r2.rows if p.row_id == repo.rows[5].row_id)
        assert engine._s(row.get("AOI-20")) == "42"
        # 마지막 이력 레코드 검증
        last = r2.history[-1]
        assert last["New Value"] == "42"
        assert last["AOI"] == "AOI-20"
        assert last["Updated By"] == "tester"
        assert last["Change Type"] == "AOI 값 수정"
        print(f"  save+history+merge OK: stats={stats}, history {hist_before}->{len(r2.history)}")


def test_concurrent_row_level_merge():
    """두 사용자가 서로 다른 행을 수정 -> 둘 다 보존되어야 한다(클로버링 방지)."""
    with tempfile.TemporaryDirectory() as tmp:
        dest, _ = _new_repo_from_sample(tmp)
        a = ParamRepository(dest); a.load()
        b = ParamRepository(dest); b.load()
        # A는 0번 행 AOI-3, B는 1번 행 AOI-13 수정
        a.rows[0].set("AOI-3", "AAA")
        b.rows[1].set("AOI-13", "BBB")
        a.save(user="userA")   # 먼저 저장
        b.save(user="userB")   # 나중 저장: 디스크 최신본을 다시 읽어 병합해야 함
        r = ParamRepository(dest); r.load()
        v0 = engine._s(next(p for p in r.rows if p.row_id == a.rows[0].row_id).get("AOI-3"))
        v1 = engine._s(next(p for p in r.rows if p.row_id == b.rows[1].row_id).get("AOI-13"))
        assert v0 == "AAA", f"userA 수정 유실: {v0!r}"
        assert v1 == "BBB", f"userB 수정 유실: {v1!r}"
        print("  concurrent row-level merge OK (no clobbering)")


def test_summary_change_count():
    with tempfile.TemporaryDirectory() as tmp:
        dest, repo = _new_repo_from_sample(tmp)
        rid = repo.rows[3].row_id
        repo.rows[3].set("AOI-25", "100")
        repo.save(user="tester")
        # 같은 셀 한번 더 변경 -> 변경횟수 2
        r2 = ParamRepository(dest); r2.load()
        tr = next(p for p in r2.rows if p.row_id == rid)
        tr.set("AOI-25", "200")
        r2.save(user="tester")
        # 요약 시트 읽어 변경횟수 확인
        import openpyxl
        wb = openpyxl.load_workbook(dest, data_only=True)
        prev = ParamRepository._read_summary(wb)
        wb.close()
        entry = prev.get(f"{rid}|AOI-25")
        assert entry is not None
        assert int(entry["변경횟수"]) == 2, entry["변경횟수"]
        assert engine._s(entry["현재값"]) == "200"
        assert engine._s(entry["이전값"]) == "100"
        print(f"  summary aggregation OK: 변경횟수={entry['변경횟수']} 현재값={entry['현재값']} 이전값={entry['이전값']}")


def test_comparison_view():
    with tempfile.TemporaryDirectory() as tmp:
        _, repo = _new_repo_from_sample(tmp)
        view = repo.comparison_view()
        assert len(view) == 132
        # 누락 호기가 있는 행이 다수 존재해야(현재 대부분 비어있음)
        with_missing = [v for v in view if v["missing"]]
        assert len(with_missing) > 0
        print(f"  comparison view OK: rows={len(view)}, 누락있는행={len(with_missing)}")


def test_special_roundtrip_and_edit():
    with tempfile.TemporaryDirectory() as tmp:
        dest, repo = _new_repo_from_sample(tmp)
        assert len(repo.special) >= 2, f"특이사항 행 {len(repo.special)}"
        # 종료 여부가 불리언인지
        assert all(isinstance(r[engine.SPECIAL_BOOL_COL], bool) for r in repo.special)
        done = [r for r in repo.special if r[engine.SPECIAL_BOOL_COL]]
        assert len(done) >= 1, "종료 True 행이 있어야"
        # 편집: 첫 행 종료여부 토글 + 새 특이사항 추가 후 저장
        repo.special[0][engine.SPECIAL_BOOL_COL] = not repo.special[0][engine.SPECIAL_BOOL_COL]
        repo.special.append({"일자": None, "호기": "AOI-99", "라트 번호": "TEST",
                             "S/M": "X", "Layer": "PI2", "목적": "테스트",
                             "진행 상황": "진행", "종료 여부": True, "특이사항": "메모"})
        repo.save(user="tester")
        r2 = ParamRepository(dest); r2.load()
        assert any(x.get("호기") == "AOI-99" and x[engine.SPECIAL_BOOL_COL] is True for x in r2.special)
        print(f"  special roundtrip+edit OK: rows={len(r2.special)}")


def test_new_row_not_jumping_top():
    with tempfile.TemporaryDirectory() as tmp:
        dest, repo = _new_repo_from_sample(tmp)
        pr = repo.add_row({"PI": "PI2", "Recipe": "ZZZ", "Zone": "ZZ",
                           "Alg": "zz", "Parameter": "new_param"})
        rid = pr.row_id
        repo.save(user="tester")
        r2 = ParamRepository(dest); r2.load()
        # 정렬 후 PI2 그룹 내에서 맨 앞이 아니어야(=display_order 0 버그 없음)
        pi2 = [p for p in r2.rows if engine._s(p.get("PI")) == "PI2"]
        assert engine._s(pi2[0].row_id) != rid, "새 행이 PI2 그룹 맨 앞으로 튐(버그 재발)"
        added = next(p for p in r2.rows if p.row_id == rid)
        assert added.display_order > pi2[0].display_order
        print(f"  new row order OK: added display_order={added.display_order}, first PI2={pi2[0].display_order}")


def test_lock_and_conflict():
    with tempfile.TemporaryDirectory() as tmp:
        dest, _ = _new_repo_from_sample(tmp)
        assert engine.read_lock(dest) is None
        engine.write_lock(dest, "alice")
        info = engine.read_lock(dest)
        assert info and info.user == "alice"
        assert not info.is_stale()
        engine.release_lock(dest, "alice")
        assert engine.read_lock(dest) is None
        # 충돌본 감지
        stem = os.path.splitext(os.path.basename(dest))[0]
        conflict = os.path.join(tmp, f"{stem}-DESKTOP123.xlsx")
        with open(conflict, "w") as fh:
            fh.write("x")
        found = engine.find_conflict_copies(dest)
        assert conflict in found, found
        print("  lock + conflict detection OK")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            print(f"[RUN] {t.__name__}")
            t()
            print(f"[PASS] {t.__name__}\n")
        except Exception as e:  # noqa: BLE001
            failed += 1
            import traceback
            print(f"[FAIL] {t.__name__}: {e}")
            traceback.print_exc()
            print()
    print(f"==== {len(tests) - failed}/{len(tests)} passed ====")
    sys.exit(1 if failed else 0)
