"""Para #83: Defect 분석 필터 = 실제 값 그대로 비교(반올림 안 함), 목록 = 실제 값 표기.

종전에는 Contrast · Area 를 소수 2자리, Width · Length 를 1자리로 반올림해서 비교 · 표기해
6.4749 처럼 소수 셋째 자리 이상의 경계로는 거를 수 없었다.
HTML(AOI_Contrast_Wizard_rev6.html)의 fv · exv · inR · fltPass 만 잘라 node 로 돌린다(node 가 없으면 건너뜀).
"""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTMLS = [ROOT / "frontend" / p / "defect" / "AOI_Contrast_Wizard_rev6.html" for p in ("public", "dist")]

CASES = r"""
const f={c0:null,c1:null,a0:null,a1:null,w0:null,w1:null,l0:null,l1:null};
const P=(o,c,a,w,l)=>fltPass({...f,...o},c,a,w,l);
const out={
  c_le:P({c1:6.4749},6.4749,1,1,1), c_gt:P({c1:6.4749},6.47491,1,1,1), c_gt2:P({c1:6.4749},6.475,1,1,1),
  c_ge:P({c0:6.4749},6.4749,1,1,1), c_lt:P({c0:6.4749},6.4748,1,1,1),
  a_noise:P({a0:1.23,a1:1.23},1,0.1*12.3,1,1)&&P({c0:1.23,c1:1.23},0.1*12.3,1,1,1),
  w_3:P({w0:2.345},1,1,2.3449,1), w_3b:P({w0:2.345},1,1,2.345,1),
  l_3:P({l1:7.001},1,1,1,7.0011), nan:P({c0:1},NaN,1,1,1), none:P({},NaN,NaN,NaN,NaN),
  fv:[fv(6.4749),fv(0.1*12.3),fv(30),fv(null),fv(NaN),fv(12.3456789)],
};
console.log(JSON.stringify(out));
"""


def cut(t, a, b):
    i = t.index(a)
    return t[i:t.index(b, i)]


@unittest.skipUnless(shutil.which("node"), "node 없음")
class ExactFilter(unittest.TestCase):
    def run_js(self, html):
        t = html.read_text(encoding="utf-8")
        code = (cut(t, "const exv=", "\n") + "\n" + cut(t, "const inR=", "/** 필터 줄 입력"))
        r = subprocess.run(["node", "-e", code + CASES], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_filter_exact(self):
        for html in HTMLS:
            with self.subTest(html=html.parent.parent.name):
                o = self.run_js(html)
                self.assertTrue(o["c_le"])        # 최대 6.4749 → 6.4749 들어옴
                self.assertFalse(o["c_gt"])       # 6.47491 빠짐
                self.assertFalse(o["c_gt2"])      # 6.475 빠짐(종전 반올림이면 6.47 → 들어왔음)
                self.assertTrue(o["c_ge"])
                self.assertFalse(o["c_lt"])
                self.assertTrue(o["a_noise"])     # 계산 잡음(1.2300000000000002)은 같은 값
                self.assertFalse(o["w_3"])        # Width 소수 셋째 자리도 정확히(종전 1자리 반올림)
                self.assertTrue(o["w_3b"])
                self.assertFalse(o["l_3"])
                self.assertFalse(o["nan"])        # 값이 없으면 범위를 건 필터에서 빠짐
                self.assertTrue(o["none"])
                self.assertEqual(o["fv"], ["6.4749", "1.23", "30", "", "", "12.3456789"])

    def test_list_shows_actual_values(self):
        """목록 · 정보 · CSV 의 Contrast · Area · Width · Length = fv(실제 값) — 반올림 함수(f1 · f2)로 쓰지 않는다."""
        for html in HTMLS:
            with self.subTest(html=html.parent.parent.name):
                t = html.read_text(encoding="utf-8")
                bad = re.findall(r"f[12]\((?:x\.(?:area|width|length|contrast|cmpContrast)|d\.Contrast|C\.(?:c|w|l)\[i\]|C\.area\[i\]\*px2)\)", t)
                self.assertEqual(bad, [])
                self.assertNotIn("Math.round(v*m)/m", t)

    def test_public_and_dist_same(self):
        self.assertEqual(HTMLS[0].read_bytes(), HTMLS[1].read_bytes())


if __name__ == "__main__":
    unittest.main()
