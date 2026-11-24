"""TB500 Review 조회(v14.4.2) — 리뷰 전용 HTML(TB500_Review.html)의 조회를 엔진(desktop_tb500)으로 옮긴 것.

시험 자료 = HTML 시험(브랜치 version_TB500_review 의 tools/tb500_review_fixture.py)과 같은 합성 자료(실제 고객 데이터 아님).
같은 자료에서 HTML 시험과 같은 결과(Layer · 재리뷰 판정 · 장비 · 호기 · 스캔 시각 · wafer 판정 · Lot History)가 나와야 한다."""
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vendor"))
from param_manager import desktop_tb500 as tb
from param_manager.desktop_batch import CACHE_SHARE_DIRNAME, DesktopBatch
from param_manager.desktop_ipc import Session
from param_manager.desktop_kla import KLA_CACHE_DIR, KLA_CACHE_FILE, DesktopKla
from param_manager.desktop_open import DesktopOpen
from param_manager.desktop_tb500 import DesktopTb500


def report(job, setup, sm, day, start, n=25, fail=0, ids=None):
    fname = f"{job}_{setup}_{sm}_{day}_({start.replace(':', '.')})_BatchReport.htm"
    yy, mon, d = day.split("-")
    hh = int(start[:2])
    ampm = "PM" if hh >= 12 else "AM"
    h12 = hh - 12 if hh > 12 else (12 if hh == 0 else hh)
    meta = [["Batch Start", f"{d}-{mon}-{yy} {h12:02d}:{start[3:]} {ampm}"], ["Job/Setup", f"{job}/{setup}"],
            ["Wafers Scanned", str(n)], ["Batch Time", "01:10:00"]]
    wafers = [{"Lot": sm, "Wafer ID": ids[i] if ids else f"W{i:02d}", "Pass/Fail": "Scan 2D Error. Aborted." if i < fail else "Pass",
               "Scanned Dice": "" if i < fail else "1200", "Bad Dice": "" if i < fail else str(10 + i),
               "Good Dice": "" if i < fail else str(1190 - i), "Faults": "" if i < fail else str(40 + i),
               "Yield": "" if i < fail else f"{(1190 - i) / 12:.2f}", "Recipe(s)": job} for i in range(n)]
    return fname, {"signature": [1, 1], "digest": "x" * 64, "report": {"file_name": fname, "metadata": meta, "wafers": wafers, "table_count": 2}}


CAMTEK = {
    "AOI-21_aaaaaaaa.json": ("AOI-21", "P:\\AOI-21\\Reports", [
        report("TB500_RDL1-Multi", "Setup1", "CMS-RDL1", "26-Oct-20", "09:10:00", fail=3),
        report("TB500_RDL3-Multi", "Setup1", "CMS", "26-Oct-18", "13:00:00"),
        report("TB500_RDL1-Multi", "Setup1", "WGB-RDL3", "26-Oct-22", "11:23:53")]),
    "AOI-22_bbbbbbbb.json": ("AOI-22", "P:\\AOI-22\\Reports", [
        report("TB500_RDL1-Multi", "Setup1", "CMS RE", "26-Oct-21", "22:05:00", 3, ids=["Slot 25", "Slot 24", "Slot 23"]),
        report("TB500_PI4-Multi", "Setup1", "CMS", "26-Oct-15", "08:00:00")]),
}
KLA = {"schema": 1, "updated_at": "2026-11-06 08:00:00", "sources": [
    {"machine": "AOI-K6", "path": "P:\\AOI-K6", "backup": False, "dates": {
        "2026-11-05": {"mtime": 1, "read_at": "2026-11-06 08:00:00", "lots": {
            "TB500.INT1041@6324_RAW": ["2026-11-05-10-02_2", "2026-11-05-10-00_1"],
            "TB500.INT948@6326_RAW": ["2026-11-05-11-00_1"]}}}},
    {"machine": "AOI-K2", "path": "P:\\AOI-K2", "backup": False, "dates": {
        "2026-11-04": {"mtime": 1, "read_at": "2026-11-06 08:00:00", "lots": {"TB500.INT1041@6314_RAW": ["2026-11-04-07-30_5"]}}}}]}
LAYERS = {"1-1. RDL4_재리뷰": ["m1.txt", "m2.txt", "x.jpg"], "1. RDL4": ["TB500_a.jpg"], "1. RDL4_재스캔 (#24,25)": ["a.txt"],
          "2. PIDS3": ["TB500_b.jpg"], "2. PIDS3_재리뷰": ["s/m1.txt"], "3-1. RDL3_재리뷰": ["m.txt"], "3. RDL3 (#23X)": ["TB500_c.jpg"],
          "3. RDL3_재스캔 All": ["q.txt"], "4. PIDS5_Skip (RDL3 재리뷰 결과 나오면 맵만 수정해 주세요)": ["k.txt"],
          "5. RDL2": ["sub/ABC123_1_2_3_4.jpg"], "6. PIDS7_Skip (RDL2 재리뷰 결과 나오면 맵만 수정해 주세요)": ["k.txt"],
          "7. RDL1": ["TB500_RDL1 - Multi_x.jpg"], "메모": ["note.txt"], "★ 5. RDL2_재리뷰 (참고용)": ["r1.txt", "TB500_s.jpg"]}
# HTML(localeCompare 'ko' numeric)과 같은 순서 — ★ 가 맨 위(#47), 1-1 이 1. 보다 앞, 한글 이름은 맨 아래.
ORDER = ["★ 5. RDL2_재리뷰 (참고용)", "1-1. RDL4_재리뷰", "1. RDL4", "1. RDL4_재스캔 (#24,25)", "2. PIDS3", "2. PIDS3_재리뷰",
         "3-1. RDL3_재리뷰", "3. RDL3 (#23X)", "3. RDL3_재스캔 All", "4. PIDS5_Skip (RDL3 재리뷰 결과 나오면 맵만 수정해 주세요)",
         "5. RDL2", "6. PIDS7_Skip (RDL2 재리뷰 결과 나오면 맵만 수정해 주세요)", "7. RDL1", "메모"]


def write_caches(local):
    base = Path(local) / "배치분석" / "누적"
    base.mkdir(parents=True)
    for name, (machine, folder, reports) in CAMTEK.items():
        (base / name).write_text(json.dumps({"schema": 1, "machine": machine, "folder": folder, "entries": dict(reports)}), encoding="utf-8")
    kla = Path(local) / KLA_CACHE_DIR
    kla.mkdir(parents=True)
    (kla / KLA_CACHE_FILE).write_text(json.dumps(KLA, ensure_ascii=False), encoding="utf-8")


def tree(root):
    return sorted((str(p.relative_to(root)), p.is_dir(), p.stat().st_size, p.stat().st_mtime_ns) for p in Path(root).rglob("*"))


class Tb500(unittest.TestCase):
    def setUp(self):
        tb._CACHE.clear()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.base = base
        self.conder = base / "Conder Scan" / "129. 4DT-TB500-H-M1"
        lot = self.conder / "976. TB500.INT1041 (CMS)"
        for folder, files in LAYERS.items():
            for f in files:
                p = lot / folder / f
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(b"x")
        z = self.conder / "977. TB500.INT10412 (ZZZ)" / "1. RDL4"
        z.mkdir(parents=True)
        (z / "TB500_z.jpg").write_bytes(b"x")
        self.docs = base / "OneDrive" / "공유" / "docs"
        self.docs.mkdir(parents=True)
        self.local = base / "local"
        write_caches(self.local)
        self.cfg = base / "cfg.json"
        self.cfg.write_text(json.dumps({"local_dir": str(self.local), "save_dir": str(self.docs), "tb500_conder": str(self.conder)}),
                            encoding="utf-8")
        self.t = DesktopTb500(self.cfg)

    def look(self, lots=("TB500.INT1041", "TB500.INT948", "tb500.int1041")):
        return self.t.lookup({"lots": list(lots)})

    # ---- 이름 규칙 -------------------------------------------------------
    def test_rules(self):
        fs = ["R_TB500 LIVE_FS_6324_LSD-FS", "R_TB500 LIVE_FS_6324_LSD-FS-DIA", "8. FS UBM", "TB500_FSUBM-Multi", "FSX_RDL1",
              "R_TB500_LIVE_PI3 - Enhanced", "CFS_RDL2"]
        self.assertEqual([(tb.stage_of(x) or {}).get("key") for x in fs], ["FS UBM", "FS UBM", "FS UBM", "FS UBM", "RDL1", "PIDS5", "RDL2"])
        self.assertEqual([tb.stage_of(x)["key"] if tb.stage_of(x) else None for x in ["4. PIDS5_Skip ", "TB500_PI4-Multi", "TB500_RDL3-Multi", "RDL12"]],
                         ["PIDS5", "PIDS3", "RDL3", None])
        self.assertEqual([tb.kind_of(x) for x in ["1-1. RDL4_재리뷰", "1. RDL4_재스캔 (#24,25)", "4. PIDS5_Skip (RDL3 재리뷰 결과 나오면)", "3. RDL3 (#23X)"]],
                         ["rereview", "rescan", "skip", "base"])
        self.assertEqual([tb.classify_image(x) for x in ["TB500_a.jpg", "TB500_RDL1 - Multi_x.jpg", "ABC123_1_2_3_4.jpg", "x.jpg"]],
                         ["Camtek", "Camtek", "KLA", "Unknown"])
        names = ["977. TB500.INT10412 (ZZZ)", "976. TB500.INT1041 (CMS)"]
        self.assertEqual(tb.find_lot("TB500.INT1041", names), "976. TB500.INT1041 (CMS)")    # 10412 는 단어 경계로 걸러짐
        self.assertIsNone(tb.find_lot("TB500.INT948", names))
        self.assertEqual(sorted(LAYERS, key=tb.ko_key), ORDER)
        self.assertEqual(tb.file_time("J_S_SM_26-Oct-22_(11.23.53)_BatchReport.htm"), "2026-10-22 11:23:53")

    # ---- 조회 ------------------------------------------------------------
    def test_lookup(self):
        r = self.look()
        self.assertEqual((r["lots"], r["done"], r["stopped"]), (2, 2, False))      # 같은 Lot 은 한 번만(대소문자 무시)
        lot, missing = r["results"]
        self.assertTrue(missing["missing"])
        self.assertEqual((lot["folder"], lot["sm"], lot["code"]), ("976. TB500.INT1041 (CMS)", "CMS", "CMS"))
        self.assertEqual([s["name"] for s in lot["subs"]], ORDER)
        row = {s["name"]: s for s in lot["subs"]}
        star = row["★ 5. RDL2_재리뷰 (참고용)"]
        self.assertEqual((star["stage"], star["status"], star["equipment"], star["hits"]), (None, "", "", []))   # #46: 이름만
        self.assertEqual(row["1-1. RDL4_재리뷰"]["status"], "rereview")
        self.assertEqual(row["1-1. RDL4_재리뷰"]["txt"], {"count": 2, "partial": False})
        self.assertEqual(row["2. PIDS3_재리뷰"]["txt"]["count"], 1)                                                     # 아래 폴더까지 센다
        r4 = row["1. RDL4"]
        self.assertEqual((r4["stage"]["key"], r4["stage"]["aoi"], r4["stage"]["rev_name"], r4["status"], r4["equipment"], r4["total"]),
                         ("RDL4", "6305", "2D/RE", "done", "Camtek", 0))
        self.assertEqual((row["1. RDL4_재스캔 (#24,25)"]["kind"], row["1. RDL4_재스캔 (#24,25)"]["equipment"]), ("rescan", "Unknown"))
        p3 = row["2. PIDS3"]
        self.assertEqual((p3["status"], p3["equipment"], p3["machines"]), ("done", "Camtek", 1))
        self.assertEqual([(h["machine"], h["at"], h["scan"]["outcome"], h["scan"]["n"]["P"]) for h in p3["hits"]],
                         [("AOI-22", "2026-10-15 08:00:00", "정상", 25)])
        self.assertEqual([v["state"] for v in p3["verdicts"]], ["한 번에 완료"])
        self.assertEqual([h["machine"] for h in row["3. RDL3 (#23X)"]["hits"]], ["AOI-21"])
        self.assertEqual((row["4. PIDS5_Skip (RDL3 재리뷰 결과 나오면 맵만 수정해 주세요)"]["status"],
                          row["4. PIDS5_Skip (RDL3 재리뷰 결과 나오면 맵만 수정해 주세요)"]["equipment"]), ("skip", ""))
        k = row["5. RDL2"]
        self.assertEqual((k["status"], k["equipment"], k["machines"]), ("need", "KLA", 2))
        self.assertEqual([(h["vendor"], h["machine"], h["at"], h["slots"], h["review"]) for h in k["hits"]],
                         [("KLA", "AOI-K6", "2026-11-05 10:00", 2, True), ("KLA", "AOI-K2", "2026-11-04 07:30", 1, False)])
        r1 = row["7. RDL1"]
        self.assertEqual((r1["status"], r1["equipment"], r1["machines"], r1["total"]), ("need", "Camtek", 2, 2))      # WGB 는 다른 Lot 코드
        self.assertEqual([(h["machine"], h["at"], h["scan"]["outcome"], h["scan"]["n"]["P"], h["scan"]["n"]["E"]) for h in r1["hits"]],
                         [("AOI-22", "2026-10-21 22:05:00", "정상", 3, 0), ("AOI-21", "2026-10-20 09:10:00", "Error", 22, 3)])
        self.assertEqual(r1["verdicts"], [{"name": "RDL1", "state": "재스캔으로 완료", "wafers": 25,
                                           "counts": {"한 번에 Pass": 22, "재스캔 Pass": 3, "중복 Pass": 0, "Pass 없음": 0}}])
        memo = row["메모"]
        self.assertEqual((memo["stage"], memo["status"]), (None, ""))
        for name in ("1-1. RDL4_재리뷰", "2. PIDS3_재리뷰", "3-1. RDL3_재리뷰"):
            self.assertEqual((row[name]["equipment"], row[name]["hits"]), ("", []), name)       # 재리뷰 결과 줄 = 호기 빈칸(#85)
        self.assertEqual([(x["key"], x["status"]) for x in lot["layers"]],
                         [("RDL4", "done"), ("PIDS3", "done"), ("RDL3", "done"), ("PIDS5", "skip"), ("RDL2", "need"), ("PIDS7", "skip"), ("RDL1", "need")])
        self.assertEqual(r["summary"], {"lots": 2, "missing": 1, "layers": 7, "done": 3, "need": 2, "skip": 2})
        self.assertEqual((r["cache"]["camtek_reports"], r["cache"]["camtek_machines"], r["cache"]["kla_lots"]), (5, 2, 3))
        self.assertEqual(r1["path"], os.path.join(str(self.conder), "976. TB500.INT1041 (CMS)", "7. RDL1"))

    def test_history_and_report(self):
        self.look()
        h = self.t.history({"lot": 0})
        self.assertEqual([x["layer"] for x in h["rows"]], ["PIDS3", "RDL3", "RDL1", "RDL1", "RDL2", "RDL2"])
        self.assertEqual([x["machine"] for x in h["rows"]], ["AOI-22", "AOI-21", "AOI-21", "AOI-22", "AOI-K2", "AOI-K6"])
        self.assertEqual(h["layers"], ["PIDS3", "RDL3", "RDL2", "RDL1"])
        self.assertIn("Review 6324 · 슬롯 2개", h["rows"][-1]["what"])
        g = {x["name"]: x for x in h["groups"]}
        self.assertEqual(sorted(g), ["PIDS3", "RDL1", "RDL3"])
        rdl1 = g["RDL1"]
        self.assertEqual(len(rdl1["wafers"]), 25)
        first = rdl1["wafers"][0]
        self.assertEqual((first["slot"], first["wid"], first["verdict"], [(i["k"], i["t"]) for i in first["items"]]),
                         (25, "W00", "재스캔 Pass", [("E", "Scan 2D Error. Aborted."), ("P", "")]))
        self.assertEqual((rdl1["wafers"][3]["slot"], rdl1["wafers"][3]["verdict"]), (22, "한 번에 Pass"))
        # Batch Report 보기: 캐시의 머리 정보 · wafer 표(원문 그대로)
        rid = rdl1["scans"][0]
        rep = self.t.report({"id": rid})
        self.assertEqual(rep["file"], "TB500_RDL1-Multi_Setup1_CMS-RDL1_26-Oct-20_(09.10.00)_BatchReport.htm")
        self.assertIn(["Job/Setup", "TB500_RDL1-Multi/Setup1"], rep["meta"])
        self.assertEqual(rep["cols"], ["Lot", "Wafer ID", "Pass/Fail", "Scanned Dice", "Bad Dice", "Good Dice", "Faults", "Yield", "Recipe(s)"])
        self.assertEqual(rep["vals"][3], ["CMS-RDL1", "W03", "Pass", "1200", "13", "1187", "43", "98.92", "TB500_RDL1-Multi"])
        self.assertEqual(rep["cells"][0], [25, "E"])
        with self.assertRaises(ValueError):
            self.t.history({"lot": 9})
        with self.assertRaises(ValueError):
            self.t.report({"id": "x"})

    def test_read_only_and_stop(self):
        before = tree(self.conder)
        cfg_before = self.cfg.read_text(encoding="utf-8")
        self.look()
        self.assertEqual(tree(self.conder), before, "Conder Scan 폴더에 아무것도 쓰지 않음")
        self.assertEqual(self.cfg.read_text(encoding="utf-8"), cfg_before, "조회는 설정도 바꾸지 않음")
        # [중단]: 하던 Lot 은 버리고 끝난 Lot 만
        real = tb.equipment_of

        def stop_once(path, cancel):
            self.t.stop()
            return real(path, cancel)
        tb.equipment_of = stop_once
        self.addCleanup(setattr, tb, "equipment_of", real)
        r = self.look(["TB500.INT1041"])
        self.assertEqual((r["stopped"], r["done"], r["results"]), (True, 0, []))

    def test_missing_conder(self):
        self.t.set_conder({"path": str(self.base / "없는 폴더")})
        with self.assertRaises(ValueError) as ctx:
            self.look()
        self.assertIn("Conder Scan 폴더를 열지 못했습니다", str(ctx.exception))

    def test_settings_and_open(self):
        s = self.t.state()
        self.assertEqual((s["conder"], s["is_default"], s["camtek"]["files"], s["kla"]["present"]), (str(self.conder), False, 2, True))
        with self.assertRaises(ValueError):
            self.t.set_conder({"path": "상대경로"})
        s = self.t.set_conder({"path": ""})
        self.assertEqual((s["conder"], s["is_default"]), (tb.DEFAULT_CONDER, True))
        self.assertNotIn("tb500_conder", json.loads(self.cfg.read_text(encoding="utf-8")))
        s = self.t.set_conder({"path": str(self.conder) + os.sep})
        self.assertEqual(s["conder"], str(self.conder))
        # [폴더 열기] = Conder Scan 폴더 안만
        sub = self.conder / "976. TB500.INT1041 (CMS)" / "7. RDL1"
        self.assertTrue(self.t.allows(sub))
        self.assertFalse(self.t.allows(self.base / "OneDrive"))
        self.assertEqual(DesktopOpen(self.cfg).resolve(str(sub)), sub.absolute())
        with self.assertRaises(ValueError):
            DesktopOpen(self.cfg).resolve(str(self.base / "Conder Scan"))

    def test_cache_update(self):
        """OneDrive 에서 Camtek · KLA 최신 캐시를 한 번에 — 개발자가 게시한 것을 장비 · 호기 등록 없는 PC 가 받아 조회."""
        DesktopBatch(self.cfg).cache_publish({})
        DesktopKla(self.cfg).cache_publish({})
        share = self.docs.parent / CACHE_SHARE_DIRNAME
        share_before = tree(share)
        ucfg = self.base / "user.json"
        ulocal = self.base / "user_local"
        ucfg.write_text(json.dumps({"local_dir": str(ulocal), "save_dir": str(self.docs), "tb500_conder": str(self.conder)}), encoding="utf-8")
        tb._CACHE.clear()
        user = DesktopTb500(ucfg, batch=DesktopBatch(ucfg), kla=DesktopKla(ucfg))
        self.assertEqual(user.state()["camtek"]["files"], 0)
        r = user.cache_update({})
        self.assertEqual((r["camtek"]["status"], r["kla"]["status"]), ("imported", "imported"), r)
        self.assertTrue(r["state"]["imported"]["at"])
        self.assertTrue(r["state"]["imported"]["camtek"].startswith("BatchReport_캐시_"))
        self.assertTrue(r["state"]["imported"]["kla"].startswith("KLA_캐시_"))
        res = user.lookup({"lots": ["TB500.INT1041"]})
        row = {s["name"]: s for s in res["results"][0]["subs"]}
        self.assertEqual([h["machine"] for h in row["7. RDL1"]["hits"]], ["AOI-22", "AOI-21"])
        self.assertEqual([h["machine"] for h in row["5. RDL2"]["hits"]], ["AOI-K6", "AOI-K2"])
        again = user.cache_update({})
        self.assertEqual((again["camtek"]["status"], again["kla"]["status"]), ("latest", "latest"))
        self.assertEqual(tree(share), share_before, "OneDrive 캐시공유 에는 쓰지 않음")
        # 게시된 캐시가 없는 곳: 받은 시각을 새로 적지 않는다
        empty = self.base / "empty.json"
        (self.base / "e" / "docs").mkdir(parents=True)
        empty.write_text(json.dumps({"local_dir": str(self.base / "e_local"), "save_dir": str(self.base / "e" / "docs")}), encoding="utf-8")
        none = DesktopTb500(empty, batch=DesktopBatch(empty), kla=DesktopKla(empty)).cache_update({})
        self.assertEqual((none["camtek"]["status"], none["kla"]["status"], none["state"]["imported"]["at"]), ("none", "none", ""))

    def test_ipc(self):
        output = io.BytesIO()
        session = Session(output)
        session.tb500 = self.t
        self.addCleanup(session.close)

        def run(rid, method, params):
            session.handle(dict(version=1, id=rid, method=method, params=params))
            for worker in list(session.workers):
                worker.join(20)
        run(1, "tb500_state", {})
        run(2, "tb500_lookup", {"lots": ["TB500.INT1041"]})
        run(3, "tb500_history", {"lot": 0})
        run(4, "tb500_report", {"id": 0})
        run(5, "tb500_stop", {})
        run(6, "tb500_lookup", {"lots": "TB500.INT1041"})
        run(7, "tb500_lookup", {"lots": ["x"], "extra": 1})
        run(8, "tb500_set_conder", {"path": str(self.conder)})
        events = [json.loads(line) for line in output.getvalue().splitlines()]
        last = {i: [e for e in events if e["id"] == i][-1] for i in range(1, 9)}
        for i in (1, 2, 3, 4, 5, 8):
            self.assertEqual(last[i]["event"], "completed", last[i])
        self.assertEqual(last[2]["tb500"]["done"], 1)
        self.assertTrue(any(e["id"] == 2 and e["event"] == "progress" for e in events))
        self.assertEqual(len(last[3]["tb500"]["rows"]), 6)
        self.assertEqual(last[6]["event"], "error")
        self.assertEqual(last[7]["event"], "error")


if __name__ == "__main__":
    unittest.main()
