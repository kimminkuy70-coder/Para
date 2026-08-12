"""Commonality 자동 감시 — 새로 생긴 S/M 폴더 감지(헤드리스).

여기서 고정하는 규칙(사용자 확정 2026-08):
  ① 감시 범위 = **감시 대상 Lot 계획**의 (디바이스, 공정번호) — 트리 전체를 훑지 않는다
  ② 기억 키는 **경로가 아니라 (디바이스, 공정, S/M)** — 백업본(Scanresult_260402 …)에
     같은 S/M 이 또 있어도 '신규'로 잡히면 안 된다
  ③ **첫 회차는 기준선만** 기록하고 알리지 않는다
  ④ 아직 쓰는 중인 폴더는 미룬다(수정시각이 settle 이내이거나 설정파일이 없으면)
  ⑤ 공정 폴더 mtime 이 그대로면 통째로 건너뛴다(파일서버 접근 최소화)
  ⑥ 찾은 S/M 은 **생성일자와 함께** 조사 계획 엑셀에 덧붙인다(원본은 백업 후 수정)
  ⑦ 감시 대상 계획과 조사 계획은 **파일 이름이 다르다**
"""

import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import openpyxl  # noqa: E402

from param_manager import cmwatcher as cw  # noqa: E402
from param_manager import commonality as cm  # noqa: E402

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


DEV = "S6WH11001-00001"
LOT = "6412"


def _mk_sm(scan_root: Path, sm: str, *, aged: bool = True) -> Path:
    """S/M 폴더 + 슬롯 + 설정파일. aged=True 면 '충분히 오래된' 것으로 만든다."""
    d = scan_root / f"2D@R3-{DEV}_0A" / LOT / sm / "CX01"
    (d / "Zones").mkdir(parents=True, exist_ok=True)
    (d / "OpticPreset.ini").write_text("[Scan2d]\nMag=5\n", encoding="utf-8")
    if aged:
        old = time.time() - 7200
        for p in [d, d.parent, d.parent.parent, d.parent.parent.parent, scan_root]:
            os.utime(p, (old, old))
    return d.parent


def _roots(base: Path):
    return cm.scanresult_roots(str(base / "AOI-9"), "AOI-9")


# --------------------------------------------------------------------------
def test_watch_plan_template_and_targets():
    """감시 대상 계획: 파일 이름이 조사 계획과 다르고, S/M 칸이 없다."""
    assert cw.WATCH_PLAN_FILENAME != cm.PLAN_FILENAME
    assert cw.WATCH_PLAN_FILENAME == "감시대상_Lot계획.xlsx"
    assert cm.PLAN_FILENAME == "Commonality_Lot계획.xlsx"
    assert "S/M" not in cw.WATCH_PLAN_HEADERS, "감시 계획엔 S/M 칸이 없다"

    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, cw.WATCH_PLAN_FILENAME)
        cw.create_watch_plan_template(p, [
            {"디바이스명": DEV, "공정번호": LOT, "AOI호기": "AOI-9"},
            {"디바이스명": DEV, "공정번호": "7000", "AOI호기": "AOI-4,9"},
            {"디바이스명": "OTHER", "공정번호": "1", "AOI호기": "AOI-6"},
        ])
        rows = cw.read_watch_plan(p)
        assert len(rows) == 3, rows
        t = cw.targets_for_machine(rows, "AOI-09")        # 0패딩 흡수
        assert t == [(DEV, LOT), (DEV, "7000")], t        # AOI-6 행은 빠진다
        # 같은 조합이 두 번 있어도 한 번만
        rows.append({"디바이스명": DEV, "공정번호": LOT, "AOI호기": "AOI-9"})
        assert len(cw.targets_for_machine(rows, "AOI-9")) == 2
    print("  감시 대상 계획(이름 구분·호기 필터·중복 제거) OK")


def test_first_cycle_is_baseline_only():
    """첫 회차는 기존 폴더를 전부 기억만 하고 **알리지 않는다**."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        sr = base / "AOI-9" / "Scanresult"
        _mk_sm(sr, "HPG")
        _mk_sm(sr, "TVS")
        st = cw.CmWatchState()
        res = cw.scan_new(_roots(base), [(DEV, LOT)], cw.seen_set(st, "AOI-9"), {})
        assert len(res["new"]) == 2, res["new"]
        notify = cw.apply_scan(st, "AOI-9", res)
        assert notify == [], "첫 회차에 알리면 안 된다"
        assert st.baseline is True
        assert len(st.seen["AOI-9"]) == 2

        # 두 번째 회차에 새 폴더가 생기면 그때는 알린다
        _mk_sm(sr, "NEWSM")
        res2 = cw.scan_new(_roots(base), [(DEV, LOT)],
                           cw.seen_set(st, "AOI-9"), {})
        notify2 = cw.apply_scan(st, "AOI-9", res2)
        assert [i["sm"] for i in notify2] == ["NEWSM"], notify2
        assert notify2[0]["created"], "생성일자가 비어 있으면 안 된다"
    print("  첫 회차 기준선(무알림) → 이후 신규만 알림 OK")


def test_backup_scanresult_is_not_new():
    """백업본에 같은 S/M 이 또 있어도 신규가 아니다(경로가 아니라 내용 키)."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        sr = base / "AOI-9" / "Scanresult"
        _mk_sm(sr, "HPG")
        st = cw.CmWatchState()
        cw.apply_scan(st, "AOI-9", cw.scan_new(_roots(base), [(DEV, LOT)],
                                               cw.seen_set(st, "AOI-9"), {}))
        # 백업 폴더가 통째로 생김 — 안에 같은 S/M 이 들어 있다
        bak = base / "AOI-9" / "SCANRESULT_BACKUP_260805"
        _mk_sm(bak, "HPG")
        roots = _roots(base)
        assert len(roots) == 2, [p.name for p in roots]
        res = cw.scan_new(roots, [(DEV, LOT)], cw.seen_set(st, "AOI-9"), {})
        assert res["new"] == [], "백업본의 같은 S/M 이 신규로 잡혔다"

        # 백업본에만 있는 새 S/M 은 정상적으로 잡힌다
        _mk_sm(bak, "ONLYBAK")
        res2 = cw.scan_new(roots, [(DEV, LOT)], cw.seen_set(st, "AOI-9"), {})
        assert [i["sm"] for i in res2["new"]] == ["ONLYBAK"], res2["new"]
        # 같은 회차 안에서 두 루트에 같은 이름이 있어도 한 번만
        _mk_sm(sr, "BOTH")
        _mk_sm(bak, "BOTH")
        st2 = cw.CmWatchState()
        res3 = cw.scan_new(roots, [(DEV, LOT)], cw.seen_set(st2, "AOI-9"), {})
        names = [i["sm"] for i in res3["new"]]
        assert names.count("BOTH") == 1, names
    print("  백업 Scanresult 중복 무시(내용 키) OK")


def test_unsettled_folder_is_deferred():
    """방금 만들어진(=아직 쓰는 중일 수 있는) 폴더는 미룬다."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        sr = base / "AOI-9" / "Scanresult"
        _mk_sm(sr, "HPG")
        st = cw.CmWatchState()
        cw.apply_scan(st, "AOI-9", cw.scan_new(_roots(base), [(DEV, LOT)],
                                               cw.seen_set(st, "AOI-9"), {}))
        fresh = _mk_sm(sr, "FRESH", aged=False)          # 지금 만든 폴더
        res = cw.scan_new(_roots(base), [(DEV, LOT)], cw.seen_set(st, "AOI-9"), {},
                          settle_minutes=10)
        assert res["new"] == [] and len(res["pending"]) == 1, res
        # 시간이 지나면 잡힌다
        old = time.time() - 7200
        os.utime(fresh, (old, old))
        res2 = cw.scan_new(_roots(base), [(DEV, LOT)], cw.seen_set(st, "AOI-9"), {},
                           settle_minutes=10)
        assert [i["sm"] for i in res2["new"]] == ["FRESH"], res2["new"]

        # 설정파일이 아직 없는 폴더도 미룬다(껍데기만 생긴 상태)
        shell = sr / f"2D@R3-{DEV}_0A" / LOT / "SHELL"
        shell.mkdir(parents=True)
        os.utime(shell, (old, old))
        res3 = cw.scan_new(_roots(base), [(DEV, LOT)], cw.seen_set(st, "AOI-9"), {},
                           settle_minutes=10)
        assert "SHELL" not in [i["sm"] for i in res3["new"]], res3["new"]
    print("  안정화 대기(수정시각·설정파일) OK")


def test_unchanged_lot_dir_is_skipped():
    """공정 폴더 mtime 이 그대로면 통째로 건너뛴다(파일서버 접근 최소화)."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        sr = base / "AOI-9" / "Scanresult"
        _mk_sm(sr, "HPG")
        st = cw.CmWatchState()
        r1 = cw.scan_new(_roots(base), [(DEV, LOT)], cw.seen_set(st, "AOI-9"), {})
        cw.apply_scan(st, "AOI-9", r1)
        assert r1["scanned"] >= 1 and r1["skipped"] == 0
        r2 = cw.scan_new(_roots(base), [(DEV, LOT)], cw.seen_set(st, "AOI-9"),
                         st.mtimes["AOI-9"])
        assert r2["scanned"] == 0 and r2["skipped"] >= 1, r2
        # 계획에 없는 (디바이스, 공정)은 아예 보지 않는다
        r3 = cw.scan_new(_roots(base), [("없는디바이스", "9999")],
                         cw.seen_set(st, "AOI-9"), {})
        assert r3["new"] == [] and r3["scanned"] == 0
    print("  mtime 불변 시 건너뜀 + 계획 밖 무시 OK")


def test_append_to_cm_plan_with_created_date():
    """조사 계획에 **생성일자와 함께** 덧붙이고, 원본은 백업한다."""
    with tempfile.TemporaryDirectory() as tmp:
        plan = os.path.join(tmp, cm.PLAN_FILENAME)
        cm.create_plan_template(plan, [
            {"디바이스명": DEV, "공정번호": LOT, "S/M": "HPG", "AOI호기": "AOI-9"}])
        items = [
            {"key": cw.sm_key(DEV, LOT, "HPG"), "device": DEV, "lot": LOT,
             "sm": "HPG", "created": "2026-08-01 09:00"},          # 이미 있음
            {"key": cw.sm_key(DEV, LOT, "NEW1"), "device": DEV, "lot": LOT,
             "sm": "NEW1", "created": "2026-08-11 13:20"},
        ]
        res = cw.append_cm_plan(plan, items, machine="AOI-9")
        assert res["added"] == 1 and res["skipped"] == 1, res
        assert res["backup"] and os.path.isfile(res["backup"]), "백업이 없다"

        rows = cm.read_plan(plan)
        assert len(rows) == 2, rows
        new = [r for r in rows if r["S/M"] == "NEW1"][0]
        assert new["디바이스명"] == DEV and new["공정번호"] == LOT
        assert new["AOI호기"] == "AOI-9"
        assert new["생성일자"] == "2026-08-11 13:20", new
        assert new.get("fail여부", "") == "", "fail 은 사람이 채운다"

        # 같은 항목을 또 넣어도 늘지 않는다
        res2 = cw.append_cm_plan(plan, items, machine="AOI-9")
        assert res2["added"] == 0 and len(cm.read_plan(plan)) == 2
    print("  조사 계획 추가(생성일자·백업·중복 방지) OK")


def test_append_adds_column_to_old_plan():
    """'생성일자' 열이 없는 구 계획 파일에도 열을 만들어 채운다."""
    with tempfile.TemporaryDirectory() as tmp:
        plan = os.path.join(tmp, cm.PLAN_FILENAME)
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Lot목록"
        ws.append(["디바이스명", "공정번호", "S/M", "AOI호기", "fail여부"])  # 구 5열
        ws.append([DEV, LOT, "HPG", "AOI-9", ""])
        wb.save(plan)
        wb.close()
        cw.append_cm_plan(plan, [{"key": cw.sm_key(DEV, LOT, "NEW1"), "device": DEV,
                                  "lot": LOT, "sm": "NEW1",
                                  "created": "2026-08-11 13:20"}], machine="AOI-9")
        rows = cm.read_plan(plan)
        new = [r for r in rows if r["S/M"] == "NEW1"][0]
        assert new["생성일자"] == "2026-08-11 13:20", new
        old = [r for r in rows if r["S/M"] == "HPG"][0]
        assert old["디바이스명"] == DEV, "기존 행이 밀리면 안 된다"
    print("  구 계획 파일에 생성일자 열 추가 OK")


def test_settings_roundtrip_is_local():
    """설정·상태는 **로컬 Cache** 에 저장되고 왕복이 유지된다."""
    with tempfile.TemporaryDirectory() as tmp:
        s, st = cw.load_settings(tmp)
        assert s.enabled is False and st.baseline is False
        s.enabled = True
        s.machines = ["AOI-9"]
        s.watch_plan = "/x/감시대상_Lot계획.xlsx"
        s.cm_plan = "/x/Commonality_Lot계획.xlsx"
        s.roots = {"AOI-9": "/w/AOI-9"}
        st.baseline = True
        st.seen = {"AOI-9": [cw.sm_key(DEV, LOT, "HPG")]}
        st.mtimes = {"AOI-9": {"/w/x": 1.0}}
        cw.save_settings(tmp, s, st)
        p = cw.settings_path(tmp)
        assert os.path.isfile(p) and "Cache" in p, p

        s2, st2 = cw.load_settings(tmp)
        assert s2.enabled and s2.machines == ["AOI-9"]
        assert s2.watch_plan.endswith(cw.WATCH_PLAN_FILENAME)
        assert s2.cm_plan.endswith(cm.PLAN_FILENAME)
        assert st2.baseline and cw.seen_set(st2, "AOI-9") == cw.seen_set(st, "AOI-9")
        # 깨진 파일이어도 예외 없이 기본값
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("{ broken")
        s3, st3 = cw.load_settings(tmp)
        assert s3.enabled is False and st3.seen == {}
        assert cw.append_log(tmp, "테스트") is True
    print("  설정/상태 로컬 저장 왕복 + 손상 파일 방어 OK")


if __name__ == "__main__":
    for t in [test_watch_plan_template_and_targets, test_first_cycle_is_baseline_only,
              test_backup_scanresult_is_not_new, test_unsettled_folder_is_deferred,
              test_unchanged_lot_dir_is_skipped, test_append_to_cm_plan_with_created_date,
              test_append_adds_column_to_old_plan, test_settings_roundtrip_is_local]:
        run(t)
    print(f"==== {PASS}/{PASS + FAIL} passed ====")
    sys.exit(1 if FAIL else 0)
