import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from param_manager import wph


class SettingsTests(unittest.TestCase):
    def test_last_run_replaces_old_targets_and_queries(self):
        cfg = {'wph_report_paths': {'A': 'folderA', 'B': 'folderB'},
               'wph_prefixes': {'A': 'ancient', 'B': 'old'}}
        self.assertEqual(wph.last_investigation(cfg), {})
        wph.remember_investigation(cfg, [('A', 'folderA', 'first', None)], 25)
        self.assertEqual(wph.last_investigation(cfg), {'A': 'first'})
        wph.remember_investigation(cfg, [('B', 'folderB', '', None)], 13)
        self.assertEqual(wph.last_investigation(cfg), {'B': ''})
        self.assertEqual(cfg['wph_prefixes'], {'B': ''})
        self.assertEqual(cfg['wph_valid_wafers'], 13)
        self.assertEqual(cfg['wph_report_paths'], {'A': 'folderA', 'B': 'folderB'})
        self.assertEqual(wph.last_investigation({'wph_last_investigation': []}), {})

if __name__ == '__main__':
    unittest.main()
