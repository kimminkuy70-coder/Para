"""OneDrive (shared save folder) access rules for the web adapters.

Company security alerts fire on bursts of shared-folder reads/creates
('Unusual High-Volume Directory Access', 2026-08). Rules pinned here:
  · no temp files in the save folder (documents, notes, cell colors)
  · an edit lock is written once per screen visit, not per save
  · a burst of cell paints is ONE write of 값확인_셀색상.json
  · lists do not open every recipe's folders/workbooks at once
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from param_manager import collate, formbuilder, locking, workdirs, formcache  # noqa: E402
from param_manager import engine as eng  # noqa: E402
from param_manager.desktop_form import DesktopForm  # noqa: E402
from param_manager.desktop_recipe import DesktopRecipe  # noqa: E402
from param_manager.desktop_update import DesktopUpdate  # noqa: E402


class SharedFolderRules(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rev1-onedrive-"))
        self.save = self.tmp / "OneDrive" / "docs"
        self.save.mkdir(parents=True)
        self.cfg = self.tmp / "c.json"
        self.cfg.write_text(json.dumps({"save_dir": str(self.save), "local_dir": str(self.tmp / "local")}), encoding="utf-8")
        machines = ["AOI-01", "AOI-02"]
        rows = [dict(PI="PI2", Recipe="R1", Zone="Z", Alg="A", Parameter=f"P{i}", **{"비고": ""},
                     **{m: str(i) for m in machines}) for i in range(5)]
        self.collate = workdirs.collate_path(str(self.save), "20260921_010101")
        collate.write_collation(self.collate, {"PI2": collate.CollateRecipe(recipe="PI2", records=rows)}, machines)
        p = patch.object(locking, "VERIFY_DELAY_SEC", 0)
        p.start()
        self.addCleanup(p.stop)

    def listing(self):
        return sorted(str(p.relative_to(self.save)) for p in self.save.rglob("*"))

    def test_notes_and_paint_leave_only_result_files(self):
        recipe = DesktopRecipe(self.cfg)
        cat = recipe.open()
        before = self.listing()
        created = []
        real_mkstemp = tempfile.mkstemp

        def watch_mkstemp(*a, **k):
            path = k.get("dir") or (a[2] if len(a) > 2 else "")
            if path and str(self.save) in str(path):
                created.append(path)
            return real_mkstemp(*a, **k)
        writes = []
        real_lock = eng.write_lock
        with patch("tempfile.mkstemp", side_effect=watch_mkstemp), \
             patch.object(eng, "write_lock", side_effect=lambda *a, **k: (writes.append(1), real_lock(*a, **k))[1]):
            for i in range(3):
                cat = recipe.edit({"snapshot": cat["version"], "row": i, "kind": "note", "value": f"n{i}"})
            recipe.paint({"snapshot": cat["version"], "cells": [
                {"row": i, "target": "AOI-01", "color": "#ffee00"} for i in range(5)]})
        self.assertEqual(created, [])                               # no temp file in the save folder
        self.assertEqual(len(writes), 1)                           # lock once for the whole visit
        after = self.listing()
        new = [n for n in after if n not in before]
        self.assertEqual(sorted(n for n in new if not n.endswith(".editlock")), ["값확인_셀색상.json"])
        self.assertEqual(len(json.loads((self.save / "값확인_셀색상.json").read_text(encoding="utf-8"))), 5)
        recipe.close()
        self.assertEqual([n for n in self.listing() if n.endswith(".editlock")], [])

    def test_form_list_does_not_scan_every_recipe(self):
        for r in ("PI2", "PI3", "PI4"):
            os.makedirs(os.path.join(self.save, workdirs.FORM_DIR, r, "20260901_000000"), exist_ok=True)
        with patch.object(workdirs, "form_version_status", side_effect=AssertionError("scanned all recipes")):
            out = DesktopForm(self.cfg).catalog()
        self.assertEqual([r["recipe"] for r in out["recipes"]], ["PI2", "PI3", "PI4"])
        with patch.object(workdirs, "latest_form", side_effect=AssertionError("opened every recipe")):
            DesktopUpdate(self.cfg).prepare({})

    def test_similar_forms_read_each_workbook_once(self):
        for r in ("PI2", "PI3"):
            run = workdirs.form_run_dir(str(self.save), r, "20260901_000000")
            formbuilder.build_initial_workbook(
                [dict(layer=r, recipe=r, mag="PI", zone="Z", alg="A", param="P", values={}, unit="",
                      raws={"양식": "1"}, use=True, extract={"src_file": "x.ini", "section": "S", "key": "K",
                                                             "transform": "RAW", "source_path": ""})],
                os.path.join(run, "init.xlsx"), level=r)
            formbuilder.build_final_from_initial(os.path.join(run, "init.xlsx"),
                                                 workdirs.form_final_path(run, r, "AOI-01", "20260901_000000"), level=r)
        local = str(self.tmp / "local")
        calls = []
        real = formbuilder.form_params
        with patch.object(formbuilder, "form_params", side_effect=lambda p: (calls.append(p), real(p))[1]):
            first = formcache.similar_forms(str(self.save), local)
            second = formcache.similar_forms(str(self.save), local)
        self.assertEqual(first, second)
        self.assertEqual(len(calls), 2)                            # opened once each, then cached locally
        self.assertTrue((self.tmp / "local" / "Cache" / formcache.CACHE_NAME).is_file())

    def test_no_atomic_temp_json_in_shared_writers(self):
        src = Path(__file__).resolve().parents[1] / "param_manager"
        for name in ("desktop_recipe.py", "desktop_documents.py"):
            text = (src / name).read_text(encoding="utf-8")
            self.assertNotIn("atomicfile", text, name)             # atomicfile = temp file beside target


if __name__ == "__main__":
    unittest.main()
