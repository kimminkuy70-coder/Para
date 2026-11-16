"""Para #75: Defect 분석(대규모) 5-1 의 Recipe 고르기 개수가 Lot · Slot · 분류 · 범위 필터를 따른다.

종전(#73)에는 등록한 전체 Defect 로 Recipe 별 개수를 세어, Lot 필터를 걸어도 괄호 안 수가 그대로였다.
HTML(AOI_Contrast_Wizard_rev6.html)의 readFlt ~ fltPass, rcp5, bigRcpFill, bigBuild 만 잘라 node 로 돌린다(node 가 없으면 건너뜀).
"""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTMLS = [ROOT / "frontend" / p / "defect" / "AOI_Contrast_Wizard_rev6.html" for p in ("public", "dist")]

STUB = r"""
const FLT_KEYS=[['c'],['a'],['w'],['l']];
const natCmp=(a,b)=>String(a).localeCompare(String(b),undefined,{numeric:true});
const esc=s=>String(s);
const S={};const opts=()=>({pix:1,coord:'wafer'});
const clsFirst=(s,i)=>s.k1[i],clsName=(s,i)=>s.k2[i];
const EL={};
const mkSel=v=>({value:v,innerHTML:'',querySelector:()=>null});
const flt={vals:{sort:'',rcp:''},querySelector(q){const m=/data-f="(\w+)"/.exec(q);if(!m)return null;const k=m[1];if(k==='rcp')return EL.rcp;
  return {get value(){return flt.vals[k]??''},set value(v){flt.vals[k]=v}}}};
EL.rcp={_v:'',innerHTML:'',get value(){return this._v},set value(v){this._v=v}};
EL.lot=mkSel('');EL.slot=mkSel('');
const $=q=>q==='#bigFlt'?flt:q==='#bigFlt [data-f="rcp"]'?EL.rcp:q==='#bigLot'?EL.lot:q==='#bigSlot'?EL.slot:null;
const mkScan=(lot,slot,rec,k1,c,rv)=>({lotPath:lot,slot,slotName:slot,errors:[],rv,k1,k2:k1,
  cols:{n:rec.length,rec:Uint8Array.from(rec),c:Float64Array.from(c),area:new Float64Array(rec.length).fill(1),w:new Float64Array(rec.length).fill(1),l:new Float64Array(rec.length).fill(1),
    x:new Float64Array(rec.length),y:new Float64Array(rec.length),ax:new Float64Array(rec.length),ay:new Float64Array(rec.length),id:new Int32Array(rec.length)}});
const scans=[mkScan('/L1','S1',[0,0,1],['A','B','A'],[10,20,30],{recipe:'PI'}),mkScan('/L2','S2',[0,1,1,2],['A','A','B','A'],[10,20,30,40],{recipe:'PI'})];
const BIG={scans,sort:'',clsOff1:new Set(),clsOff2:new Set(),lotOff:new Set()};
const bigSources=()=>BIG.scans;
const run=()=>{const V=bigBuild();bigRcpFill(V.rc);return {m:V.m,rc:Object.fromEntries([...V.rc].sort()),opts:EL.rcp.innerHTML}};
const out={};
out.all=run();
EL.lot.value='/L1';out.lot=run();EL.lot.value='';
BIG.lotOff.add('/L1');out.lotOff=run();BIG.lotOff.clear();
EL.slot.value='S2';out.slot=run();EL.slot.value='';
BIG.clsOff1.add('B');out.cls=run();BIG.clsOff1.clear();
flt.vals.c0='25';out.contrast=run();flt.vals.c0='';
EL.rcp.value='1';EL.lot.value='/L1';out.rcpLot=run();
EL.rcp.value='2';out.keep=run();
console.log(JSON.stringify(out));
"""


def cut(t, a, b):
    i = t.index(a)
    return t[i:t.index(b, i)]


@unittest.skipUnless(shutil.which("node"), "node 없음")
class RecipeCountFollowsFilter(unittest.TestCase):
    def run_js(self, html):
        t = html.read_text(encoding="utf-8")
        code = (cut(t, "function readFlt(", "/** 필터 줄 입력") + "\n"
                + cut(t, "const rcp5=", "\n") + "\n"
                + cut(t, "function bigRcpFill(", "/** 필터 → 정렬") + "\n"
                + cut(t, "function bigBuild(", "const bigAt="))
        r = subprocess.run(["node", "-e", STUB.replace("const out={};", code + "\nconst out={};", 1)],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_counts(self):
        for html in HTMLS:
            with self.subTest(html=html.parent.parent.name):
                o = self.run_js(html)
                self.assertEqual(o["all"]["rc"], {"0 (PI)": 3, "1": 3, "2": 1})
                self.assertEqual(o["all"]["m"], 7)
                self.assertIn("0 (PI) (3)", o["all"]["opts"])
                self.assertEqual(o["lot"]["rc"], {"0 (PI)": 2, "1": 1})            # Lot 필터
                self.assertIn("1 (1)", o["lot"]["opts"])
                self.assertNotIn("2 (", o["lot"]["opts"])
                self.assertEqual(o["lotOff"]["rc"], {"0 (PI)": 1, "1": 2, "2": 1})  # Lot 제외
                self.assertEqual(o["slot"]["rc"], {"0 (PI)": 1, "1": 2, "2": 1})    # Slot 필터
                self.assertEqual(o["cls"]["rc"], {"0 (PI)": 2, "1": 2, "2": 1})     # 분류 끄기
                self.assertEqual(o["contrast"]["rc"], {"1": 2, "2": 1})            # Contrast ≥ 25
                # Recipe 를 고르면 목록은 그 Recipe 만, 개수는 다른 필터 기준(다른 Recipe 로 바꿀 수 있게)
                self.assertEqual(o["rcpLot"]["m"], 1)
                self.assertEqual(o["rcpLot"]["rc"], {"0 (PI)": 2, "1": 1})
                # 고른 Recipe 가 필터로 0개가 되어도 칸에 남는다
                self.assertEqual(o["keep"]["m"], 0)
                self.assertIn("2 (0)", o["keep"]["opts"])

    def test_public_and_dist_same(self):
        self.assertEqual(HTMLS[0].read_bytes(), HTMLS[1].read_bytes())


if __name__ == "__main__":
    unittest.main()
