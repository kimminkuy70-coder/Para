"""Headless behavioral regressions for version_new; no equipment/network access."""
import ast
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from param_manager import atomicfile, cmwatcher, errlog, watcher, wph
import openpyxl


class ReviewTests(unittest.TestCase):
    def test_log_fallback_never_writes_to_shared_folder(self):
        with tempfile.TemporaryDirectory() as d:
            shared = Path(d) / 'shared'
            shared.mkdir()
            with patch('param_manager.localdirs.active_root', side_effect=OSError), patch.dict(os.environ, LOCALAPPDATA=d):
                self.assertTrue(errlog.write_log(str(shared), 'TEST', 'fallback'))
                self.assertEqual(list(shared.iterdir()), [])
                self.assertTrue((Path(d) / 'CamtekAOI/Logs' / errlog.LOG_NAME).exists())

    def test_local_atomic_failure_preserves_settings(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'settings.json'
            p.write_text('{"old": 1}')
            with patch.object(atomicfile.os, 'replace', side_effect=PermissionError):
                with self.assertRaises(PermissionError):
                    atomicfile.write_json(p, {'new': 2})
            self.assertEqual(json.loads(p.read_text()), {'old': 1})
            self.assertEqual(list(Path(d).iterdir()), [p])

    def test_pending_scan_retries_without_parent_mtime_change(self):
        with tempfile.TemporaryDirectory() as d:
            lot = Path(d) / 'lot'
            sm = lot / 'SM1'
            sm.mkdir(parents=True)
            seen = set()
            with patch.object(cmwatcher, 'lot_dirs_for', return_value=[lot]):
                with patch.object(cmwatcher, '_has_config', return_value=False):
                    first = cmwatcher.scan_new([], [('device', 'lot')], seen, {}, settle_minutes=0)
                self.assertEqual(len(first['pending']), 1)
                with patch.object(cmwatcher, '_has_config', return_value=True):
                    second = cmwatcher.scan_new([], [('device', 'lot')], seen, first['mtimes'], settle_minutes=0)
                    self.assertEqual(len(second['new']), 1)
                    third = cmwatcher.scan_new([], [('device', 'lot')], seen, second['mtimes'], settle_minutes=0)
                    self.assertEqual(third['skipped'], 1)

    def test_wph_deduplicates_and_rejects_paths(self):
        with tempfile.TemporaryDirectory() as d:
            name = 'example_BatchReport.htm'
            (Path(d) / name).touch()
            self.assertEqual(wph._resolve_names(d, '', [name, name]), [name])
            self.assertEqual(wph._resolve_names(d, '', []), [])
            with self.assertRaises(ValueError):
                wph._resolve_names(d, '', ['../' + name])

    def test_wph_more_than_2000_rows_has_formulas_and_statistics(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'wph.xlsx'
            rows = [dict(source_file=str(i), wafers=25, avg_scan_sec=100, batch_sec=3000) for i in range(2001)]
            wph.write_wph_excel(p, rows)
            wb = openpyxl.load_workbook(p)
            try:
                ws = wb['01_Raw_Data']
                self.assertEqual(ws['A2002'].value, 2001)
                self.assertTrue(ws['J2002'].value.startswith('='))
                formulas = [c.value for s in wb if s != ws for row in s for c in row if c.data_type == 'f']
                self.assertTrue(any('2002' in f for f in formulas))
            finally:
                wb.close()

if __name__ == '__main__':
    unittest.main()
