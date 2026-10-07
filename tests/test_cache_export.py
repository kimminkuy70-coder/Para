"""Batch Report 취합 캐시 내보내기(이슈 #16): 배치분석/누적/*.json → zip 1개 + manifest, 폴더에서 보기."""
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
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


if __name__ == "__main__":
    unittest.main()
