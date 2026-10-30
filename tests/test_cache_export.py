"""Batch Report 취합 캐시 zip(이슈 #16 형식): 배치분석/누적/*.json → zip 1개 + manifest.
OneDrive 게시 · 목록 · 불러오기(이슈 #39 — 종전 로컬 '내보내기'는 삭제), 가져오기(이슈 #29): 다른 PC 의 zip → 이 PC 캐시에 합침
(호기 이름으로 짝 · 이 PC 폴더로 옮겨 적음 · 있던 것 유지)."""
import hashlib
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from param_manager import batchreport_store
from param_manager.desktop_batch import (CACHE_SHARE_DIRNAME, CACHE_SHARE_INDEX, CHOICES_FILE, DesktopBatch,
                                         cache_share_dir)
from param_manager.desktop_ipc import Session
from param_manager.desktop_open import DesktopOpen


def cache(machine, folder, n):
    return {"schema": 1, "machine": machine, "folder": folder,
            "entries": {f"J_S_LOT{i}_26-Oct-0{i + 1}_(10.00.00)_BatchReport.htm": report_entry(i) for i in range(n)}}


class CachePublish(unittest.TestCase):
    """이슈 #39: 개발자 PC 가 로컬 캐시를 OneDrive 캐시공유/(저장 폴더 docs 옆)에 zip 으로 게시 → 다른 PC 가 목록에서 골라 받아 불러옴."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.base = base
        self.share = base / "OneDrive" / "0. Camtek AOI parameter 취합"
        self.docs = self.share / "docs"
        self.docs.mkdir(parents=True)
        self.local = base / "local"
        self.cfg = base / "config.json"
        self.cfg.write_text(json.dumps({"local_dir": str(self.local), "save_dir": str(self.docs)}), encoding="utf-8")
        self.batch = DesktopBatch(self.cfg)
        self.folder = self.share / CACHE_SHARE_DIRNAME

    def write_caches(self, local=None):
        local = local or self.local
        acc = local / "배치분석" / "누적"
        acc.mkdir(parents=True)
        (acc / ("a" * 64 + ".json")).write_text(json.dumps(cache("M01", r"\\eq\M01\Reports", 3)), encoding="utf-8")
        (acc / ("b" * 64 + ".json")).write_text(json.dumps(cache("M02", r"\\eq\M02\Reports", 2)), encoding="utf-8")
        (acc / ("c" * 64 + ".json")).write_text("{broken", encoding="utf-8")            # 깨진 캐시는 건너뜀
        (local / "Cache").mkdir()
        (local / "Cache" / CHOICES_FILE).write_text(json.dumps({"schema": 1, "choices": {}}), encoding="utf-8")

    def index(self):
        return json.loads((self.folder / CACHE_SHARE_INDEX).read_text(encoding="utf-8"))

    def test_needs_cache_and_save_dir(self):
        with self.assertRaises(ValueError):
            self.batch.cache_publish({})                       # 캐시 없음
        self.assertFalse(self.folder.exists())                 # 실패하면 OneDrive 에 아무것도 만들지 않음
        self.cfg.write_text(json.dumps({"local_dir": str(self.local)}), encoding="utf-8")
        self.write_caches()
        for call in (lambda: self.batch.cache_publish({}), lambda: self.batch.cache_share_list({}),
                     lambda: self.batch.cache_share_import({"name": "BatchReport_캐시_20261030_090000.zip"})):
            with self.assertRaises(ValueError):                # 저장 폴더 미지정
                call()
        with self.assertRaises(ValueError):
            DesktopBatch(self.cfg).cache_publish({"x": 1})

    def test_publish_writes_one_zip_and_index_next_to_docs(self):
        self.write_caches()
        out = self.batch.cache_publish({})
        path = Path(out["path"])
        self.assertEqual(path.parent, self.folder)            # docs 옆 캐시공유/
        self.assertEqual(sorted(p.name for p in self.folder.iterdir()), sorted([path.name, CACHE_SHARE_INDEX]))
        self.assertEqual((out["files"], out["machines"], out["reports"]), (2, ["M01", "M02"], 5))
        with zipfile.ZipFile(path) as zf:
            names = set(zf.namelist())
            manifest = json.loads(zf.read("manifest.json"))
            self.assertIn("사람선택/" + CHOICES_FILE, names)
            for f in manifest["files"]:
                self.assertIn(f["file"], names)
                self.assertEqual(len(json.loads(zf.read(f["file"]))["entries"]), f["reports"])
        item = self.index()["items"][0]
        self.assertEqual((item["name"], item["size"], item["sha256"]),
                         (path.name, path.stat().st_size, hashlib.sha256(path.read_bytes()).hexdigest()))
        # 로컬 임시 zip 은 지워지고, docs 안에는 아무것도 생기지 않는다
        self.assertFalse(any((self.local / "Temp").iterdir()) if (self.local / "Temp").exists() else False)
        self.assertEqual(list(self.docs.iterdir()), [])
        self.assertFalse((self.local / "배치분석" / "내보내기").exists())
        # 폴더 열기: OneDrive 캐시 zip 은 탐색기에서 선택(reveal)만, 내용 열기는 거부
        opener = DesktopOpen(self.cfg)
        self.assertEqual(opener.resolve(str(path), reveal=True), path)
        with self.assertRaises(ValueError):
            opener.resolve(str(path))

    def test_keeps_latest_three_and_removes_only_ours(self):
        self.write_caches()
        self.folder.mkdir()
        old = []
        for i in range(3):
            name = f"BatchReport_캐시_2020010{i}_000000.zip"
            (self.folder / name).write_bytes(b"x")
            old.append(dict(name=name, size=1, sha256="0" * 64, exported_at=f"2020-01-0{i}", cache_schema=1))
        (self.folder / CACHE_SHARE_INDEX).write_text(json.dumps({"schema": 1, "items": old[::-1]}), encoding="utf-8")
        (self.folder / "BatchReport_캐시_20191231_000000.zip").write_bytes(b"x")   # 목록에 없는 예전 게시본(중간에 멈춘 것)
        (self.folder / "메모.txt").write_text("남의 파일", encoding="utf-8")
        out = self.batch.cache_publish({})
        left = sorted(p.name for p in self.folder.glob("*.zip"))
        self.assertEqual(left, sorted([Path(out["path"]).name, old[2]["name"], old[1]["name"]]))
        self.assertEqual([i["name"] for i in self.index()["items"]], [Path(out["path"]).name, old[2]["name"], old[1]["name"]])
        self.assertTrue((self.folder / "메모.txt").exists())
        self.assertEqual(out["kept"], 3)

    def test_other_pc_lists_and_imports_without_writing_onedrive(self):
        self.write_caches()
        published = self.batch.cache_publish({})
        # PC B: 같은 OneDrive 공유 폴더, 다른 로컬 · 같은 호기 이름
        local_b = self.base / "local_b"
        cfg_b = self.base / "config_b.json"
        reports_b = self.base / "eq_b" / "M01" / "Reports"
        reports_b.mkdir(parents=True)
        cfg_b.write_text(json.dumps({"local_dir": str(local_b), "save_dir": str(self.docs),
                                     "wph_report_paths": {"M01": str(reports_b)}}), encoding="utf-8")
        pc_b = DesktopBatch(cfg_b)
        before = {p.name: (p.stat().st_mtime_ns, p.stat().st_size) for p in self.folder.iterdir()}
        listed = pc_b.cache_share_list({})
        self.assertEqual(listed["folder"], str(self.folder))
        self.assertEqual([(i["name"], i["present"], i["compatible"], i["machines"], i["reports"]) for i in listed["items"]],
                         [(published["name"], True, True, ["M01", "M02"], 5)])
        out = pc_b.cache_share_import({"name": published["name"]})
        self.assertEqual((out["added"], out["machines"], out["source"]), (3, ["M01"], published["name"]))
        self.assertEqual(out["skipped"], [{"machine": "M02", "reports": 2}])
        self.assertEqual(len(list((local_b / "배치분석" / "누적").glob("*.json"))), 1)
        after = {p.name: (p.stat().st_mtime_ns, p.stat().st_size) for p in self.folder.iterdir()}
        self.assertEqual(before, after)                          # OneDrive 에는 아무것도 쓰지 않음
        self.assertEqual(list((local_b / "Temp").iterdir()), [])   # 받은 zip 은 로컬 임시 폴더에서 지움
        # 다시 받으면 이미 있는 것은 그대로
        self.assertEqual(pc_b.cache_share_import({"name": published["name"]})["kept"], 3)

    def test_import_rejects_partial_sync_and_unknown_names(self):
        self.write_caches()
        published = self.batch.cache_publish({})
        path = Path(published["path"])
        data = path.read_bytes()
        path.write_bytes(data[: len(data) // 2])               # OneDrive 동기화가 덜 끝난 파일
        with self.assertRaises(ValueError) as ctx:
            self.batch.cache_share_import({"name": published["name"]})
        self.assertIn("동기화", str(ctx.exception))
        self.assertEqual(list((self.local / "Temp").iterdir()), [])
        path.unlink()
        self.assertFalse(self.batch.cache_share_list({})["items"][0]["present"])
        with self.assertRaises(ValueError):
            self.batch.cache_share_import({"name": published["name"]})
        for params in ({}, {"name": "../x.zip"}, {"name": "BatchReport_캐시_20200101_000000.zip"},
                       {"name": published["name"], "x": 1}, {"name": 1}):
            with self.assertRaises(ValueError, msg=params):
                self.batch.cache_share_import(params)
        # 캐시정보.json 이 깨졌으면 빈 목록(예외 없음)
        (self.folder / CACHE_SHARE_INDEX).write_text("{broken", encoding="utf-8")
        self.assertEqual(self.batch.cache_share_list({})["items"], [])

    def test_share_dir_is_sibling_of_save_dir(self):
        self.assertEqual(Path(cache_share_dir(str(self.docs))), self.folder)
        root = Path(self.docs.anchor)
        self.assertEqual(Path(cache_share_dir(str(root))), root / CACHE_SHARE_DIRNAME)   # 드라이브 루트면 그 안

    def test_ipc(self):
        self.write_caches()
        output = io.BytesIO()
        session = Session(output)
        session.batch = self.batch
        self.addCleanup(session.close)
        session.handle(dict(version=1, id=1, method="batch_cache_publish", params={}))
        for worker in list(session.workers):
            worker.join(20)
        session.handle(dict(version=1, id=2, method="batch_cache_share_list", params={}))
        for worker in list(session.workers):
            worker.join(20)
        events = [json.loads(line) for line in output.getvalue().splitlines()]
        done = [e for e in events if e["id"] == 1][-1]
        self.assertEqual(done["event"], "completed", done)
        self.assertEqual(done["batch"]["reports"], 5)
        listed = [e for e in events if e["id"] == 2][-1]
        self.assertEqual(listed["event"], "completed", listed)
        self.assertEqual(len(listed["batch"]["items"]), 1)
        # 지난 버전의 내보내기 요청은 없다(#39: zip 만들기 삭제)
        session.handle(dict(version=1, id=3, method="batch_cache_export", params={}))
        bad = [json.loads(line) for line in output.getvalue().splitlines() if json.loads(line)["id"] == 3][-1]
        self.assertNotEqual(bad["event"], "completed")


def report_entry(i, mtime=1000):
    return {"signature": [mtime + i, 100 + i], "digest": f"{i:064x}", "report": {"rows": [i]}}


class CacheImport(unittest.TestCase):
    """PC A(장비 폴더 P:\\AOI-1\\Reports)가 내보낸 zip 을 PC B(같은 호기, 다른 경로)가 끌어 넣는다."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.local = self.base / "local"
        self.real = self.base / "eq" / "AOI-1" / "Reports"          # B 의 실제 Report 폴더
        self.real.mkdir(parents=True)
        self.link = self.base / "drive"                                # B 는 연결 경로(resolve 하면 바뀜)로 등록
        self.link.symlink_to(self.base / "eq", target_is_directory=True)
        self.folder = str(self.link / "AOI-1" / "Reports")
        self.cfg = self.base / "config.json"
        self.cfg.write_text(json.dumps({"local_dir": str(self.local), "wph_report_paths": {"AOI-1": self.folder}}), encoding="utf-8")
        self.batch = DesktopBatch(self.cfg)

    def make_zip(self, caches, name="BatchReport_캐시_20261013_090000.zip", manifest=None):
        path = self.base / name
        with zipfile.ZipFile(path, "w") as zf:
            for i, state in enumerate(caches):
                zf.writestr(f"누적/{state['machine']}_{i:08d}.json", json.dumps(state, ensure_ascii=False))
            zf.writestr("사람선택/" + CHOICES_FILE, json.dumps({"schema": 1, "choices": {"x": 1}}))
            zf.writestr("manifest.json", json.dumps(manifest or {"schema": 1, "cache_schema": 1, "exported_at": "2026-10-13 09:00:00",
                                                                 "app_version": "12.5.16", "files": []}))
        return path

    def other_pc(self, machine, folder, names):
        return {"schema": 1, "machine": machine, "folder": folder,
                "entries": {n: report_entry(i) for i, n in enumerate(names)}}

    def cache_files(self):
        return sorted((self.local / "배치분석" / "누적").glob("*.json"))

    def test_import_maps_folder_and_keeps_existing(self):
        names = [f"J_S_LOT{i}_26-Oct-0{i}_(10.00.00)_BatchReport.htm" for i in range(1, 4)]
        zip_path = self.make_zip([self.other_pc("AOI-1", r"P:\AOI-1\Reports", names),
                                  self.other_pc("AOI-9", r"P:\AOI-9\Reports", names[:1]),     # 이 PC 에 없는 호기
                                  dict(self.other_pc("AOI-1", r"P:\AOI-1\Reports", []), entries={"../evil.htm": report_entry(9),
                                                                                                  names[0]: {"bad": 1}})])
        out = self.batch.cache_import({"path": str(zip_path)})
        self.assertEqual((out["added"], out["kept"], out["machines"]), (3, 0, ["AOI-1"]))
        self.assertEqual(out["skipped"], [{"machine": "AOI-9", "reports": 1}])
        self.assertEqual(out["invalid"], 2)                 # 경로 문자 든 이름 · 형식이 깨진 항목은 넣지 않음
        self.assertTrue(out["choices_skipped"])
        self.assertFalse((self.local / "Cache" / CHOICES_FILE).exists())   # 사람 선택은 PC 마다 따로
        files = self.cache_files()
        self.assertEqual(len(files), 1)
        state = json.loads(files[0].read_text(encoding="utf-8"))
        self.assertEqual((state["machine"], state["folder"]), ("AOI-1", str(Path(self.folder))))
        self.assertEqual(sorted(state["entries"]), sorted(names))
        # 장비 접근 없이 캐시만으로: 찾기 1단계 · 지난 범위 복원이 가져온 것을 본다
        cached = batchreport_store.load_cached(self.local, [{"machine": "AOI-1", "folder": self.folder}])
        self.assertEqual(len(cached["records"]), 3)
        # 다시 넣으면 이미 있는 것은 그대로
        again = self.batch.cache_import({"path": str(zip_path)})
        self.assertEqual((again["added"], again["kept"]), (0, 3))
        self.assertEqual(len(self.cache_files()), 1)

    def test_collect_adopts_imported_cache_and_reads_only_new(self):
        names = [f"J_S_LOT{i}_26-Oct-0{i}_(10.00.00)_BatchReport.htm" for i in range(1, 3)]
        for n in names:
            (self.real / n).write_text("x", encoding="utf-8")
        entries = {}
        for i, n in enumerate(names):
            st = (self.real / n).stat()
            entries[n] = dict(report_entry(i), signature=[st.st_mtime_ns, st.st_size])
        zip_path = self.make_zip([{"schema": 1, "machine": "AOI-1", "folder": r"P:\AOI-1\Reports", "entries": entries}])
        self.batch.cache_import({"path": str(zip_path)})
        plain = self.cache_files()
        out = batchreport_store.collect(self.local, [{"machine": "AOI-1", "folder": self.folder}], host_gap=0)
        self.assertEqual((out["parsed"], out["reused"]), (0, 2))       # 장비에서 다시 열지 않음
        after = self.cache_files()
        self.assertEqual(len(after), 1)
        self.assertNotEqual(after, plain)                                # resolve 한 이름으로 옮겨 씀
        self.assertEqual(sorted(json.loads(after[0].read_text(encoding="utf-8"))["entries"]), sorted(names))

    def test_rejects_bad_input(self):
        for params in ({}, {"path": ""}, {"path": "relative.zip"}, {"path": str(self.base / "x.txt")},
                       {"path": str(self.base / "missing.zip")}, {"path": str(self.base / "a.zip"), "x": 1}):
            with self.assertRaises(ValueError, msg=params):
                self.batch.cache_import(params)
        broken = self.base / "broken.zip"
        broken.write_bytes(b"not a zip")
        with self.assertRaises(ValueError):
            self.batch.cache_import({"path": str(broken)})
        with self.assertRaises(ValueError):          # 다른 캐시 형식
            self.batch.cache_import({"path": str(self.make_zip([], "old.zip", {"schema": 1, "cache_schema": 99}))})
        with self.assertRaises(ValueError):          # 이 PC 에 같은 호기가 없음
            self.batch.cache_import({"path": str(self.make_zip([self.other_pc("AOI-9", "P:\\x", ["a_BatchReport.htm"])], "other.zip"))})

    def test_round_trip_and_ipc(self):
        # B 가 만든 zip(게시와 같은 형식) → 새 PC(C) 가 IPC 로 import
        acc = self.local / "배치분석" / "누적"
        acc.mkdir(parents=True)
        (acc / ("a" * 64 + ".json")).write_text(json.dumps(self.other_pc("AOI-1", self.folder, ["r1_BatchReport.htm", "r2_BatchReport.htm"])), encoding="utf-8")
        zip_path = self.base / "BatchReport_캐시_20261030_090000.zip"
        self.batch._build_cache_zip(self.local, zip_path)
        other = self.base / "pc_c"
        cfg = self.base / "config_c.json"
        cfg.write_text(json.dumps({"local_dir": str(other), "wph_report_paths": {"AOI-1": str(self.real)}}), encoding="utf-8")
        output = io.BytesIO()
        session = Session(output)
        session.batch = DesktopBatch(cfg)
        self.addCleanup(session.close)
        session.handle(dict(version=1, id=1, method="batch_cache_import", params={"path": str(zip_path)}))
        for worker in list(session.workers):
            worker.join(20)
        events = [json.loads(line) for line in output.getvalue().splitlines()]
        done = [e for e in events if e["id"] == 1][-1]
        self.assertEqual(done["event"], "completed", done)
        self.assertEqual((done["batch"]["added"], done["batch"]["targets"][0]["folder"]), (2, str(self.real)))


if __name__ == "__main__":
    unittest.main()
