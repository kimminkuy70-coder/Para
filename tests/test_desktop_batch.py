"""Synthetic local fixtures, no equipment or production config access."""
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from param_manager import batchreport_service as service, batchreport_store as store
from param_manager.desktop_batch import DesktopBatch, options
from param_manager.desktop_ipc import Session
from test_batchreport import report, html_report


class DesktopBatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / 'equipment'
        self.source.mkdir()
        self.root = self.base / 'local'
        self.config = self.base / 'config.json'
        self.cfg = {'wph_report_paths': {'AOI-01': str(self.source)}, 'local_dir': str(self.root),
                    'unrelated': 'preserve', 'batch_last': {'targets': [], 'options': {}}}
        self.config.write_text(json.dumps(self.cfg), encoding='utf-8')
        self.adapter = DesktopBatch(self.config)
        self.params = {'targets': [{'machine': 'AOI-01', 'query': '', 'start': '', 'end': ''}],
                       'options': {'metrics': ['M01', 'M03', 'M10'], 'valid_wafers': 1}}
        self.rep = self.source / 'BatchReport_demo.htm'
        self.rep.write_text(html_report(report()), encoding='utf-8')

    def test_configuration_and_path_allowlist(self):
        self.assertEqual(self.adapter.describe()['machines'][0]['id'], 'AOI-01')
        for item in ({'machine':'AOI-02'}, {'machine':'AOI-01','folder':'/etc'}, {'machine':'../secret'}):
            with self.assertRaises(ValueError):
                self.adapter.prepare(dict(self.params, targets=[item]))

    def test_reports_listing_and_names_selection(self):
        out = self.adapter.reports({'machine': 'AOI-01', 'query': '', 'start': '', 'end': ''})
        self.assertIn('BatchReport_demo.htm', out['names'])
        self.assertEqual(out['total'], len(out['names']))
        with self.assertRaises(ValueError):
            self.adapter.reports({'machine': 'AOI-02'})
        _root, targets, _opts = self.adapter.prepare(
            dict(self.params, targets=[{'machine': 'AOI-01', 'names': ['BatchReport_demo.htm']}]))
        self.assertEqual(targets[0]['names'], ['BatchReport_demo.htm'])
        with self.assertRaises(ValueError):
            self.adapter.prepare(dict(self.params, targets=[{'machine': 'AOI-01', 'names': [123]}]))

    def test_auto_state_and_run_record(self):
        from datetime import datetime
        self.assertEqual(self.adapter.describe()['auto']['enabled'], False)
        cfg = dict(self.cfg, batch_auto=True)
        self.config.write_text(json.dumps(cfg), encoding='utf-8')
        self.assertTrue(self.adapter.auto_state()['due'])          # never ran
        self.adapter.record_run(True)
        state = json.loads(self.config.read_text(encoding='utf-8'))
        self.assertEqual(state['unrelated'], 'preserve')
        datetime.strptime(state['batch_schedule']['last_run'], '%Y-%m-%d %H:%M:%S')   # watcher format, no 'T'
        self.assertFalse(self.adapter.auto_state()['due'])         # ran today
        self.adapter.record_run(False, error='조사 실패')
        self.assertEqual(json.loads(self.config.read_text(encoding='utf-8'))['batch_schedule']['fail_count'], 1)

    def test_options_and_dates(self):
        for value in ({'metrics':[]}, {'yield_drop':float('nan')}, {'valid_wafers':True}, {'min_baseline':1}, {'by_recipe':1}):
            with self.assertRaises(ValueError): options(value)
        # Retired metric keys saved by older versions are dropped, not rejected.
        self.assertEqual(options({'metrics':['M01','M07','M03','M01']})['metrics'], ['M01','M03'])
        with self.assertRaises(ValueError): options({'metrics':['M07']})
        cfg = dict(self.cfg, batch_last={'targets': [], 'options': {'metrics': ['M01', 'M07']}})
        self.config.write_text(json.dumps(cfg), encoding='utf-8')
        self.assertEqual(self.adapter.describe()['last']['options']['metrics'], ['M01'])
        with self.assertRaises(ValueError):
            self.adapter.prepare(dict(self.params, targets=[{'machine':'AOI-01','start':'2026-09-21','end':'2026-09-01'}]))

    def test_pipeline_output_and_latest_only_legacy_untouched(self):
        before = self.config.read_bytes(), self.rep.read_bytes()
        output = self.adapter.run(self.adapter.prepare(self.params), None, lambda:False)
        self.assertEqual(output['result']['summary']['Batch(리포트) 수'], 1)
        self.assertTrue(Path(output['xlsx']).is_file())
        self.assertTrue(Path(output['html']).is_file())
        self.params['targets'][0]['query'] = 'missing'
        self.adapter.run(self.adapter.prepare(self.params), None, lambda:False)
        self.assertEqual(self.adapter.describe()['last']['targets'][0]['query'], 'missing')
        self.assertEqual(before, (self.config.read_bytes(), self.rep.read_bytes()))

    def test_cancel_before_collect_and_before_publish(self):
        root, targets, opts = self.adapter.prepare(self.params)
        with self.assertRaises(store.Cancelled):
            service.run(root, targets, opts, cancel=lambda:True)
        cancelled = False
        original = service.output.write_excel
        def write_then_cancel(*args, **kwargs):
            nonlocal cancelled
            original(*args, **kwargs)
            cancelled = True
        with patch.object(service.output, 'write_excel', write_then_cancel):
            with self.assertRaises(store.Cancelled):
                service.run(root, targets, opts, cancel=lambda:cancelled)
        self.assertFalse(list((root/'배치분석').glob('조사_*')))
        self.assertFalse(list((root/'배치분석').glob('.진행중_*')))

    def test_reject_symlink_output_and_report_escape(self):
        target = self.base / 'outside'
        target.mkdir()
        self.root.symlink_to(target, target_is_directory=True)
        with self.assertRaises(ValueError): self.adapter.describe()
        self.root.unlink()
        outside = target/'BatchReport_secret.htm'
        outside.write_bytes(self.rep.read_bytes())
        self.rep.unlink()
        self.rep.symlink_to(outside)
        result = store.collect(self.root, [{'machine':'AOI-01','folder':str(self.source)}], host_gap=0)
        self.assertEqual(len(result['errors']), 1)
        self.assertEqual(result['records'], [])

    def test_ipc_investigation_and_page(self):
        output = io.BytesIO()
        session = Session(output)
        session.batch = self.adapter
        self.addCleanup(session.close)
        session.handle(dict(version=1,id=1,method='investigate',params=self.params))
        session.worker.join(10)
        self.assertFalse(session.worker.is_alive())
        events = [json.loads(line) for line in output.getvalue().splitlines()]
        final = events[-1]
        self.assertEqual(final['event'], 'completed')
        self.assertEqual(final['summary']['Batch(리포트) 수'], 1)
        session.handle(dict(version=1,id=2,method='table_page',params={'job':1,'table':0}))
        self.assertEqual(json.loads(output.getvalue().splitlines()[-1])['total'], 3)
        session.handle(dict(version=1,id=3,method='release',params={'job':1}))
        self.assertIsNone(session.job)


if __name__ == '__main__': unittest.main()
