// AOI_Contrast_Wizard_rev4.html 자동 시험(Para #50, rev4 = rev3 + 5-1 Surface.flt.md 를 Step 1 순서로 찾기 + 5-2 에서 5-1 값 ↔ Step 1 값 확인. rev3 = rev2 + Color 연결 보강 + 5-2 · 5-3 Step 1 과 같은 읽기. rev2 = Step 5 3단계 · 폴더 = 레시피/Setup/Lot/Slot). 폴더 고르기 창은 자동화할 수 없어 window.__cw.addEntries 로 합성 파일을 넣는다.
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
await page.goto('file://'+resolve(root,'AOI_Contrast_Wizard_rev4.html'));
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
// 폴더 인식(소유자 확정 2026-11-10: 레시피 / Setup / Lot / Slot): Surface.flt 폴더 = Slot, 바로 위 = Lot — 어느 폴더를 골라도 같은 Lot
const pu=await page.evaluate(()=>{const c=window.__cw,E=ps=>ps.map(p=>({path:p})),f=r=>r.units.map(u=>[u.lotPath,u.slotName,u.files.map(e=>e.path.split('/').pop()).sort().join('|')]);
  return {
    // 레시피 폴더를 고름: Lot 폴더의 ProductInfo · 레시피 폴더의 글 파일은 그 아래 Slot 이 같이 씀, 사진은 안 나눔
    rcp:f(c.planUnits(E(['RCP/SETUP1/LOTA/W01/Surface.flt','RCP/SETUP1/LOTA/W02/Surface.flt','RCP/SETUP1/LOTA/ProductInfo.ini','RCP/SETUP1/LOTA/a.jpeg','RCP/SETUP1/LOTB/W01/Surface.flt','RCP/SETUP1/LOTB/W01/x.jpeg','RCP/note.txt']))),
    sum:c.planUnits(E(['RCP/SETUP1/LOTA/W01/Surface.flt','RCP/SETUP1/LOTB/W01/Surface.flt'])).sum,
    lot:f(c.planUnits(E(['LOT/W01/Surface.flt','LOT/W02/Surface.flt']))),          // Lot 폴더를 고름
    slot:f(c.planUnits(E(['W07/Surface.flt']))),                                     // Slot 폴더를 고름 → Slot 1개짜리 Lot
    ca:f(c.planUnits(E(['RUN/CA20/Surface.flt','RUN/CA27/Surface.flt'])))}});         // 아래 폴더마다 다른 CA + Surface.flt 바로 → 그 폴더들 = Lot
assert.deepEqual(pu.rcp,[['RCP/SETUP1/LOTA','W01','ProductInfo.ini|Surface.flt|note.txt'],['RCP/SETUP1/LOTA','W02','ProductInfo.ini|Surface.flt|note.txt'],['RCP/SETUP1/LOTB','W01','Surface.flt|note.txt|x.jpeg']]);
assert.equal(pu.sum,"폴더 'RCP' → Lot 2개(LOTA, LOTB)");
assert.deepEqual(pu.lot.map(x=>x.slice(0,2)),[['LOT','W01'],['LOT','W02']]);
assert.deepEqual(pu.slot.map(x=>x.slice(0,2)),[['W07','W07']]);
assert.deepEqual(pu.ca.map(x=>x.slice(0,2)),[['RUN/CA20','CA20'],['RUN/CA27','CA27']]);
// Color 연결(2026-11-10 소유자 "Color 이미지 정보는 어떤 경우에도 있다 · 사진은 모두 Slot 폴더 안"): Gray 는 찾는데 Color 를 못 찾던 조건들 —
//  실제 결과 폴더(사진 제외.zip)를 본뜬 합성: id 전부 1, Color Index = 기록 순서. ① 좌표 그대로 ② 100 µm 어긋남 ③ 어긋남 + Index 없음 ④ 어긋남 + 항목마다 ±8 µm 흔들림 ⑤ 사진 이름만(ini 없음)
const ck=await page.evaluate(async()=>{const c=window.__cw,N=120;let seed=7;const rnd=()=>(seed=(seed*16807)%2147483647)/2147483647;
  const D=Array.from({length:N},(_,i)=>[100000+((i*9973)%60000)+rnd()*500,120000+((i*7919)%50000)+rnd()*500]);
  const scan=(colors)=>{const s={id:900+N*Math.random(),colors,colorByIndex:new Map(),defects:[]};for(const x of colors)if(x.index!=null&&!s.colorByIndex.has(x.index))s.colorByIndex.set(x.index,x);
    s.defects=D.map((p,i)=>({i,id:1,resultID:134217728+i*2,x:p[0],y:p[1],ActualX:p[0],ActualY:p[1],X:p[0],Y:p[1],scan:s}));return s};
  const col=(f)=>D.map((p,i)=>({file:`c${i}.jpeg`,...f(p,i),w:1380,h:1036,psx:.4624,psy:.4622}));
  const run=s=>{let right=0,none=0;const how={};for(const d of s.defects){const r=c.linkColor(d,s,5);if(!r){none++;continue}if(r.c.file===`c${d.i}.jpeg`)right++;const h=r.how.replace(/[-\d.]+/g,'#');how[h]=(how[h]||0)+1}return {right,none,how}};
  const out={};
  out.same=run(scan(col((p,i)=>({x:p[0],y:p[1],index:i}))));
  out.off=run(scan(col((p,i)=>({x:p[0]+100,y:p[1],index:i}))));
  out.offNoIdx=run(scan(col((p,i)=>({x:p[0]+100,y:p[1]-40,index:null}))));
  out.jitter=run(scan(col((p,i)=>({x:p[0]+100+(rnd()-.5)*16,y:p[1]+(rnd()-.5)*16,index:null}))));
  const named=c.colorsFromNames(D.map((p,i)=>`${Math.floor(p[0])}.${Math.floor(p[1])}.c.${-1000-i}.jpeg`).concat(['-56211.70388.t.jpeg','x.jpeg']));
  const sn=scan(named);out.named={n:named.length,...(()=>{let right=0;for(const d of sn.defects){const r=c.linkColor(d,sn,5);if(r&&r.c.file.endsWith(`.c.${-1000-d.i}.jpeg`))right++}return {right}})()};
  const far=scan([{file:'z.jpeg',x:0,y:0,index:null}]);out.far=[c.linkColor(far.defects[0],far,5),c.colorWhy(far.defects[0],far,5)];
  // UTF-16(BOM) · UTF-16(BOM 없음) · UTF-8 BOM · EUC-KR ini 도 같은 글로 읽음
  const txt='[203335.203642.c.-1448302202.jpeg]\r\nFaultX=203335.06\r\nIndex=0\r\n',u16=new Uint8Array(txt.length*2);for(let i=0;i<txt.length;i++)u16[i*2]=txt.charCodeAt(i);
  out.text=[await c.readText(new Blob([new Uint8Array([0xFF,0xFE]),u16])),await c.readText(new Blob([u16])),await c.readText(new Blob([new Uint8Array([0xEF,0xBB,0xBF]),new TextEncoder().encode(txt)]))].map(s=>s===txt);
  out.parsed=c.parseColors(await c.readText(new Blob([new Uint8Array([0xFF,0xFE]),u16])))[0];
  return out});
for(const k of ['same','off','offNoIdx','jitter'])assert.deepEqual([ck[k].right,ck[k].none],[120,0],k+' '+JSON.stringify(ck[k]));
assert.deepEqual(Object.keys(ck.same.how),['좌표(# µm)']);
assert.ok(Object.keys(ck.off.how).every(h=>/어긋남 #, # µm 보정/.test(h)),JSON.stringify(ck.off.how));
assert.deepEqual(ck.named,{n:120,right:120});
assert.equal(ck.far[0],null);assert.match(ck.far[1],/가장 가까운 Color z\.jpeg 도 \d+ µm 떨어져 사진 범위 밖/);
assert.deepEqual(ck.text,[true,true,true]);assert.deepEqual([ck.parsed.file,ck.parsed.x,ck.parsed.index],['203335.203642.c.-1448302202.jpeg',203335.06,0]);
// 폴더 등록
// Para #59: 등록 중 로딩창이 'Slot 폴더 k / N' · '파일 x / M' 을 실시간으로 보여 주고, 끝나면 닫힌다
const prog=await page.evaluate(async fx=>{const f=JSON.parse(fx),seen=[],el=document.getElementById('busy');
  const ob=new MutationObserver(()=>{if(!el.hidden)seen.push(document.getElementById('busyN').textContent+' | '+document.getElementById('busyF').textContent)});
  ob.observe(el,{subtree:true,childList:true,characterData:true,attributes:true});
  await window.__cw.addEntries(Object.entries(f).map(([p,b])=>({path:p,file:new File([Uint8Array.from(atob(b),c=>c.charCodeAt(0))],p.split('/').pop())})));
  await new Promise(r=>setTimeout(r,0));ob.disconnect();return {seen,hidden:el.hidden,n:Object.keys(f).length}},fixture);
assert.ok(prog.hidden,'로딩창이 끝나고 닫혀야 함');
assert.ok(prog.seen.some(t=>/^0 \/ 3 Slot 폴더/.test(t)),prog.seen.join('\n'));
assert.ok(prog.seen.some(t=>/^2 \/ 3 Slot 폴더/.test(t)),prog.seen.join('\n'));
assert.ok(prog.seen.some(t=>t.startsWith('3 / 3 Slot 폴더')&&t.includes(`파일 ${prog.n} / ${prog.n}개 (100%)`)),prog.seen.join('\n'));
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
assert.match(csv,/CA20 - CA27,3,103,5000\.00,5000\.00.*C2\.c\.1\.jpeg,Index 3 \(id · 좌표 없음\),,,,좌표 변환 보정 필요/);
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
// ── 목록 필터 · 정렬(소유자 세션 지시 2026-11-10): Step 4 리뷰 패널 — Contrast(실제) · Area · Width 범위 + 정렬
await page.locator('#unit3').selectOption('lot');
await page.locator('nav button[data-step="4"]').click();await page.locator('#step4.on').waitFor();
const p4n=async()=>page.evaluate(()=>window.__cw.PANELS.p4.items.map(it=>+it.d.Contrast.toFixed(2)));
const base4=await p4n();assert.ok(base4.length>=3,String(base4));   // Lot 별 CA20 → CA27: 없어진 Defect 3개
await page.locator('#p4Flt [data-f="sort"]').selectOption('c-d');await page.waitForTimeout(350);
assert.deepEqual(await p4n(),[...base4].sort((a,b)=>b-a));
assert.match(await page.locator('#p4Cnt').innerText(),/정렬: Contrast\(실제\) 큰 순/);
await page.locator('#p4Flt [data-f="c0"]').fill('35');await page.waitForTimeout(350);
assert.deepEqual(await p4n(),base4.filter(v=>v>=35).sort((a,b)=>b-a));
assert.match(await page.locator('#p4Cnt').innerText(),new RegExp(`필터에 맞는 것 ${base4.filter(v=>v>=35).length} / ${base4.length}개`));
// Area 는 화면 값(µm², 소수 2자리)으로: 82 px × 0.7708² = 48.72 → 최소 48.72 에 들어온다
await page.locator('#p4Flt [data-f="c0"]').fill('');await page.locator('#p4Flt [data-f="a0"]').fill('48.72');await page.locator('#p4Flt [data-f="a1"]').fill('48.72');await page.waitForTimeout(350);
const ar=await page.evaluate(()=>window.__cw.PANELS.p4.items.map(it=>it.d.area));assert.ok(ar.length&&ar.every(v=>v===82),String(ar));
await page.locator('#p4Flt [data-f="clear"]').click();await page.locator('#p4Flt [data-f="sort"]').selectOption('');await page.waitForTimeout(350);
assert.deepEqual(await p4n(),base4);assert.doesNotMatch(await page.locator('#p4Cnt').innerText(),/필터|정렬/);
// Width 필터(모든 합성 Defect 가 7.5) — 범위 밖이면 목록이 비고 '없습니다' 안내
await page.locator('#p4Flt [data-f="w0"]').fill('8');await page.waitForTimeout(350);
assert.equal((await p4n()).length,0);assert.match(await page.locator('#p4Color').innerText(),/Escape Defect 가 없습니다/);
await page.locator('#p4Flt [data-f="clear"]').click();await page.waitForTimeout(100);assert.deepEqual(await p4n(),base4);
// ── Step 5 (3단계, 소유자 확정 2026-11-10): 레시피 / Setup / Lot / Slot
//    5-1 폴더 핸들(가짜)로 훑기 — Slot 안 목록은 만들지 않고 Surface.flt 만 읽음 → 필터 · 정렬
//    5-2 걸러낸 Defect 만 Color · Gray 짝짓기 + 파일 확인 → 경로 CSV(사진 픽셀은 안 읽음)  5-3 Color 원본 + Gray Crop 정밀 조사
await page.locator('nav button[data-step="5"]').click();await page.locator('#step5.on').waitFor();
assert.equal(await page.locator('[data-b5="2"]').isDisabled(),true);
await page.evaluate(fx=>{const f=JSON.parse(fx),log=window.__fsLog={reads:[],lists:[]};
  const fh=(name,b64)=>({kind:'file',name,getFile:async()=>{log.reads.push(name);return new File([Uint8Array.from(atob(b64),ch=>ch.charCodeAt(0))],name)}});
  const mk=(name,path)=>({kind:'directory',name,path,kids:new Map(),async *entries(){log.lists.push(this.path);await new Promise(r=>setTimeout(r,5));yield* this.kids},
    async getFileHandle(n){await new Promise(r=>setTimeout(r,2));const h=[...this.kids.values()].find(k=>k.kind==='file'&&k.name.toLowerCase()===n.toLowerCase());if(!h)throw new DOMException('없음','NotFoundError');return h}});
  const root=mk('RCP','RCP/');
  for(const [p,b] of Object.entries(f)){const m=/^(CA\d+)\/LOTA\/(W0[12])\/(.+)$/.exec(p);if(!m)continue;const segs=['SETUP1','LOT_'+m[1],m[2],m[3]];let d=root;
    for(const s of segs.slice(0,-1)){if(!d.kids.has(s))d.kids.set(s,mk(s,d.path+s+'/'));d=d.kids.get(s)}d.kids.set(segs.at(-1),fh(segs.at(-1),b))}
  window.showDirectoryPicker=async()=>root},fixture);
const s51=await page.evaluate(async()=>{const seen=new Set(),beat=new Set(),el=document.getElementById('busy');
  const ob=new MutationObserver(()=>{if(el.hidden)return;const on=document.querySelector('#busyS li.on');seen.add(document.getElementById('busyT').textContent+' | '+(on?on.textContent:''));beat.add(document.getElementById('busyH').textContent.replace(/[\d.]+/g,'#'))});
  ob.observe(el,{subtree:true,childList:true,characterData:true,attributes:true});
  document.getElementById('bigAdd').click();
  await new Promise(r=>{const t=setInterval(()=>{if(el.hidden&&window.__cw.BIG.scans.length){clearInterval(t);r()}},20)});ob.disconnect();
  const L=window.__fsLog;return {seen:[...seen],beat:[...beat],reads:[...L.reads],lists:[...L.lists],scans:window.__cw.BIG.scans.map(s=>[s.lotPath,s.slotName,s.cols.n,s.errors.length])}});
assert.ok(s51.seen.some(t=>/^5-1 Contrast 모으기 \| ▶ ① 폴더 훑기/.test(t)),s51.seen.join('\n'));
assert.ok(s51.seen.some(t=>/^5-1 Contrast 모으기 \| ▶ ② Slot 마다 Surface\.flt 읽기/.test(t)),s51.seen.join('\n'));
assert.ok(s51.beat.some(t=>/^경과 #초 · 마지막 진행 #초 전/.test(t)),s51.beat.join('\n'));
assert.ok(s51.reads.length&&s51.reads.every(n=>/^(surface\.flt(\.md)?|productinfo\.ini)$/i.test(n)),s51.reads.join());   // 5-1 에서 읽는 파일 = Surface.flt(+ .md) · ProductInfo.ini 뿐
assert.deepEqual(s51.lists.filter(p=>/W0\d\/$/.test(p)),['RCP/SETUP1/LOT_CA27/W02/'],s51.lists.join());   // Slot 폴더 안은 목록을 만들지 않음(사진 수천 장이어도 빠름) — rev4: Surface.flt.md 가 Slot 바로 안에 없는 Slot(W02)만 하위 폴더를 보려고 한 번
assert.deepEqual(s51.scans,[['RCP/SETUP1/LOT_CA20','W01',4,0],['RCP/SETUP1/LOT_CA27','W01',3,0],['RCP/SETUP1/LOT_CA27','W02',0,1]]);
assert.match(await page.locator('#bigMsg').innerText(),/폴더 'RCP' → Lot 2개\(LOT_CA20, LOT_CA27\) · Slot 3개 · Defect 7개 — 제외한 Slot 1개: RCP\/SETUP1\/LOT_CA27\/W02\(잘못된 Record Size[\s\S]*사진은 읽지 않음/);
assert.match(await page.locator('#bigCnt').innerText(),/^Defect 7개/);
assert.match(await page.locator('#bigMsg').innerText(),/Surface\.flt\.md 위치\(Step 1 과 같은 순서로 찾음\): Slot 안 2 · 없음\(기본 배치\) 1/);   // rev4
const col=async j=>page.locator('#bigList .br').evaluateAll((els,j)=>els.map(e=>e.children[j].textContent),j);
const cs=(await col(4)).map(Number);assert.deepEqual(cs,[...cs].sort((a,b)=>b-a));assert.equal(cs[0],45);
assert.match(await page.locator('#bigList .bh').innerText(),/Contrast\(실제\) ▼/);
await page.locator('#bigFlt [data-f="c0"]').fill('36');await page.locator('#bigFlt [data-f="c1"]').fill('40');await page.waitForTimeout(350);
assert.deepEqual((await col(4)).map(Number),[40,36]);assert.match(await page.locator('#bigCnt').innerText(),/^Defect 2개 \(전체 7개 중/);
assert.match(await page.locator('#toB2').innerText(),/걸러낸 Defect 2개/);
await page.locator('#bigFlt [data-f="clear"]').click();await page.waitForTimeout(100);
await page.locator('#bigList .bh [data-sort="a"]').click();assert.deepEqual((await col(5)).map(Number).slice(0,2),[71.3,48.72]);   // Area 큰 순
await page.locator('#bigLot').selectOption({index:1});await page.waitForTimeout(100);assert.match(await page.locator('#bigCnt').innerText(),/^Defect 4개 \(전체 7개 중/);
await page.locator('#bigLot').selectOption('');await page.locator('#bigFlt [data-f="sort"]').selectOption('c-d');await page.waitForTimeout(350);
// 5-2: [다음] = 지금 목록(7개)으로 짝짓기 → 끝나면 CSV 자동 저장(다운로드)
await page.locator('#toB2').scrollIntoViewIfNeeded();
const rd0=await page.evaluate(()=>window.__fsLog.reads.length);
await page.evaluate(()=>{const b=document.getElementById('bigBase');b.value='Y:\\AOI\\SR';b.dispatchEvent(new Event('change'))});
// 저장 위치 고르기 창은 자동화할 수 없어 가짜 핸들로 받는다(누른 직후 위치를 고르고, 짝짓기가 끝나면 그 파일에 씀)
await page.evaluate(()=>{window.__picked=[];window.showSaveFilePicker=async o=>{window.__picked.push(o.suggestedName);return {name:o.suggestedName,createWritable:async()=>({write:async b=>{window.__saved={name:o.suggestedName,text:await b.text()}},close:async()=>{}})}}});
await page.locator('#toB2').click();await page.locator('#b5pairSt',{hasText:'CSV 저장:'}).waitFor();
const sv=await page.evaluate(()=>({picked:window.__picked,saved:window.__saved}));
assert.equal(sv.picked.length,1);assert.match(sv.saved.name,/^Defect_짝_RCP_\d{8}_\d{6}\.csv$/);
const csv5=sv.saved.text;
assert.equal(csv5.trim().split('\r\n').length,8);
assert.ok(csv5.includes('Y:\\AOI\\SR\\RCP\\SETUP1\\LOT_CA20\\W01\\C1.c.1.jpeg'),csv5);
assert.ok(csv5.includes('Y:\\AOI\\SR\\RCP\\SETUP1\\LOT_CA20\\W01\\F1.t.1.jpeg,1100.0,200.0,frameToChuckPlane'),csv5);
assert.match(csv5,/Color 만 \(Gray 없음\),LOT_CA20,RCP\/SETUP1\/LOT_CA20,W01,3,.*C2\.c\.1\.jpeg.*Index 3 \(id · 좌표 없음\).*Gray: 좌표 변환 보정 필요/);
assert.deepEqual(await page.locator('#b5sum .kpi b').allInnerTexts(),['2','1','0','4']);   // 짝 완료 · Color 만 · Gray 만 · 둘 다 없음
assert.match(await page.locator('#b5pairSt').innerText(),/Defect 7개 짝짓기 끝[\s\S]*CSV 저장: Defect_짝_RCP_/);
const rd1=await page.evaluate(rd0=>window.__fsLog.reads.slice(rd0),rd0);
assert.ok(rd1.length&&!rd1.some(n=>/\.jpe?g$/i.test(n)),rd1.join());   // 5-2 는 사진 픽셀을 읽지 않음(사진은 이름만)
assert.ok(rd1.includes('ColorImageGrabingInfo.ini')&&rd1.includes('ScanLog.txt'),rd1.join());   // rev3: Step 1 과 같은 방식 = Slot 의 글 파일을 모두(ScanLog 등) 읽음
// rev3: Slot 별 읽은 결과 표 — CA20 W01: 리스트 4 · Color 항목 2 · Color 연결 2 · 사진 2 · Gray 프레임 2 · 연결 1 · 사진 1
const sl5=await page.locator('#b5slotTbl tbody tr').allInnerTexts();assert.equal(sl5.length,2,sl5.join('\n'));
assert.match(sl5[0],/LOT_CA20\s+W01\s+4\s+2\s+2 \(50%\)\s+2 \(50%\)\s+2\s+frameToChuckPlane\.ini\s+1 \(25%\)\s+1 \(25%\)\s+11 \(사진 4\)/);
assert.match(sl5[1],/LOT_CA27\s+W01\s+3\s+2\s+1 \(33%\)\s+1 \(33%\)\s+2\s+/);
assert.equal(await page.evaluate(()=>window.__cw.BIG.scans.every(s=>s.errors.length||!!s.full)),true);   // 짝지은 Slot 은 Step 1 과 같은 결과(s.full)를 가짐
assert.equal(await page.locator('#b5list .br').count(),7);
await page.locator('#b5show').selectOption('ok');assert.equal(await page.locator('#b5list .br').count(),2);
// 5-3: 짝 완료 2개 — Color 원본 + Gray Crop · 진행 기록 · 경로
await page.locator('#toB3').click();await page.locator('#c5Color img').waitFor();await page.locator('#c5Gray canvas').waitFor();
await page.locator('#c5St',{hasText:'이 Defect 끝'}).waitFor();
const st5=await page.locator('#c5St').innerText();
assert.match(st5,/✔ Color 이미지 읽기 · 디코딩: C1\.c\.1\.jpeg/);assert.match(st5,/✔ Gray 프레임 읽기 · 디코딩: F1\.t\.1\.jpeg/);assert.match(st5,/✔ 크롭 · GL 계산 — 픽셀 \(1100\.\d, 200\.0\)/);
const in5=await page.locator('#c5Info').innerText();assert.match(in5,/Gray 경로\s*RCP\/SETUP1\/LOT_CA\d+\/W01\/F1\.t\.1\.jpeg/);assert.match(in5,/ROI mean/);
assert.equal(await page.locator('#c5list .br').count(),2);
await page.locator('#c5list').focus();await page.keyboard.press('ArrowDown');await page.locator('#c5Info',{hasText:'2 / 2'}).waitFor();
const [w5]=await Promise.all([page.waitForEvent('popup'),page.locator('#c5list .br').nth(0).dblclick()]);
await w5.waitForLoadState();assert.match(await w5.locator('.hd').innerText(),/RCP\/SETUP1\/LOT_CA\d+\] ID \d+ · /);await w5.close();
await page.locator('#b5okOnly').uncheck();assert.equal(await page.locator('#c5list .br').count(),7);
// 모두 미리 준비(로딩창 · 같은 Gray 프레임끼리) → 격자
await page.evaluate(()=>window.__cw.THUMB.clear());await page.locator('#b5prep').click();
await page.waitForFunction(()=>document.getElementById('busy').hidden&&window.__cw.THUMB.size===7);
await page.locator('[data-v5="grid"]').click();await page.locator('#c5gst',{hasText:'준비돼 있습니다'}).waitFor();
assert.equal(await page.locator('#c5grid .g5').count(),7);assert.equal(await page.locator('#c5grid .g5.st-ok img').count(),4);
await page.locator('#c5grid .g5').first().click();assert.equal(await page.locator('#c5one').isHidden(),false);
// 설정: Crop 크기는 짝짓기와 무관(경고 없음), X Offset 은 짝짓기와 달라짐(경고) — Step 2 칸과 같은 값
await page.locator('#c5opt [data-m="cropSz"]').fill('96');await page.locator('#c5opt [data-m="cropSz"]').dispatchEvent('change');
assert.equal(await page.locator('#cropSz').inputValue(),'96');assert.equal(await page.locator('#b5stale3').innerText(),'');
await page.locator('#c5opt [data-m="offX"]').fill('3');await page.locator('#c5opt [data-m="offX"]').dispatchEvent('change');
assert.equal(await page.locator('#offX').inputValue(),'3');assert.match(await page.locator('#b5stale3').innerText(),/설정이 바뀌었습니다/);
assert.equal(await page.locator('#b5opt [data-m="offX"]').inputValue(),'3');
await page.locator('#c5opt [data-m="offX"]').fill('0');await page.locator('#c5opt [data-m="offX"]').dispatchEvent('change');await page.locator('#c5opt [data-m="cropSz"]').fill('160');await page.locator('#c5opt [data-m="cropSz"]').dispatchEvent('change');
assert.equal(await page.locator('#b5stale3').innerText(),'');
// 중지: 큰 목록 짝짓기를 [중지] 하면 남은 것은 '확인 안 함'
// 많은 Defect: 합성 30만 개(Slot 3개)도 열 배열로 바로 필터 · 정렬(표는 보이는 줄만 그림)
await page.locator('[data-b5="1"]').click();
const perf=await page.evaluate(async()=>{const c=window.__cw,REC=c.REC,N=100000,mk=seed=>{const b=new ArrayBuffer(N*REC),dv=new DataView(b);for(let i=0;i<N;i++){const o=i*REC;dv.setFloat64(o+8,i%1000*300,true);dv.setFloat64(o+16,(i/1000|0)*3000,true);dv.setInt32(o+40,i,true);dv.setFloat64(o+80,(i*7+seed)%500+1,true);dv.setFloat64(o+88,(i%90)/10,true);dv.setFloat64(o+136,((i*31+seed)%6000)/100,true)}return b};
  const es=[];for(let k=0;k<3;k++)es.push({path:`HUGE/S1/LOT${k}/W0${k}/Surface.flt`,file:new File([mk(k)],'Surface.flt')});
  const t0=performance.now();await c.addBigEntries(es);const t1=performance.now();
  document.querySelector('#bigFlt [data-f="c0"]').value='59.9';c.bigRefresh();const t2=performance.now();
  return {load:t1-t0,flt:t2-t1,m:c.BIG.view.m,total:c.BIG.view.total,rows:document.querySelectorAll('#bigList .br').length,first:+document.querySelector('#bigList .br').children[4].textContent}});
assert.equal(perf.total,300007);assert.ok(perf.m>0&&perf.m<perf.total/50,JSON.stringify(perf));assert.ok(perf.rows<80,JSON.stringify(perf));assert.ok(perf.first>=59.9);
assert.ok(perf.load<15000&&perf.flt<5000,JSON.stringify(perf));console.log('step5 30만 Defect:',JSON.stringify(perf));
// 중지: 5-2 짝짓기를 시작하자마자 [중지] → 처리 못 한 것 = '확인 안 함', 자동 CSV 저장 안 함
const stop=await page.evaluate(async()=>{const c=window.__cw;const p=c.b5Pair({h:null});c.BIG.stop=true;await p;const P=c.BIG.pairs;return {n:P.length,skip:P.filter(x=>x.st==='skip').length}});
assert.equal(stop.n,500);assert.ok(stop.skip>0,JSON.stringify(stop));
await page.locator('[data-b5="2"]').click();assert.match(await page.locator('#b5pairSt').innerText(),/중지로 확인 안 함 \d+[\s\S]*중지해서 CSV 를 자동 저장하지 않았습니다/);
// ── rev4: 5-1 이 Surface.flt.md 를 Step 1 과 같은 순서로 찾음 + 5-2 안전장치(5-1 값 ↔ Step 1 값) ─────────────
//    md 가 x · y 자리를 바꿔 적은 경우(다른 장비 SW 가정, 바이트도 그 자리)를 Lot 폴더 · Slot 하위 폴더에 두어도 5-1 좌표가 맞아야 한다.
const scen=async opt=>{const pg=await browser.newPage();const er=[];pg.on('pageerror',e=>er.push(String(e)));
  await pg.goto('file://'+resolve(root,'AOI_Contrast_Wizard_rev4.html'));
  const r=await pg.evaluate(async ({fx,opt})=>{const f=JSON.parse(fx),c=window.__cw,lists=[];
    const b=k=>Uint8Array.from(atob(f['CA20/LOTA/W01/'+k]),ch=>ch.charCodeAt(0));
    const mk=(name,path)=>({kind:'directory',name,path,kids:new Map(),async *entries(){lists.push(this.path);yield* this.kids},
      async getFileHandle(n){const h=[...this.kids.values()].find(k=>k.kind==='file'&&k.name.toLowerCase()===n.toLowerCase());if(!h)throw new DOMException('없음','NotFoundError');return h}});
    const put=(d,name,bytes)=>d.kids.set(name,{kind:'file',name,getFile:async()=>new File([bytes],name)});
    const R=mk('RCP','RCP/'),S1=mk('SETUP1','RCP/SETUP1/'),L=mk('LOT_CA20','RCP/SETUP1/LOT_CA20/'),W=mk('W01','RCP/SETUP1/LOT_CA20/W01/'),SUB=mk('Sub','RCP/SETUP1/LOT_CA20/W01/Sub/');
    R.kids.set('SETUP1',S1);S1.kids.set('LOT_CA20',L);L.kids.set('W01',W);W.kids.set('Sub',SUB);
    const orig=b('Surface.flt').buffer.slice(0),flt=new Uint8Array(orig.slice(0));let md=b('Surface.flt.md');
    if(opt.swap){for(let o=0;o+152<=flt.length;o+=152){const x=flt.slice(o+8,o+16);flt.copyWithin(o+8,o+16,o+24);flt.set(x,o+16)}
      md=new TextEncoder().encode('<?xml version="1.0"?><Record size="152"><Field name="x" type="double" offset="16"/><Field name="y" type="double" offset="8"/><Field name="Contrast" type="double" offset="136"/><Field name="area" type="double" offset="80"/></Record>')}
    for(const k of Object.keys(f)){const m=/^CA20\/LOTA\/W01\/(.+)$/.exec(k);if(!m||m[1]==='Surface.flt.md'||m[1]==='Surface.flt')continue;put(W,m[1],b(m[1]))}
    put(W,'Surface.flt',flt);put({slot:W,lot:L,sub:SUB}[opt.md],'Surface.flt.md',md);
    await c.bigPickHandle(R);const s=c.BIG.scans[0],exp=c.parseFltCols(orig).cols;
    const r={mdAt:s.mdAt,mdPath:s.mdPath,xOk:[...s.cols.x].every((v,i)=>v===exp.x[i])&&[...s.cols.y].every((v,i)=>v===exp.y[i]),n:s.cols.n,
      msg:document.getElementById('bigMsg').innerText,slotListed:lists.includes('RCP/SETUP1/LOT_CA20/W01/')};
    if(opt.corrupt){for(let i=0;i<s.cols.n;i++)s.cols.x[i]+=5000;s.cols.c[0]=-1;   // 5-1 값이 Step 1 과 다른 경우(안전장치 시험): 좌표 전부 + Contrast 하나
      document.querySelector('#bigFlt [data-f="c0"]').value='0';c.bigRefresh();r.m0=c.BIG.view.m}
    await c.b5Pair(null);
    r.m=c.BIG.view.m;r.pairs=c.BIG.pairs.map(p=>[p.i,p.st,p.c&&p.c.file,p.g&&p.g.file,p.g&&+p.g.px.toFixed(2)]).sort((a,b)=>a[0]-b[0]);
    r.reread=s.reread?s.reread.text:null;r.pairSt=document.getElementById('b5pairSt').innerText;r.bigMsg=document.getElementById('bigMsg').innerText;
    r.row=[...document.querySelectorAll('#b5slotTbl tbody tr')].map(x=>x.innerText).join('\n');r.yellow=!!document.querySelector('#b5slotTbl tbody tr[style*="warnbg"]');
    r.same=c.colsDiff(s.cols,s.full.defects);return r},{fx:fixture,opt});
  await pg.close();return {...r,er}};
const base=await scen({md:'slot'});
assert.equal(base.mdAt,'slot');assert.equal(base.xOk,true);assert.equal(base.slotListed,false);assert.equal(base.reread,null);assert.equal(base.n,4);
assert.ok(!/Surface\.flt\.md 위치/.test(base.msg),base.msg);   // 모두 Slot 안이면 따로 알리지 않음
assert.match(base.row,/Slot 안 · 값 같음/);assert.equal(base.same,null);assert.deepEqual(base.er,[]);
const lotSw=await scen({md:'lot',swap:true});   // rev3 까지: 5-1 좌표 전부 틀림 → Color 0
assert.equal(lotSw.mdAt,'up');assert.equal(lotSw.mdPath,'RCP/SETUP1/LOT_CA20/Surface.flt.md');assert.equal(lotSw.xOk,true,JSON.stringify(lotSw));
assert.match(lotSw.msg,/Surface\.flt\.md 위치\(Step 1 과 같은 순서로 찾음\): 위쪽 폴더 1/);
assert.deepEqual(lotSw.pairs,base.pairs);assert.equal(lotSw.reread,null);assert.match(lotSw.row,/위쪽 폴더 · 값 같음/);assert.deepEqual(lotSw.er,[]);
const subSw=await scen({md:'sub',swap:true});
assert.equal(subSw.mdAt,'sub');assert.equal(subSw.mdPath,'RCP/SETUP1/LOT_CA20/W01/Sub/Surface.flt.md');assert.equal(subSw.xOk,true);assert.equal(subSw.slotListed,true);
assert.match(subSw.msg,/Slot 하위 폴더 1/);assert.deepEqual(subSw.pairs,base.pairs);assert.equal(subSw.reread,null);assert.deepEqual(subSw.er,[]);
// 안전장치: 5-1 값이 Step 1 과 다르면 Step 1 값으로 바꾸고 5-1 필터를 다시 걸어 목록을 다시 만든다(Contrast 를 틀리게 읽어 빠졌던 Defect 도 돌아옴)
const guard=await scen({md:'slot',corrupt:true});
assert.equal(guard.m0,3);assert.equal(guard.m,4);assert.equal(guard.reread,'x 4개 · Contrast 1개');assert.deepEqual(guard.pairs,base.pairs);
assert.match(guard.pairSt,/Slot 1개는 5-1 에서 모은 값이 Step 1 방식으로 읽은 값과 달라 Step 1 값으로 바꾸고 5-1 필터를 다시 걸었습니다\(Defect 3개 → 4개\): W01 — x 4개 · Contrast 1개/);
assert.match(guard.bigMsg,/Defect 3개 → 4개/);assert.match(guard.row,/Slot 안 · 값 다름 → Step 1 값으로 \(x 4개 · Contrast 1개\)/);assert.equal(guard.yellow,true);
assert.equal(guard.same,null);assert.deepEqual(guard.er,[]);
assert.deepEqual(errors,[]);assert.deepEqual(requests,[]);
await browser.close();
console.log('test_contrast_wizard_rev4: passed');
