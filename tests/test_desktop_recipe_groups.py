"""Recipe 값 확인(2026-09): Zone → Alg 제목 줄 접기/펼치기, 값 없는 호기 제외, 비교 호기 100개씩."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from param_manager import collate, workdirs
from param_manager.desktop_recipe import DesktopRecipe


class RecipeGroupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name); shared = root / 'shared'; shared.mkdir()
        self.machines = [f'AOI-{i:02}' for i in range(1, 121)]
        filled = self.machines[:110]                       # AOI-111..120: 값이 하나도 없음
        spec = [('Surface', 'Genesis', 3), ('Surface', 'EdgeUncert', 2), ('Bump', 'Genesis', 4)]
        rows = []
        for zone, alg, n in spec:
            for i in range(n):
                rows.append(dict(PI='PI2', Recipe='R1', Zone=zone, Alg=alg, Parameter=f'{zone}-{alg}-{i}', **{'비고': ''},
                                 **{m: ('823.799998247089' if m in filled else '') for m in self.machines}))
        collate.write_collation(workdirs.collate_path(str(shared), '20260929_010101'),
                                {'PI2': collate.CollateRecipe(recipe='PI2', records=rows)}, self.machines)
        cfg = root / 'c.json'; cfg.write_text(json.dumps({'save_dir': str(shared)}))
        self.adapter = DesktopRecipe(cfg); self.v = self.adapter.open()['version']

    def page(self, **kw):
        return self.adapter.page(dict(snapshot=self.v, selected_machine='AOI-01', group=True, **kw))

    def test_zone_and_alg_titles_toggle(self):
        p = self.page(limit=100)
        shape = [(r['kind'], r.get('title') or r['name']) for r in p['rows']]
        self.assertEqual(shape[:2], [('zone', 'Surface'), ('alg', 'Genesis')])
        self.assertEqual([t for k, t in shape if k != 'row'], ['Surface', 'Genesis', 'EdgeUncert', 'Bump', 'Genesis'])
        self.assertEqual((p['total'], p['row_total']), (9 + 5, 9))
        self.assertEqual(p['rows'][0]['count'], 5)
        # Zone 접기: 그 Zone 은 제목만 남는다.
        p = self.page(limit=100, collapsed=['z\x1fSurface'])
        self.assertEqual([(r['kind'], r.get('title')) for r in p['rows'][:3]], [('zone', 'Surface'), ('zone', 'Bump'), ('alg', 'Genesis')])
        self.assertTrue(p['rows'][0]['collapsed'])
        # Alg 하나만 접기(같은 이름 Genesis 라도 Zone 이 다르면 따로).
        p = self.page(limit=100, collapsed=['a\x1fSurface\x1fGenesis'])
        self.assertEqual(sum(1 for r in p['rows'] if r['kind'] == 'row'), 6)
        # 특정 Zone: Alg 제목만.
        p = self.page(limit=100, zone='Surface')
        self.assertEqual([r.get('title') for r in p['rows'] if r['kind'] != 'row'], ['Genesis', 'EdgeUncert'])
        self.assertIn('a\x1fSurface\x1fEdgeUncert', p['group_keys'])
        # 그룹 없이(구 요청)는 예전과 같은 평면 목록.
        flat = self.adapter.page(dict(snapshot=self.v, selected_machine='AOI-01', limit=100))
        self.assertEqual(flat['total'], 9)

    def test_hundred_machines_per_page_and_hide_empty(self):
        p = self.page(limit=5, machine_limit=100)
        self.assertEqual((len(p['machines']), p['machine_total']), (100, 120))
        self.assertEqual(p['rows'][2]['value'], '823.799998247089')
        p = self.page(limit=5, machine_limit=100, hide_empty=True)
        self.assertEqual(p['machine_total'], 110)
        self.assertEqual(p['empty_machines'], self.machines[110:])
        self.assertNotIn('AOI-111', self.page(limit=5, machine_offset=100, machine_limit=100, hide_empty=True)['machines'])
        with self.assertRaises(ValueError):
            self.page(limit=5, machine_limit=101)
        with self.assertRaises(ValueError):
            self.page(limit=5, collapsed='z')


if __name__ == '__main__':
    unittest.main()
