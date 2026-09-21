import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from param_manager import commonality as cm, collate, workdirs, desktop_ipc
from param_manager.desktop_commonality import DesktopCommonality


class CommonalityTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        cfg = self.root / 'config.json'
        cfg.write_text(json.dumps({'local_dir': str(self.root/'local')}))
        run = workdirs.commonality_run_dir(str(self.root/'local/Commonality'), 'AOI-01', 'sample')
        self.file = workdirs.commonality_result_path(run, 'R', 'AOI-01', 'sample')
        records = [dict(PI='R', Recipe='V', Zone='Z', Alg='A', Parameter=f'P{i}',
                        L1='1', L2='2', L3='1') for i in range(25)]
        cm.write_lot_result(self.file, 'R', 'AOI-01', collate.CollateRecipe(recipe='R', records=records),
                            ['L1', 'L2', 'L3'], fail_labels=['L2'], low_labels=['L3'])
        self.adapter = DesktopCommonality(cfg)
        self.catalog = self.adapter.catalog()

    def compare(self):
        return self.adapter.compare({'catalog': self.catalog['catalog'], 'files': ['0']})

    def test_comparison_pages_and_export(self):
        result = self.compare()
        self.assertEqual(result['changed'], 25)
        page = self.adapter.page({'snapshot': result['snapshot'], 'limit': 2, 'changed_only': True})
        self.assertEqual(len(page['headers']), 15)
        self.assertEqual(len(page['rows']), 2)
        self.assertTrue(page['rows'][1]['fail'])
        self.assertEqual(len(page['rows'][1]['outliers']), 12)
        self.assertTrue(self.adapter.page({'snapshot': result['snapshot'], 'offset': 2})['rows'][0]['low_match'])
        self.assertEqual(self.adapter.page({'snapshot': result['snapshot'], 'query': 'absent'})['parameter_total'], 0)
        path = Path(self.adapter.export({'snapshot': result['snapshot'], 'changed_only': True})['path'])
        self.assertTrue(path.is_file())
        self.assertTrue(path.is_relative_to(self.root/'local'))

    def test_reject_paths_duplicates_stale_input(self):
        for ids in (['../outside'], ['0', '0'], [], [True]):
            with self.assertRaises(ValueError):
                self.adapter.compare({'catalog': self.catalog['catalog'], 'files': ids})
        with open(self.file, 'ab') as stream:
            stream.write(b'changed')
        with self.assertRaises(ValueError):
            self.compare()

    def test_page_bounds_snapshot_and_symlink(self):
        result = self.compare()
        for values in ({'limit': 101}, {'offset': -1}, {'column': True}, {'snapshot': 'stale'}):
            with self.assertRaises(ValueError):
                self.adapter.page({'snapshot': result['snapshot'], **values})
        linked = self.root/'local/linked'
        try:
            linked.symlink_to(self.file)
        except OSError:
            self.skipTest('Symlinks unavailable')
        with self.assertRaises(ValueError):
            self.adapter.safe(linked)

    def test_export_formula_text(self):
        result = self.compare()
        self.adapter.result['rows'][0]['S/M'] = '=1+1'
        path = self.adapter.export({'snapshot': result['snapshot'], 'changed_only': False})['path']
        wb = openpyxl.load_workbook(path)
        try:
            self.assertEqual(wb.active['A2'].value, '=1+1')
            self.assertEqual(wb.active['A2'].data_type, 's')
        finally:
            wb.close()

    def test_worker_blocks_parallel_jobs_and_waits_at_close(self):
        output = io.BytesIO()
        session = desktop_ipc.Session(output)
        started, proceed = threading.Event(), threading.Event()
        def delayed(params):
            started.set()
            proceed.wait(3)
            return {'snapshot': 'test'}
        with patch.object(session.commonality, 'compare', side_effect=delayed):
            session.handle(dict(version=1, id=1, method='commonality_compare', params={'catalog':'x','files':['0']}))
            self.assertTrue(started.wait(1))
            session.handle(dict(version=1, id=2, method='analyze', params={'records': []}))
            proceed.set()
            session.close()
        events = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertTrue(any(e['id']==2 and e['event']=='error' for e in events))
        self.assertTrue(any(e['id']==1 and e['event']=='completed' for e in events))
        self.assertFalse(session.worker.is_alive())


if __name__ == '__main__':
    unittest.main()
