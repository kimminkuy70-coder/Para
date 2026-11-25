"""서체 = Pretendard(소유자 2026-11-25 "그 글꼴 사용해") — 프로그램 안 파일(인터넷에서 받지 않음) · OFL 라이선스 동봉 · 못 읽으면 맑은 고딕."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FE = ROOT / 'frontend'


class FontTest(unittest.TestCase):
    def test_bundled_with_license(self):
        for base in (FE / 'public/fonts', FE / 'dist/fonts'):
            f = base / 'PretendardVariable.woff2'
            self.assertTrue(f.is_file(), f)
            self.assertEqual(f.read_bytes()[:4], b'wOF2')
            lic = (base / 'Pretendard-LICENSE.txt').read_text(encoding='utf-8')
            self.assertIn('SIL Open Font License, Version 1.1', lic)
        self.assertEqual((FE / 'public/fonts/PretendardVariable.woff2').read_bytes(), (FE / 'dist/fonts/PretendardVariable.woff2').read_bytes())

    def test_font_face_local_only(self):
        css = (FE / 'src/styles.css').read_text(encoding='utf-8')
        face = re.search(r'@font-face\{[^}]*\}', css).group(0)
        self.assertIn("url('/fonts/PretendardVariable.woff2')", face)
        self.assertNotIn('http', face)
        self.assertIn(":root{font-family:'Pretendard','Pretendard Variable','Malgun Gothic'", css)
        skin = (FE / 'public/defect/para-skin.css').read_text(encoding='utf-8')
        self.assertIn("font:14px/1.55 'Pretendard','Pretendard Variable','Malgun Gothic'", skin)
        idx = (FE / 'index.html').read_text(encoding='utf-8')
        self.assertNotIn('fonts.googleapis', idx)
        self.assertNotRegex(re.search(r'Content-Security-Policy" content="([^"]+)"', idx).group(1), r'font-src[^;]*http')

    def test_served_as_font(self):
        ws = (ROOT / 'param_manager/webserver.py').read_text(encoding='utf-8')
        self.assertIn('".woff2": "font/woff2"', ws)


if __name__ == '__main__':
    unittest.main()
