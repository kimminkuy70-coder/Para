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
// 쌍별 비교(리스트 2개 = 1쌍), 이름 표기(유지 · 소거 · 신규 없음)
assert.equal(await page.locator('#pairTbl tbody tr').count(),1);
assert.deepEqual(await page.locator('#pairTbl tbody tr').nth(0).locator('td').allInnerTexts(),['CA20 → CA27','4','3','2','2','1','50.0%','보기']);
assert.deepEqual(await page.locator('#kpis .kpi .muted:first-child').allInnerTexts(),['CA20 (전체)','CA27 (전체)','CA20 ∩ CA27','CA20 ∖ CA27','CA27 ∖ CA20','감소율']);
// 보기 6개(합집합 + 5가지) · 표 필터 · 완전한 Die
assert.deepEqual(await page.locator('#legend [data-view]').allInnerTexts(),['CA20 ∪ CA27','CA20 (전체)','CA27 (전체)','CA20 ∖ CA27','CA20 ∩ CA27','CA27 ∖ CA20']);
await page.locator('#fltSt').selectOption('A');assert.equal(await page.locator('#detTbl tbody tr').count(),4);
await page.locator('#fltSt').selectOption('B');assert.equal(await page.locator('#detTbl tbody tr').count(),3);
await page.locator('#fltSt').selectOption('all');assert.equal(await page.locator('#detTbl tbody tr').count(),5);
await page.locator('#legend [data-view="gone"]').click();await page.waitForTimeout(100);
assert.equal(await page.evaluate(()=>document.querySelectorAll('#legend [aria-pressed="true"]').length),1);
await page.locator('#legend [data-view="all"]').click();await page.waitForTimeout(100);
const fd=await page.evaluate(()=>window.__cw.state.fullDies);
// Para #51 후속: 맵 파일 없이 ProductInfo(Pitch 37249×44905.8, Cols 10, Rows 9) + 300 mm 원으로 소유자 예시 맵과 같은 Die 30개
assert.equal(fd,30,'계산 Die '+fd);
assert.match(await page.locator('#mapSt').innerText(),/계산 Die 30개 \(격자 8×9, 지름 300 mm\)/);
assert.ok(await page.evaluate(()=>window.__cw.state.dieSet.has('3,1')),'#50 검증 예 Die (3, 1) 은 wafer 안');
// Para #51: Wafer Map 파일(소유자 예시)이 있으면 '___' 아닌 칸만 Die 로 그린다(종전: ProductInfo Cols×Rows 전부 → die 가 많았다)
const MAP='DEVICE:4DT-TB500-H-M1\nLOT:TB500.INT025@6322\nWAFER:00RW8126XYC1\nFNLOC:180\nROWCT:6\nCOLCT:7\nBCEQU:000\nREFPX:1\nREFPY:1\nDUTMS:mm\nXDIES:\nYDIES:\n'
  +['___ ___ 023 000 023 ___ ___','___ 000 023 000 000 000 ___','000 000 000 000 023 000 000','000 023 000 023 023 000 023','___ 000 000 000 000 000 ___','___ ___ 000 000 000 ___ ___'].map(r=>'RowData:'+r).join('\n')+'\n';
const wm=await page.evaluate(m=>{const c=window.__cw,p=c.parseWaferMap(m);return {rows:p.rows,cols:p.cols,dies:p.dies,fn:p.head.FNLOC,ok:c.setWaferMap(m,'map.txt')}},MAP);
assert.deepEqual(wm,{rows:6,cols:7,dies:30,fn:'180',ok:true});
await page.waitForTimeout(150);
assert.deepEqual(await page.evaluate(()=>{const S=window.__cw.state;return [S.mapFrom,S.mapDies,S.fullDies,S.mapCheck.ok,S.mapCheck.both]}),['calc',30,30,true,30]);
assert.match(await page.locator('#mapSt').innerText(),/맵 map\.txt Die 30개와 일치 ✔/);
// 지름을 줄이면 Die 가 줄고 맵과 다르다고 알린다 → 되돌리기
await page.evaluate(()=>{const e=document.querySelector('#waferD');e.value='280';e.dispatchEvent(new Event('change'))});await page.waitForTimeout(200);
assert.ok(await page.evaluate(()=>window.__cw.state.fullDies)<30);assert.match(await page.locator('#mapSt').innerText(),/다름: 계산에만 0 · 맵에만 \d+/);
await page.evaluate(()=>{const e=document.querySelector('#waferD');e.value='300';e.dispatchEvent(new Event('change'))});await page.waitForTimeout(200);
assert.equal(await page.evaluate(()=>window.__cw.state.fullDies),30);
assert.ok(!/유지|소거|신규/.test(await page.locator('main').innerText()));
// Wafer map 이 그려진다(직사각형 · wafer 원 · 점)
const painted=await page.evaluate(()=>{const c=document.querySelector('#map'),d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;let n=0;for(let i=3;i<d.length;i+=4)if(d[i])n++;return n});
assert.ok(painted>2000,'map pixels '+painted);
// 표: Die · Area · Contrast
const t=await page.locator('#detTbl tbody tr').evaluateAll(trs=>trs.map(tr=>[...tr.cells].map(c=>c.innerText).join('|')));
const r1=t.find(x=>/\|1\|200498\.0/.test(x));assert.ok(r1,t.join('\n'));assert.match(r1,/\(3, 1\)/);assert.match(r1,/48\.72/);assert.match(r1,/34\.45/);
// CSV
const csv=await page.evaluate(()=>window.__cw.csvText());
assert.ok(csv.startsWith('﻿구분,ID'));
assert.match(csv,/CA20 ∖ CA27,3,103,5000\.00,5000\.00.*C2\.c\.1\.jpeg,Index 3 \(id\),,,,좌표 변환 보정 필요/);
assert.match(csv,/CA20 ∖ CA27,4,104,.*,,연결 실패,/);
assert.match(csv,/CA27 ∖ CA20,9,109,.*,,연결 실패,/);
assert.match(csv,/CA20 ∩ CA27,2,102,1100\.00,200\.00.*C1\.c\.1\.jpeg,좌표\(0\.0 µm\),F1\.t\.1\.jpeg,1100\.0,200\.0,transform/);
// 지도 hover → 툴팁 + 그림
await page.locator('#map').hover({position:{x:5,y:5}});
// 리뷰: 없어진 Defect 2개, 키 이동, Gray crop / 범위 밖 문구, 위치 지도 깜빡임
await page.locator('nav button[data-step="4"]').click();
await page.locator('#rvCount').filter({hasText:'CA27 에서 없어진 Defect (CA20 ∖ CA27) 2개'}).waitFor();
const rv=await page.evaluate(async()=>{const S=window.__cw.state;const a=S.rvGeo&&S.rvGeo.length;const c=document.querySelector('#rvMap');
  const seen=new Set();for(let i=0;i<8;i++){seen.add(c.toDataURL());await new Promise(r=>setTimeout(r,200))}return {a,changed:seen.size>1,n:seen.size,w:c.width,on:document.querySelector('#step4').classList.contains('on'),hl:!!S.rvList[S.rv]}});
assert.equal(rv.a,5);assert.ok(rv.changed,'보고 있는 점이 깜빡여야 함 '+JSON.stringify(rv));
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
// 새 창 사진은 창 높이 안에 맞춘다
const fit=await pop.evaluate(()=>{const c=document.querySelector('figure canvas');return {h:c.getBoundingClientRect().height,vh:innerHeight}});
assert.ok(fit.h<=fit.vh,JSON.stringify(fit));
await pop.close();
// 리스트 3개 → 3쌍
await page.evaluate(()=>{const S=window.__cw.state,b=S.scans.find(s=>s.name==='Lot/CA27');const c={...b,id:99,seq:99,name:'Lot/CA30',step:'CA30',contrast:30,_rule:null};
  c.defects=b.defects.slice(1).map(d=>({...d,scan:c}));S.scans.push(c)});
await page.locator('nav button[data-step="2"]').click();await page.locator('#runBtn').click();await page.locator('#step3.on').waitFor();
assert.equal(await page.locator('#pairTbl tbody tr').count(),3);
assert.deepEqual(await page.locator('#step3 .pairtabs button').allInnerTexts(),['CA20 → CA27 · 없어짐 2','CA20 → CA30 · 없어짐 3','CA27 → CA30 · 없어짐 1']);
await page.locator('#step3 .pairtabs button').nth(2).click();
assert.deepEqual(await page.locator('#kpis .kpi b').allInnerTexts(),['3','2','2','1','0','33.3%']);
assert.deepEqual(errors,[]);assert.deepEqual(requests,[]);
await browser.close();
console.log('test_contrast_wizard: passed');
