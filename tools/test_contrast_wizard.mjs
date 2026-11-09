// AOI_Contrast_Wizard.html 자동 시험(Para #50). 폴더 고르기 창은 자동화할 수 없어 window.__cw.addEntries 로 합성 파일을 넣는다.
// 실행: PARA_TEST_NODE_MODULES=<playwright 가 있는 node_modules> node tools/test_contrast_wizard.mjs
import {createRequire} from 'node:module';
import {execFileSync} from 'node:child_process';
import {resolve,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url);
const {chromium}=require(require.resolve('playwright',{paths:[process.env.PARA_TEST_NODE_MODULES||process.cwd(),'/opt/node-tools/node_modules']}));
const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const fixture=execFileSync('python3',[resolve(root,'tools/contrast_wizard_fixture.py')],{encoding:'utf-8',maxBuffer:1<<26});
const browser=await chromium.launch();
const page=await browser.newPage({viewport:{width:1400,height:1000}});
const errors=[],requests=[];page.on('pageerror',e=>errors.push(String(e)));
page.on('request',r=>{if(!r.url().startsWith('file:')&&!r.url().startsWith('blob:')&&!r.url().startsWith('data:'))requests.push(r.url())});
await page.goto('file://'+resolve(root,'AOI_Contrast_Wizard.html'));
assert.match(await page.locator('header .lim').innerText(),/간단 버전: Reference 이미지 없음, 좌표 모델 보정 필요 가능/);
// 순수 함수
const fn=await page.evaluate(()=>{const c=window.__cw;
  const die=c.dieOf(200498,279473,{pitchX:37249,pitchY:44905.8,cols:10,rows:9,offX:0,offY:0});
  const m=c.matchSets([{X:0,Y:0},{X:1,Y:0},{X:50,Y:50}],[{X:0.5,Y:0},{X:100,Y:100}],2);
  const t=c.parseTransform('Scan_X=2 0 10\nScan_Y=0 2 20\n');
  return {die:[die.col,die.row,Math.round(die.dx),Math.round(die.dy),die.valid],
    match:[m.keep.length,m.gone.length,m.added.length,m.keep[0].a.X],
    area:+(82*0.7708**2).toFixed(2),inv:t.inv,off:t.off,
    colors:c.parseColors('[a.jpg]\nFaultX=1\nFaultY=2\nDefectIndex=7\n[s]\nImageName=b.jpg\nIndex=3\n').map(x=>[x.file,x.index,x.x]),
    frames:c.parseFrames('Version=1\nA.t.2.jpeg;5;6\nbad\n'),
    count:c.surfaceCount('Total Surface defects = 123'),
    gl:c.measureGL({width:10,height:10,data:Uint8ClampedArray.from({length:400},(_,k)=>{const p=k>>2,x=p%10,y=(p/10)|0;return k%4===3?255:(x>=4&&x<6&&y>=4&&y<6?200:100)})},5,5,2,2,2)}});
assert.deepEqual(fn.die,[3,1,14253,10038,true]);
assert.deepEqual(fn.match,[1,2,1,0]);   // 1:1 — (0,0) 이 (0.5,0) 과 짝, (1,0) 은 중복 매칭 안 됨
assert.equal(fn.area,48.72);
assert.deepEqual(fn.inv.flat().map(v=>v+0),[0.5,0,0,0.5]);assert.deepEqual(fn.off,[10,20]);
assert.deepEqual(fn.colors,[['a.jpg',7,1],['b.jpg',3,null]]);
assert.deepEqual(fn.frames,[{file:'A.t.2.jpeg',x:5,y:6,recipe:2}]);
assert.equal(fn.count,123);
assert.equal(fn.gl.mean,200);assert.equal(fn.gl.ring,100);assert.equal(fn.gl.delta,100);
// 폴더 등록
await page.evaluate(fx=>{const f=JSON.parse(fx);return window.__cw.addEntries(Object.entries(f).map(([p,b])=>({path:p,file:new File([Uint8Array.from(atob(b),c=>c.charCodeAt(0))],p.split('/').pop())})))},fixture);
const rows=await page.locator('#scanTbl tbody tr').allInnerTexts();
assert.equal(rows.length,3,rows.join('\n'));
const msgs=await page.locator('#loadMsg .msg').allInnerTexts();
assert.ok(msgs.some(m=>/bad.*잘못된 Record Size: 150 byte/.test(m)),msgs.join('\n'));
const st=await page.evaluate(()=>window.__cw.state.scans.map(s=>({n:s.name,c:s.contrast,d:s.defects.length,img:s.images,w:s.warns,e:s.errors,t:s.transforms.size,p:!!s.product})));
const a=st.find(s=>s.n==='Lot/CA20'),b=st.find(s=>s.n==='Lot/CA27');
assert.equal(a.c,20);assert.equal(b.c,27);assert.equal(a.d,4);assert.equal(b.d,3);assert.equal(a.img,4);assert.equal(a.t,1);assert.ok(a.p);
assert.ok(b.w.some(w=>/Surface defect 수 5 ≠ 파싱 3/.test(w)),b.w.join('|'));
assert.ok(!a.w.some(w=>/Surface defect/.test(w)));
// 잘못된 스캔 삭제 → 비교
await page.evaluate(()=>{const s=window.__cw.state;s.scans=s.scans.filter(x=>!x.errors.length)});
await page.locator('nav button[data-step="2"]').click();
await page.locator('#tol').fill('2');
await page.locator('#runBtn').click();
await page.locator('#step3.on').waitFor();
const kp=await page.locator('#kpis .kpi b').allInnerTexts();
assert.deepEqual(kp,['4','3','2','2','1','25.0%']);
assert.equal(await page.locator('#allTbl tbody tr').count(),2);
assert.deepEqual(await page.locator('#allTbl tbody tr').nth(1).locator('td').allInnerTexts(),['CA27','27','','3','2','2','2','1','50.0%']);
// 표: Die · Area · Contrast
const t=await page.locator('#detTbl tbody tr').evaluateAll(trs=>trs.map(tr=>[...tr.cells].map(c=>c.innerText).join('|')));
const r1=t.find(x=>/\|1\|200498\.0/.test(x));assert.ok(r1,t.join('\n'));assert.match(r1,/\(3, 1\)/);assert.match(r1,/48\.72/);assert.match(r1,/34\.45/);
// CSV
const csv=await page.evaluate(()=>window.__cw.csvText());
assert.ok(csv.startsWith('﻿상태,ID'));
assert.match(csv,/소거,3,103,5000\.00,5000\.00.*C2\.c\.1\.jpeg,Index 3 \(id\),,,,좌표 변환 보정 필요/);
assert.match(csv,/소거,4,104,.*,,연결 실패,/);
assert.match(csv,/신규,9,109,.*,,연결 실패,/);
assert.match(csv,/유지,2,102,1100\.00,200\.00.*C1\.c\.1\.jpeg,좌표\(0\.0 µm\),F1\.t\.1\.jpeg,1100\.0,200\.0,transform/);
// 지도 hover → 툴팁 + 그림
await page.locator('#map').hover({position:{x:5,y:5}});
// 리뷰: 소거 2개, 키 이동, Gray crop / 범위 밖 문구
await page.locator('nav button[data-step="4"]').click();
await page.locator('#rvCount').filter({hasText:'소거 Defect 2개'}).waitFor();
const first=await page.locator('#rvList .it.sel').innerText();
await page.keyboard.press('j');
const second=await page.locator('#rvList .it.sel').innerText();
assert.notEqual(first,second);
await page.keyboard.press('k');assert.equal(await page.locator('#rvList .it.sel').innerText(),first);
// id 3 = 범위 밖 → 문구
const k3=await page.evaluate(()=>window.__cw.state.rvList.findIndex(r=>r.d.id===3));
for(let i=0;i<k3;i++)await page.keyboard.press('ArrowDown');
await page.locator('#rvGray .ph').filter({hasText:'좌표 변환 보정 필요'}).waitFor();
await page.locator('#rvColor img').waitFor();
// 유지 defect 의 Gray crop 은 캔버스로 그려진다
const crop=await page.evaluate(async()=>{const S=window.__cw.state;S.rvList=S.rows.filter(r=>r.d.id===2&&r.st==='keep');S.rv=0;window.__cw.go(4);
  await new Promise(r=>setTimeout(r,400));return {c:!!document.querySelector('#rvGray canvas'),gl:S.rvList[0].d.gl}});
assert.ok(crop.c);assert.ok(crop.gl&&crop.gl.n>0);
await page.keyboard.press('o');assert.match(await page.locator('#modelSt').innerText(),/미확정 \(맞음 1\/10/);
// Enter = 새 창
const [pop]=await Promise.all([page.waitForEvent('popup'),page.keyboard.press('Enter')]);
await pop.waitForFunction(()=>document.querySelector('canvas'));
assert.match(await pop.locator('body').innerText(),/ID 2/);
assert.deepEqual(errors,[]);assert.deepEqual(requests,[]);
await browser.close();
console.log('test_contrast_wizard: passed');
