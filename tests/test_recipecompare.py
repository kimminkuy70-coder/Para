"""레시피 비교 모드(이슈 #14) 테스트 — 합성 Batch Report(test_lotmodel 형식), 장비 접근 없음."""
import io
import json
import re
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from param_manager import batchview, recipecompare as rc
from param_manager.desktop_batch import DesktopBatch
from param_manager.desktop_ipc import Session

FMT = "%d-%b-%y %I:%M:%S %p"
JOB = "TB500_RDL3 - Multi"
IDS = [f"61GW53{n:02d}EWB4" for n in range(25)]


def rep(sm, recipe, start, minutes, bad, status=None, ids=IDS, scan="00:09:00", lot=None):
    """25매 Report. bad = wafer 마다 Bad Dice(정수 또는 목록), status = {슬롯 위치: 상태}."""
    begin = datetime.strptime(start, "%Y-%m-%d %H:%M")
    status = status or {}
    wafers = []
    for i, wid in enumerate(ids):
        st = status.get(i, "Pass")
        b = bad[i] if isinstance(bad, list) else bad
        ok = st == "Pass"
        wafers.append({"Lot": lot or sm, "Wafer ID": wid, "Faults": str(b * 3) if ok else "-", "Scanned Dice": "30" if ok else "-",
                       "Bad Dice": str(b) if ok else "-", "Good Dice": str(30 - b) if ok else "-", "Yield": "90%" if ok else "-",
                       "Pass/Fail": st, "Recipe(s)": recipe})
    end = begin + timedelta(minutes=minutes)
    meta = [("Batch Start", begin.strftime(FMT)), ("Batch End", end.strftime(FMT)), ("Batch Time", f"{minutes // 60:02d}:{minutes % 60:02d}:00"),
            ("Wafers Scanned", str(sum(w["Pass/Fail"] == "Pass" for w in wafers))), ("Avg. Scan Time", scan), ("Job/Setup", f"{JOB}/Setup1")]
    return {"file_name": f"{JOB}_Setup1_{sm}_{begin:%y-%b-%d}_({begin:%H.%M.%S})_BatchReport.htm", "metadata": meta, "wafers": wafers, "table_count": 3}


def data():
    """AOI-1: x20 정상 Lot 2개(각 100분) · x5 정상 Lot 1개(25분, 같은 wafer 를 3시간 뒤 다시 — Bad Dice 동등)
    AOI-1: x20 Lot 하나는 Alignment Error(오류 포함 WPH 손실), AOI-2: x20 만(같은 호기 비교에서 빠짐), TEST Lot x5 1개."""
    return [{"id": f"{i:03d}", "machine": m, "report": r} for i, (m, r) in enumerate([
        ("AOI-1", rep("AAA-RDL3", "x20", "2026-09-01 08:00", 100, 5)),
        ("AOI-1", rep("AAA-RDL3 RE", "x5", "2026-09-01 11:00", 25, [5] * 20 + [4] * 5, scan="00:00:55")),
        ("AOI-1", rep("BBB-RDL3", "x20", "2026-09-02 08:00", 100, 2, ids=[f"BB{n:04d}XYZ1" for n in range(25)])),
        ("AOI-1", rep("CCC-RDL3", "x20", "2026-09-03 08:00", 120, 2, status={3: "Alignment Error."}, ids=[f"CC{n:04d}XYZ1" for n in range(25)])),
        ("AOI-2", rep("DDD-RDL3", "x20", "2026-09-03 08:00", 80, 2, ids=[f"DD{n:04d}XYZ1" for n in range(25)])),
        ("AOI-1", rep("TEST", "x5", "2026-09-04 08:00", 50, 2, ids=[f"TT{n:04d}XYZ1" for n in range(25)], lot="TEST")),
    ])]


class Engine(unittest.TestCase):
    def setUp(self):
        self.view = batchview.View(data())
        self.spec = {"a": {"name": "기존 x20", "keys": [f"{JOB} · x20"]}, "b": {"name": "x5", "keys": [f"{JOB} · x5"]}, "options": {}}

    def test_recipe_list(self):
        keys = {r["key"]: r for r in rc.recipes(self.view)}
        self.assertEqual(keys[f"{JOB} · x20"]["reports"], 4)
        self.assertEqual(keys[f"{JOB} · x20"]["machines"], ["AOI-1", "AOI-2"])
        self.assertEqual(keys[f"{JOB} · x5"]["reports"], 2)

    def test_speed_same_machine_and_test_excluded(self):
        r = rc.compare(self.view, self.spec)
        s = r["speed"][0]
        self.assertEqual(s["A"]["machines"], ["AOI-1"])                        # AOI-2 는 B 가 없어 빠짐
        self.assertAlmostEqual(s["A"]["wph25"], 50 * 3600 / (200 * 60))       # 정상 25매 2개(100분씩)
        self.assertAlmostEqual(s["B"]["wph25"], 25 * 3600 / (25 * 60))       # TEST Lot 제외 → 25분 Lot 하나
        self.assertAlmostEqual(r["summary"]["ratio"], 4.0)
        self.assertEqual(s["B"]["reports"], 1)
        # 실제 WPH 는 Alignment Error Report 의 시간까지 넣는다.
        self.assertAlmostEqual(s["A"]["wph_all"], 74 * 3600 / (320 * 60))
        self.assertEqual(r["err"]["A"]["items"][0][0], "Alignment Error")

    def test_robust_table_and_detection(self):
        r = rc.compare(self.view, self.spec)
        self.assertEqual(len(r["robust"]), 12)
        self.assertEqual(sum(x["main"] for x in r["robust"]), 1)
        self.assertEqual(r["summary"]["direction"], "B가 빠름")
        d = r["detection"]
        self.assertEqual((d["n"], d["up"], d["dn"], d["eq"]), (25, 0, 5, 20))     # 같은 wafer 25장, 5장만 B 가 1개 적음
        self.assertEqual(r["layers"][0]["verdict"], "차이 없음")                   # 5장 차이는 우연 범위(p=0.0625)
        self.assertEqual(r["pairs"][0]["n"], 25)

    def test_test_lot_option_and_validation(self):
        spec = dict(self.spec, options={"exclude_test": False})
        self.assertEqual(rc.compare(self.view, spec)["speed"][0]["B"]["reports"], 2)
        with self.assertRaises(ValueError):
            rc.compare(self.view, {"a": {"keys": [f"{JOB} · x20"]}, "b": {"keys": [f"{JOB} · x20"]}})
        with self.assertRaises(ValueError):
            rc.compare(self.view, {"a": {"keys": []}, "b": {"keys": [f"{JOB} · x5"]}})
        with self.assertRaises(ValueError):
            rc.compare(self.view, dict(self.spec, b={"keys": [f"{JOB} · x5"], "since": "2027-01-01"}))
        same = rc.compare(batchview.View(data()[:2] + [dict(data()[1], id="x", report=rep("EEE-RDL3", "x20", "2026-09-05 08:00", 25, 5, ids=[f"EE{n:04d}XYZ1" for n in range(25)]))]),
                          {"a": {"keys": [f"{JOB} · x20"], "since": "2026-09-05"}, "b": {"keys": [f"{JOB} · x5"]}})
        self.assertEqual(same["summary"]["direction"], "비슷함")                  # 25분 대 25분
        self.assertTrue(rc.is_test(["TEST"]) and not rc.is_test(["GUP-RDL3"]) and rc.is_test(["LoadPort A", "pi2 engineer test3"]))

    def test_html_embeds_raw_and_data(self):
        r = rc.compare(self.view, self.spec)
        page = rc.build_html(r, self.view)
        self.assertIn('class="app-rpt"', page)
        self.assertIn('id="rawgz"', page)
        blob = json.loads(re.search(r'id="cmp">(.*?)</script>', page).group(1))
        self.assertEqual(blob["summary"]["ratio"], r["summary"]["ratio"])
        self.assertNotIn("</script", re.search(r'id="cmp">(.*?)</script>', page).group(1))


class Ipc(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        cfg = base / "config.json"
        cfg.write_text(json.dumps({"local_dir": str(base / "local")}), encoding="utf-8")
        self.batch = DesktopBatch(cfg)
        self.batch.set_view("scope", data())
        self.output = io.BytesIO()
        self.session = Session(self.output)
        self.session.batch = self.batch
        self.addCleanup(self.session.close)
        self.rid = 0

    def call(self, method, **params):
        self.rid += 1
        self.session.handle(dict(version=1, id=self.rid, method=method, params=params))
        for worker in list(self.session.workers):
            worker.join(20)
        events = [json.loads(line) for line in self.output.getvalue().splitlines()]
        return [e for e in events if e["id"] == self.rid][-1]

    def test_methods(self):
        out = self.call("batch_compare_recipes", view="scope")
        self.assertEqual(out["event"], "completed", out)
        self.assertEqual(len(out["batch"]["recipes"]), 2)
        spec = {"a": {"name": "A", "keys": [f"{JOB} · x20"]}, "b": {"name": "B", "keys": [f"{JOB} · x5"]}, "options": {}}
        out = self.call("batch_compare", view="scope", spec=spec)
        self.assertEqual(out["event"], "completed", out)
        self.assertAlmostEqual(out["batch"]["summary"]["ratio"], 4.0)
        out = self.call("batch_compare_export", view="scope", spec=spec)
        self.assertEqual(out["event"], "completed", out)
        path = Path(out["batch"]["path"])
        self.assertTrue(path.is_file() and path.parent.name == "비교")
        bad = self.call("batch_compare", view="scope", spec={"a": {"keys": []}})
        self.assertEqual(bad["event"], "error")


if __name__ == "__main__":
    unittest.main()
