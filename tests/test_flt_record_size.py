"""Para #74: Surface.flt 레코드 크기를 152 로 고정하지 않고 Surface.flt.md 의 RecordSize 를 쓴다.

실제 사례: 25 Slot 의 Surface.flt 크기가 모두 136 의 배수(152 로는 나머지가 남음) → 종전에는 25 Slot 전부 '잘못된 Record Size' 로 빠졌다.
HTML(AOI_Contrast_Wizard_rev6.html)의 파서 부분(REC ~ parseFltCols)만 잘라 node 로 돌린다(node 가 없으면 건너뜀).
"""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTMLS = [ROOT / "frontend" / p / "defect" / "AOI_Contrast_Wizard_rev6.html" for p in ("public", "dist")]

SCRIPT = r"""
const out={};
const mk=(rec,n,fill)=>{const b=new ArrayBuffer(rec*n),dv=new DataView(b);for(let i=0;i<n;i++)fill(dv,i*rec,i);return b};
// 136 byte 레코드(md: Contrast 를 120 에) 3개
const md136={recordSize:136,fields:[{name:'x',type:'float64',offset:8},{name:'y',type:'float64',offset:16},{name:'Contrast',type:'float64',offset:120}]};
const b136=mk(136,3,(dv,o,i)=>{dv.setFloat64(o+8,100+i,true);dv.setFloat64(o+16,200+i,true);dv.setFloat64(o+120,30+i,true)});
const L=fltLayout(md136).lay,r=fltRec(md136,b136.byteLength),p=parseFlt(b136,L,r),c=parseFltCols(b136,L,r);
out.md136={rec:r,ok:p.ok,n:p.defects.length,x:p.defects.map(d=>d.x),c:p.defects.map(d=>d.Contrast),colsOk:c.ok,colsN:c.cols.n,colsC:[...c.cols.c]};
// md 없음 · 152 배수 → 152(종전과 같음)
const b152=mk(152,2,(dv,o,i)=>dv.setFloat64(o+136,40+i,true));
const r2=fltRec(null,b152.byteLength),p2=parseFlt(b152,null,r2);out.def={rec:r2,ok:p2.ok,c:p2.defects.map(d=>d.Contrast)};
// md 가 136 이라 해도 파일이 152 배수면 152
out.mdWrong=fltRec(md136,152*5);
// md 없음 · 136 배수(152 로 나머지) → 오류 글에 md 안내
const p3=parseFlt(b136,null,fltRec(null,b136.byteLength));out.noMd={ok:p3.ok,err:fltRecErr(p3,null)};
// 함수 기본값(rec 생략) = 152
out.legacy=parseFlt(b152).ok;
console.log(JSON.stringify(out));
"""


@unittest.skipUnless(shutil.which("node"), "node 없음")
class FltRecordSize(unittest.TestCase):
    def run_js(self, html):
        t = html.read_text(encoding="utf-8")
        a, b = t.index("const REC = 152;"), t.index("/** [section] key=value INI")
        r = subprocess.run(["node", "-e", t[a:b] + SCRIPT], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_record_size_from_md(self):
        for html in HTMLS:
            with self.subTest(html=html.parent.parent.name):
                o = self.run_js(html)
                self.assertEqual(o["md136"], {"rec": 136, "ok": True, "n": 3, "x": [100, 101, 102], "c": [30, 31, 32],
                                              "colsOk": True, "colsN": 3, "colsC": [30, 31, 32]})
                self.assertEqual(o["def"], {"rec": 152, "ok": True, "c": [40, 41]})
                self.assertEqual(o["mdWrong"], 152)
                self.assertFalse(o["noMd"]["ok"])
                self.assertIn("Surface.flt.md 없음", o["noMd"]["err"])
                self.assertIn("152 로 나누어떨어지지 않음", o["noMd"]["err"])
                self.assertTrue(o["legacy"])

    def test_public_and_dist_same(self):
        self.assertEqual(HTMLS[0].read_bytes(), HTMLS[1].read_bytes())


if __name__ == "__main__":
    unittest.main()
