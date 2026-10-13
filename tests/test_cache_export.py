"""Batch Report 취합 캐시 내보내기(이슈 #16): 배치분석/누적/*.json → zip 1개 + manifest, 폴더에서 보기.
가져오기(이슈 #29): 다른 PC 의 zip → 이 PC 캐시에 합침(호기 이름으로 짝 · 이 PC 폴더로 옮겨 적음 · 있던 것 유지)."""
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from param_manager import batchreport_store
from param_manager.desktop_batch import CHOICES_FILE, DesktopBatch
from param_manager.desktop_ipc import Session
from param_manager.desktop_open import DesktopOpen


def cache(machine, folder, n):
    return {"schema": 1, "machine": machine, "folder": folder,
            "entries": {f"R{i}.htm": {"signature": [i, i], "report": {"rows": [i]}} for i in range(n)}}


class CacheExport(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.local = base / "local"
        self.cfg = base / "config.json"
        self.cfg.write_text(json.dumps({"local_dir": str(self.local)}), encoding="utf-8")
        self.batch = DesktopBatch(self.cfg)

    def write_caches(self):
        acc = self.local / "배치분석" / "누적"
        acc.mkdir(parents=True)
        (acc / ("a" * 64 + ".json")).write_text(json.dumps(cache("M01", r"\\eq\M01\Reports", 3)), encoding="utf-8")
        (acc / ("b" * 64 + ".json")).write_text(json.dumps(cache("M02", r"\\eq\M02\Reports", 2)), encoding="utf-8")
        (acc / ("c" * 64 + ".json")).write_text("{broken", encoding="utf-8")            # 깨진 캐시는 건너뜀
        (self.local / "Cache").mkdir()
        (self.local / "Cache" / CHOICES_FILE).write_text(json.dumps({"schema": 1, "choices": {}}), encoding="utf-8")

    def test_empty_cache_is_error(self):
        with self.assertRaises(ValueError):
            self.batch.cache_export({})

    def test_zip_contains_every_cache_and_manifest(self):
        self.write_caches()
        out = self.batch.cache_export({})
        path = Path(out["path"])
        self.assertTrue(path.is_file() and path.parent.name == "내보내기" and path.suffix == ".zip")
        self.assertEqual((out["files"], out["machines"], out["reports"]), (2, 2, 5))
        with zipfile.ZipFile(path) as zf:
            names = set(zf.namelist())
            manifest = json.loads(zf.read("manifest.json"))
            self.assertIn("사람선택/" + CHOICES_FILE, names)
            for f in manifest["files"]:
                self.assertIn(f["file"], names)
                self.assertEqual(len(json.loads(zf.read(f["file"]))["entries"]), f["reports"])
        self.assertEqual({f["machine"] for f in manifest["files"]}, {"M01", "M02"})
        self.assertEqual(manifest["reports"], 5)
        self.assertFalse(list(path.parent.glob(".*.tmp")))
        with self.assertRaises(ValueError):
            self.batch.cache_export({"x": 1})
        # 폴더 열기: zip 은 탐색기에서 선택(reveal)만 허용, 내용 열기는 계속 거부
        opener = DesktopOpen(self.cfg)
        self.assertEqual(opener.resolve(str(path), reveal=True), path)
        with self.assertRaises(ValueError):
            opener.resolve(str(path))

    def test_keeps_latest_three(self):
        self.write_caches()
        folder = self.local / "배치분석" / "내보내기"
        folder.mkdir(parents=True)
        for i in range(4):
            (folder / f"BatchReport_캐시_2020010{i}_000000.zip").write_bytes(b"x")
        out = self.batch.cache_export({})
        left = sorted(p.name for p in folder.glob("BatchReport_캐시_*.zip"))
        self.assertEqual(len(left), 3)
        self.assertIn(Path(out["path"]).name, left)

    def test_ipc(self):
        self.write_caches()
        output = io.BytesIO()
        session = Session(output)
        session.batch = self.batch
        self.addCleanup(session.close)
        session.handle(dict(version=1, id=1, method="batch_cache_export", params={}))
        for worker in list(session.workers):
            worker.join(20)
        events = [json.loads(line) for line in output.getvalue().splitlines()]
        done = [e for e in events if e["id"] == 1][-1]
        self.assertEqual(done["event"], "completed", done)
        self.assertEqual(done["batch"]["reports"], 5)


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
        # B 가 직접 export → 새 PC(C) 가 IPC 로 import
        acc = self.local / "배치분석" / "누적"
        acc.mkdir(parents=True)
        (acc / ("a" * 64 + ".json")).write_text(json.dumps(self.other_pc("AOI-1", self.folder, ["r1_BatchReport.htm", "r2_BatchReport.htm"])), encoding="utf-8")
        zip_path = Path(self.batch.cache_export({})["path"])
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
