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
assert.deepEqual(fn.die,[5,6,14253,10038,true]);   // #52: 좌측 하단 (0,0) 에서 오른쪽 · 위쪽으로 1씩
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
assert.equal(rows.length,2,rows.join('\n'));   // Para #57: 줄 = Lot(CA20/LOTA · CA27/LOTA)
const msgs=await page.locator('#loadMsg .msg').allInnerTexts();
assert.ok(msgs.some(m=>/Lot CA27\/LOTA: Slot 2개\(W01, W02\).*제외할 Slot: W02\(잘못된 Record Size: 150 byte/.test(m)),msgs.join('\n'));
const st=await page.evaluate(()=>window.__cw.state.scans.map(s=>({n:s.name,c:s.contrast,d:s.defects.length,img:s.images,w:s.warns,e:s.errors,t:s.transforms.size,p:!!s.product})));
const a=st.find(s=>s.n==='CA20/LOTA/W01'),b=st.find(s=>s.n==='CA27/LOTA/W01');
assert.equal(a.c,20);assert.equal(b.c,27);assert.equal(a.d,4);assert.equal(b.d,3);assert.equal(a.img,4);assert.equal(a.t,1);assert.ok(a.p);
assert.ok(b.w.some(w=>/Surface defect 수 5 ≠ 파싱 3/.test(w)),b.w.join('|'));
assert.ok(!a.w.some(w=>/Surface defect/.test(w)));
// 잘못된 스캔 삭제 → 비교
await page.evaluate(()=>{const s=window.__cw.state;s.scans=s.scans.filter(x=>!x.errors.length)});
await page.locator('nav button[data-step="2"]').click();
await page.locator('#tol').fill('2');
await page.locator('#runBtn').click();
await page.locator('#step3.on').waitFor();
await page.locator('#step3 details summary').click();   // Para #55: 쌍별 상세 표 · CSV 는 접힌 상자 안
const kp=await page.locator('#kpis .kpi b').allInnerTexts();
assert.deepEqual(kp,['4','3','2','2','1','25.0%']);
// 쌍별 비교(리스트 2개 = 순서쌍 2개, Para #56), 이름 표기(유지 · 소거 · 신규 없음)
assert.equal(await page.locator('#pairTbl tbody tr').count(),2);
assert.deepEqual(await page.locator('#pairTbl tbody tr').nth(0).locator('td').allInnerTexts(),['CA20 → CA27','4','3','2','2','1','50.0%','보기']);
assert.deepEqual(await page.locator('#pairTbl tbody tr').nth(1).locator('td').allInnerTexts(),['CA27 → CA20','3','4','2','1','2','33.3%','보기']);
assert.deepEqual(await page.locator('#kpis .kpi .muted:first-child').allInnerTexts(),['CA20 (전체)','CA27 (전체)','CA20 ∩ CA27','CA20 - CA27','CA27 - CA20','감소율']);
// 표 필터 6가지(합집합 + 5가지)
assert.deepEqual(await page.locator('#fltSt option').allInnerTexts(),['CA20 ∪ CA27','CA20 (전체)','CA27 (전체)','CA20 - CA27','CA20 ∩ CA27','CA27 - CA20']);
await page.locator('#fltSt').selectOption('A');assert.equal(await page.locator('#detTbl tbody tr').count(),4);
await page.locator('#fltSt').selectOption('B');assert.equal(await page.locator('#detTbl tbody tr').count(),3);
await page.locator('#fltSt').selectOption('all');assert.equal(await page.locator('#detTbl tbody tr').count(),5);
// Para #55: Step 3 = 집합 고르기 → [결과] → 벤다이어그램(모든 스캔) + wafer map + 목록 · 사진
assert.equal(await page.locator('#vennArea').isHidden(),true);
assert.deepEqual(await page.locator('#setPick input:checked').count(),2);
await page.locator('#vennBtn').click();await page.locator('#vennArea').waitFor();await page.waitForTimeout(150);
const v1=await page.evaluate(()=>{const c=window.__cw,V=c.state.venn;return {n:V.cl.length,counts:[...V.counts].sort((a,b)=>a[0]-b[0]),lab:[1,2,3].map(c.regLabel),items:c.PANELS.p3.items.length,
  rows:[...document.querySelectorAll('#regTbl tbody tr')].map(r=>r.innerText.replace(/\s+/g,' ').trim()),painted:(()=>{const cv=document.querySelector('#venn'),d=cv.getContext('2d').getImageData(0,0,cv.width,cv.height).data;let k=0;for(let i=3;i<d.length;i+=4)if(d[i])k++;return k})()}});
assert.equal(v1.n,5);assert.deepEqual(v1.counts,[[1,2],[2,1],[3,2]]);   // CA20 에만 2 · CA27 에만 1 · 둘 다 2 (= 쌍 비교와 같음)
assert.deepEqual(v1.lab,['CA20 - CA27','CA27 - CA20','CA20 ∩ CA27']);
assert.equal(v1.items,5);assert.ok(v1.painted>5000,'venn pixels '+v1.painted);assert.equal(v1.rows.length,3);
assert.match(await page.locator('#p3Cnt').innerText(),/고른 집합 전체\(CA20 ∪ CA27\) · Defect 5개/);
// 영역 표 클릭 = 그 영역만 · 벤다이어그램 클릭(가운데 = 두 원 겹침) = 그 영역
await page.locator('#regTbl tr[data-reg="1"]').click();
assert.match(await page.locator('#p3Cnt').innerText(),/CA20 - CA27 · Defect 2개/);
// Para #56: Ctrl 없이 클릭 = 더하기, 다시 클릭 = 빼기
const vb=await page.locator('#venn').boundingBox();await page.mouse.click(vb.x+vb.width/2,vb.y+vb.height/2);
assert.match(await page.locator('#p3Cnt').innerText(),/CA20 - CA27 \+ CA20 ∩ CA27 · Defect 4개/);
await page.locator('#regTbl tr[data-reg="1"]').click();
assert.match(await page.locator('#p3Cnt').innerText(),/^CA20 ∩ CA27 · Defect 2개/);
await page.locator('#venn').click({position:{x:4,y:4}});   // 빈 곳 = 고른 집합 전체
assert.match(await page.locator('#p3Cnt').innerText(),/Defect 5개/);
// 집합 하나만 고르면(결과 뒤에는 바로 반영) 그 집합과 관련된 영역만 색 · 목록
await page.locator('#setPick input[data-set="1"]').uncheck();
assert.match(await page.locator('#p3Cnt').innerText(),/고른 집합 전체\(CA20\) · Defect 4개/);
assert.equal(await page.evaluate(()=>window.__cw.PANELS.p3.bg.length),1);   // CA27 에만 있는 1개 = 회색 배경 점
await page.locator('#setPick input[data-set="1"]').check();
// 목록 j/k 이동 · 지도 깜빡임
await page.locator('#p3List').focus();const s3a=await page.locator('#p3List .it.sel').innerText();await page.keyboard.press('j');assert.notEqual(await page.locator('#p3List .it.sel').innerText(),s3a);await page.keyboard.press('k');
const bl=await page.evaluate(async()=>{const c=document.querySelector('#p3Map'),seen=new Set();for(let i=0;i<8;i++){seen.add(c.toDataURL());await new Promise(r=>setTimeout(r,200))}return seen.size});
assert.ok(bl>1,'Step 3 wafer map 깜빡임');
// wafer map 새 창 = 실시간 연동(목록을 옮기면 새 창 글 · 그림도 바뀐다)
const [mp]=await Promise.all([page.waitForEvent('popup'),page.locator('#p3Pop').click()]);
await mp.waitForFunction(()=>{const c=document.querySelector('canvas');return c&&c.width>100});
const h1=await mp.locator('.hd').innerText();await page.keyboard.press('j');await page.waitForTimeout(100);
const h2=await mp.locator('.hd').innerText();assert.notEqual(h1,h2);assert.match(h2,/보고 있는 Defect/);
const pp=await mp.evaluate(()=>{const c=document.querySelector('.mp canvas'),d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;let k=0;for(let i=3;i<d.length;i+=4)if(d[i])k++;return k});assert.ok(pp>2000,'popup map '+pp);
// Para #56: 새 창에 벤다이어그램도 있고, 새 창 벤다이어그램 클릭 = 이 화면 영역 더하기/빼기
const pv=await mp.evaluate(()=>{const c=document.querySelector('.sd canvas'),d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;let k=0;for(let i=3;i<d.length;i+=4)if(d[i])k++;return k});assert.ok(pv>2000,'popup venn '+pv);
const before=await page.locator('#p3Cnt').innerText();
const sb=await mp.locator('.sd canvas').boundingBox();await mp.mouse.click(sb.x+sb.width/2,sb.y+sb.height/2);
assert.notEqual(await page.locator('#p3Cnt').innerText(),before);
await page.locator('#venn').click({position:{x:4,y:4}});assert.match(await mp.locator('.hd').innerText(),/고른 집합 전체/);
await mp.close();await page.keyboard.press('k');
// 목록 더블 클릭 = 새 창(큰 화면)
const [big]=await Promise.all([page.waitForEvent('popup'),page.locator('#p3List .it.sel').dblclick()]);
await big.waitForFunction(()=>document.querySelector('.pane'));assert.match(await big.locator('.hd').innerText(),/ID \d/);await big.close();
const fd=await page.evaluate(()=>window.__cw.state.fullDies);
// Para #51 후속: 맵 파일 없이 ProductInfo(Pitch 37249×44905.8, Cols 10, Rows 9) + 300 mm 원으로 소유자 예시 맵과 같은 Die 30개
assert.equal(fd,30,'계산 Die '+fd);
assert.match(await page.locator('#mapSt').innerText(),/Die 30개 \[기준 계산\(네 모서리가 원 안 · 확인 필요\)\] \(Col 0~6 × Row 0~5, 좌측 하단 \(0,0\), 지름 300 mm, wafer 중심 130372, 134717 µm · 추정\(중심 정보 없음 · 확인 필요\)\)/);   // 합성 ProductInfo 에 CenterX/Y 없음 → 종전 추정
// Notch: 맵 파일이 없으면 기본 아래(180)
assert.deepEqual(await page.evaluate(()=>[window.__cw.state.notchDeg,window.__cw.state.notchSrc]),[180,'기본값']);assert.match(await page.locator('#mapSt').innerText(),/Notch 아래 \(기본값\)/);
// Para #51: Wafer Map 파일(소유자 예시)이 있으면 '___' 아닌 칸만 Die 로 그린다(종전: ProductInfo Cols×Rows 전부 → die 가 많았다)
const MAP='DEVICE:4DT-TB500-H-M1\nLOT:TB500.INT025@6322\nWAFER:00RW8126XYC1\nFNLOC:180\nROWCT:6\nCOLCT:7\nBCEQU:000\nREFPX:1\nREFPY:1\nDUTMS:mm\nXDIES:\nYDIES:\n'
  +['___ ___ 023 000 023 ___ ___','___ 000 023 000 000 000 ___','000 000 000 000 023 000 000','000 023 000 023 023 000 023','___ 000 000 000 000 000 ___','___ ___ 000 000 000 ___ ___'].map(r=>'RowData:'+r).join('\n')+'\n';
const wm=await page.evaluate(m=>{const c=window.__cw,p=c.parseWaferMap(m);return {rows:p.rows,cols:p.cols,dies:p.dies,fn:p.head.FNLOC,ok:c.setWaferMap(m,'map.txt')}},MAP);
assert.deepEqual(wm,{rows:6,cols:7,dies:30,fn:'180',ok:true});
await page.waitForTimeout(150);
assert.deepEqual(await page.evaluate(()=>{const S=window.__cw.state;return [S.mapFrom,S.mapDies,S.fullDies,S.mapCheck.ok,S.mapCheck.both]}),['map',30,30,true,30]);
assert.match(await page.locator('#mapSt').innerText(),/Die 30개 \[기준 Wafer Map 파일\].*맵 map\.txt Die 30개 = 계산 일치 ✔/);
assert.match(await page.locator('#mapSt').innerText(),/Notch 아래 \(맵 FNLOC:180\)/);
// Notch 를 직접 고르면(오른쪽 90) 다시 그린다 → 자동으로 되돌리기
await page.evaluate(()=>{const e=document.querySelector('#notch');e.value='90';e.dispatchEvent(new Event('change'))});await page.waitForTimeout(150);
assert.equal(await page.evaluate(()=>window.__cw.state.notchDeg),90);assert.match(await page.locator('#mapSt').innerText(),/Notch 오른쪽 \(직접 고름\)/);
await page.evaluate(()=>{const e=document.querySelector('#notch');e.value='auto';e.dispatchEvent(new Event('change'))});await page.waitForTimeout(150);
assert.equal(await page.evaluate(()=>window.__cw.state.notchDeg),180);
// 지름을 줄여도 맵 파일이 있으면 맵 기준으로 그린다(어떤 자재에도 맞게) — 계산과 다르다고만 알린다 → 되돌리기
await page.evaluate(()=>{const e=document.querySelector('#waferD');e.value='280';e.dispatchEvent(new Event('change'))});await page.waitForTimeout(200);
assert.equal(await page.evaluate(()=>window.__cw.state.fullDies),30);assert.match(await page.locator('#mapSt').innerText(),/맵 map\.txt Die 30개와 계산 다름: 계산에만 0 · 맵에만 \d+ \(그리기는 맵 기준\)/);
await page.evaluate(()=>{const e=document.querySelector('#waferD');e.value='300';e.dispatchEvent(new Event('change'))});await page.waitForTimeout(200);
assert.equal(await page.evaluate(()=>window.__cw.state.fullDies),30);
// Para #52(소유자 확정): Die 좌표 = 좌측 하단 (0,0) 에서 오른쪽 · 위쪽으로 1씩. 맨 아래 줄(Row 0) = Col 2~4, 가운데 줄 = Col 0~6
assert.deepEqual(await page.evaluate(()=>{const D=window.__cw.state.dieSet;return [[2,3,4].every(c=>D.has(c+',0')),D.has('1,0'),D.has('0,2'),D.has('6,3'),D.has('7,3'),D.has('3,5'),D.has('3,6')]}),[true,false,true,true,false,true,false]);
// 첫 Defect (200498, 279473) = Die (5, 6) → wafer map 위쪽 밖 칸
const d52=await page.evaluate(()=>window.__cw.dieOf(200498,279473,{pitchX:37249,pitchY:44905.8,offX:0,offY:0}));assert.deepEqual([d52.col,d52.row],[5,6]);
assert.ok(!/유지|소거|신규/.test(await page.locator('main').innerText()));
// Wafer map 이 그려진다(직사각형 · wafer 원 · 점)
const painted=await page.evaluate(()=>{const c=document.querySelector('#p3Map'),d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;let n=0;for(let i=3;i<d.length;i+=4)if(d[i])n++;return n});
assert.ok(painted>2000,'map pixels '+painted);
// 표: Die · Area · Contrast
const t=await page.locator('#detTbl tbody tr').evaluateAll(trs=>trs.map(tr=>[...tr.cells].map(c=>c.innerText).join('|')));
const r1=t.find(x=>/\|1\|200498\.0/.test(x));assert.ok(r1,t.join('\n'));assert.match(r1,/\(5, 6\) · wafer 밖 칸/);assert.match(r1,/48\.72/);assert.match(r1,/34\.45/);
// CSV
const csv=await page.evaluate(()=>window.__cw.csvText());
assert.ok(csv.startsWith('﻿구분,ID'));
assert.match(csv,/CA20 - CA27,3,103,5000\.00,5000\.00.*C2\.c\.1\.jpeg,Index 3 \(id\),,,,좌표 변환 보정 필요/);
assert.match(csv,/CA20 - CA27,4,104,.*,,연결 실패,/);
assert.match(csv,/CA27 - CA20,9,109,.*,,연결 실패,/);
assert.match(csv,/CA20 ∩ CA27,2,102,1100\.00,200\.00.*C1\.c\.1\.jpeg,좌표\(0\.0 µm\),F1\.t\.1\.jpeg,1100\.0,200\.0,transform/);
// Para #53: 실제 결과 폴더 형식 — ProductInfo CenterX/CenterY 가 있으면 그 중심을 쓴다(실제 자료: (5.5·PitchX, 5·PitchY), 맨 왼쪽 아래 Die = 장비 Col 2 · Row 2).
// 종전 추정 중심(3.5·PitchX, 3·PitchY)은 Defect 를 2칸씩 오른쪽 위로 밀었다. s_DieLocation(Die 중심) 30개와 계산 Die 가 같아야 한다.
const r53=await page.evaluate(()=>{const c=window.__cw,S=c.state,PX=37249,PY=44905.8,T=[...new Set([...S.scans,...S.cmpScans])];
  const rowsSpec=[[2,[4,5,6]],[3,[3,4,5,6,7]],[4,[2,3,4,5,6,7,8]],[5,[2,3,4,5,6,7,8]],[6,[3,4,5,6,7]],[7,[4,5,6]]];
  const loc=[];for(const [r,cs] of rowsSpec)for(const cc of cs)loc.push({x:(cc+.5)*PX,y:(r+.5)*PY,sx:PX,sy:PY});
  const saved=T.map(s=>[s.product,s.dieLoc]);
  for(const s of T){s.product={...s.product,centerX:5.5*PX,centerY:5*PY,centerSrc:'ProductInfo'};s.dieLoc=loc}
  const D53=c.dieCells();const out={fd:D53.calc,base:S.dieBase,loc:S.dieLocCheck,src:S.center.src,cx:Math.round(S.center.cx)};
  // 실제 자료 첫 Defect 와 같은 꼴: Wafer (203335, 203642) = 장비 Col 5, Row 4 → 화면 Die (3, 2)
  const d=c.dieOf(203335,203642,{pitchX:PX,pitchY:PY,offX:0,offY:0});out.eq=[d.col,d.row];out.rel=[d.col-S.dieBase.c,d.row-S.dieBase.r];out.inSet=S.dieSet.has(d.col+','+d.row);
  out.dl=c.parseDieLoc(new Uint8Array(256).buffer,null).length;
  T.forEach((s,i)=>{s.product=saved[i][0];s.dieLoc=saved[i][1]});c.dieCells();return out});
assert.equal(r53.fd,30);assert.deepEqual(r53.base,{c:2,r:2});assert.equal(r53.loc.ok,true);assert.equal(r53.loc.n,30);assert.equal(r53.src,'ProductInfo');assert.equal(r53.cx,204870);
assert.deepEqual(r53.eq,[5,4]);assert.deepEqual(r53.rel,[3,2]);assert.equal(r53.inSet,true);assert.equal(r53.dl,2);
// 어떤 자재에도 맞게: s_DieLocation(실제 스캔 Die)이 있으면 계산 규칙과 달라도 그 Die 로 그린다(맨 위 줄 가운데 Die 를 뺀 29개)
const pr=await page.evaluate(()=>{const c=window.__cw,S=c.state,PX=37249,PY=44905.8,T=[...new Set([...S.scans,...S.cmpScans])];
  const rowsSpec=[[2,[4,5,6]],[3,[3,4,5,6,7]],[4,[2,3,4,5,6,7,8]],[5,[2,3,4,5,6,7,8]],[6,[3,4,5,6,7]],[7,[4,6]]];
  const loc=[];for(const [r,cs] of rowsSpec)for(const cc of cs)loc.push({x:(cc+.5)*PX,y:(r+.5)*PY,sx:PX,sy:PY});
  const saved=T.map(s=>[s.product,s.dieLoc]),um=S.userMap;S.userMap=null;
  for(const s of T){s.product={...s.product,centerX:5.5*PX,centerY:5*PY,centerSrc:'ProductInfo'};s.dieLoc=loc}
  const D=c.dieCells();const out={n:D.calc,from:D.from,src:S.dieSrc,miss:S.dieSet.has('5,7'),loc:S.dieLocCheck.ok,onlyCalc:S.dieLocCheck.onlyCalc};
  T.forEach((s,i)=>{s.product=saved[i][0];s.dieLoc=saved[i][1]});S.userMap=um;c.dieCells();return out});
assert.deepEqual(pr,{n:29,from:'dieloc',src:'s_DieLocation(실제 스캔 Die)',miss:false,loc:false,onlyCalc:1});
// 지도 hover → 툴팁 + 그림
await page.locator('#p3Map').hover({position:{x:5,y:5}});
// 리뷰: 없어진 Defect 2개, 키 이동, Gray crop / 범위 밖 문구, 위치 지도 깜빡임
await page.locator('nav button[data-step="4"]').click();
assert.equal(await page.locator('nav button[data-step="4"]').innerText(),'4Escape Defect 리뷰');
await page.locator('#p4Cnt').filter({hasText:'CA20 → CA27 Escape Defect (CA20 - CA27) 2개'}).waitFor();
const rv=await page.evaluate(async()=>{const P=window.__cw.PANELS.p4;const a=P.geo&&P.geo.length;const c=document.querySelector('#p4Map');
  const seen=new Set();for(let i=0;i<8;i++){seen.add(c.toDataURL());await new Promise(r=>setTimeout(r,200))}return {a,changed:seen.size>1,n:seen.size,w:c.width,es:window.__cw.state.esGeo.map(g=>g&&g.length)}});
assert.equal(rv.a,5);assert.deepEqual(rv.es,[4,5]);   // 간략 그림: A = 유지 2 + 없어짐 2, B = 유지 2 + 신규 1 + 없어진 자리 2
assert.match(await page.locator('#esAt').innerText(),/A = CA20 \(전체 4\) · 빨강 = B 에서 없어진 2개/);assert.ok(rv.changed,'보고 있는 점이 깜빡여야 함 '+JSON.stringify(rv));
const first=await page.locator('#p4List .it.sel').innerText();
await page.keyboard.press('j');
const second=await page.locator('#p4List .it.sel').innerText();
assert.notEqual(first,second);
await page.keyboard.press('k');assert.equal(await page.locator('#p4List .it.sel').innerText(),first);
// id 3 = 범위 밖 → 문구
const k3=await page.evaluate(()=>window.__cw.PANELS.p4.items.findIndex(r=>r.d.id===3));
for(let i=0;i<k3;i++)await page.keyboard.press('ArrowDown');
await page.locator('#p4Gray .ph').filter({hasText:'좌표 변환 보정 필요'}).waitFor();
await page.locator('#p4Color img').waitFor();
// 유지 defect 의 Gray crop 은 캔버스로 그려진다
const crop=await page.evaluate(async()=>{const c=window.__cw,S=c.state,P=c.PANELS.p4,r=S.rows.find(r=>r.d.id===2&&r.st==='keep');c.setPanel(P,[{d:r.d,X:r.d.X,Y:r.d.Y,c:'--keep',label:'keep'}],[],'test');
  await new Promise(r=>setTimeout(r,400));return {c:!!document.querySelector('#p4Gray canvas'),gl:r.d.gl}});
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
// Para #56: Step 4 새 창 = 간략 지도 2개 + wafer map
const [p4w]=await Promise.all([page.waitForEvent('popup'),page.locator('#p4Pop').click()]);
await p4w.waitForFunction(()=>document.querySelectorAll('.sd canvas').length===2&&/A = /.test(document.querySelector('.sd').innerText));
assert.match(await p4w.locator('.sd').innerText(),/A = CA20/);
const p4px=await p4w.evaluate(()=>[...document.querySelectorAll('.sd canvas')].map(c=>{const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;let k=0;for(let i=3;i<d.length;i+=4)if(d[i])k++;return k}));
assert.ok(p4px.every(n=>n>1000),'popup esc '+p4px);await p4w.close();
// 리스트 3개 → 순서쌍 6개(Para #56)
await page.evaluate(()=>{const S=window.__cw.state,b=S.scans.find(s=>s.name==='CA27/LOTA/W01');const c={...b,id:99,seq:99,name:'CA30/LOTA/W01',lotPath:'CA30/LOTA',step:'CA30',contrast:30,_rule:null};
  c.defects=b.defects.slice(1).map(d=>({...d,scan:c}));S.scans.push(c)});
await page.locator('nav button[data-step="2"]').click();await page.locator('#runBtn').click();await page.locator('#step3.on').waitFor();
assert.equal(await page.locator('#pairTbl tbody tr').count(),6);
const tabs=await page.locator('#step3 .pairtabs button').allInnerTexts();
assert.deepEqual(tabs.map(t=>t.split(' · ')[0]),['CA20 → CA27','CA20 → CA30','CA27 → CA20','CA27 → CA30','CA30 → CA20','CA30 → CA27']);
assert.deepEqual([tabs[0],tabs[1],tabs[3]],['CA20 → CA27 · 없어짐 2','CA20 → CA30 · 없어짐 3','CA27 → CA30 · 없어짐 1']);
assert.equal(tabs[2],'CA27 → CA20 · 없어짐 1');   // CA27 에만 있는 1개
// 스캔 3개 = 원 3개 벤다이어그램(7영역 중 Defect 있는 영역), 집합 선택은 다시 비교해도 유지
const v3=await page.evaluate(()=>{const c=window.__cw,V=c.state.venn;return {n:V.scans.length,shown:V.shown,sel:V.sel.size,sum:[...V.counts.values()].reduce((a,b)=>a+b,0),cl:V.cl.length,lab:c.regLabel(3),geo:V.geo&&V.geo.E.length}});
assert.deepEqual(v3,{n:3,shown:true,sel:2,sum:v3.cl,cl:v3.cl,lab:'CA20 ∩ CA27 - CA30',geo:3});
await page.locator('#step3 .pairtabs button').nth(3).click();
assert.deepEqual(await page.locator('#kpis .kpi b').allInnerTexts(),['3','2','2','1','0','33.3%']);
// Para #57: Lot 폴더 안 Slot 폴더 — Lot 별(모든 Slot 겹침, 같은 Slot 끼리만 짝) / Slot 별(고른 Slot 만)
const lot=await page.evaluate(()=>{const c=window.__cw,S=c.state;
  // CA20 · CA27 Lot 에 Slot W03 을 더한다: CA20 W03 의 Defect 하나는 CA20 W01 의 Defect 1 과 같은 좌표지만 다른 Wafer
  const mk=(lotPath,step,ca,src,pts)=>{const w={...src,id:200+S.scans.length,seq:200+S.scans.length,name:lotPath+'/W03',lotPath,step,contrast:ca,slot:'w03',slotName:'W03',_rule:null};
    w.defects=pts.map(([x,y],i)=>({...src.defects[0],i,id:50+i,no:50+i,x,y,ActualX:x,ActualY:y,slot:'w03',scan:w}));return w};
  const a=S.scans.find(s=>s.name==='CA20/LOTA/W01'),b=S.scans.find(s=>s.name==='CA27/LOTA/W01');
  S.scans=S.scans.filter(s=>s.lotPath!=='CA30/LOTA');
  S.scans.push(mk('CA20/LOTA','CA20',20,a,[[200498,279473],[3000,3000]]),mk('CA27/LOTA','CA27',27,b,[[3000.5,3000]]));c.renderScans();
  return {opts:[...document.querySelectorAll('#unit option')].map(o=>o.textContent),lots:c.lotsOf().map(l=>[l.path,l.wafers.map(w=>w.slotName).join(',')])}});
assert.deepEqual(lot.lots,[['CA20/LOTA','W01,W03'],['CA27/LOTA','W01,W03']]);
assert.deepEqual(lot.opts,['Lot 별 (모든 Slot 합침)','Slot 별 · W01 (2/2 Lot)','Slot 별 · W03 (2/2 Lot)']);
await page.locator('nav button[data-step="2"]').click();await page.locator('#unit').selectOption('lot');await page.locator('#runBtn').click();await page.locator('#step3.on').waitFor();
// Lot 별: CA20 = 4 + 2, CA27 = 3 + 1. W03 (200498, 279473) 은 W01 의 같은 좌표와 짝짓지 않는다(다른 Wafer)
assert.deepEqual(await page.locator('#pairTbl tbody tr').nth(0).locator('td').allInnerTexts(),['CA20 → CA27','6','4','3','3','1','50.0%','보기']);
assert.match(await page.locator('#cmpMsg').innerText(),/Lot 별\(모든 Slot\) · 리스트 2개/);
assert.match(await page.locator('#mapSt').innerText(),/Lot 별: Slot 2개까지 한 wafer map 에 겹쳐 그림/);
assert.equal(await page.evaluate(()=>window.__cw.state.venn.cl.length),7);   // 묶음도 Slot 끼리: W01 5 + W03 2
// Step 3 에서 Slot 별(W03)로 바꾸면 바로 다시 비교
await page.locator('#unit3').selectOption('slot:w03');
assert.deepEqual(await page.locator('#pairTbl tbody tr').nth(0).locator('td').allInnerTexts(),['CA20 → CA27','2','1','1','1','0','50.0%','보기']);
assert.equal(await page.locator('#unit').inputValue(),'slot:w03');
const sl=await page.evaluate(()=>window.__cw.state.rows.map(r=>r.d.scan.slotName));assert.ok(sl.every(x=>x==='W03'),sl.join());
assert.match(await page.locator('#detTbl thead').innerText(),/Slot/);assert.match(await page.evaluate(()=>window.__cw.csvText()),/,Step,Slot,ContrastAVG,/);
await page.locator('#unit3').selectOption('slot:w01');
assert.deepEqual(await page.locator('#pairTbl tbody tr').nth(0).locator('td').allInnerTexts(),['CA20 → CA27','4','3','2','2','1','50.0%','보기']);
// Para #57 추가: 다른 파일의 Wafer Map 이 계산 Die 보다 크면 종전에는 왼쪽 아래만 맞춰 맵이 오른쪽 위로 밀렸다 → 맵 가운데 = wafer 중심
const al=await page.evaluate(()=>{const c=window.__cw,S=c.state;
  const big='FNLOC:180\nROWCT:8\nCOLCT:9\n'+Array.from({length:8},()=>'RowData:'+Array(9).fill('000').join(' ')).join('\n')+'\n';
  c.setWaferMap(big,'big.txt');const D=c.dieCells(),F=D.dies.filter(d=>d.full),p=D.p;
  const fx=(Math.min(...F.map(d=>d.x0))+Math.max(...F.map(d=>d.x0))+p.pitchX)/2,fy=(Math.min(...F.map(d=>d.y0))+Math.max(...F.map(d=>d.y0))+p.pitchY)/2;
  const r={n:F.length,dx:Math.abs(fx-D.cx)/p.pitchX,dy:Math.abs(fy-D.cy)/p.pitchY};
  // s_DieLocation 이 중심 값과 다른 기준(오른쪽 위로 몇 칸)이면 원 · Notch 를 Die 묶음에 맞춘다
  const PX=37249,PY=44905.8,loc=[];for(let r2=0;r2<6;r2++)for(let c2=0;c2<7;c2++)loc.push({x:(c2+6.5)*PX,y:(r2+6.5)*PY});
  const um=S.userMap,sp=S.cmpScans.map(v=>v.product);S.userMap=null;S.cmpScans.forEach(v=>{v.dieLoc=loc;v.product={...v.product,centerX:3.5*PX,centerY:3*PY,centerSrc:'ProductInfo'}});
  const D2=c.dieCells();r.shift=S.centerShift&&[+(S.centerShift.dx/PX).toFixed(2),+(S.centerShift.dy/PY).toFixed(2)];r.cx=+(D2.cx/PX).toFixed(3);r.cy=+(D2.cy/PY).toFixed(3);r.src=S.center.src;
  S.cmpScans.forEach((v,i)=>{v.dieLoc=null;v.product=sp[i]});S.userMap=um;c.dieCells();return r});
assert.equal(al.n,72);assert.ok(al.dx<=0.5&&al.dy<=0.5,JSON.stringify(al));
assert.deepEqual([al.cx,al.cy],[9.5,9]);assert.ok(al.shift&&al.shift[0]>1&&al.shift[1]>1,JSON.stringify(al));assert.match(al.src,/Die 묶음 가운데\(ProductInfo 중심과 \d+, \d+ µm 달라 Die 에 맞춤\)/);
assert.deepEqual(errors,[]);assert.deepEqual(requests,[]);
await browser.close();
console.log('test_contrast_wizard: passed');
