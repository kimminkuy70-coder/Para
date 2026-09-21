"""Headless tests for the desktop history (이력 확인) adapter."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from param_manager import collate, workdirs
from param_manager.desktop_history import DesktopHistory


def _collate_file(path, rows, machines):
    res = collate.CollateRecipe(recipe="PI3", machines=machines)
    for pi, rc, zone, alg, param, vals in rows:
        rec = {"PI": pi, "Recipe": rc, "Zone": zone, "Alg": alg, "Parameter": param, "비고": ""}
        rec.update(vals)
        res.records.append(rec)
    collate.write_collation(path, {"PI3": res}, machines)


class DesktopHistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rev1-hist-")
        self.save = os.path.join(self.tmp, "save")
        os.makedirs(self.save)
        m = ["AOI-24", "AOI-25"]
        _collate_file(workdirs.collate_path(self.save, "20260101_000000_000000"),
                      [("PI3", "PI", "GlobalRTP", "GLOBAL", "Max Defects", {"AOI-24": "3000", "AOI-25": "3000"}),
                       ("PI3", "PI", "PI Opening", "Surface", "삭제될 항목", {"AOI-24": "1"})], m)
        _collate_file(workdirs.collate_path(self.save, "20260202_000000_000000"),
                      [("PI3", "PI", "GlobalRTP", "GLOBAL", "Max Defects", {"AOI-24": "7000", "AOI-25": "3000"}),
                       ("PI3", "PI", "PI Opening", "Surface", "새 항목", {"AOI-24": "9"})], m)
        self.cfg = os.path.join(self.tmp, "c.json")
        with open(self.cfg, "w", encoding="utf-8") as fh:
            json.dump({"save_dir": self.save}, fh)
        self.h = DesktopHistory(config_path=self.cfg)

    def test_files_lists_collations(self):
        out = self.h.files()
        self.assertTrue(out["save_dir"])
        self.assertEqual(len(out["files"]), 2)

    def test_diff_and_page(self):
        files = self.h.files()
        ids = [f["id"] for f in files["files"]]     # newest first
        # old = older file (last), new = newest (first)
        d = self.h.diff({"catalog": files["catalog"], "old": ids[1], "new": ids[0]})
        self.assertEqual(d["changes"], 1)           # Max Defects AOI-24 3000→7000
        self.assertEqual(d["added"], 1)
        self.assertEqual(d["removed"], 1)
        page = self.h.page({"snapshot": d["snapshot"], "offset": 0, "limit": 100, "kind": "", "query": ""})
        self.assertEqual(page["total"], 1)
        row = page["rows"][0]
        self.assertEqual((row["old"], row["new"], row["kind"], row["machine"]), ("3000", "7000", "값변경", "AOI-24"))

    def test_page_query_filter(self):
        files = self.h.files()
        ids = [f["id"] for f in files["files"]]
        d = self.h.diff({"catalog": files["catalog"], "old": ids[1], "new": ids[0]})
        empty = self.h.page({"snapshot": d["snapshot"], "offset": 0, "limit": 100, "kind": "", "query": "없는파라미터"})
        self.assertEqual(empty["total"], 0)

    def test_same_file_rejected(self):
        files = self.h.files()
        ids = [f["id"] for f in files["files"]]
        with self.assertRaises(ValueError):
            self.h.diff({"catalog": files["catalog"], "old": ids[0], "new": ids[0]})

    def test_no_save_dir(self):
        empty = os.path.join(self.tmp, "empty.json")
        with open(empty, "w", encoding="utf-8") as fh:
            json.dump({}, fh)
        self.assertEqual(DesktopHistory(config_path=empty).files(), {"save_dir": False, "catalog": None, "files": []})


if __name__ == "__main__":
    unittest.main()
