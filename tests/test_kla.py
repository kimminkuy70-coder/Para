"""KLA 자재 찾기(이슈 #30): {장비}\\{날짜}\\{Lot}\\{스캔 시각}_{슬롯} 폴더 이름만 보고 Lot 경로를 찾는다."""
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from param_manager.desktop_ipc import Session
from param_manager.desktop_kla import DesktopKla, slot_info
from param_manager.desktop_open import DesktopOpen


def make_slot(root, day, lot, slot_dir, files=("a.jpg",)):
    d = Path(root) / day / lot / slot_dir
    d.mkdir(parents=True)
    for f in files:
        (d / f).write_bytes(b"x")
    return d


class Kla(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.cfg = self.base / "config.json"
        self.cfg.write_text(json.dumps({"save_dir": str(self.base / "save")}), encoding="utf-8")
        self.drive = self.base / "J"
        self.k2 = self.drive / "2.K2"
        self.k1 = self.drive / "1.K1"
        make_slot(self.k2, "2025-05-21", "RINT63@6324", "2025-05-21-09-08_16",
                  ("120072022.16_9_1_31_1.jpg", "RDL_RINT63@6324_120072022.16.001", "RDL_RINT63@6324_120072022.16.pass"))
        make_slot(self.k2, "2025-05-21", "RINT63@6324", "2025-05-21-09-30_2")
        make_slot(self.k2, "2025-05-22", "RINT63@6324", "2025-05-22-01-00_16")
        make_slot(self.k2, "2025-05-22", "ABC11@1111", "2025-05-22-02-00_1")
        make_slot(self.k1, "2025-06-01", "rint63@7777", "2025-06-01-10-00_5")
        (self.k2 / "misc").mkdir()                                      # 날짜가 아닌 폴더는 무시
        self.kla = DesktopKla(self.cfg)

    def test_slot_info(self):
        self.assertEqual(slot_info("2025-05-21-09-08_16"), ("16", "2025-05-21 09:08"))
        self.assertEqual(slot_info("2025-05-21-09-08-33_03"), ("3", "2025-05-21 09:08:33"))
        self.assertEqual(slot_info("weird_7"), ("7", ""))
        self.assertEqual(slot_info("weird"), ("", ""))

    def test_roots_saved_and_validated(self):
        self.assertEqual(self.kla.state(), {"roots": [], "backup": True})
        out = self.kla.set_roots({"roots": [{"name": "2.K2", "path": str(self.k2)}]})
        self.assertEqual(out["roots"], [{"name": "2.K2", "path": str(self.k2), "backups": []}])
        cfg = json.loads(self.cfg.read_text(encoding="utf-8"))
        self.assertEqual(cfg["kla_roots"], {"2.K2": str(self.k2)})
        self.assertEqual(cfg["save_dir"], str(self.base / "save"))          # 다른 설정은 그대로
        for bad in ([{"name": "", "path": str(self.k2)}], [{"name": "a/b", "path": str(self.k2)}],
                    [{"name": "K", "path": "relative\\path"}],
                    [{"name": "K", "path": str(self.k2)}, {"name": "K", "path": str(self.k1)}],
                    [{"name": "K", "path": str(self.k2), "backups": ["relative"]}],
                    [{"name": "K", "path": str(self.k2), "backups": [str(self.k1)] * 21}],
                    [{"name": "K", "path": str(self.k2), "other": 1}]):
            with self.assertRaises(ValueError):
                self.kla.set_roots({"roots": bad})

    def test_search_machine_folder(self):
        self.kla.set_roots({"roots": [{"name": "2.K2", "path": str(self.k2)}]})
        out = self.kla.search({"query": "rint63"})
        self.assertEqual([(h["date"], h["lot"]) for h in out["hits"]],
                         [("2025-05-22", "RINT63@6324"), ("2025-05-21", "RINT63@6324")])   # 최근 날짜 먼저
        first = out["hits"][1]
        self.assertEqual(first["machine"], "2.K2")
        self.assertEqual(first["path"], str(self.k2 / "2025-05-21" / "RINT63@6324"))
        self.assertEqual([(s["slot"], s["time"]) for s in first["slots"]], [("16", "2025-05-21 09:08"), ("2", "2025-05-21 09:30")])
        self.assertEqual(out["dates"], 2)
        # 여러 단어 = 모두 포함, 기간
        self.assertEqual(len(self.kla.search({"query": "RINT 6324", "start": "2025-05-22", "end": "2025-05-22"})["hits"]), 1)
        self.assertEqual(self.kla.search({"query": "RINT 9999"})["hits"], [])
        with self.assertRaises(ValueError):
            self.kla.search({"query": "  "})
        with self.assertRaises(ValueError):
            self.kla.search({"query": "x", "start": "2025/05/01"})

    def test_parent_folder_finds_machine_folders(self):
        """J:\\ 하나만 등록 → 그 아래 장비 폴더(1.K1, 2.K2)를 모두 찾는다."""
        self.kla.set_roots({"roots": [{"name": "J", "path": str(self.drive)}]})
        out = self.kla.search({"query": "rint63"})
        self.assertEqual(sorted({h["machine"] for h in out["hits"]}), ["J › 1.K1", "J › 2.K2"])
        self.assertEqual(len(out["hits"]), 3)
        self.assertEqual(sorted(out["machines"]), ["J › 1.K1", "J › 2.K2"])

    def test_missing_root_reported(self):
        self.kla.set_roots({"roots": [{"name": "2.K2", "path": str(self.k2)}, {"name": "X", "path": str(self.base / "nope")}]})
        out = self.kla.search({"query": "abc11"})
        self.assertEqual(len(out["hits"]), 1)
        self.assertEqual([f["machine"] for f in out["failed"]], ["X"])
        self.assertEqual(len(self.kla.search({"query": "abc11", "machines": ["X"]})["hits"]), 0)

    def test_search_does_not_write(self):
        self.kla.set_roots({"roots": [{"name": "2.K2", "path": str(self.k2)}]})
        before = sorted((str(p), p.stat().st_mtime_ns) for p in self.k2.rglob("*"))
        self.kla.search({"query": "rint"})
        self.assertEqual(sorted((str(p), p.stat().st_mtime_ns) for p in self.k2.rglob("*")), before)

    def test_open_folder_allowed_only_inside_kla_roots(self):
        self.kla.set_roots({"roots": [{"name": "2.K2", "path": str(self.k2)}]})
        opener = DesktopOpen(self.cfg)
        slot = self.k2 / "2025-05-21" / "RINT63@6324" / "2025-05-21-09-08_16"
        self.assertEqual(opener.resolve(str(slot)), slot.absolute())
        self.assertEqual(opener.resolve(str(slot.parent)), slot.parent.absolute())
        with self.assertRaises(ValueError):
            opener.resolve(str(self.k1 / "2025-06-01"))                  # 등록하지 않은 장비
        with self.assertRaises(ValueError):
            opener.resolve(str(slot / "RDL_RINT63@6324_120072022.16.001"))   # 파일(.001)은 열지 않음

    def test_defect_image_backup(self):
        """#32: 장비마다 Defect 이미지 백업 폴더(날짜 폴더째 옮겨 둔 곳)를 등록하고 켜고 끈다(기본 켬)."""
        backup = self.base / "K" / "KLA_backup" / "2.K2"
        make_slot(backup, "2025-04-01", "RINT63@5555", "2025-04-01-08-00_3")
        make_slot(backup, "2025-05-21", "RINT63@6324", "2025-05-21-09-08_16")      # 원본과 같은 Lot 이 백업에도
        out = self.kla.set_roots({"roots": [{"name": "2.K2", "path": str(self.k2), "backups": [str(backup), str(backup)]}]})
        self.assertEqual(out["roots"][0]["backups"], [str(backup)])                  # 같은 경로는 한 번만
        self.assertTrue(out["backup"])
        # backups 를 빼고 다시 저장하면(장비 폴더만 고침) 백업 폴더는 그대로
        self.assertEqual(self.kla.set_roots({"roots": [{"name": "2.K2", "path": str(self.k2)}]})["roots"][0]["backups"], [str(backup)])
        res = self.kla.search({"query": "rint63"})
        self.assertTrue(res["backup"])
        self.assertEqual(res["backup_folders"], 1)
        self.assertEqual([(h["date"], h["lot"], h["backup"]) for h in res["hits"]],
                         [("2025-05-22", "RINT63@6324", False), ("2025-05-21", "RINT63@6324", False),
                          ("2025-05-21", "RINT63@6324", True), ("2025-04-01", "RINT63@5555", True)])  # 같은 Lot 은 원본 먼저
        self.assertEqual(res["machines"], ["2.K2"])
        # 백업 폴더 안의 폴더도 열 수 있음
        self.assertTrue(self.kla.allows(str(backup / "2025-04-01" / "RINT63@5555")))
        # 끄면 원본만
        self.assertFalse(self.kla.set_backup({"enabled": False})["backup"])
        res = self.kla.search({"query": "rint63"})
        self.assertFalse(res["backup"])
        self.assertEqual([h["backup"] for h in res["hits"]], [False, False])
        cfg = json.loads(self.cfg.read_text(encoding="utf-8"))
        self.assertIs(cfg["kla_backup"], False)
        self.assertEqual(cfg["kla_backups"], {"2.K2": [str(backup)]})
        for bad in ({"enabled": 1}, {}, {"enabled": True, "x": 1}):
            with self.assertRaises(ValueError):
                self.kla.set_backup(bad)
        # 못 읽는 백업 폴더는 failed 에 backup 표시
        self.kla.set_backup({"enabled": True})
        self.kla.set_roots({"roots": [{"name": "2.K2", "path": str(self.k2), "backups": [str(self.base / "gone")]}]})
        res = self.kla.search({"query": "rint63"})
        self.assertEqual([(f["machine"], f["backup"]) for f in res["failed"]], [("2.K2", True)])
        self.assertEqual(len(res["hits"]), 2)
        # 장비를 지우면 그 백업 폴더 등록도 지워짐
        self.assertEqual(self.kla.set_roots({"roots": []}), {"roots": [], "backup": True})
        self.assertEqual(json.loads(self.cfg.read_text(encoding="utf-8"))["kla_backups"], {})

    def test_ipc(self):
        self.kla.set_roots({"roots": [{"name": "2.K2", "path": str(self.k2)}]})
        output = io.BytesIO()
        session = Session(output)
        session.kla = self.kla
        self.addCleanup(session.close)
        session.handle(dict(version=1, id=1, method="kla_state", params={}))
        session.handle(dict(version=1, id=2, method="kla_search", params={"query": "RINT63", "machines": ["2.K2"], "start": "", "end": ""}))
        for worker in list(session.workers):
            worker.join(20)
        session.handle(dict(version=1, id=3, method="kla_search", params={"bad": 1}))
        session.handle(dict(version=1, id=4, method="kla_set_backup", params={"enabled": False}))
        events = [json.loads(line) for line in output.getvalue().splitlines()]
        state = [e for e in events if e["id"] == 1][-1]
        self.assertEqual(state["kla"]["roots"][0]["name"], "2.K2")
        done = [e for e in events if e["id"] == 2][-1]
        self.assertEqual(done["event"], "completed", done)
        self.assertEqual(len(done["kla"]["hits"]), 2)
        self.assertEqual([e for e in events if e["id"] == 3][-1]["event"], "error")
        self.assertIs([e for e in events if e["id"] == 4][-1]["kla"]["backup"], False)


if __name__ == "__main__":
    unittest.main()
