"""Lot 단위 Batch Report 모델 테스트.

합성 자료는 사용자가 준 실제 Batch Report 424개에서 확인한 형식을 그대로 흉내 낸다
(웨이퍼 표 열, Wafer ID 3가지 형식, S/M 꼬리, 25→1 슬롯 순서, LoadPort 미판독 행).
실제 자료로도 돌려 보려면 PARA_BATCH_SAMPLE=폴더 를 지정한다(저장소에는 넣지 않음).
"""
import os
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from param_manager import lotmodel as lm

JOB, SETUP = "CMP2D-DT-GH10N-BIN1-H-U1_0856268PD-0A", "6392"
FMT = "%d-%b-%y %I:%M:%S %p"


def report(sm, rows, start, minutes=30, recipe="2D_WBG", job=JOB, setup=SETUP):
    """rows = [(wafer_id, status)] — 장비 순서(보통 슬롯 25→1)."""
    begin = datetime.strptime(start, "%Y-%m-%d %H:%M")
    end = begin + timedelta(minutes=minutes)
    wafers = []
    for wid, status in rows:
        unread = wid.startswith("Slot")
        ok = status == "Pass"
        wafers.append({"Lot": "LoadPort A" if unread else sm, "Wafer ID": wid, "Faults": "0" if ok else "-",
                       "Scanned Dice": "29" if ok else "-", "Bad Dice": "1" if ok else "-",
                       "Good Dice": "28" if ok else "-", "Yield": "96.6" if ok else "-",
                       "Pass/Fail": status, "Recipe(s)": recipe})
    name = f"{job}_{setup}_{sm}_{begin:%y-%b-%d}_({begin:%H.%M.%S})_BatchReport.htm"
    meta = [("Batch Start", begin.strftime(FMT)), ("Batch End", end.strftime(FMT)),
            ("Batch Time", f"00:{minutes:02d}:00"), ("Wafers Scanned", str(sum(s == "Pass" for _, s in rows))),
            ("Job/Setup", f"{job}/{setup}")]
    return {"file_name": name, "metadata": meta, "wafers": wafers, "table_count": 3}


def full(statuses, ids=None):
    """25행(슬롯 25→1). statuses 는 슬롯 25부터의 상태 목록(모자라면 Pass)."""
    statuses = list(statuses) + ["Pass"] * (25 - len(statuses))
    ids = ids or [str(slot) for slot in range(25, 0, -1)]
    return list(zip(ids, statuses))


def records(*items):
    """items = (machine, report)"""
    return [{"id": f"{i:03d}", "machine": m, "report": r} for i, (m, r) in enumerate(items)]


def only(model, code):
    lots = [lot for lot in model["lots"] if lot["code"] == code]
    assert len(lots) == 1, [lot["label"] for lot in model["lots"]]
    return lots[0]


def wafer(bunch, slot):
    return next(w for w in bunch["wafers"] if w["slot"] == slot)


class Rules(unittest.TestCase):
    def test_sm_and_lot_code(self):
        name = f"{JOB}_{SETUP}_KDT-PR RW_26-May-06_(11.21.36)_BatchReport.htm"
        self.assertEqual(lm.sm_of(name, JOB, SETUP), "KDT-PR RW")
        self.assertEqual(lm.sm_of(f"{JOB}_{SETUP}_BBF_WBG_26-May-22_(10.07.42)_BatchReport.htm", JOB, SETUP), "BBF_WBG")
        # 형식이 다르면 웨이퍼 Lot 칸 최빈값(LoadPort 제외)
        self.assertEqual(lm.sm_of("odd.htm", JOB, SETUP, ["LoadPort A", "XYZ", "XYZ"]), "XYZ")
        cases = {"BAW": "BAW", "BAW-0911S": "BAW", "BAW0911S": "BAW", "NSW WBG": "NSW", "HXN - WBG": "HXN",
                 "CCP-PIDS7": "CCP", "0701 N SPT PARTICLE 1-3 RE": "SPT", "bbf_re": "BBF",
                 "0": None, "FOCUS": None, "": None}
        for sm, code in cases.items():
            self.assertEqual(lm.lot_code(sm), code, sm)

    def test_pass_and_first_phrase_is_cause(self):
        self.assertIsNone(lm.cause_of("Pass"))
        self.assertEqual(lm.cause_of("Scan 2D Error. Aborted.")[0], "2D Scan 오류")
        self.assertEqual(lm.cause_of("Failed to read wafer id. Reading error = U4R-ON9?NT. Wafer Skipped.")[0],
                         "Wafer ID 판독 오류")
        self.assertEqual(lm.cause_of("Clean Reference Error.")[0], "Clean Reference 오류")
        self.assertEqual(lm.cause_of(""), (lm.EMPTY, "(빈 상태)"))          # 빈칸도 Error
        self.assertEqual(lm.cause_of("Laser drift")[0], lm.UNKNOWN)

    def test_chain_after_first_error(self):
        a = lm.attempt(records(("AOI-1", report("NSN", full(["Pass", "Scan 2D Error.", "Aborted.", "Skipped."]), "2026-09-01 19:41")))[0])
        kinds = [r["kind"] for r in a["rows"][:4]]
        self.assertEqual(kinds, [None, "원인", "연쇄", "연쇄"])
        b = lm.attempt(records(("AOI-1", report("BAW", full(["Aborted.", "Aborted."]), "2026-05-23 10:05")))[0])
        self.assertEqual([r["kind"] for r in b["rows"][:2]], ["원인", "연쇄"])   # 첫 Aborted 는 직접

    def test_slot_rules(self):
        # 25행이면 Wafer ID 형식과 무관하게 1행=25번(실데이터 8,490행 전부 일치).
        ids = [f"W74942{n:02d}XYH0" for n in range(26, 51)]
        a = lm.attempt(records(("AOI-1", report("CYG", full([], ids), "2026-05-27 12:02")))[0])
        self.assertEqual([r["slot"] for r in a["rows"]][:3], [25, 24, 23])
        self.assertEqual(lm.wafer_slot(0, 3, "Slot 14"), 14)
        self.assertEqual(lm.wafer_slot(0, 3, "14"), 14)
        self.assertEqual(lm.wafer_slot(0, 3, "SF14G14-A0"), 14)
        self.assertIsNone(lm.wafer_slot(0, 3, "W7494230XYA6"))
        self.assertEqual(lm.full_id("SF14G25-A0"), ("SF14G", 25))
        self.assertTrue(lm.ids_close("SH47T", "SA47T"))
        self.assertFalse(lm.ids_close("SC93F", "SA78K"))


class Bunches(unittest.TestCase):
    def test_bunches_split_at_12h_and_dup_only_inside_bunch(self):
        """BBF 실제 흐름: WBG 시도 3회 → 25.5h 뒤 CMP → 27일 뒤 재검사."""
        m = lm.build(records(
            ("AOI-1", report("BBF_WBG", full(["Nothing to Scan."] * 19 + ["Aborted."] * 6), "2026-05-22 08:38")),
            ("AOI-1", report("BBF_WBG", full(["Pass"] * 21 + ["Aborted."] * 4), "2026-05-22 08:54")),
            ("AOI-1", report("BBF_WBG", [(str(s), "Pass") for s in range(5, 0, -1)], "2026-05-22 09:54")),
            ("AOI-1", report("BBF", full([], [f"SA89H{s:02d}-C4" for s in range(25, 0, -1)]), "2026-05-23 11:41", recipe="2D")),
            ("AOI-1", report("BBF", full(["Wafer Map Import failed."] * 11 + ["Aborted."] * 14,
                                         [f"SA89H{s:02d}-C4" for s in range(25, 14, -1)] + [f"Slot {s}" for s in range(14, 0, -1)]),
                             "2026-06-19 18:57", recipe="2D")),
            ("AOI-1", report("BBF_RE", full([], [f"SA89H{s:02d}-C4" for s in range(25, 0, -1)]), "2026-06-19 19:11", recipe="2D"))))
        lot = only(m, "BBF")
        self.assertEqual(lot["lot_id"], "SA89H")              # WBG 숫자 ID 묶음도 같은 Lot
        self.assertEqual([len(b["attempts"]) for b in lot["bunches"]], [3, 1, 2])
        self.assertEqual([b["step"] for b in lot["bunches"]], ["2D_WBG", "2D", "2D"])
        wbg, cmp_, re_ = lot["bunches"]
        # 묶음 1: 25번은 시도 2에서 처음 Pass → 회복. 5번은 시도 2·3 둘 다 Pass → 중복.
        self.assertEqual(wafer(wbg, 25)["verdict"], lm.RECOVERED)
        self.assertEqual(wafer(wbg, 5)["verdict"], lm.DUPLICATE)
        self.assertEqual(wafer(wbg, 5)["pick"], 2)             # 가장 나중 Pass 추천
        self.assertEqual(wbg["counts"], {lm.RECOVERED: 24, lm.DUPLICATE: 1})
        self.assertEqual(cmp_["counts"], {lm.OK: 25})          # 묶음이 다르면 중복 아님
        self.assertEqual(re_["counts"], {lm.RECOVERED: 25})    # Slot 14 ↔ SA89H14 같은 웨이퍼
        self.assertEqual(lot["state"], "오류 후 회복")

    def test_split_scan_totals_use_picked_rows(self):
        """NSN: 에러로 3번 나눠 스캔해 25장 완료 — 합계는 웨이퍼마다 고른 행 하나씩."""
        ids = [f"SH66M{s:02d}-D5" for s in range(25, 0, -1)]
        first = list(zip(ids, ["Pass"] * 3 + ["Scan 2D Error.", "Aborted.", "Failed to read wafer id. Reading error = ."] + ["Skipped."] * 19))
        second = list(zip(ids[3:], ["Pass", "Pass", "Aborted."] + ["Skipped."] * 19))
        third = [(i, "Pass") for i in ids[5:]]
        m = lm.build(records(("AOI-1", report("NSN", first, "2026-09-01 19:41", recipe="2D")),
                             ("AOI-1", report("NSN", second, "2026-09-01 23:34", recipe="2D")),
                             ("AOI-1", report("NSN", third, "2026-09-02 05:34", recipe="2D"))))
        bunch = only(m, "NSN")["bunches"][0]
        self.assertEqual(bunch["counts"], {lm.OK: 3, lm.RECOVERED: 22})
        self.assertEqual(bunch["totals"]["scanned"], 25 * 29)
        self.assertEqual(bunch["totals"]["bad"], 25)
        self.assertEqual(wafer(bunch, 22)["cause"], "2D Scan 오류")
        self.assertEqual(wafer(bunch, 20)["cause"], "Wafer ID 판독 오류")

    def test_chained_wafer_cause_is_the_trigger(self):
        """KVW: Nothing to Scan 뒤의 Skipped 는 원인 '검사 대상 없음'(연쇄)로 센다."""
        m = lm.build(records(("AOI-1", report("KVW WBG", full(["Nothing to Scan."] * 8 + ["Skipped."] * 17), "2026-07-09 17:25")),
                             ("AOI-1", report("KVW WBG", full([]), "2026-07-09 20:02"))))
        bunch = only(m, "KVW")["bunches"][0]
        self.assertEqual((wafer(bunch, 18)["cause"], wafer(bunch, 18)["chain_only"]), ("검사 대상 없음", False))
        self.assertEqual((wafer(bunch, 17)["cause"], wafer(bunch, 17)["chain_only"]), ("검사 대상 없음", True))
        from param_manager import lotreport
        summary = {c["cause"]: c for c in lotreport.cause_summary(m)}
        self.assertEqual((summary["검사 대상 없음"]["wafers"], summary["검사 대상 없음"]["chain"]), (25, 17))
        self.assertNotIn("검사 제외", summary)

    def test_override_changes_pick_and_totals(self):
        m = lm.build(records(("AOI-1", report("KVW WBG", full([]), "2026-07-09 20:02")),
                             ("AOI-1", report("KVW WBG", full([]), "2026-07-09 21:42"))))
        bunch = only(m, "KVW")["bunches"][0]
        self.assertEqual(bunch["duplicates"], 25)
        self.assertEqual(wafer(bunch, 25)["pick"], 1)
        first_id = bunch["attempts"][0]["id"]
        m = lm.build(records(("AOI-1", report("KVW WBG", full([]), "2026-07-09 20:02")),
                             ("AOI-1", report("KVW WBG", full([]), "2026-07-09 21:42"))),
                     overrides={(bunch["key"], "S25"): first_id})
        chosen = wafer(only(m, "KVW")["bunches"][0], 25)
        self.assertEqual((chosen["pick"], chosen["overridden"]), (0, True))

    def test_unresolved(self):
        m = lm.build(records(("AOI-1", report("FMC-WBG", full(["Aborted."] * 25), "2026-07-03 01:58"))))
        lot = only(m, "FMC")
        self.assertEqual((lot["unresolved"], lot["state"]), (25, "미해결 있음"))
        self.assertEqual(lot["bunches"][0]["totals"]["scanned"], 0)


class Lots(unittest.TestCase):
    def test_same_code_different_lot_id_is_split(self):
        """BAH: 같은 S/M 이 같은 날 서로 다른 Lot 2개에 쓰였다 → Wafer ID 의 Lot ID 로 가른다."""
        sc = [f"SC93F{s:02d}-F1" for s in range(25, 0, -1)]
        sa = [f"SA78K{s:02d}-B6" for s in range(25, 0, -1)]
        m = lm.build(records(("AOI-1", report("BAH-WBG", full([]), "2026-05-19 10:15")),
                             ("AOI-1", report("BAH", full([], sc), "2026-05-20 09:05", recipe="2D")),
                             ("AOI-1", report("BAH", full([], sc), "2026-05-20 20:09", recipe="2D")),
                             ("AOI-1", report("BAH", full([], sa), "2026-05-20 21:35", recipe="2D"))))
        labels = sorted(lot["label"] for lot in m["lots"])
        self.assertEqual(labels, ["BAH · Lot ID 미확인", "BAH · SA78K", "BAH · SC93F"])
        sc_lot = next(lot for lot in m["lots"] if lot["lot_id"] == "SC93F")
        self.assertEqual(sc_lot["duplicates"], 25)            # 같은 Lot 을 두 번 스캔

    def test_lot_id_reading_error_is_tolerated(self):
        ids = [f"SH47T{s:02d}-E0" for s in range(25, 0, -1)]
        ids[2] = "SA47T23-G5"                                  # 실데이터의 판독 오차
        m = lm.build(records(("AOI-1", report("NSF WBG", full([], ids), "2026-08-28 07:12", recipe="2D"))))
        self.assertEqual(len(m["lots"]), 1)
        self.assertEqual(m["lots"][0]["lot_id"], "SH47T")

    def test_check_scans_are_excluded(self):
        m = lm.build(records(("AOI-1", report("FOCUS", [("24", "Aborted.")], "2026-03-24 02:06")),
                             ("AOI-1", report("0", full([]), "2026-07-10 10:47")),
                             ("AOI-1", report("0701 N SPT PARTICLE 1-3 RE", [("10", "Pass")], "2026-07-02 04:06"))))
        self.assertEqual(sorted(a["sm"] for a in m["excluded"]), ["0", "FOCUS"])
        self.assertEqual([lot["code"] for lot in m["lots"]], ["SPT"])


class MachineMove(unittest.TestCase):
    def failed(self, machine, start):
        return (machine, report("LDF", full(["Alignment Error."] + ["Aborted."] * 24), start))

    def test_unresolved_then_other_machine_same_step_joins(self):
        m = lm.build(records(self.failed("AOI-9", "2026-07-16 08:00"), self.failed("AOI-9", "2026-07-16 09:00"),
                             self.failed("AOI-9", "2026-07-16 10:00"),
                             ("AOI-12", report("LDF-RE", full([]), "2026-07-17 08:00"))))
        lot = only(m, "LDF")
        self.assertEqual(len(lot["bunches"]), 1)
        bunch = lot["bunches"][0]
        self.assertTrue(bunch["moved"] and lot["moved"])
        self.assertEqual(bunch["machines"], ["AOI-9", "AOI-12"])
        self.assertEqual(bunch["counts"], {lm.RECOVERED: 25})
        self.assertEqual(wafer(bunch, 25)["cause"], "Alignment 오류")

    def test_other_machine_is_new_bunch_otherwise(self):
        ok = ("AOI-9", report("LDF", full([]), "2026-07-16 08:00"))
        cases = {
            "앞 묶음이 다 Pass": [ok, ("AOI-12", report("LDF", full([]), "2026-07-16 12:00"))],
            "다른 공정 단계": [self.failed("AOI-9", "2026-07-16 08:00"),
                          ("AOI-12", report("LDF", full([]), "2026-07-17 08:00", recipe="2D"))],
            "2일 초과": [self.failed("AOI-9", "2026-07-16 08:00"), ("AOI-12", report("LDF", full([]), "2026-07-19 08:00"))],
        }
        for name, items in cases.items():
            lot = only(lm.build(records(*items)), "LDF")
            self.assertEqual(len(lot["bunches"]), 2, name)
            self.assertFalse(lot["moved"], name)


@unittest.skipUnless(os.environ.get("PARA_BATCH_SAMPLE"), "PARA_BATCH_SAMPLE 폴더 없음")
class RealSample(unittest.TestCase):
    def test_real_reports(self):
        from param_manager import wph
        folder = Path(os.environ["PARA_BATCH_SAMPLE"])
        seen, recs = set(), []
        for path in sorted(folder.rglob("*.htm")):
            rep = wph.parse_report(path)
            digest = repr((rep["metadata"], rep["wafers"]))
            if digest not in seen:
                seen.add(digest)
                recs.append({"id": path.name, "machine": "AOI-X", "report": rep})
        m = lm.build(recs)
        lots = m["lots"]
        self.assertGreater(len(lots), 0)
        for lot in lots:
            for bunch in lot["bunches"]:
                self.assertEqual(sum(bunch["counts"].values()), len(bunch["wafers"]))
        print(f"\n실자료: Batch Report {len(recs)} · Lot {len(lots)} · 묶음 {sum(len(l['bunches']) for l in lots)} · "
              f"점검 스캔 {len(m['excluded'])} · 미해결 Lot {sum(l['unresolved'] > 0 for l in lots)}")


if __name__ == "__main__":
    unittest.main()
