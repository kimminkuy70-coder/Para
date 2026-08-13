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
import re
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import openpyxl  # noqa: E402

from param_manager import cmwatcher as cw  # noqa: E402
from param_manager import commonality as cm
from param_manager import engine  # noqa: E402

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


def _mk_scan_sm(base, machine, device, lot, sm, delta):
    """가짜 Scanresult S/M 폴더 하나(슬롯 CX01 안에 설정 파일)."""
    w = (Path(base) / machine / "Scanresult" / f"2D@R3-{device}" / lot / sm / "CX01")
    (w / "Zones").mkdir(parents=True)
    (w / "Zones" / "Z1.ini").write_text(
        f"[General]\nZoneName=PI Opening\n[Surface]\nHigh_Delta={delta}\n",
        encoding="utf-8")
    (w / "OpticPreset.ini").write_text(
        "[Scan2d]\nCameraName=TDI\nMag=5\nLightSrcRef_NominalGL=1\n", encoding="utf-8")
    (w / "GlobalRTP.ini").write_text("[GLOBAL_RTP]\nMaxFaultsPerWafer=3000\n",
                                     encoding="utf-8")
    return w.parent


def _mk_form(tmp, rep_dir, name="감시양식.xlsx"):
    """대표 S/M 으로 확정 양식 하나(감시 켤 때 사람이 만드는 그것)."""
    from param_manager import formbuilder
    pivot, _labels = cm.parse_lots([("REP", Path(rep_dir) / "CX01")], level="PI3")
    init = os.path.join(tmp, "init.xlsx")
    form = os.path.join(tmp, name)
    formbuilder.build_initial_workbook(pivot, init, level="PI3")
    formbuilder.build_final_from_initial(init, form, level="PI3", aoi="AOI-9")
    return form


def test_sm_candidates_sorted_by_created_desc():
    """대표 S/M 은 사람이 고른다 — 후보는 **생성일자 최신순**이어야 한다."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        for sm in ("ASD", "ASD X20", "BQC"):
            _mk_scan_sm(base, "AOI-9", "DEV1-0001", "6412", sm, 25)
        roots = cm.scanresult_roots(str(base), "AOI-9")
        cands = cw.sm_candidates(roots, "DEV1-0001", "6412")
        assert {c["sm"] for c in cands} == {"ASD", "ASD X20", "BQC"}, cands
        created = [c["created"] for c in cands]
        assert created == sorted(created, reverse=True), created   # 최신순
        assert all(c["slots"] == 1 for c in cands)
        # 백업본에 같은 S/M 이 또 있어도 후보는 한 번만
        bak = base / "AOI-9" / "Scanresult_260402" / "2D@R3-DEV1-0001" / "6412" / "ASD"
        bak.mkdir(parents=True)
        roots2 = cm.scanresult_roots(str(base), "AOI-9")
        again = cw.sm_candidates(roots2, "DEV1-0001", "6412")
        assert sum(1 for c in again if c["sm"] == "ASD") == 1, again
    print("  대표 S/M 후보 최신순 정렬 + 백업본 중복 제거 OK")


def test_form_binding_is_per_target():
    """양식은 **감시 대상(호기·디바이스·공정)마다** 따로 묶인다."""
    s, _st = cw.CmWatchSettings(), None
    assert cw.form_for(s, "AOI-9", "D1", "6412") == {}
    cw.set_form(s, "AOI-9", "D1", "6412", "/x/form1.xlsx", "PI3", sm="ASD")
    cw.set_form(s, "AOI-9", "D2", "6412", "/x/form2.xlsx", "PI4")
    a = cw.form_for(s, "AOI-9", "D1", "6412")
    assert a["form"] == "/x/form1.xlsx" and a["recipe"] == "PI3" and a["sm"] == "ASD"
    assert cw.form_for(s, "AOI-9", "D2", "6412")["form"] == "/x/form2.xlsx"
    # 호기가 다르면 다른 대상
    assert cw.form_for(s, "AOI-8", "D1", "6412") == {}
    # 0패딩·구분자 차이는 같은 대상으로 본다
    assert cw.form_for(s, "AOI-09", "d1", "6412")["form"] == "/x/form1.xlsx"
    # 파일이 실제로 없으면 '미지정'으로 잡아 준다
    miss = cw.missing_forms(s, "AOI-9", [("D1", "6412"), ("D9", "9999")])
    assert ("D1", "6412") in miss and ("D9", "9999") in miss, miss
    print("  대상별 양식 지정/조회 OK")


def test_survey_records_slot_and_created():
    """자동 조사: 이름순 **첫 슬롯**만 읽고, 어느 슬롯을 읽었는지 남긴다."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "scan"
        rep = _mk_scan_sm(base, "AOI-9", "DEV1-0001", "6412", "ASD", 25)
        new = _mk_scan_sm(base, "AOI-9", "DEV1-0001", "6412", "ASD X20", 30)
        # 이름순으로는 앞이지만 **비어 있는** 슬롯 — 이걸 읽으면 0건이 된다.
        # 내용이 있는 슬롯 중 이름순 첫(CX01)을 골라야 한다.
        (new / "AX99" / "Zones").mkdir(parents=True)
        form = _mk_form(tmp, rep)

        dest = os.path.join(tmp, "감시조사.xlsx")
        items = [{"key": cw.sm_key("DEV1-0001", "6412", "ASD X20"),
                  "device": "DEV1-0001", "lot": "6412", "sm": "ASD X20",
                  "path": str(new), "created": "2026-08-05 13:10"}]
        res = cw.survey_items(
            items, machine="AOI-9", form_path=form, recipe="PI3",
            dest_xlsx=dest, copy_dir=os.path.join(tmp, "복사본"))
        assert res["done"] == ["ASD X20"], res
        assert not res["skipped"], res["skipped"]

        d = cm.read_lot_result(dest)
        assert d["lots"] == ["ASD X20"], d["lots"]
        assert d["created"]["ASD X20"] == "2026-08-05 13:10"
        assert d["slots"]["ASD X20"] == "CX01", d["slots"]   # 빈 AX99 는 건너뜀
        assert cw.usable_slots(new) and cw.usable_slots(new)[0].name == "CX01"
        assert not cw.slot_has_config(new / "AX99"), "빈 슬롯을 쓸 수 있다고 보면 안 됨"
        assert d["scan_times"].get("ASD X20"), "Scan일자도 남아야"
        assert d["records"], "파라미터 행이 있어야"
        # 원본은 건드리지 않는다
        assert (new / "CX01" / "Zones" / "Z1.ini").is_file()
    print("  자동 조사: 첫 슬롯 조사 + 생성일자/조사슬롯 기록 OK")


def test_survey_accumulates_into_one_file():
    """회차마다 새 파일을 만들지 않고 **한 파일에 S/M 열을 누적**한다."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "scan"
        rep = _mk_scan_sm(base, "AOI-9", "DEV1-0001", "6412", "ASD", 25)
        a = _mk_scan_sm(base, "AOI-9", "DEV1-0001", "6412", "ASD X20", 30)
        b = _mk_scan_sm(base, "AOI-9", "DEV1-0001", "6412", "ASD REWORK", 35)
        form = _mk_form(tmp, rep)
        dest = os.path.join(tmp, "감시조사.xlsx")
        copy_dir = os.path.join(tmp, "복사본")

        def it(sm, path, created):
            return [{"key": cw.sm_key("DEV1-0001", "6412", sm),
                     "device": "DEV1-0001", "lot": "6412", "sm": sm,
                     "path": str(path), "created": created}]

        r1 = cw.survey_items(it("ASD X20", a, "2026-08-05 13:10"),
                                    machine="AOI-9", form_path=form, recipe="PI3",
                                    dest_xlsx=dest, copy_dir=copy_dir)
        r2 = cw.survey_items(it("ASD REWORK", b, "2026-08-07 08:00"),
                                    machine="AOI-9", form_path=form, recipe="PI3",
                                    dest_xlsx=dest, copy_dir=copy_dir)
        assert r1["merged"]["added"] == 1 and r2["merged"]["added"] == 1
        assert r2["merged"]["lots"] == 2, r2["merged"]

        d = cm.read_lot_result(dest)
        assert d["lots"] == ["ASD X20", "ASD REWORK"], d["lots"]
        assert set(d["created"]) == {"ASD X20", "ASD REWORK"}
        # 결과 파일은 **하나뿐**이어야 한다
        made = [f for f in os.listdir(tmp) if f.startswith("감시조사")]
        assert made == ["감시조사.xlsx"], made
        # 비교표에 같은 S/M 이 중복되지 않는다
        comp = cm.build_comparison([dest])
        pairs = [(r["S/M"], r["호기"]) for r in comp["rows"]]
        assert len(pairs) == len(set(pairs)) == 2, pairs
    print("  결과 한 파일 누적 + 비교표 중복 없음 OK")


def test_survey_skips_when_form_does_not_match():
    """양식과 매칭이 너무 적으면 결과에 넣지 않고 사유를 남긴다."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "scan"
        rep = _mk_scan_sm(base, "AOI-9", "DEV1-0001", "6412", "ASD", 25)
        form = _mk_form(tmp, rep)
        # 설정 파일이 전혀 다른 S/M (양식 항목이 하나도 안 맞음)
        odd = (base / "AOI-9" / "Scanresult" / "2D@R3-DEV1-0001" / "6412"
               / "ODD" / "CX01")
        (odd / "Zones").mkdir(parents=True)
        (odd / "Zones" / "Other.ini").write_text(
            "[General]\nZoneName=완전다른Zone\n[Genesis]\nBrightSeedTh=9\n",
            encoding="utf-8")
        dest = os.path.join(tmp, "감시조사.xlsx")
        res = cw.survey_items(
            [{"key": "k", "device": "DEV1-0001", "lot": "6412", "sm": "ODD",
              "path": str(odd.parent), "created": ""}],
            machine="AOI-9", form_path=form, recipe="PI3",
            dest_xlsx=dest, copy_dir=os.path.join(tmp, "복사본"))
        # **열은 남긴다** — 빼 버리면 그런 S/M 이 있었다는 사실이 사라진다
        assert res["done"] == ["ODD"], res
        assert res["low"] == ["ODD"], res
        assert res["flagged"] and "매칭" in res["flagged"][0][1], res["flagged"]
        d0 = cm.read_lot_result(dest)
        assert "ODD" in d0["lots"], d0["lots"]
        assert "ODD" in d0["lows"], d0["lows"]      # 색 표시 대상으로 기록
        comp0 = cm.build_comparison([dest])
        assert comp0["low_rows"] == {0}, comp0["low_rows"]

        # 슬롯이 아예 없는 S/M 도 조용히 건너뛴다
        empty = base / "AOI-9" / "Scanresult" / "2D@R3-DEV1-0001" / "6412" / "EMPTY"
        empty.mkdir(parents=True)
        res2 = cw.survey_items(
            [{"key": "k2", "device": "DEV1-0001", "lot": "6412", "sm": "EMPTY",
              "path": str(empty), "created": ""}],
            machine="AOI-9", form_path=form, recipe="PI3",
            dest_xlsx=dest, copy_dir=os.path.join(tmp, "복사본"))
        assert res2["done"] == [] and res2["skipped"], res2
    print("  양식 불일치는 열 유지+색 표시, 빈 폴더는 제외 OK")


def test_gui_is_wired():
    """헤드리스 모듈이 **실제로 화면에 연결**돼 있어야 한다(소스 규칙).

    엔진만 있고 부르는 곳이 없으면 프로그램에서는 아무 일도 일어나지 않는다.
    """
    src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "param_manager")
    with open(os.path.join(src_dir, "equip_app.py"), encoding="utf-8") as fh:
        app = fh.read()
    assert "from . import cmwatcher" in app, "cmwatcher 를 import 하지 않음"
    # ① 탭 최상단 감시 배너 + 설정창
    for name in ("_cm_watch_banner", "_cmw_dialog", "_cmw_forms_dialog",
                 "_cmw_make_form", "_cmw_build_form"):
        assert f"def {name}(" in app, name
    # 감시 배너는 조사 단계(Step 1)보다 **먼저**(최상단) 그려져야 한다 —
    # 탭에 들어오면 바로 보이게(종전엔 맨 아래 7번이라 초기 화면에서 안 보였다).
    assert app.index("self._cm_watch_banner(inner)") < app.index("조사할 장비(호기) 선택"), \
        "감시 배너가 조사 단계보다 위에 있지 않음(초기 화면에서 안 보임)"
    # ② 주기 실행이 실제로 걸려 있어야 한다(안 걸면 영원히 안 돈다)
    assert "def _cmw_tick(" in app and "self.after(40_000, self._cmw_tick)" in app, \
        "주기 확인 타이머가 시작되지 않음"
    assert "self.after(60_000, self._cmw_tick)" in app, "틱이 스스로 다시 예약되지 않음"
    # should_run(now, settings, state) — now 가 첫 인자다. 인자를 빼먹으면
    # tick 마다 TypeError 로 감시가 영원히 안 돈다(실제로 그랬다).
    assert "watcher.should_run(datetime.now(), s, st)" in app, \
        "should_run 을 올바른 시그니처(now, s, st)로 부르지 않음"
    # ③ 회차 로직은 **헤드리스**(cmwatcher.run_cycle)에 있어야 테스트가 잡는다.
    #    GUI 는 로컬 루트·변환계수만 넘기는 얇은 래퍼여야 한다.
    m = re.search(r"def _cmw_cycle_work.*?(?=\n    def )", app, re.S)
    assert m, "_cmw_cycle_work 를 찾지 못함"
    body = m.group(0)
    assert "cmwatcher.run_cycle(" in body, "회차 로직을 헤드리스로 부르지 않음"
    assert "local_root=" in body and "coef_rows=" in body, "필요한 인자를 넘기지 않음"
    # 무인 회차는 모달을 띄우면 안 된다
    assert "_run_bg(" in app, "무인 회차가 백그라운드로 돌지 않음"
    # ④ 대표 S/M 은 최신순 후보에서 사람이 고른다
    f = re.search(r"def _cmw_make_form.*?(?=\n    def )", app, re.S)
    assert f and "cmwatcher.sm_candidates(" in f.group(0), "대표 S/M 후보 조회 없음"
    assert "_pick_list_chooser(" in f.group(0), "사람이 고르는 단계가 없음"
    # ④' 다중 레시피면 레시피별로 양식을 만든다(detect_recipes → set_forms)
    b = re.search(r"def _cmw_build_form.*?(?=\n    def _cmw_pick_file)", app, re.S)
    assert b and "cm.detect_recipes(" in b.group(0), "감시 양식이 다중 레시피를 감지하지 않음"
    assert "cmwatcher.set_forms(" in app, "레시피별 양식 목록을 묶지 않음(set_forms)"
    # ④'' 대표 S/M 은 **로컬로 안전복사한 뒤** 그 복사본을 읽는다(원본 반복접근 금지)
    assert "cm.copy_lot(" in b.group(0) and "cm.set_wafer(" in b.group(0), \
        "대표 S/M 을 로컬로 복사해 읽지 않음"
    assert "자동감시" in b.group(0) and "commonality_root(local" in b.group(0), \
        "대표 S/M 복사본이 로컬 자동감시 폴더가 아님"
    # ⑤ 산출물은 로컬(commonality 규칙)
    assert "_cmw_local(" in app and "save_dir" not in re.findall(
        r"def _cmw_local.*?(?=\n    def )", app, re.S)[0], \
        "감시 설정을 저장폴더에 두고 있음"
    # ⑥ 창을 닫아도 **두 감시 중 하나라도** 켜져 있으면 트레이 상주(백그라운드 계속).
    #    종전엔 _on_close 가 장비 감시(_watch_is_on)만 봐서, commonality 감시만 켠 채
    #    창을 닫으면 프로그램이 종료돼 감시가 멈췄다.
    assert "def _cmw_is_on(" in app, "commonality 감시 on 판정(_cmw_is_on)이 없음"
    oc = re.search(r"def _on_close.*?(?=\n    def |\n\n\ndef )", app, re.S)
    assert oc and "_any_watch_on(" in oc.group(0), \
        "_on_close 가 두 감시를 함께 보지 않음(_any_watch_on)"
    anyw = re.search(r"def _any_watch_on.*?(?=\n    def )", app, re.S)
    assert anyw and "_cmw_is_on(" in anyw.group(0) and "_watch_is_on(" in anyw.group(0), \
        "_any_watch_on 이 장비·commonality 감시를 OR 하지 않음"
    # ⑦ 트레이 툴팁이 **어떤 감시가 도는지** 보여준다(마우스를 올리면 뜬다).
    assert "def _watch_tooltip(" in app, "트레이 툴팁 헬퍼(_watch_tooltip)가 없음"
    tt = re.search(r"def _watch_tooltip.*?(?=\n    def )", app, re.S)
    assert tt and "Commonality" in tt.group(0) and "장비" in tt.group(0), \
        "툴팁이 장비/commonality 두 감시를 구분해 보여주지 않음"
    ts = re.search(r"def _tray_start.*?(?=\n    def )", app, re.S)
    assert ts and "_watch_tooltip(" in ts.group(0), "트레이 시작이 감시상태 툴팁을 안 씀"
    print("  GUI 연결(카드·설정창·주기틱·회차·대표S/M·양쪽 감시 상주·툴팁) OK")


def _write_watch_plan(path, rows):
    """감시 대상 계획 엑셀 하나 — rows=[(device, lot, machine)]."""
    cw.create_watch_plan_template(path, [
        {"디바이스명": d, "공정번호": l, "AOI호기": m} for d, l, m in rows])


def test_run_cycle_first_is_baseline_then_detects_and_surveys():
    """헤드리스 회차 전체 — 첫 회차 무알림, 둘째 회차에 신규 감지+자동 조사.

    GUI(_cmw_cycle_work)가 부르는 바로 그 로직이다. tkinter 없이 끝까지 돈다.
    """
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "scan"
        local = str(Path(tmp) / "CamtekAOI")
        rep = _mk_scan_sm(base, "AOI-9", "DEV1-0001", "6412", "ASD", 25)
        form = _mk_form(tmp, rep)

        plan = os.path.join(tmp, cw.WATCH_PLAN_FILENAME)
        _write_watch_plan(plan, [("DEV1-0001", "6412", "AOI-9")])
        cm_plan = os.path.join(tmp, cm.PLAN_FILENAME)

        s, st = cw.load_settings(local)
        s.machines = ["AOI-9"]
        s.watch_plan, s.cm_plan = plan, cm_plan
        s.roots = {"AOI-9": str(base)}
        s.settle_minutes = 0                 # 테스트에선 안정화 대기 없음
        cw.set_form(s, "AOI-9", "DEV1-0001", "6412", form, "PI3", sm="ASD")

        # ── 1회차: 기존 ASD 뿐 → 기준선만, 알림 없음
        r1 = cw.run_cycle(s, st, local_root=local, coef_rows=[])
        assert r1["found"] == [], r1
        assert st.baseline is True
        assert not os.path.exists(cw.result_path(local, "AOI-9", "PI3")), \
            "기준선 회차인데 조사 결과를 만들었다"

        # ── 새 S/M 이 생김
        _mk_scan_sm(base, "AOI-9", "DEV1-0001", "6412", "ASD X20", 30)

        # ── 2회차: 신규 감지 → 계획 추가 + 자동 조사
        r2 = cw.run_cycle(s, st, local_root=local, coef_rows=[])
        assert [i["sm"] for i in r2["found"]] == ["ASD X20"], r2["found"]
        assert r2["surveyed"] == ["ASD X20"], r2
        # 조사 계획 엑셀에 생성일자와 함께 추가됐다
        added = cm.read_plan(cm_plan)
        assert any(rr.get("S/M") == "ASD X20" for rr in added), added
        # 결과 파일에 열이 누적됐다
        d = cm.read_lot_result(cw.result_path(local, "AOI-9", "PI3"))
        assert d["lots"] == ["ASD X20"], d["lots"]
        assert d["slots"].get("ASD X20"), "조사슬롯 기록 없음"
        # 상태가 저장됐다(다시 읽어도 기준선·마지막 결과 유지)
        s2, st2 = cw.load_settings(local)
        assert st2.baseline is True and "조사 1건" in st2.last_result
    print("  run_cycle 전체(기준선→감지→계획추가→조사→저장) OK")


def test_run_cycle_missing_form_adds_plan_but_skips_survey():
    """양식이 없는 대상은 계획 추가·알림만, 조사는 건너뛴다(사유 남김)."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "scan"
        local = str(Path(tmp) / "CamtekAOI")
        _mk_scan_sm(base, "AOI-9", "DEV1-0001", "6412", "ASD", 25)
        plan = os.path.join(tmp, cw.WATCH_PLAN_FILENAME)
        _write_watch_plan(plan, [("DEV1-0001", "6412", "AOI-9")])
        cm_plan = os.path.join(tmp, cm.PLAN_FILENAME)

        s, st = cw.load_settings(local)
        s.machines = ["AOI-9"]
        s.watch_plan, s.cm_plan, s.roots = plan, cm_plan, {"AOI-9": str(base)}
        s.settle_minutes = 0
        # 양식 지정 안 함

        cw.run_cycle(s, st, local_root=local)        # 기준선
        _mk_scan_sm(base, "AOI-9", "DEV1-0001", "6412", "ASD X20", 30)
        r = cw.run_cycle(s, st, local_root=local)
        assert [i["sm"] for i in r["found"]] == ["ASD X20"]
        assert r["surveyed"] == [], "양식 없는데 조사함"
        assert any("양식 없음" in n for n in r["notes"]), r["notes"]
        # 계획에는 들어갔다(무엇이 언제 생겼는지 기록은 남겨야)
        assert any(rr.get("S/M") == "ASD X20" for rr in cm.read_plan(cm_plan))
        assert not os.path.exists(cw.result_path(local, "AOI-9", "PI3"))
    print("  run_cycle 양식 없으면 계획만·조사 건너뜀 OK")


def test_run_cycle_skips_machine_without_root():
    """호기 폴더가 지정 안 된 호기는 건너뛰고 사유를 남긴다(예외 없이)."""
    with tempfile.TemporaryDirectory() as tmp:
        local = str(Path(tmp) / "CamtekAOI")
        plan = os.path.join(tmp, cw.WATCH_PLAN_FILENAME)
        _write_watch_plan(plan, [("DEV1-0001", "6412", "AOI-9")])
        s, st = cw.load_settings(local)
        s.machines = ["AOI-9"]
        s.watch_plan = plan
        s.roots = {}                          # 루트 미지정
        r = cw.run_cycle(s, st, local_root=local)
        assert r["found"] == []
        assert any("호기 폴더 미지정" in n for n in r["notes"]), r["notes"]
        assert st.last_run, "실패해도 회차 시각은 기록"
    print("  run_cycle 호기 폴더 미지정 안전 처리 OK")


def test_run_cycle_uses_coefficient_from_rows():
    """계수는 넘겨준 coef_rows(변환계수.xlsx)로만 적용된다 — 파일을 고치지 않는다."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "scan"
        local = str(Path(tmp) / "CamtekAOI")
        rep = _mk_scan_sm(base, "AOI-9", "DEV1-0001", "6412", "ASD", 25)
        # 대표 S/M 에 LINEAR 변환 대상(µ) 파라미터
        (rep / "CX01" / "Zones" / "Z1.ini").write_text(
            "[General]\nZoneName=PI Opening\n[Surface]\nBrightLength=100\n",
            encoding="utf-8")
        form = _mk_form(tmp, rep)
        plan = os.path.join(tmp, cw.WATCH_PLAN_FILENAME)
        _write_watch_plan(plan, [("DEV1-0001", "6412", "AOI-9")])

        s, st = cw.load_settings(local)
        s.machines = ["AOI-9"]
        s.watch_plan = plan
        s.cm_plan = os.path.join(tmp, cm.PLAN_FILENAME)
        s.roots = {"AOI-9": str(base)}
        s.settle_minutes = 0
        cw.set_form(s, "AOI-9", "DEV1-0001", "6412", form, "PI3", sm="ASD")
        cw.run_cycle(s, st, local_root=local, coef_rows=[])   # 기준선

        new = _mk_scan_sm(base, "AOI-9", "DEV1-0001", "6412", "ASD X20", 30)
        (new / "CX01" / "Zones" / "Z1.ini").write_text(
            "[General]\nZoneName=PI Opening\n[Surface]\nBrightLength=100\n",
            encoding="utf-8")
        # coef 키는 (호기, 변형). 변형 없는 행 = 그 호기의 공통 계수(어떤 변형에도 적용)
        coef_rows = [{"호기": "AOI-9", "MAG": "5", "변형": "",
                      "계수": "0.5", "비고": "사람"}]
        before = [dict(r) for r in coef_rows]
        cw.run_cycle(s, st, local_root=local, coef_rows=coef_rows)

        d = cm.read_lot_result(cw.result_path(local, "AOI-9", "PI3"))
        length = next((r for r in d["records"]
                       if "Length" in engine._s(r.get("Parameter"))), None)
        assert length is not None, d["records"]
        # BrightLength=100 raw × 계수 0.5 = 50 (기본계수면 84.6 근처)
        assert abs(float(length["ASD X20"]) - 50.0) < 0.01, length
        # coef_rows(변환계수.xlsx)는 읽기만 — 새 행이 붙거나 값이 바뀌면 안 된다
        assert coef_rows == before, "회차가 변환계수를 고쳤다"
    print("  run_cycle 계수는 coef_rows 로만 적용, 파일 무변경 OK")


def test_forms_multi_and_legacy_compat():
    """감시 대상에 **레시피별 양식 여러 개**를 묶을 수 있다(다중 레시피).
    구 형식(단일 dict)도 1개짜리 목록으로 정규화해 읽는다(하위호환)."""
    s = cw.CmWatchSettings()
    cw.set_forms(s, "AOI-9", "DEV", "6412", [
        {"form": "/f1.xlsx", "recipe": "PI3_PI", "prefix": "", "sm": "ASD"},
        {"form": "/f2.xlsx", "recipe": "PI3_PI_Bubble", "prefix": "Recipe2-", "sm": "ASD"}])
    fs = cw.forms_for(s, "AOI-9", "DEV", "6412")
    assert [f["recipe"] for f in fs] == ["PI3_PI", "PI3_PI_Bubble"], fs
    assert [f["prefix"] for f in fs] == ["", "Recipe2-"], fs
    # 대표(첫) 양식 호환 — form_for 는 여전히 dict 하나
    assert cw.form_for(s, "AOI-9", "DEV", "6412")["recipe"] == "PI3_PI"
    # 구 형식(단일 dict, prefix 없음)도 목록 1개로
    s2 = cw.CmWatchSettings()
    s2.forms = {cw.survey_key("AOI-9", "DEV", "6412"):
                {"form": "/old.xlsx", "recipe": "PI3", "sm": "ASD"}}
    fs2 = cw.forms_for(s2, "AOI-9", "DEV", "6412")
    assert len(fs2) == 1 and fs2[0]["recipe"] == "PI3" and fs2[0]["prefix"] == "", fs2
    # set_form(단일)도 목록에 저장된다
    cw.set_form(s2, "AOI-9", "DEV", "7000", "/one.xlsx", "PI4")
    assert len(cw.forms_for(s2, "AOI-9", "DEV", "7000")) == 1
    print("  레시피별 양식 목록 + 구 단일형식 호환 OK")


def _add_recipe2(slot_dir: Path, delta2):
    """기존 슬롯(CX01)에 **두 번째 레시피**(RecipesInfo + Recipe2- 파일)를 얹는다."""
    (slot_dir / "RecipesInfo.ini").write_text(
        "[Recipe-1]\nName=PI\n[Recipe-2]\nName=PI_Bubble\n[Recipes]\nCount=2\n",
        encoding="utf-8")
    (slot_dir / "Recipe2-Zones").mkdir(exist_ok=True)
    (slot_dir / "Recipe2-Zones" / "Z1.ini").write_text(
        f"[General]\nZoneName=PI Opening\n[Surface]\nHigh_Delta={delta2}\n",
        encoding="utf-8")
    (slot_dir / "Recipe2-OpticPreset.ini").write_text(
        "[Scan2d]\nCameraName=TDI\nMag=5\nLightSrcRef_NominalGL=1\n", encoding="utf-8")


def _mk_form_prefixed(tmp, slot_dir, level, prefix, name):
    """대표 슬롯을 그 레시피 접두로 파싱해 확정 양식 하나."""
    from param_manager import formbuilder
    pivot, _ = cm.parse_lots([("REP", Path(slot_dir))], level=level,
                             recipe_prefix=prefix)
    init = os.path.join(tmp, f"init_{name}")
    form = os.path.join(tmp, name)
    formbuilder.build_initial_workbook(pivot, init, level=level)
    formbuilder.build_final_from_initial(init, form, level=level, aoi="AOI-9")
    return form


def test_run_cycle_surveys_all_recipes():
    """다중 레시피면 회차가 **레시피마다 양식을 물려 둘 다 조사**한다.

    예전엔 대상당 양식이 하나뿐이라 2번째 레시피(RecipeN- 접두 파일)가 조사에서
    통째로 빠졌다. 이제 레시피별 양식·결과가 각각 나온다.
    """
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "scan"
        local = str(Path(tmp) / "CamtekAOI")
        rep = _mk_scan_sm(base, "AOI-9", "DEV1-0001", "6412", "ASD", 25)
        _add_recipe2(rep / "CX01", 77)
        form1 = _mk_form_prefixed(tmp, rep / "CX01", "PI3_PI", "", "f_r1.xlsx")
        form2 = _mk_form_prefixed(tmp, rep / "CX01", "PI3_PI_Bubble", "Recipe2-",
                                  "f_r2.xlsx")

        plan = os.path.join(tmp, cw.WATCH_PLAN_FILENAME)
        _write_watch_plan(plan, [("DEV1-0001", "6412", "AOI-9")])
        s, st = cw.load_settings(local)
        s.machines = ["AOI-9"]
        s.watch_plan = plan
        s.cm_plan = os.path.join(tmp, cm.PLAN_FILENAME)
        s.roots = {"AOI-9": str(base)}
        s.settle_minutes = 0
        cw.set_forms(s, "AOI-9", "DEV1-0001", "6412", [
            {"form": form1, "recipe": "PI3_PI", "prefix": "", "sm": "ASD"},
            {"form": form2, "recipe": "PI3_PI_Bubble", "prefix": "Recipe2-",
             "sm": "ASD"}])

        cw.run_cycle(s, st, local_root=local, coef_rows=[])          # 기준선

        new = _mk_scan_sm(base, "AOI-9", "DEV1-0001", "6412", "ASD X20", 30)
        _add_recipe2(new / "CX01", 88)
        r2 = cw.run_cycle(s, st, local_root=local, coef_rows=[])

        # 두 레시피 결과 파일이 **각각** 생겼다
        p1 = cw.result_path(local, "AOI-9", "PI3_PI")
        p2 = cw.result_path(local, "AOI-9", "PI3_PI_Bubble")
        assert os.path.exists(p1) and os.path.exists(p2), (p1, p2)
        d1, d2 = cm.read_lot_result(p1), cm.read_lot_result(p2)
        assert d1["lots"] == ["ASD X20"] and d2["lots"] == ["ASD X20"], (d1, d2)
        # 같은 S/M 이 두 레시피 모두에서 조사됐다
        assert r2["surveyed"].count("ASD X20") == 2, r2["surveyed"]

        # 레시피별로 **다른 값**(접두 라우팅 확인): Recipe-1=base(30), Recipe-2=Recipe2-(88)
        def hd(d):
            for r in d["records"]:
                if "Delta" in engine._s(r.get("Parameter")):
                    return engine._s(r.get("ASD X20"))
            return None
        v1, v2 = hd(d1), hd(d2)
        assert v1 and v2 and v1 != v2, (v1, v2)
    print("  다중 레시피 회차: 레시피마다 양식 물려 둘 다 조사(값 분리) OK")


if __name__ == "__main__":
    for t in [test_watch_plan_template_and_targets, test_first_cycle_is_baseline_only,
              test_backup_scanresult_is_not_new, test_unsettled_folder_is_deferred,
              test_unchanged_lot_dir_is_skipped, test_append_to_cm_plan_with_created_date,
              test_append_adds_column_to_old_plan, test_settings_roundtrip_is_local,
              test_sm_candidates_sorted_by_created_desc,
              test_form_binding_is_per_target,
              test_survey_records_slot_and_created,
              test_survey_accumulates_into_one_file,
              test_survey_skips_when_form_does_not_match,
              test_gui_is_wired,
              test_run_cycle_first_is_baseline_then_detects_and_surveys,
              test_run_cycle_missing_form_adds_plan_but_skips_survey,
              test_run_cycle_skips_machine_without_root,
              test_run_cycle_uses_coefficient_from_rows,
              test_forms_multi_and_legacy_compat,
              test_run_cycle_surveys_all_recipes]:
        run(t)
    print(f"==== {PASS}/{PASS + FAIL} passed ====")
    sys.exit(1 if FAIL else 0)
