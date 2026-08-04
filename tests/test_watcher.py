"""watcher.py 검증 — 주기/시간대/backoff/안정성 필터/변경 보고서(GUI·장비 비의존)."""

import os
import sys
import tempfile
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import openpyxl  # noqa: E402

from param_manager import collate, engine, watcher, workdirs  # noqa: E402

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


def _collate_file(path, rows, machines=("AOI-6",)):
    """취합 파일 흉내 — 레시피 시트 1개 + 호기 열."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "PI3"
    heads = list(engine.META_FIELDS) + list(machines)
    ws.append(heads)
    for r in rows:
        ws.append([r.get(h) for h in heads])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    wb.save(path)
    return path


def _row(param, value, machine="AOI-6"):
    return {"PI": "PI3", "Recipe": "PI", "Zone": "PAD", "Alg": "Contrast",
            "Parameter": param, "비고": "", machine: value}


# --------------------------------------------------------------------------
def test_settings_roundtrip_and_defaults():
    with tempfile.TemporaryDirectory() as tmp:
        s, st = watcher.load_settings(tmp)            # 파일 없음 → 기본값
        assert s.enabled is False
        assert s.conn_mode == watcher.CONN_SESSION, "기본 접속은 net use 없이"
        assert s.interval_hours == watcher.DEFAULT_INTERVAL_HOURS
        s.enabled = True
        s.interval_hours = 3
        s.conn_mode = watcher.CONN_NETUSE
        s.window_start, s.window_end = 22, 6
        watcher.save_settings(tmp, s, watcher.WatchState(last_run="2026-01-01 00:00:00"))
        s2, st2 = watcher.load_settings(tmp)
        assert s2.enabled and s2.interval_hours == 3
        assert s2.conn_mode == watcher.CONN_NETUSE
        assert (s2.window_start, s2.window_end) == (22, 6)
        assert st2.last_run == "2026-01-01 00:00:00"
    print("  설정 저장/복원 + 기본값(기존 세션 모드) OK")


def test_settings_survives_corrupt_file():
    with tempfile.TemporaryDirectory() as tmp:
        with open(watcher.settings_path(tmp), "w", encoding="utf-8") as fh:
            fh.write("{깨진 JSON")
        s, st = watcher.load_settings(tmp)
        assert s.conn_mode == watcher.CONN_SESSION and st.fail_count == 0
    print("  설정 파일이 깨져도 기본값으로 동작 OK")


def test_time_window():
    s = watcher.WatchSettings(window_start=0, window_end=0)
    assert watcher.in_window(datetime(2026, 8, 4, 3), s), "start==end 면 제한 없음"
    s2 = watcher.WatchSettings(window_start=9, window_end=18)
    assert watcher.in_window(datetime(2026, 8, 4, 10), s2)
    assert not watcher.in_window(datetime(2026, 8, 4, 20), s2)
    s3 = watcher.WatchSettings(window_start=22, window_end=6)   # 자정 넘김
    assert watcher.in_window(datetime(2026, 8, 4, 23), s3)
    assert watcher.in_window(datetime(2026, 8, 4, 2), s3)
    assert not watcher.in_window(datetime(2026, 8, 4, 12), s3)
    print("  실행 시간대 창(자정 넘김 포함) OK")


def test_should_run_interval():
    s = watcher.WatchSettings(enabled=True, interval_hours=6)
    now = datetime(2026, 8, 4, 12, 0, 0)
    assert watcher.should_run(now, s, watcher.WatchState()), "첫 실행은 즉시"
    recent = watcher.WatchState(
        last_run=(now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"))
    assert not watcher.should_run(now, s, recent), "주기 전에는 실행 안 함"
    old = watcher.WatchState(
        last_run=(now - timedelta(hours=7)).strftime("%Y-%m-%d %H:%M:%S"))
    assert watcher.should_run(now, s, old)
    s.enabled = False
    assert not watcher.should_run(now, s, old), "꺼져 있으면 실행 안 함"
    print("  주기 판단(첫 실행/대기/도래/비활성) OK")


def test_backoff_delays_after_failures():
    """연속 실패 시 다음 시도를 미룬다 — 바쁜 장비에 몰아치지 않기 위해."""
    s = watcher.WatchSettings(enabled=True, interval_hours=6)
    now = datetime(2026, 8, 4, 12, 0, 0)
    last = (now - timedelta(hours=7)).strftime("%Y-%m-%d %H:%M:%S")
    ok_state = watcher.WatchState(last_run=last, fail_count=0)
    assert watcher.should_run(now, s, ok_state)
    failed = watcher.WatchState(last_run=last, fail_count=2)   # 6h*4=24h 뒤
    assert not watcher.should_run(now, s, failed), "실패가 쌓이면 더 미룬다"
    n1 = watcher.next_run_at(s, ok_state)
    n2 = watcher.next_run_at(s, failed)
    assert n2 > n1
    print("  연속 실패 backoff(재시도 몰아치기 방지) OK")


def test_record_run_updates_state():
    with tempfile.TemporaryDirectory() as tmp:
        s = watcher.WatchSettings(enabled=True)
        st = watcher.WatchState()
        st = watcher.record_run(tmp, s, st, ok=False, note="접속 실패")
        assert st.fail_count == 1 and st.last_run
        st = watcher.record_run(tmp, s, st, ok=False)
        assert st.fail_count == 2
        st = watcher.record_run(tmp, s, st, ok=True, note="정상")
        assert st.fail_count == 0, "성공하면 backoff 초기화"
        _, reloaded = watcher.load_settings(tmp)
        assert reloaded.fail_count == 0 and reloaded.last_result == "정상"
    print("  회차 상태 기록/복원(실패 누적·성공 초기화) OK")


def test_unstable_file_detection():
    """장비가 쓰는 중이던 파일은 그 회차에서 제외 — 거짓 변경 방지."""
    with tempfile.TemporaryDirectory() as tmp:
        stable = os.path.join(tmp, "GlobalRTP.ini")
        moving = os.path.join(tmp, "Zones.ini")
        for p in (stable, moving):
            with open(p, "w", encoding="utf-8") as fh:
                fh.write("[A]\nx=1\n")
        sigs = [(stable, watcher.file_sig(stable)), (moving, watcher.file_sig(moving))]
        time.sleep(0.01)
        with open(moving, "a", encoding="utf-8") as fh:      # 복사 도중 장비가 씀
            fh.write("y=2\n")
        bad = watcher.unstable_files(sigs)
        assert moving in bad and stable not in bad, bad
    print("  찢어진 읽기 감지(복사 중 변한 파일) OK")


def test_drop_unstable_filters_sources():
    with tempfile.TemporaryDirectory() as tmp:
        d1 = os.path.join(tmp, "AOI-6"); os.makedirs(d1)
        d2 = os.path.join(tmp, "AOI-9"); os.makedirs(d2)
        bad_file = os.path.join(d1, "Zones.ini")
        with open(bad_file, "w", encoding="utf-8") as fh:
            fh.write("x")
        sources = [(d1, "PI3", "AOI-6"), (d2, "PI3", "AOI-9")]
        kept = watcher.drop_unstable(sources, [bad_file])
        assert len(kept) == 1 and kept[0][2] == "AOI-9", kept
        assert watcher.drop_unstable(sources, []) == sources
    print("  불안정 파일이 속한 소스 제외 OK")


def test_compare_and_report_detects_change():
    with tempfile.TemporaryDirectory() as tmp:
        prev = _collate_file(os.path.join(tmp, "파라미터 값 취합", "old.xlsx"),
                             [_row("Contrast Delta - Bright", "25"),
                              _row("Min Defect Width", "10")])
        new = _collate_file(os.path.join(tmp, "파라미터 값 취합", "new.xlsx"),
                            [_row("Contrast Delta - Bright", "99"),
                             _row("Min Defect Width", "10")])
        res = watcher.compare_and_report(tmp, prev, new, st="20260804_120000")
        assert res.ran and res.has_change, res
        assert res.changed == 1, res.changed
        assert res.report and os.path.exists(res.report)
        assert "값변경 1건" in res.summary(), res.summary()
        # 보고서에 어느 파라미터가 바뀌었는지 들어 있어야 한다(변경내역 시트)
        wb = openpyxl.load_workbook(res.report)
        text = "\n".join(
            " ".join(str(c) for c in row if c is not None)
            for ws in wb.worksheets for row in ws.iter_rows(values_only=True))
        wb.close()
        assert "Contrast Delta - Bright" in text, text[:400]
        assert "99" in text
    print("  변경 감지 + 보고서 생성(무엇이 바뀌었는지 포함) OK")


def test_no_change_makes_no_report():
    """변경이 없으면 보고서도 알림도 만들지 않는다(알림 피로 방지)."""
    with tempfile.TemporaryDirectory() as tmp:
        rows = [_row("Contrast Delta - Bright", "25")]
        prev = _collate_file(os.path.join(tmp, "c", "old.xlsx"), rows)
        new = _collate_file(os.path.join(tmp, "c", "new.xlsx"), rows)
        res = watcher.compare_and_report(tmp, prev, new)
        assert res.ran and not res.has_change, res
        assert res.report == ""
        assert res.summary() == "변경 없음"
    print("  무변경 → 보고서 없음 OK")


def test_first_run_has_no_baseline():
    with tempfile.TemporaryDirectory() as tmp:
        new = _collate_file(os.path.join(tmp, "c", "new.xlsx"),
                            [_row("Contrast Delta - Bright", "25")])
        res = watcher.compare_and_report(tmp, None, new)
        assert res.ran and not res.has_change and res.report == ""
    print("  첫 실행(기준선 없음) 처리 OK")


def test_connection_check_and_guide():
    """기본 모드는 net use 없이 — 연결 안 된 장비를 미리 알려준다."""
    chk = watcher.check_connections([("AOI-6", "10.255.255.1")], timeout=0.3)
    assert len(chk["missing"]) == 1, chk        # 개발환경엔 장비가 없다
    assert chk["stopped"] is False
    guide = watcher.connection_guide(chk["missing"])
    assert "AOI-6" in guide and "c$" in guide
    assert "비밀번호를 저장하지 않" in guide
    assert watcher.connection_guide([]) == ""
    print("  무인 모드 연결 사전 점검 + 안내문 OK")


def test_connection_check_is_bounded_by_timeout():
    """미응답 장비에서 무한정 붙들리면 화면이 멈춘다(응답없음 버그).
    호스트당 타임아웃이 지켜지는지 확인."""
    targets = [("AOI-6", "10.255.255.1"), ("AOI-9", "10.255.255.2"),
               ("AOI-12", "10.255.255.3")]
    t0 = time.time()
    chk = watcher.check_connections(targets, timeout=0.3)
    elapsed = time.time() - t0
    assert len(chk["missing"]) == 3, chk
    # 3대 × 0.3초 + 여유. 타임아웃이 안 먹으면 수십 초가 걸린다.
    assert elapsed < 5, f"연결 점검이 너무 오래 걸림: {elapsed:.1f}초"
    assert watcher.probe_host("", timeout=0.3) is False      # 빈 IP 방어
    print(f"  연결 점검 타임아웃 준수 OK ({elapsed:.1f}초)")


def test_connection_check_progress_and_cancel():
    """진행 보고 + 사용자 취소(중단) 지원 — 긴 점검을 멈출 수 있어야 한다."""
    targets = [("AOI-6", "10.255.255.1"), ("AOI-9", "10.255.255.2"),
               ("AOI-12", "10.255.255.3")]
    seen = []
    chk = watcher.check_connections(
        targets, timeout=0.2,
        progress=lambda done, total, m: seen.append((done, total, m)),
        should_stop=lambda: len(seen) >= 2)      # 2대 확인 후 취소
    assert chk["stopped"] is True, chk
    assert len(chk["ok"]) + len(chk["missing"]) < 3, chk
    assert seen and seen[0][1] == 3, seen
    print("  연결 점검 진행보고 + 취소 OK")


def test_selected_targets_persist():
    """감시 대상(장비·레시피) 선택이 저장·복원되어야 한다."""
    with tempfile.TemporaryDirectory() as tmp:
        s, st = watcher.load_settings(tmp)
        assert s.machines == [] and s.recipes == [], "기본은 미선택(호출부가 폴백 결정)"
        s.enabled = True
        s.machines = ["AOI-6", "AOI-9"]
        s.recipes = ["PI3", "RDL2"]
        watcher.save_settings(tmp, s, st)
        s2, _ = watcher.load_settings(tmp)
        assert s2.machines == ["AOI-6", "AOI-9"], s2.machines
        assert s2.recipes == ["PI3", "RDL2"], s2.recipes
        # 선택한 장비만 점검 대상이 된다
        targets = [(m, f"10.255.255.{i+1}") for i, m in enumerate(s2.machines)]
        chk = watcher.check_connections(targets, timeout=0.2)
        assert len(chk["ok"]) + len(chk["missing"]) == 2, chk
    print("  감시 대상 장비·레시피 선택 저장/복원 + 선택분만 점검 OK")


def test_stale_selection_is_filtered():
    """선택 저장 후 장비·레시피가 삭제됐으면 실행 시 걸러져야 한다."""
    with tempfile.TemporaryDirectory() as tmp:
        s, st = watcher.load_settings(tmp)
        s.machines = ["AOI-6", "사라진호기"]
        s.recipes = ["PI3", "사라진레시피"]
        watcher.save_settings(tmp, s, st)
        s2, _ = watcher.load_settings(tmp)
        # _watch_run_cycle 과 같은 필터 규칙
        avail_m, avail_r = {"AOI-6", "AOI-9"}, {"PI3", "PI4"}
        machines = [m for m in s2.machines if m in avail_m]
        recipes = [r for r in s2.recipes if r in avail_r]
        assert machines == ["AOI-6"], machines
        assert recipes == ["PI3"], recipes
    print("  삭제된 장비·레시피 선택 자동 제외 OK")


def test_unselected_machines_keep_values():
    """감시 대상을 1대만 골라도 **나머지 호기의 기존 값이 남아 있어야** 한다.

    (버그) 선택한 장비만 취합 열로 쓰면 나머지 호기 값이 통째로 빠져
    변경보고서에 '삭제'로 잘못 찍혔다. 열은 항상 전체 호기여야 한다.
    """
    import shutil
    from param_manager import collate, extract_io, workdirs
    with tempfile.TemporaryDirectory() as tmp:
        machines_all = ["AOI-17", "AOI-19", "AOI-25"]
        # 양식 1개(파라미터 1행)
        recipe = "PI3"
        run_dir = workdirs.form_run_dir(tmp, recipe, "20260101_000000")
        form = workdirs.form_final_path(run_dir, recipe, "AOI-19", "20260101_000000")
        rec = {"PI": recipe, "Recipe": "PI", "Zone": "PAD", "Alg": "Contrast",
               "Parameter": "Contrast Delta - Bright", "비고": ""}
        extract_io.write_snapshot(form, [rec], machines=[], sheet_name="PI_ALL",
                                  extracts=[{"src_file": "Zones/PAD.ini",
                                             "section": "Contrast",
                                             "key": "Delta", "transform": "RAW"}],
                                  stage="final", level=recipe)
        # 직전 취합본: 세 호기 모두 값이 있음
        prev_res = collate.build_collation(tmp, [recipe], [], machines_all)
        made = {r: v for r, v in prev_res.items() if not v.missing_form}
        for r, v in made.items():
            for row in v.records:
                for m, val in zip(machines_all, ["17값", "19값", "25값"]):
                    row[m] = val
        prev_path = workdirs.collate_path(tmp, "20260101_010000")
        collate.write_collation(prev_path, made, machines_all)

        # 감시 회차: AOI-19 만 선택했지만 **열은 전체 호기**로 취합(고친 동작)
        out = collate.build_collation(tmp, [recipe], [], machines_all,
                                      prev_collate_path=prev_path)
        made2 = {r: v for r, v in out.items() if not v.missing_form}
        new_path = workdirs.collate_path(tmp, "20260101_020000")
        collate.write_collation(new_path, made2, machines_all)

        sheets, cols = collate.load_collation(new_path)
        for m in machines_all:
            assert m in cols, f"{m} 열이 사라짐: {cols}"
        row = sheets[recipe][0]
        assert row["AOI-17"] == "17값", row     # 선택 안 한 호기 값 유지
        assert row["AOI-25"] == "25값", row

        # 변경보고서에 '삭제'가 찍히면 안 된다
        res = watcher.compare_and_report(tmp, prev_path, new_path)
        assert res.removed == 0, f"선택 안 한 호기가 삭제로 잡힘: {res.summary()}"
        assert not res.has_change, res.summary()
        shutil.rmtree(os.path.join(tmp, "양식"), ignore_errors=True)
    print("  선택 안 한 호기 값 유지 + 오탐 '삭제' 없음 OK")


def test_plan_roundtrip():
    """무인 수집 계획이 저장·복원되어야 무인 회차가 선택창 없이 돈다."""
    from param_manager.collector import CollectPlan
    with tempfile.TemporaryDirectory() as tmp:
        assert watcher.plan_from_dict({}) is None, "계획 없으면 None"
        plan = CollectPlan(job_keyword="PI", job_name="JobA", setup_name="Setup1",
                           recipe_names=["PI3"], recipe_map={"PI3": ["PI3_FOLDER"]})
        s, st = watcher.load_settings(tmp)
        s.plan = watcher.plan_to_dict(plan)
        watcher.save_settings(tmp, s, st)
        s2, _ = watcher.load_settings(tmp)
        back = watcher.plan_from_dict(s2.plan)
        assert back is not None
        assert back.job_keyword == "PI" and back.setup_name == "Setup1"
        assert back.recipe_map == {"PI3": ["PI3_FOLDER"]}, back.recipe_map
    print("  무인 수집 계획 저장/복원 OK")


def test_log_appends():
    with tempfile.TemporaryDirectory() as tmp:
        watcher.append_log(tmp, "회차 시작")
        watcher.append_log(tmp, "변경 없음")
        with open(watcher.log_path(tmp), encoding="utf-8") as fh:
            body = fh.read()
        assert "회차 시작" in body and "변경 없음" in body
        assert body.count("\n") == 2
    print("  감시 로그 누적 OK")


if __name__ == "__main__":
    for t in [test_settings_roundtrip_and_defaults, test_settings_survives_corrupt_file,
              test_time_window, test_should_run_interval,
              test_backoff_delays_after_failures, test_record_run_updates_state,
              test_unstable_file_detection, test_drop_unstable_filters_sources,
              test_compare_and_report_detects_change, test_no_change_makes_no_report,
              test_first_run_has_no_baseline, test_connection_check_and_guide,
              test_connection_check_is_bounded_by_timeout,
              test_connection_check_progress_and_cancel,
              test_selected_targets_persist, test_stale_selection_is_filtered,
              test_unselected_machines_keep_values, test_plan_roundtrip,
              test_log_appends]:
        run(t)
    print(f"==== {PASS}/{PASS + FAIL} passed ====")
    sys.exit(1 if FAIL else 0)
