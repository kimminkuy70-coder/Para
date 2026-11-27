"""Defect 분석 = 프로그램 화면 안(Shadow DOM, frontend/src/DefectHost.ts) — 소유자 2026-11-25 "창이 분리되어 있어서 로딩 중 아래가 잘리는 등 버그,
프로그램에 제대로 이식". 확인: iframe 없음 · 빌드가 만든 함수 파일(dist/defect/*.run.js)이 HTML · para-skin.js 스크립트와 글자까지 같음 ·
화면 보안 정책은 그대로(script-src 'self', 문자열 실행 없음 — img-src 에 blob: 만 더함: Color 사진) · 로딩창 = 보이는 부분에 고정."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FE = ROOT / 'frontend'
PUB, DIST = FE / 'public/defect', FE / 'dist/defect'


def run_js(name, src, params):
    return (f'/* 자동 생성(frontend/vite.config.ts defectRun) — 원본 = frontend/public/defect/{name}. 이 파일은 고치지 말 것 */\n'
            f'(window.__dfxRun=window.__dfxRun||{{}})["{name}"]=function({params}){{\n{src}\n}};\n')


class DefectHostTest(unittest.TestCase):
    def setUp(self):
        self.vite = (FE / 'vite.config.ts').read_text(encoding='utf-8')
        self.host = (FE / 'src/DefectHost.ts').read_text(encoding='utf-8')
        self.params = re.search(r"RUN_PARAMS = '([^']+)'", self.vite).group(1)

    def test_no_iframe(self):
        tsx = (FE / 'src/DefectAnalysis.tsx').read_text(encoding='utf-8')
        self.assertNotIn('<iframe', tsx)
        self.assertIn("mountDefect(host, mode, sessionToken()", tsx)
        self.assertNotIn('new Function', self.host)
        self.assertNotIn('eval(', self.host)

    def test_run_files_match_sources(self):
        html = (PUB / 'AOI_Contrast_Wizard_rev6.html').read_text(encoding='utf-8')
        script = '\n;\n'.join(re.findall(r'<script>([\s\S]*?)</script>', html))
        self.assertEqual((DIST / 'AOI_Contrast_Wizard_rev6.run.js').read_text(encoding='utf-8'),
                         run_js('AOI_Contrast_Wizard_rev6.html', script, self.params))
        self.assertEqual((DIST / 'para-skin.run.js').read_text(encoding='utf-8'),
                         run_js('para-skin.js', (PUB / 'para-skin.js').read_text(encoding='utf-8'), self.params))
        # DefectHost 가 같은 차례로 넘긴다
        self.assertEqual(self.params, 'document,window,location,localStorage,addEventListener,removeEventListener,self,globalThis,scrollTo,paraHost')
        self.assertIn('f.call(win, doc, win, loc, ls, winAdd, winRemove, win, win, noScroll, paraHost)', self.host)
        for n in ('AOI_Contrast_Wizard_rev6.html', 'para-skin.js', 'para-skin.css'):   # HTML · 겉모습 파일은 종전대로 dist 에도
            self.assertEqual((DIST / n).read_bytes(), (PUB / n).read_bytes(), n)

    def test_csp_unchanged_except_blob_images(self):
        for p in (FE / 'index.html', FE / 'dist/index.html'):
            csp = re.search(r'Content-Security-Policy" content="([^"]+)"', p.read_text(encoding='utf-8')).group(1)
            d = dict(x.strip().split(' ', 1) for x in csp.split(';') if x.strip())
            self.assertEqual(d['script-src'], "'self'", p)
            self.assertEqual(d['img-src'], "'self' data: blob:", p)
            self.assertEqual(d['connect-src'], "'self'", p)
            self.assertNotIn('unsafe-eval', csp)

    def test_overlays_cover_whole_screen(self):
        css = (PUB / 'para-skin.css').read_text(encoding='utf-8')
        # 소유자 2026-11-27: 로딩창 · 같은 창 칸 = 프로그램 화면 전체(머리 · 탭까지 어둡게)
        self.assertIn('body.pskin .busy{position:fixed;inset:0;width:auto;height:auto;z-index:2147481000;', css)
        self.assertIn('body.pskin .ovw{position:fixed;inset:0;width:auto;height:auto;z-index:2147481000}', css)
        self.assertNotIn('var(--vh', css)
        for v in ("'--vt'", "'--vh'", "'--vl'", "'--vw'"):
            self.assertIn(f"s.setProperty({v}", self.host)
        skin = (PUB / 'para-skin.js').read_text(encoding='utf-8')
        self.assertIn("const host = typeof paraHost === 'function' ? paraHost : null;", skin)
        self.assertIn('if (!host) {   // 화면 안(DefectHost)일 때는', skin)   # 프로그램 전체 focus 는 바꾸지 않음

    def test_css_scoping(self):
        sys.path.insert(0, str(ROOT))
        cases = {':root{--a:1}': ':host{--a:1}', ':root[data-theme="dark"] body.pskin{x:1}': ':host([data-theme="dark"]) .dfx-body.pskin{x:1}',
                 ':root:not([data-theme="dark"]) body.pskin{}': ':host(:not([data-theme="dark"])) .dfx-body.pskin{}',
                 'html,body{height:100%}': ':host,.dfx-body{height:100%}', 'tbody td{}': 'tbody td{}', 'body>.ovw{}': '.dfx-body>.ovw{}'}
        # DefectHost.scopeCss 의 정규식을 그대로 옮겨 확인(같은 식인지는 아래 글자 확인)
        rules = [(r':root((?:\[[^\]]*\]|:not\((?:[^()]|\([^()]*\))*\))+)', ':host(\\1)'), (r':root(?![\w-])', ':host'),
                 (r'(^|[\s,>+~{}(])html(?![\w-])', '\\1:host'), (r'(^|[\s,>+~{}(])body(?![\w-])', '\\1.dfx-body')]
        for a, want in cases.items():
            for pat, rep in rules:
                a = re.sub(pat, rep, a)
            self.assertEqual(a, want)
        for pat in (r":root((?:\[[^\]]*\]|:not\((?:[^()]|\([^()]*\))*\))+)/g, ':host($1)'", r":root(?![\w-])/g, ':host'",
                    r"(^|[\s,>+~{}(])html(?![\w-])/g, '$1:host'", r"(^|[\s,>+~{}(])body(?![\w-])/g, '$1.dfx-body'"):
            self.assertIn(pat, self.host)


if __name__ == '__main__':
    unittest.main()
