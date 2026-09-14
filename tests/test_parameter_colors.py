"""Color persistence/compatibility and scroll-aware note geometry, without equipment IO."""
import ast
import os
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import openpyxl
from param_manager import namestore as ns, locking, engine


class ColorTests(unittest.TestCase):
    def test_repeated_variants_keep_single_edit_and_reject_conflicting_edits(self):
        entries = {1: {'alg': 'Surface', 'orig': 'BrightArea'},
                   3: {'alg': 'Surface', 'orig': 'BrightArea'}}
        initial = {1: '#FFFF80', 3: '#FFFF80'}
        result = ns.resolve_color_edits(entries, initial, {1: '#123456', 3: '#FFFF80'})
        self.assertEqual(result, {1: '#123456', 3: '#123456'})
        with self.assertRaises(ValueError):
            ns.resolve_color_edits(entries, initial, {1: '#123456', 3: '#654321'})

    def test_legacy_workbook_and_new_color_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            path = ns.name_path(d)
            wb = openpyxl.Workbook()
            wb.active.append(ns.NAME_HEADERS[:-1])
            wb.active.append(['Surface', 'BrightArea', 'Bright area', 'Y', 'keep note'])
            wb.save(path)
            wb.close()
            rows = ns.load(path)
            self.assertEqual(rows[0]['색상코드'], '')
            self.assertTrue(ns.upsert(rows, 'Surface', 'BrightArea', color='ffaa00'))
            ns.save(path, rows)
            restored = ns.load(path)
            self.assertEqual(restored[0]['비고'], 'keep note')
            self.assertEqual(restored[0]['사용'], 'Y')
            lookup = ns.make_color_lookup(restored)
            self.assertEqual(lookup('Surface', 'BrightArea'), '#FFAA00')
            self.assertEqual(lookup('Surface', 'Bright area'), '#FFAA00')
            self.assertFalse(ns.upsert(restored, 'Surface', 'BrightArea', color='#FFAA00'))

    def test_color_only_save_preserves_name_use_and_notes(self):
        with tempfile.TemporaryDirectory() as d:
            path = ns.name_path(d)
            rows = [{'Alg': 'Surface', '원본항목': 'BrightArea', '장비화면이름': 'My name', '사용': 'Y', '비고': 'memo'}]
            ns.save(path, rows)
            selection = [{'alg': 'Surface', 'ext': {'key': 'BrightArea'}, 'color': '#123456'}]
            with patch.object(locking, 'VERIFY_DELAY_SEC', 0):
                n, saved = ns.save_selected(path, selection, 'test', locking.file_stamp(path))
                self.assertEqual(n, 1)
                self.assertEqual(saved[0]['사용'], 'Y')
                self.assertEqual(saved[0]['장비화면이름'], 'My name')
                self.assertEqual(saved[0]['비고'], 'memo')
                before = Path(path).read_bytes()
                n, _ = ns.save_selected(path, selection, 'test')
                self.assertEqual(n, 0)
                self.assertEqual(Path(path).read_bytes(), before)

    def test_conflict_and_stale_snapshot_do_not_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            path = ns.name_path(d)
            ns.create_blank(path)
            before = Path(path).read_bytes()
            selection = [{'alg': 'Surface', 'ext': {'key': 'BrightArea'}, 'color': '#123456'}]
            with patch.object(locking, 'VERIFY_DELAY_SEC', 0):
                with self.assertRaises(ValueError):
                    ns.save_selected(path, selection, 'test', (0, 0))
                with patch.object(locking, 'conflict_copies', return_value=['conflict.xlsx']):
                    with self.assertRaises(ValueError):
                        ns.save_selected(path, selection, 'test')
            self.assertEqual(Path(path).read_bytes(), before)

    def test_validation_and_auto_color(self):
        for invalid in ('#12345', 'red', '#FFZZ00', '=1+1'):
            with self.assertRaises(ValueError):
                ns.normalize_color(invalid)
        self.assertEqual(ns.normalize_color(''), '')
        self.assertEqual(ns.default_color('Surface', 'Min Defect Area - Bright'), '#FFFF80')
        self.assertEqual(ns.default_color('GenesisV12', 'Adaptive Dark Sigma'), '#9080FF')
        self.assertEqual(ns.contrast_text('#FFFF80'), '#202020')
        self.assertEqual(ns.contrast_text('#111111'), '#FFFFFF')

    def test_view_resolves_raw_key_for_next_form(self):
        self.assertEqual(ns.resolve_original([], 'Surface', 'Min Defect Width - Bright'), 'BrightDiameter')
        rows = [{'Alg': 'Surface', '원본항목': 'a', '장비화면이름': 'same'},
                {'Alg': 'Surface', '원본항목': 'b', '장비화면이름': 'same'}]
        with self.assertRaises(ValueError):
            ns.resolve_original(rows, 'Surface', 'same')

    def test_note_editor_tracks_cell_after_scroll_not_click(self):
        source = Path(__file__).resolve().parents[1] / 'param_manager/equip_app.py'
        tree = ast.parse(source.read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'EquipApp')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_edit_note_cell')
        tk = Mock()
        top = tk.Toplevel.return_value
        top.winfo_screenwidth.return_value = 1920
        top.winfo_screenheight.return_value = 1080
        ns_ = {'tk': tk, 'engine': engine}
        exec(compile(ast.Module(body=[method], type_ignores=[]), '<method>', 'exec'), ns_)
        mt = Mock(col_positions=[0, 24, 314, 426, 606], row_positions=[0, 28, 56, 84])
        mt.winfo_rootx.return_value = 100
        mt.winfo_rooty.return_value = 200
        mt.canvasx.return_value = 0
        mt.canvasy.return_value = 28
        app = SimpleNamespace(fonts={'base': ('Arial', 10)})
        ns_['_edit_note_cell'](app, SimpleNamespace(MT=mt), 2, 3,
                              engine.ParamRow({'비고': 'note'}), SimpleNamespace(x_root=999, y_root=999))
        top.wm_geometry.assert_called_once_with('180x28+526+228')


if __name__ == '__main__':
    unittest.main()
