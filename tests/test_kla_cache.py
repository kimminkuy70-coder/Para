"""KLA 캐시(이슈 Para #40): 개발자 PC 가 KLA 장비 폴더 이름(날짜 · Lot · 슬롯)을 로컬 색인으로 모으고
OneDrive 캐시공유/ 에 KLA_캐시_*.zip + KLA캐시정보.json 으로 게시 → 다른 PC 가 받아 장비 없이 캐시에서 찾는다.
Camtek 캐시(BatchReport_캐시_*.zip · 캐시정보.json)와 이름으로 구분되고 서로 건드리지 않는다."""
import hashlib
import io
import json
import os
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from param_manager.desktop_batch import CACHE_SHARE_DIRNAME, CACHE_SHARE_INDEX
from param_manager.desktop_ipc import Session
from param_manager.desktop_kla import (KLA_CACHE_DIR, KLA_CACHE_FILE, KLA_SHARE_INDEX, KLA_SHARE_KEEP, DesktopKla,
                                       clean_index, merge_index)


def make_slot(root, day, lot, slot_dir):
    d = Path(root) / day / lot / slot_dir
    d.mkdir(parents=True)
    (d / "a.jpg").write_bytes(b"x")
    return d


class KlaCache(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.base = base
        self.share = base / "OneDrive" / "공유"
        self.docs = self.share / "docs"
        self.docs.mkdir(parents=True)
        self.folder = self.share / CACHE_SHARE_DIRNAME
        self.drive = base / "P"
        self.k6 = self.drive / "AOI-K6"
        make_slot(self.k6, "2026-11-05", "TB500.INT948@6326_RAW", "2026-11-05-10-00_1")
        make_slot(self.k6, "2026-11-05", "TB500.INT948@6326_RAW", "2026-11-05-10-02_2")
        make_slot(self.k6, "2020-01-01", "OLD11@6312", "2020-01-01-01-00_5")
        self.cfg = base / "dev.json"
        self.local = base / "local_dev"
        self.cfg.write_text(json.dumps({"local_dir": str(self.local), "save_dir": str(self.docs),
                                        "kla_roots": {"AOI-K6": str(self.k6)}}), encoding="utf-8")
        self.kla = DesktopKla(self.cfg)
        # 장비가 없는 사용자 PC(같은 OneDrive, KLA 장비 등록 없음)
        self.ucfg = base / "user.json"
        self.ulocal = base / "local_user"
        self.ucfg.write_text(json.dumps({"local_dir": str(self.ulocal), "save_dir": str(self.docs)}), encoding="utf-8")
        self.user = DesktopKla(self.ucfg)

    def test_build_and_search_cache(self):
        self.assertEqual(self.kla.state()["cache"]["lots"], 0)
        out = self.kla.cache_build({})
        self.assertEqual(out["machines"], ["AOI-K6"])
        self.assertEqual((out["lots"], out["dates"], out["read_dates"]), (2, 2, 2))
        path = self.local / KLA_CACHE_DIR / KLA_CACHE_FILE
        self.assertTrue(path.is_file())
        res = self.kla.search({"query": "int948 6326", "source": "cache"})
        self.assertEqual(res["source"], "cache")
        self.assertEqual([(h["machine"], h["date"], h["lot"]) for h in res["hits"]],
                         [("AOI-K6", "2026-11-05", "TB500.INT948@6326_RAW")])
        self.assertEqual([s["slot"] for s in res["hits"][0]["slots"]], ["1", "2"])
        self.assertEqual(res["hits"][0]["path"], os.path.join(str(self.k6), "2026-11-05", "TB500.INT948@6326_RAW"))
        # 장비 찾기와 결과가 같다
        eq = self.kla.search({"query": "int948 6326"})
        self.assertEqual([h["path"] for h in eq["hits"]], [h["path"] for h in res["hits"]])
        # 기간 · 장비 거르기
        self.assertEqual(self.kla.search({"query": "old11", "source": "cache", "start": "2021-01-01"})["hits"], [])
        self.assertEqual(self.kla.search({"query": "old11", "source": "cache", "machines": ["X"]})["hits"], [])
        # 오래된 날짜는 수정시각이 같으면 다시 읽지 않고, 최근 날짜는 다시 읽는다(새 슬롯 반영)
        make_slot(self.k6, "2026-11-05", "TB500.INT948@6326_RAW", "2026-11-05-11-00_3")
        again = self.kla.cache_build({})
        self.assertEqual((again["read_dates"], again["reused_dates"]), (1, 1))
        res = self.kla.search({"query": "int948", "source": "cache"})
        self.assertEqual([s["slot"] for s in res["hits"][0]["slots"]], ["1", "2", "3"])
        # 장비가 끊겨도 예전 색인은 지우지 않는다
        cfg = json.loads(self.cfg.read_text(encoding="utf-8"))
        cfg["kla_roots"]["AOI-K9"] = str(self.drive / "gone")
        self.cfg.write_text(json.dumps(cfg), encoding="utf-8")
        out = self.kla.cache_build({})
        self.assertEqual([f["machine"] for f in out["failed"]], ["AOI-K9"])
        self.assertEqual(out["lots"], 2)
        for bad in ({"x": 1},):
            with self.assertRaises(ValueError):
                self.kla.cache_build(bad)
        with self.assertRaises(ValueError):
            self.kla.search({"query": "a", "source": "nas"})

    def test_cache_search_needs_cache_and_build_needs_roots(self):
        with self.assertRaises(ValueError):
            self.user.search({"query": "int948", "source": "cache"})
        with self.assertRaises(ValueError):
            self.user.cache_build({})
        with self.assertRaises(ValueError):
            self.kla.cache_publish({})                    # 색인 없음
        self.assertFalse(self.folder.exists())            # 실패하면 OneDrive 에 아무것도 만들지 않음

    def test_publish_list_import_and_separate_from_camtek(self):
        self.kla.cache_build({})
        # Camtek 캐시 게시본이 이미 있다고 가정 — KLA 게시가 건드리면 안 된다
        self.folder.mkdir(parents=True)
        camtek_zip = self.folder / "BatchReport_캐시_20261101_090000.zip"
        camtek_zip.write_bytes(b"camtek")
        (self.folder / CACHE_SHARE_INDEX).write_text(json.dumps({"schema": 1, "items": []}), encoding="utf-8")
        before = (self.folder / CACHE_SHARE_INDEX).read_bytes()
        pub = self.kla.cache_publish({})
        self.assertRegex(pub["name"], r"^KLA_캐시_\d{8}_\d{6}\.zip$")
        target = self.folder / pub["name"]
        self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), pub["sha256"])
        with zipfile.ZipFile(target) as zf:
            self.assertEqual(sorted(zf.namelist()), ["KLA색인.json", "manifest.json"])
            self.assertEqual(json.loads(zf.read("manifest.json"))["kind"], "kla")
        self.assertTrue(camtek_zip.is_file())
        self.assertEqual((self.folder / CACHE_SHARE_INDEX).read_bytes(), before)
        index = json.loads((self.folder / KLA_SHARE_INDEX).read_text(encoding="utf-8"))
        self.assertEqual([i["name"] for i in index["items"]], [pub["name"]])
        self.assertEqual(sorted(p.name for p in self.folder.iterdir()),
                         sorted(["BatchReport_캐시_20261101_090000.zip", CACHE_SHARE_INDEX, KLA_SHARE_INDEX, pub["name"]]))
        self.assertFalse(list((self.local / "Temp").glob("*")) if (self.local / "Temp").exists() else [])
        # 다른 PC: 목록 → 불러오기 → 캐시에서 찾기(OneDrive 무변경)
        snapshot = {p.name: p.read_bytes() for p in self.folder.iterdir()}
        listed = self.user.cache_share_list({})
        self.assertEqual([(i["name"], i["present"], i["compatible"], i["lots"]) for i in listed["items"]],
                         [(pub["name"], True, True, 2)])
        got = self.user.cache_share_import({"name": pub["name"]})
        self.assertEqual((got["source"], got["lots"]), (pub["name"], 2))
        self.assertEqual({p.name: p.read_bytes() for p in self.folder.iterdir()}, snapshot)
        res = self.user.search({"query": "INT948", "source": "cache"})
        self.assertEqual([h["machine"] for h in res["hits"]], ["AOI-K6"])
        self.assertEqual(self.user.state()["cache"]["machines"], ["AOI-K6"])
        # 동기화가 덜 된 zip(내용이 다름)은 거부
        target.write_bytes(target.read_bytes()[:-5] + b"xxxxx")
        with self.assertRaises(ValueError):
            self.user.cache_share_import({"name": pub["name"]})
        for bad in ({"name": "BatchReport_캐시_20261101_090000.zip"}, {"name": "../x.zip"}, {}):
            with self.assertRaises(ValueError):
                self.user.cache_share_import(bad)

    def test_keep_three(self):
        self.kla.cache_build({})
        names = []
        for _ in range(KLA_SHARE_KEEP + 1):
            names.append(self.kla.cache_publish({})["name"])
            time.sleep(1.05)
        zips = sorted(p.name for p in self.folder.glob("KLA_캐시_*.zip"))
        self.assertEqual(zips, sorted(names[1:]))

    def test_merge_and_clean(self):
        a = clean_index({"schema": 1, "updated_at": "2026-11-01 00:00:00", "sources": [
            {"machine": "K", "path": "P:\\K", "dates": {"2026-11-01": {"mtime": 1, "read_at": "2026-11-01 00:00:00", "lots": {"A": ["s_1"]}},
                                                        "bad": {}}}]})
        b = clean_index({"schema": 1, "updated_at": "2026-11-02 00:00:00", "sources": [
            {"machine": "K", "path": "P:\\K", "dates": {"2026-11-01": {"mtime": 2, "read_at": "2026-11-02 00:00:00", "lots": {"A": ["s_1", "s_2"], "../x": []}}}},
            {"machine": 1, "path": "x", "dates": {}}]})
        self.assertEqual(list(a["sources"][0]["dates"]), ["2026-11-01"])
        self.assertEqual(len(b["sources"]), 1)
        m = merge_index(a, b)
        self.assertEqual(m["sources"][0]["dates"]["2026-11-01"]["lots"], {"A": ["s_1", "s_2"]})
        self.assertEqual(merge_index(b, a)["sources"][0]["dates"]["2026-11-01"]["lots"], {"A": ["s_1", "s_2"]})
        with self.assertRaises(ValueError):
            clean_index({"schema": 2, "sources": []})

    def test_ipc(self):
        output = io.BytesIO()
        session = Session(output)
        session.kla = self.kla
        self.addCleanup(session.close)

        def run(rid, method, params):
            session.handle(dict(version=1, id=rid, method=method, params=params))
            for worker in list(session.workers):
                worker.join(20)
        run(1, "kla_cache_build", {})
        run(2, "kla_cache_publish", {})
        run(3, "kla_cache_share_list", {})
        run(4, "kla_search", {"query": "INT948", "source": "cache"})
        run(5, "kla_cache_share_import", {"bad": 1})
        events = [json.loads(line) for line in output.getvalue().splitlines()]
        last = {i: [e for e in events if e["id"] == i][-1] for i in range(1, 6)}
        for i in range(1, 5):
            self.assertEqual(last[i]["event"], "completed", last[i])
        self.assertEqual(len(last[3]["kla"]["items"]), 1)
        self.assertEqual(len(last[4]["kla"]["hits"]), 1)
        self.assertEqual(last[5]["event"], "error")


if __name__ == "__main__":
    unittest.main()
