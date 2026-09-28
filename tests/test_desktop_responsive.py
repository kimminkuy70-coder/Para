"""Regression: a team config / a slow screen must not freeze the whole web app.

Field report (2026-09-28): after pointing the web app at the team's OneDrive save
folder, every screen stayed at "불러오는 중" and 값 업데이트 never loaded.
Two causes are pinned here:
1. `batchreport_store.local_root` resolved every registered equipment Report folder
   (network shares) on nearly every request — a disconnected share blocks for the
   SMB timeout, so the engine's input loop was stuck.
2. One global busy flag: any slow job (e.g. reading a big collation on OneDrive)
   made every other screen's first request fail, leaving it on "불러오는 중".
"""
import io
import json
import pathlib
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from param_manager import batchreport_store
from param_manager.desktop_batch import DesktopBatch
from param_manager.desktop_ipc import Session

SHARES = [f"\\\\10.0.0.{i}\\c$\\Reports" for i in range(1, 25)] + ["P:\\AOI-21\\Reports", "//10.9.9.9/share"]


class NoNetworkResolveTests(unittest.TestCase):
    def test_configuration_never_resolves_equipment_paths(self):
        tmp = Path(tempfile.mkdtemp(prefix="rev1-resp-"))
        cfg = tmp / "c.json"
        cfg.write_text(json.dumps({"local_dir": str(tmp / "local"),
                                   "wph_report_paths": {f"AOI-{i:02}": p for i, p in enumerate(SHARES)}}), encoding="utf-8")
        real = pathlib.Path.resolve

        def guarded(self, *a, **kw):
            text = str(self)
            if "10.0.0." in text or "AOI-21" in text or "10.9.9.9" in text:
                raise AssertionError(f"equipment path touched: {text}")
            return real(self, *a, **kw)
        with patch.object(pathlib.Path, "resolve", guarded):
            DesktopBatch(cfg).describe()
            batchreport_store.local_root(tmp / "local", SHARES)

    def test_local_source_overlap_still_rejected(self):
        tmp = Path(tempfile.mkdtemp(prefix="rev1-resp-"))
        with self.assertRaises(ValueError):
            batchreport_store.local_root(tmp / "src" / "out", [str(tmp / "src")])
        with self.assertRaises(ValueError):
            batchreport_store.local_root(tmp / "src", [str(tmp / "src" / "reports")])
        batchreport_store.local_root(tmp / "out", [str(tmp / "src")])


class ScreenIndependenceTests(unittest.TestCase):
    def test_slow_recipe_load_does_not_block_other_screens(self):
        out = io.BytesIO()
        session = Session(out)
        started, proceed = threading.Event(), threading.Event()

        def slow_open():
            started.set()
            proceed.wait(5)
            return {"version": "v"}
        with patch.object(session.recipe, "open", side_effect=slow_open), \
                patch.object(session.update, "prepare", return_value={"recipes": ["PI3"]}), \
                patch.object(session.documents, "open", return_value={"snapshot": "s"}):
            session.handle(dict(version=1, id=1, method="recipe_open", params={}))
            self.assertTrue(started.wait(2))
            session.handle(dict(version=1, id=2, method="update_prepare", params={}))
            session.handle(dict(version=1, id=3, method="document_open", params={"kind": "ip"}))
            session.handle(dict(version=1, id=4, method="recipe_open", params={}))   # same screen: guarded
            for w in list(session.workers):
                if w.is_alive() and w is not session.worker:
                    w.join(2)
            proceed.set()
            for w in list(session.workers):
                w.join(2)
        events = [json.loads(line) for line in out.getvalue().splitlines()]
        done = {e["id"]: e for e in events if e["event"] in ("completed", "error")}
        self.assertEqual(done[2]["event"], "completed")
        self.assertEqual(done[2]["update"], {"recipes": ["PI3"]})
        self.assertEqual(done[3]["event"], "completed")
        self.assertEqual(done[4]["event"], "error")
        self.assertIn("Recipe 관리", done[4]["message"])
        self.assertEqual(done[1]["event"], "completed")
        self.assertFalse(session.running)
        session.close()


if __name__ == "__main__":
    unittest.main()
