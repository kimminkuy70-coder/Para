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
        assert res["done"] == [], res
        assert res["skipped"] and "매칭" in res["skipped"][0][1], res["skipped"]
        assert not os.path.exists(dest), "안 맞는 데이터로 결과를 만들면 안 된다"

        # 슬롯이 아예 없는 S/M 도 조용히 건너뛴다
        empty = base / "AOI-9" / "Scanresult" / "2D@R3-DEV1-0001" / "6412" / "EMPTY"
        empty.mkdir(parents=True)
        res2 = cw.survey_items(
            [{"key": "k2", "device": "DEV1-0001", "lot": "6412", "sm": "EMPTY",
              "path": str(empty), "created": ""}],
            machine="AOI-9", form_path=form, recipe="PI3",
            dest_xlsx=dest, copy_dir=os.path.join(tmp, "복사본"))
        assert res2["done"] == [] and res2["skipped"], res2
    print("  양식 불일치·빈 폴더는 결과에서 제외 OK")


if __name__ == "__main__":
    for t in [test_watch_plan_template_and_targets, test_first_cycle_is_baseline_only,
              test_backup_scanresult_is_not_new, test_unsettled_folder_is_deferred,
              test_unchanged_lot_dir_is_skipped, test_append_to_cm_plan_with_created_date,
              test_append_adds_column_to_old_plan, test_settings_roundtrip_is_local,
              test_sm_candidates_sorted_by_created_desc,
              test_form_binding_is_per_target,
              test_survey_records_slot_and_created,
              test_survey_accumulates_into_one_file,
              test_survey_skips_when_form_does_not_match]:
        run(t)
    print(f"==== {PASS}/{PASS + FAIL} passed ====")
    sys.exit(1 if FAIL else 0)
