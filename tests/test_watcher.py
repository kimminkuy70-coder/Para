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
    chk = watcher.check_connections([("AOI-6", "10.0.0.1")])
    assert len(chk["missing"]) == 1, chk        # 개발환경엔 장비가 없다
    guide = watcher.connection_guide(chk["missing"])
    assert "AOI-6" in guide and "c$" in guide
    assert "비밀번호를 저장하지 않" in guide
    assert watcher.connection_guide([]) == ""
    print("  무인 모드 연결 사전 점검 + 안내문 OK")


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
              test_log_appends]:
        run(t)
    print(f"==== {PASS}/{PASS + FAIL} passed ====")
    sys.exit(1 if FAIL else 0)
