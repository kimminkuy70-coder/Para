// AOI_Contrast_Wizard_rev6.html 자동 시험(rev6 = rev5 + 5-3 흑백 GL(원) 측정 · 정렬 · 두 손잡이 범위 바 · 측정 원 그리기 창 · 사진에 원 표시. 아래는 rev5 시험 그대로 + rev6 시험)
// 바탕: rev5 시험(Para #50, rev5 = rev4 + Step 5 Color · Gray 매칭 = Para colorgray.py 그대로(5-1 에서 계산) · 5-2 결과 목록 · 사진 새 창 · 보정 설정 없음. Step 1 ~ 4 부분은 rev4 시험과 같음). 폴더 고르기 창은 자동화할 수 없어 window.__cw.addEntries 로 합성 파일을 넣는다.
// 실행: PARA_TEST_NODE_MODULES=<playwright 가 있는 node_modules> node tools/test_contrast_wizard_rev6.mjs
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
await page.goto('file://'+resolve(root,'AOI_Contrast_Wizard_rev6.html'));
assert.match(await page.locator('header .lim').innerText(),/간단 버전: Reference 이미지 없음 · Step 5 Color · Gray 매칭 = Para 프로그램과 같은 계산/);
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
// ── Step 5 rev5 (소유자 2026-11-10 "프로그램에 있는 기능을 최우선으로 · 설정은 아예 없애 · 결과는 목록, 새 창에서 큰 화면으로 사진들만")
//    5-1 = Surface.flt + 매칭 파일 3개(이름으로 바로)만 읽고 Para colorgray.py 와 같은 계산으로 짝을 미리 구함 → 5-2 = 사진 파일 이름만 확인 · 결과 목록 · CSV · 사진 새 창
//    5-3 = Gray Crop = Color 시야(프로그램 Crop). 보정 설정 없음.
// 설정 없앰: 결함 좌표 · Pixel Size · Color 허용오차 · 반전 · Offset 칸이 없고 opts() 는 종전 기본값
const noSet=await page.evaluate(()=>({ids:['coordSrc','pix','ctol','flipX','flipY','offX','offY','b5opt','c5opt'].filter(id=>document.getElementById(id)),o:window.__cw.opts()}));
assert.deepEqual(noSet.ids,[]);assert.deepEqual([noSet.o.pix,noSet.o.ctol,noSet.o.coord,noSet.o.flipX,noSet.o.flipY,noSet.o.offX,noSet.o.offY],[0.7708,5,'xy',false,false,0,0]);
// 순수 함수 = colorgray.py 와 같음(파싱 · 변환 파일 키 · 반올림 · crop_size · choose_frame 동점 = 앞)
const pf=await page.evaluate(()=>{const c=window.__cw;
  const cols=c.cgColors('[a.c.1.jpeg]\nFaultX = 1100\nFaultY=200\nRecipeNumber=0\n[b.jpeg]\nX=5\nY=6\n[c.jpeg]\nRecipeNumber=\nFaultX=\nFaultY=1\n');
  const fr=c.cgFrames('Version=1\n"F1.t.1.jpeg";0;0\nF2.t.2.JPG\t1000\t0\nbad,x,1\nF3.t.jpeg,5,6\n');
  const t={inv:[[1,0],[0,1]],off:[0,0]},tie=c.cgChoose(1584,512,[{file:'A',x:0,y:0},{file:'B',x:0,y:0}],t);
  return {cols:cols.map(x=>[x.file,...c.cgFault(x).map(v=>Number.isNaN(v)?'NaN':v),String(c.cgRecipe(x))]),
    fr:fr.map(f=>[f.file,f.x,f.y,f.recipe]),keys:['frameToChuckPlane.ini','FRAMETOCHUCKPLANE.2.ini','frameToChuckPlane.ab.ini','x.ini'].map(k=>String(c.cgTfKey(k))),
    round:[c.pyRound(2.5),c.pyRound(3.5),c.pyRound(0.5),c.pyRound(838.07)],crop:c.cgCropSize({}),crop2:c.cgCropSize({ImageSizeX:'1380',ImageSizeY:'1036',PixelSizeX:'0.462440013885498',PixelSizeY:'0.462249010801315'}),tie:tie.frame.file,tieN:tie.n}});
assert.deepEqual(pf.cols,[['a.c.1.jpeg',1100,200,'0'],['b.jpeg',5,6,'1'],['c.jpeg','NaN',1,'1']]);   // RecipeNumber 없음 · 빈 칸 = 1(프로그램 'or 1')
assert.deepEqual(pf.fr,[['"F1.t.1.jpeg"',0,0,null],['F2.t.2.JPG',1000,0,2],['F3.t.jpeg',5,6,null]]);   // 따옴표가 붙으면 레시피 번호 못 읽음(colorgray.parse_frames 와 같음)
assert.deepEqual(pf.keys,['null','2','ab','undefined']);assert.deepEqual(pf.round,[2,4,0,838]);
assert.deepEqual(pf.crop,{cw:838,ch:629,ow:1380,oh:1036});assert.deepEqual(pf.crop2,{cw:829,ch:622,ow:1380,oh:1036});assert.equal(pf.tie,'A');assert.equal(pf.tieN,2);

await page.locator('nav button[data-step="5"]').click();await page.locator('#step5.on').waitFor();
assert.equal(await page.locator('[data-b5="2"]').isDisabled(),true);
assert.match(await page.locator('[data-b5="2"]').innerText(),/결과 목록 · 사진 새 창 · CSV/);
const fakeTree=`window.__mkTree=(f,map,opt)=>{opt=opt||{};const log=window.__fsLog={reads:[],lists:[]};
  const fh=(name,path,b)=>({kind:'file',name,getFile:async()=>{log.reads.push(name);if(opt.bad&&opt.bad.includes(path))throw new DOMException('A requested file or directory could not be found at the time an operation was processed.','NotFoundError');
    return new File([typeof b==='string'?Uint8Array.from(atob(b),ch=>ch.charCodeAt(0)):b],name)}});
  const mk=(name,path)=>({kind:'directory',name,path,kids:new Map(),async *entries(){log.lists.push(this.path);await new Promise(r=>setTimeout(r,2));for(const kv of this.kids)if(!(opt.blockIni&&/\.ini$/i.test(kv[0])))yield kv},
    async getFileHandle(n){if(opt.blockIni&&/\.ini$/i.test(n))throw new TypeError("Failed to execute 'getFileHandle' on 'FileSystemDirectoryHandle': Name is not allowed.");const fl=opt.flaky&&opt.flaky[n];if(fl>0){opt.flaky[n]=fl-1;(log.err||(log.err=[])).push(n);throw new DOMException('The I/O operation has been aborted','NotReadableError')}
      const h=[...this.kids.values()].find(k=>k.kind==='file'&&(opt.cs?k.name===n:k.name.toLowerCase()===n.toLowerCase()));if(!h)throw new DOMException('없음','NotFoundError');return h}});
  const root=mk('RCP','RCP/');
  for(const [p,b] of Object.entries(f)){const segs=map(p);if(!segs)continue;let d=root;for(const s of segs.slice(0,-1)){if(!d.kids.has(s))d.kids.set(s,mk(s,d.path+s+'/'));d=d.kids.get(s)}
    d.kids.set(segs.at(-1),fh(segs.at(-1),'RCP/'+segs.join('/'),b))}
  return root}`;
await page.evaluate(src=>{(0,eval)(src)},fakeTree);
await page.evaluate(fx=>{const f=JSON.parse(fx);const root=window.__mkTree(f,p=>{const m=/^(CA\d+)\/LOTA\/(W0[12])\/(.+)$/.exec(p);return m?['SETUP1','LOT_'+m[1],m[2],m[3]]:null});window.showDirectoryPicker=async()=>root},fixture);
const s51=await page.evaluate(async()=>{const seen=new Set(),el=document.getElementById('busy');
  const ob=new MutationObserver(()=>{if(el.hidden)return;const on=document.querySelector('#busyS li.on');seen.add(document.getElementById('busyT').textContent+' | '+(on?on.textContent:''))});
  ob.observe(el,{subtree:true,childList:true,characterData:true,attributes:true});
  document.getElementById('bigAdd').click();
  await new Promise(r=>{const t=setInterval(()=>{if(el.hidden&&window.__cw.BIG.scans.length){clearInterval(t);r()}},20)});ob.disconnect();
  const L=window.__fsLog;return {seen:[...seen],reads:[...L.reads],lists:[...L.lists],scans:window.__cw.BIG.scans.map(s=>[s.lotPath,s.slotName,s.cols.n,s.errors.length]),
    cg:window.__cw.BIG.scans.filter(s=>s.cg&&s.cg.plan).map(s=>[s.slotName,s.cg.colors.length,s.cg.plan.hits,s.cg.plan.mode,s.cg.path])}});
assert.ok(s51.seen.some(t=>/^5-1 Contrast 모으기 \| ▶ ② Slot 마다 Surface\.flt \+ 매칭 파일 읽기/.test(t)),s51.seen.join('\n'));
// 5-1 에서 여는 파일 = Surface.flt(+ .md) · ProductInfo · 매칭 파일 3개 뿐(사진 · ScanLog 등 다른 파일은 안 엶)
assert.ok(s51.reads.length&&s51.reads.every(n=>/^(surface\.flt(\.md)?|productinfo\.ini|colorimagegrabinginfo\.ini|scanresultimagelist\.txt|frametochuckplane\.ini)$/i.test(n)),s51.reads.join());
assert.ok(s51.reads.includes('ColorImageGrabingInfo.ini')&&s51.reads.includes('frameToChuckPlane.ini'),s51.reads.join());
assert.deepEqual(s51.lists.filter(p=>/W01\/$/.test(p)),[],s51.lists.join());   // 매칭 파일이 바로 안에 있는 Slot 은 안을 나열하지 않음(사진 수천 장이어도 빠름)
assert.deepEqual(s51.scans,[['RCP/SETUP1/LOT_CA20','W01',4,0],['RCP/SETUP1/LOT_CA27','W01',3,0],['RCP/SETUP1/LOT_CA27','W02',0,1]]);
assert.deepEqual(s51.cg,[['W01',2,1,0,'RCP/SETUP1/LOT_CA20/W01'],['W01',2,1,0,'RCP/SETUP1/LOT_CA27/W01']]);
assert.match(await page.locator('#bigMsg').innerText(),/Color · Gray 매칭\(Para 프로그램과 같은 계산, 사진은 아직 안 읽음\): Color 항목 4개 중 Gray 위치 2개 · Defect 7개 중 Color 연결 3개/);
assert.match(await page.locator('#bigCnt').innerText(),/^Defect 7개/);
const col=async j=>page.locator('#bigList .br').evaluateAll((els,j)=>els.map(e=>e.children[j].textContent),j);
const cs=(await col(6)).map(Number);assert.deepEqual(cs,[...cs].sort((a,b)=>b-a));assert.equal(cs[0],45);
assert.deepEqual((await col(14)).sort(),['Color · Gray','Color · Gray','Color 만','✖ 짝 없음','✖ 짝 없음','✖ 짝 없음','✖ 짝 없음']);   // 5-1 목록에 매칭 칸(사진 파일 확인 전)
assert.match(await page.locator('#bigList .bh').innerText(),/ID\s+첫번째 분류\s+재분류\s+Contrast\(실제\) ▼[\s\S]*Color · Gray 매칭/);
assert.deepEqual([...new Set(await col(4)),...new Set(await col(5))],['#0','#0']);assert.match(await page.locator('#bigCls').innerText(),/첫번째 분류\s+#0\s+7\s+재분류\s+#0\s+7/);   // ManReClassify.ini 가 없으면 코드 번호
await page.locator('#bigFlt [data-f="c0"]').fill('36');await page.locator('#bigFlt [data-f="c1"]').fill('40');await page.waitForTimeout(350);
assert.deepEqual((await col(6)).map(Number),[40,36]);assert.match(await page.locator('#bigCnt').innerText(),/^Defect 2개 \(전체 7개 중/);
assert.match(await page.locator('#toB2').innerText(),/걸러낸 Defect 2개 결과 목록 · 사진 확인/);
await page.locator('#bigFlt [data-f="clear"]').click();await page.waitForTimeout(100);
await page.locator('#bigList .bh [data-sort="a"]').click();assert.deepEqual((await col(7)).map(Number).slice(0,2),[71.3,48.72]);   // Area 큰 순
await page.locator('#bigLot').selectOption({index:1});await page.waitForTimeout(100);assert.match(await page.locator('#bigCnt').innerText(),/^Defect 4개 \(전체 7개 중/);
await page.locator('#bigLot').selectOption('');
// Lot 제외(소유자 "5-1 에서 필터로 제외할 Lot 고를 수 있게"): 체크를 끄면 그 Lot 이 목록에서 빠지고, 다시 켜면 돌아옴 · 모두 끄기/켜기
assert.match(await page.locator('#bigLotSum').innerText(),/^Lot 제외: 없음 \(전체 2개\)$/);await page.locator('#bigLotSum').click();
{const ck=page.locator('#bigLotOff [data-lotoff]');assert.equal(await ck.count(),2);const n0=+(await page.locator('#bigLotOff .clsck').first().locator('.muted').innerText());
  await ck.first().uncheck();assert.match(await page.locator('#bigCnt').innerText(),new RegExp(`^Defect ${7-n0}개 \\(전체 7개 중`));
  assert.equal(await page.locator('#bigLotSum').innerText(),'Lot 제외 1개 / 전체 2개');
  assert.equal(await page.evaluate(()=>{const c=window.__cw,V=c.BIG.view,off=[...c.BIG.lotOff][0];let k=0;for(let j=0;j<V.m;j++)if(V.src[V.gs[j]].lotPath===off)k++;return k}),0);
  await page.locator('#bigLotOff [data-lotall]').click();assert.equal(await page.locator('#bigLotSum').innerText(),'Lot 제외: 없음 (전체 2개)');assert.match(await page.locator('#bigCnt').innerText(),/^Defect 7개/);
  await page.locator('#bigLotOff [data-lotall]').click();assert.match(await page.locator('#bigCnt').innerText(),/전체 7개 중|^레시피 폴더|^Defect 0개/);assert.equal(await page.evaluate(()=>window.__cw.BIG.view.m),0);
  await page.locator('#bigLotOff [data-lotall]').click();assert.match(await page.locator('#bigCnt').innerText(),/^Defect 7개/);await page.locator('#bigLotSum').click()}await page.locator('#bigFlt [data-f="sort"]').selectOption('c-d');await page.waitForTimeout(350);
// 5-2: [다음] = 지금 목록(7개) — 사진 파일은 이름만 확인(어떤 파일도 열지 않음) → 결과 목록 · CSV 자동 저장
await page.locator('#toB2').scrollIntoViewIfNeeded();
const rd0=await page.evaluate(()=>window.__fsLog.reads.length);
await page.evaluate(()=>{const b=document.getElementById('bigBase');b.value='Y:\\AOI\\SR';b.dispatchEvent(new Event('change'))});
await page.evaluate(()=>{window.__picked=[];window.showSaveFilePicker=async o=>{window.__picked.push(o.suggestedName);return {name:o.suggestedName,createWritable:async()=>({write:async b=>{window.__saved={name:o.suggestedName,text:await b.text()}},close:async()=>{}})}}});
await page.locator('#toB2').click();await page.locator('#b5pairSt',{hasText:'CSV 저장:'}).waitFor();
const sv=await page.evaluate(()=>({picked:window.__picked,saved:window.__saved}));
assert.equal(sv.picked.length,1);assert.match(sv.saved.name,/^Defect_짝_RCP_\d{8}_\d{6}\.csv$/);
const csv5=sv.saved.text;assert.equal(csv5.trim().split('\r\n').length,8);
assert.match(csv5.split('\r\n')[0],/Color이미지,Color경로,Color연결,FaultX,FaultY,Gray프레임,Gray경로,GrayPX\(3168x1024기준\),GrayPY\(3168x1024기준\),후보프레임,Gray계산,좌표기준,CropW,CropH,매칭폴더,Gray프레임목록,변환,이유/);
assert.ok(csv5.includes('Y:\\AOI\\SR\\RCP\\SETUP1\\LOT_CA20\\W01\\C1.c.1.jpeg,좌표 (5 µm 안),1100.00,200.00,F1.t.1.jpeg,Y:\\AOI\\SR\\RCP\\SETUP1\\LOT_CA20\\W01\\F1.t.1.jpeg,1100.0,200.0,2,Color 좌표,그대로,838,629,Y:\\AOI\\SR\\RCP\\SETUP1\\LOT_CA20\\W01,'),csv5);
assert.match(csv5,/둘 다 없음,LOT_CA20,RCP\/SETUP1\/LOT_CA20,W01,4,.*Color 파일 없음: Section2 .*Gray: 좌표 값을 읽을 수 없음/);   // FileName 키는 프로그램처럼 안 씀(섹션 이름 = 파일)
assert.deepEqual(await page.locator('#b5sum .kpi b').allInnerTexts(),['2','0','0','5']);   // 짝 완료 · Color 만 · Gray 만 · 둘 다 없음
const pst5=await page.locator('#b5pairSt').innerText();
assert.match(pst5,/Defect 7개 확인 끝[\s\S]*Color 연결: [\s\S]*CSV 저장: Defect_짝_RCP_/);assert.match(pst5,/좌표 \(5 µm 안\) 2/);assert.match(pst5,/Index \(Color 좌표 없음\) 1/);
assert.deepEqual(await page.evaluate(rd0=>window.__fsLog.reads.slice(rd0),rd0),[]);   // 5-2 는 파일을 하나도 열지 않음(이름 목록만)
const sl5=await page.locator('#b5slotTbl tbody tr').allInnerTexts();assert.equal(sl5.length,2,sl5.join('\n'));
assert.match(sl5[0],/LOT_CA20\s+W01\s+4\s+2\s+2 \(50%\)\s+1 \(25%\)\s+2\s+frameToChuckPlane\.ini\s+1 \(25%\)\s+1 \(25%\)\s+그대로\s+매칭 폴더 RCP\/SETUP1\/LOT_CA20\/W01/);
assert.match(sl5[1],/LOT_CA27\s+W01\s+3\s+2\s+1 \(33%\)\s+1 \(33%\)\s+2\s+frameToChuckPlane\.ini\s+1 \(33%\)\s+1 \(33%\)\s+그대로/);
assert.equal(await page.locator('#b5list .br').count(),7);
await page.locator('#b5show').selectOption('ok');assert.equal(await page.locator('#b5list .br').count(),2);
// 결과 목록에 사진 전체 경로 칸(원본 폴더 경로 + 고른 폴더부터의 경로)
assert.deepEqual((await page.locator('#b5list .br').nth(0).locator('span').allInnerTexts()).slice(12),
  ['Y:\\AOI\\SR\\RCP\\SETUP1\\LOT_CA27\\W01\\C1.c.1.jpeg','Y:\\AOI\\SR\\RCP\\SETUP1\\LOT_CA27\\W01\\F1.t.1.jpeg']);
// 전체 경로 = [원본 폴더 경로(PC)] + 고른 폴더부터: 상위 폴더 · 고른 폴더 자체(이름이 같으면 겹치지 않게) · UNC · 비었으면 그대로
const pcp=await page.evaluate(()=>{const c=window.__cw,b=document.getElementById('bigBase'),old=b.value,set=v=>{b.value=v;return c.pcPath('RCP/SETUP1/LOT_A/W01/x.c.1.jpeg')};
  const r=[set('Y:\\AOI\\SR'),set('Y:\\AOI\\SR\\RCP\\'),set('"\\\\nas01\\aoi\\RCP"'),set('/mnt/aoi'),set('')];b.value=old;return r});
assert.deepEqual(pcp,['Y:\\AOI\\SR\\RCP\\SETUP1\\LOT_A\\W01\\x.c.1.jpeg','Y:\\AOI\\SR\\RCP\\SETUP1\\LOT_A\\W01\\x.c.1.jpeg','\\\\nas01\\aoi\\RCP\\SETUP1\\LOT_A\\W01\\x.c.1.jpeg','/mnt/aoi/RCP/SETUP1/LOT_A/W01/x.c.1.jpeg','RCP/SETUP1/LOT_A/W01/x.c.1.jpeg']);
assert.equal(await page.locator('#bigBase1').inputValue(),'Y:\\AOI\\SR');   // 5-1 · 5-2 두 칸은 같은 값
// 사진 새 창(큰 화면 · 사진만): 줄 더블 클릭 → Color · Gray Crop(Color 크기) · Gray 프레임, 새 창 ↓ = 목록도 이동, 목록 ↓ = 새 창도 바뀜
const [pw]=await Promise.all([page.waitForEvent('popup'),page.locator('#b5list .br').nth(0).dblclick()]);
await pw.locator('#ff canvas').waitFor();
const capOf=()=>pw.evaluate(()=>[...document.querySelectorAll('figcaption')].map(f=>({b:f.querySelector('b').textContent,pp:(f.querySelector('.pp')||{}).textContent||'',text:f.textContent,tip:f.title})));
const pw1=await pw.evaluate(()=>({hd:document.getElementById('hd').textContent,
  c:!!document.querySelector('#fc canvas'),x:[document.querySelector('#fx canvas').width,document.querySelector('#fx canvas').height],tables:document.querySelectorAll('table,dl,button,input:not(#pwLock)').length}));
assert.match(pw1.hd,/^1 \/ 2 · LOT_CA27 · W01 · ID \d+ · #0 · Contrast /);   // 분류도 머리에
assert.doesNotMatch(pw1.hd,/원본 폴더 경로/);
// 사진 파일명 + 전체 경로(소유자 "사진 파일명뿐만 아니라 전체 경로도") — 칸 제목(사진 위, 사진을 가리지 않음), 마우스를 올려도 경로
const cap1=await capOf();
assert.deepEqual(cap1.map(c=>c.b),['C1.c.1.jpeg','F1.t.1.jpeg','F1.t.1.jpeg']);
assert.deepEqual(cap1.map(c=>c.pp),['Y:\\AOI\\SR\\RCP\\SETUP1\\LOT_CA27\\W01\\C1.c.1.jpeg','Y:\\AOI\\SR\\RCP\\SETUP1\\LOT_CA27\\W01\\F1.t.1.jpeg','Y:\\AOI\\SR\\RCP\\SETUP1\\LOT_CA27\\W01\\F1.t.1.jpeg']);
assert.deepEqual(cap1.map(c=>c.tip),cap1.map(c=>c.pp));
assert.match(cap1[2].text,/^Gray 프레임 · F1\.t\.1\.jpeg · 픽셀 \(1100\.0, 200\.0\) · 빨간 네모 = Defect · 노란 상자 = Crop 범위Y:/);
assert.equal(await pw.evaluate(()=>[...document.querySelectorAll('figure')].every(f=>f.firstElementChild.tagName==='FIGCAPTION'&&f.querySelector('.im canvas'))),true);
// 원본 폴더 경로를 비우면 고른 폴더부터 + 안내, 다시 적으면 바로 PC 경로로 다시 그림
await page.locator('#bigBase').fill('');await page.locator('#bigBase').dispatchEvent('change');assert.equal(await page.locator('#bigBase1').inputValue(),'');
await pw.locator('#hd',{hasText:'원본 폴더 경로(PC)'}).waitFor();assert.equal((await capOf())[0].pp,'RCP/SETUP1/LOT_CA27/W01/C1.c.1.jpeg');
await page.locator('#bigBase').fill('Y:\\AOI\\SR\\RCP');await page.locator('#bigBase').dispatchEvent('change');   // 고른 폴더 자체 경로를 적어도 됨
await pw.waitForFunction(()=>document.querySelector('#fc .pp').textContent.startsWith('Y:'));assert.equal((await capOf())[0].pp,'Y:\\AOI\\SR\\RCP\\SETUP1\\LOT_CA27\\W01\\C1.c.1.jpeg');
assert.equal(await page.locator('#bigBase1').inputValue(),'Y:\\AOI\\SR\\RCP');assert.equal(await page.evaluate(()=>localStorage.getItem('cw.bigBase')),'Y:\\AOI\\SR\\RCP');
assert.equal(pw1.c,true);assert.deepEqual(pw1.x,[1380,1036]);assert.equal(pw1.tables,0);   // 사진만(표 · 단추 없음)
// 큰 화면에서 방향키(소유자 "방향키로 다음 목록"): ↓ → = 다음, ↑ ← = 이전, 끝에서는 멈춤, Home · End — 목록도 같이 움직임
await pw.keyboard.press('ArrowDown');await pw.locator('#hd',{hasText:/^2 \/ 2/}).waitFor();
assert.equal(await page.evaluate(()=>window.__cw.PW.V.sel),1);
await pw.keyboard.press('ArrowRight');await pw.waitForTimeout(150);assert.match(await pw.locator('#hd').innerText(),/^2 \/ 2/);   // 마지막에서 멈춤
await pw.keyboard.press('ArrowLeft');await pw.locator('#hd',{hasText:/^1 \/ 2/}).waitFor();assert.equal(await page.evaluate(()=>window.__cw.PW.V.sel),0);
await pw.keyboard.press('ArrowRight');await pw.locator('#hd',{hasText:/^2 \/ 2/}).waitFor();
await pw.keyboard.press('Home');await pw.locator('#hd',{hasText:/^1 \/ 2/}).waitFor();await pw.keyboard.press('End');await pw.locator('#hd',{hasText:/^2 \/ 2/}).waitFor();
// Para #67: Defect 빨간 네모 — 흑백 Crop · Gray 프레임 둘 다, Defect 상자(BoxWidth × BoxHeight)를 가리지 않음(선 안쪽 가장자리 > 상자 반폭)
const box67=await page.evaluate(()=>{const c=window.__cw,g=document.createElement('canvas');g.width=3168;g.height=1024;const x=g.getContext('2d');x.fillStyle='rgb(128,128,128)';x.fillRect(0,0,3168,1024);
  x.fillStyle='rgb(250,250,250)';x.fillRect(1500-5,500-4,10,8);   // Defect(밝은 점, 10 × 8 px)
  const d={BoxWidth:10,BoxHeight:8},cs={cw:200,ch:150,ow:800,oh:600},k=c.cgCropCanvas(g,{px:1500,py:500},cs,document,d),o=k.canvas.getContext('2d');
  const px=(cv,X,Y)=>[...cv.getContext('2d').getImageData(X,Y,1,1).data].slice(0,3);
  const m=k.mark,hw=5*4,hh=4*4,lw=Math.max(2,Math.round(800/300));
  const plain=c.cgCropCanvas(g,{px:1500,py:500},cs,document);   // d 없으면 네모 없음(종전 그대로)
  let red=0,redIn=0;const im=o.getImageData(0,0,800,600).data;for(let y=0;y<600;y++)for(let X=0;X<800;X++){const i=(y*800+X)*4,r=im[i]>200&&im[i+1]<80&&im[i+2]<80;if(!r)continue;red++;if(Math.abs(X-400)<=hw&&Math.abs(y-300)<=hh)redIn++}
  const fr=c.cgFrameCanvas(g,{px:1500,py:500},{cw:200,ch:150},document,d),fim=fr.getContext('2d').getImageData(1490,492,20,16).data;let frIn=0;for(let i=0;i<fim.length;i+=4)if(fim[i]>200&&fim[i+1]<80)frIn++;
  return {mark:m,inner:[400-(m[0]+lw),300-(m[1]+lw)],hw,hh,center:px(k.canvas,400,300),edge:px(k.canvas,Math.round(m[0]+lw/2),300),red,redIn,plain:plain.mark,frIn,
    frEdge:px(fr,Math.round(1500-Math.max(5+4,3168/60)-1),500)}});
assert.ok(box67.inner[0]>box67.hw&&box67.inner[1]>box67.hh,'네모 안쪽이 Defect 상자보다 커야 함');
assert.ok(box67.red>100);assert.equal(box67.redIn,0);   // Defect 상자 안에는 빨간 점 0개
assert.deepEqual(box67.center,[250,250,250]);assert.ok(box67.edge[0]>200&&box67.edge[1]<80,'네모 선 = 빨강');
assert.equal(box67.plain,null);assert.equal(box67.frIn,0);assert.ok(box67.frEdge[0]>200&&box67.frEdge[1]<80,'Gray 프레임도 빨간 네모');
// 실제 새 창: Gray Crop · 프레임에 빨간 픽셀이 있다(흑백 위)
assert.equal(await pw.evaluate(()=>['#fx canvas','#ff canvas'].every(q=>{const cv=document.querySelector(q),d=cv.getContext('2d').getImageData(0,0,cv.width,cv.height).data;for(let i=0;i<d.length;i+=4)if(d[i]>200&&d[i+1]<80&&d[i+2]<80)return true;return false})),true);
// Para #67: 새 창 확대가 여러 단계 — 누르기 2배씩(창 맞춤 → 2 → 4 → … 원래 픽셀 16배 끝 → 창 맞춤), Shift · 오른쪽 = 축소, 휠, Esc = 창 맞춤, 다음 사진 = 창 맞춤
const zoomOf=()=>pw.evaluate(()=>{const cv=document.querySelector('#fx canvas');return {z:cv._z,w:cv.getBoundingClientRect().width,fit:window.opener.__cw.pwFit(cv),full:cv.parentNode.classList.contains('full'),zb:cv.parentNode.parentNode.querySelector('.zb').textContent}});
const z0=await zoomOf();assert.equal(z0.z,1);assert.equal(z0.full,false);
const zs=[];for(let n=0;n<12;n++){await pw.locator('#fx canvas').click();const z=await zoomOf();zs.push(z.z);if(z.z===1)break}
const zmax=16/z0.fit;assert.ok(zs.length>=4,`확대 단계 ${zs}`);assert.equal(zs[0],2);assert.equal(zs[1],4);assert.equal(zs.at(-1),1);   // 끝까지 가면 창 맞춤으로
assert.ok(Math.abs(zs.at(-2)-zmax)<1e-6||zs.at(-2)*2>zmax);
await pw.locator('#fx canvas').click();await pw.locator('#fx canvas').click();let zz=await zoomOf();assert.equal(zz.z,4);assert.ok(Math.abs(zz.w-1380*z0.fit*4)<2);assert.equal(zz.full,true);assert.match(zz.zb,/^확대 ×4 · 원래 크기의 \d+%$/);
await pw.locator('#fx canvas').click({modifiers:['Shift']});assert.equal((await zoomOf()).z,2);
await pw.locator('#fx canvas').click({button:'right'});assert.equal((await zoomOf()).z,1);
await pw.locator('#fx').hover();await pw.mouse.wheel(0,-100);await pw.waitForTimeout(50);assert.ok(Math.abs((await zoomOf()).z-1.25)<1e-6);
await pw.locator('#fx canvas').click();await pw.keyboard.press('Escape');zz=await zoomOf();assert.equal(zz.z,1);assert.equal(zz.full,false);assert.equal(zz.zb,'');
await pw.locator('#fx canvas').click();await pw.keyboard.press('ArrowUp');await pw.locator('#hd',{hasText:/^1 \/ 2/}).waitFor();await pw.locator('#fx canvas').waitFor();
assert.equal((await zoomOf()).z,1);await pw.keyboard.press('End');await pw.locator('#hd',{hasText:/^2 \/ 2/}).waitFor();await pw.locator('#fx canvas').waitFor();
await pw.locator('#fx canvas').click();await pw.keyboard.press('ArrowUp');await pw.locator('#hd',{hasText:/^1 \/ 2/}).waitFor();   // 사진을 눌러 원래 크기로 봐도 키는 그대로
await page.locator('#b5list').focus();await page.keyboard.press('ArrowRight');await pw.locator('#hd',{hasText:/^2 \/ 2/}).waitFor();   // 목록 → 도 새 창을 바꿈
await page.keyboard.press('ArrowUp');await pw.locator('#hd',{hasText:/^1 \/ 2/}).waitFor();
// 확대 · 위치 고정(소유자 "가운데만 크롭해서 보게 — 배율과 위치를 고정, 고정 체크박스"): 켜면 다음 Defect 도 같은 배율 · 같은 곳(프레임은 Defect 를 따라감), 끄면 창 맞춤
const lockOf=()=>pw.evaluate(()=>{const c=window.opener.__cw,o={};for(const id of ['fx','ff']){const cv=document.querySelector('#'+id+' canvas'),[x,y]=c.pwCenter(cv),a=cv._anchor||[0,0];o[id]={z:+cv._z.toFixed(4),dx:+(x-a[0]).toFixed(3),dy:+(y-a[1]).toFixed(3)}}
  o.on=document.getElementById('pwLock').checked;o.zb=document.querySelector('#fx .zb').textContent;return o});
assert.equal((await lockOf()).on,false);
await pw.locator('#fx canvas').click();await pw.locator('#fx canvas').click();
{const b=await pw.locator('#fx .im').boundingBox();await pw.mouse.move(b.x+b.width/2,b.y+b.height/2);await pw.mouse.down();await pw.mouse.move(b.x+b.width/2-80,b.y+b.height/2-40,{steps:5});await pw.mouse.up()}   // 끌어서 보는 곳 옮김
await pw.locator('#ff canvas').click();
await pw.locator('#pwLock').check();const L1=await lockOf();assert.equal(L1.on,true);assert.equal(L1.fx.z,4);assert.equal(L1.ff.z,2);assert.match(L1.zb,/🔒 고정/);
assert.ok(Math.abs(L1.fx.dx-0.5)>0.01,JSON.stringify(L1));   // 끌어서 가운데가 아님
await pw.keyboard.press('ArrowDown');await pw.locator('#hd',{hasText:/^2 \/ 2/}).waitFor();await pw.locator('#ff canvas').waitFor();
const L2=await lockOf();assert.deepEqual([L2.fx.z,L2.ff.z],[4,2]);
for(const id of ['fx','ff'])for(const k of ['dx','dy'])assert.ok(Math.abs(L2[id][k]-L1[id][k])<0.01,`${id}.${k} ${L1[id][k]} → ${L2[id][k]}`);
assert.equal(await page.evaluate(()=>localStorage.getItem('cw.pwLock')),'1');
await pw.locator('#fx canvas').click({button:'right'});await pw.keyboard.press('ArrowUp');await pw.locator('#hd',{hasText:/^1 \/ 2/}).waitFor();await pw.locator('#ff canvas').waitFor();
assert.equal((await lockOf()).fx.z,2);   // 고정 중에 바꾼 배율도 따라감
await pw.keyboard.press('f');const L3=await lockOf();assert.equal(L3.on,false);assert.doesNotMatch(L3.zb,/고정/);   // F = 고정 켜고 끄기
await pw.keyboard.press('ArrowDown');await pw.locator('#hd',{hasText:/^2 \/ 2/}).waitFor();await pw.locator('#ff canvas').waitFor();
assert.deepEqual([(await lockOf()).fx.z,(await lockOf()).ff.z],[1,1]);assert.equal(await page.evaluate(()=>localStorage.getItem('cw.pwLock')),'0');
await pw.keyboard.press('ArrowUp');await pw.locator('#hd',{hasText:/^1 \/ 2/}).waitFor();
// 새 창을 새로 고침(F5) → 빈 창은 다른 출처라 손댈 수 없음 → 다음 이동 때 닫고 새 창으로 다시 그림
await pw.reload();const [pw2]=await Promise.all([page.waitForEvent('popup'),(async()=>{await page.locator('#b5list').focus();await page.keyboard.press('ArrowDown')})()]);
await pw2.locator('#hd',{hasText:/^2 \/ 2/}).waitFor();await pw2.locator('#fx canvas').waitFor();assert.equal(pw.isClosed(),true);
await pw2.keyboard.press('ArrowUp');await pw2.locator('#hd',{hasText:/^1 \/ 2/}).waitFor();
await pw2.close();await page.locator('#b5list').focus();await page.keyboard.press('ArrowDown');   // 닫힌 새 창은 따라가지 않음(오류 없음)
// 5-3: 짝 완료 2개 — Color 원본 + Gray Crop(Color 시야 = 838×629 → 1380×1036) · 진행 기록 · 경로 · GL
await page.locator('#toB3').click();await page.locator('#c5Color canvas').waitFor();await page.locator('#c5Gray canvas').waitFor();
await page.locator('#c5St',{hasText:'이 Defect 끝'}).waitFor();
const st5=await page.locator('#c5St').innerText();
assert.match(st5,/✔ Color 이미지 읽기 · 디코딩: C1\.c\.1\.jpeg/);assert.match(st5,/✔ Gray 프레임 읽기 · 디코딩: F1\.t\.1\.jpeg/);
assert.match(st5,/✔ Crop\(Color 시야\) · GL 계산 — 픽셀 \(1100\.0, 200\.0\) · Crop 838×629 → 1380×1036/);
const in5=await page.locator('#c5Info').innerText();assert.match(in5,/Gray 경로\s*Y:\\AOI\\SR\\RCP\\SETUP1\\LOT_CA\d+\\W01\\F1\.t\.1\.jpeg/);assert.match(in5,/Color 경로\s*Y:\\AOI\\SR\\RCP\\SETUP1\\LOT_CA\d+\\W01\\C1\.c\.1\.jpeg/);assert.match(in5,/ROI mean/);
assert.match(in5,/Gray\s*F1\.t\.1\.jpeg · \(1100\.0, 200\.0\) · 후보 2 · 좌표 기준 그대로 · frameToChuckPlane/);
const cap5=await page.locator('#c5one figcaption').allInnerTexts();   // 사진 파일명 + 전체 경로(사진 위)
assert.match(cap5[0],/^Color 원본 · C1\.c\.1\.jpeg\s*Y:\\AOI\\SR\\RCP\\SETUP1\\LOT_CA\d+\\W01\\C1\.c\.1\.jpeg$/);assert.match(cap5[1],/^Gray Crop \(Color 시야\) · F1\.t\.1\.jpeg\s*Y:\\AOI\\SR\\RCP\\SETUP1\\LOT_CA\d+\\W01\\F1\.t\.1\.jpeg$/);
assert.equal(await page.locator('#c5list .br').count(),2);
await page.locator('#c5list').focus();await page.keyboard.press('ArrowRight');await page.locator('#c5Info',{hasText:'2 / 2'}).waitFor();   // ← → 도 이전 · 다음
await page.keyboard.press('ArrowLeft');await page.locator('#c5Info',{hasText:'1 / 2'}).waitFor();
await page.keyboard.press('ArrowDown');await page.locator('#c5Info',{hasText:'2 / 2'}).waitFor();
const [w5]=await Promise.all([page.waitForEvent('popup'),page.locator('#c5list .br').nth(0).dblclick()]);
await w5.locator('#fx canvas').waitFor();assert.match(await w5.locator('#hd').innerText(),/^1 \/ 2 · /);
// #68 최종 목록: 목록에서 Space = ☑/☐(첫 칸), 새 창에서도 Space → 목록에 반영, 엑셀(사진 포함) = ☑ 한 Defect 만
const pickN=()=>page.locator('#c5pickN').innerText(),firstCells=()=>page.$$eval('#c5list .br',r=>r.map(x=>x.children[0].textContent));
assert.equal(await pickN(),'☑ 0개');assert.equal(await page.locator('#c5save').isDisabled(),true);assert.match(await w5.locator('#hd').innerText(),/☐ 최종 목록 아님/);
await page.locator('#c5list').focus();await page.keyboard.press('Home');await page.keyboard.press(' ');
assert.equal(await pickN(),'☑ 1개');assert.deepEqual(await firstCells(),['☑','☐']);assert.equal(await page.locator('#c5save').isDisabled(),false);
await w5.locator('#hd',{hasText:'☑ 최종 목록'}).waitFor();   // 열린 새 창 머리도 바로 바뀜
await w5.keyboard.press('ArrowDown');await w5.locator('#hd',{hasText:/^2 \/ 2 · .*☐ 최종 목록 아님/}).waitFor();
await w5.keyboard.press(' ');await w5.locator('#hd',{hasText:'☑ 최종 목록'}).waitFor();assert.deepEqual(await firstCells(),['☑','☑']);assert.equal(await pickN(),'☑ 2개');
await w5.keyboard.press(' ');await w5.locator('#hd',{hasText:'☐ 최종 목록 아님'}).waitFor();assert.deepEqual(await firstCells(),['☑','☐']);
await w5.keyboard.press(' ');assert.deepEqual(await firstCells(),['☑','☑']);await w5.close();
await page.locator('#c5list .br').nth(1).locator('span.pk').click();assert.deepEqual(await firstCells(),['☑','☐']);   // ☑ 칸을 눌러도 됨
await page.locator('#c5list .br').nth(1).locator('span.pk').click();
await page.evaluate(()=>{window.__xlOld=window.showSaveFilePicker;window.showSaveFilePicker=async o=>{window.__xlName=o.suggestedName;window.__xlTypes=o.types;return {name:o.suggestedName,createWritable:async()=>({write:async b=>{window.__xl=b},close:async()=>{}})}}});
await page.locator('#c5save').click();await page.locator('#c5saveSt',{hasText:'저장:'}).waitFor({timeout:30000});
const xl=await page.evaluate(async()=>{const b=new Uint8Array(await window.__xl.arrayBuffer());let s='';for(let i=0;i<b.length;i+=0x8000)s+=String.fromCharCode(...b.subarray(i,i+0x8000));
  const r={b64:btoa(s),name:window.__xlName,ext:Object.values(window.__xlTypes[0].accept)[0],st:document.getElementById('c5saveSt').textContent};window.showSaveFilePicker=window.__xlOld;return r});
assert.match(xl.name,/^최종목록_\d{8}_\d{6}\.xlsx$/);assert.deepEqual(xl.ext,['.xlsx']);assert.match(xl.st,/Defect 2개 · 사진 6장/);
const xlChk=JSON.parse(execFileSync('python3',['-I','-c',`
import sys,io,zipfile,base64,json,xml.etree.ElementTree as ET
z=zipfile.ZipFile(io.BytesIO(base64.b64decode(sys.stdin.read())));assert z.testzip() is None
for n in z.namelist():
    if n.endswith('.xml') or n.endswith('.rels'): ET.fromstring(z.read(n))
ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
ws=ET.fromstring(z.read('xl/worksheets/sheet1.xml'));rows=[[ (c.findtext('m:is/m:t',default=None,namespaces=ns) or c.findtext('m:v',default='',namespaces=ns)) for c in r.findall('m:c',ns)] for r in ws.find('m:sheetData',ns)]
media=[n for n in z.namelist() if n.startswith('xl/media/')];jp=all(z.read(n)[:3]==bytes([255,216,255]) for n in media)
dr=z.read('xl/drawings/drawing1.xml').decode();print(json.dumps({'rows':rows,'media':len(media),'jpeg':jp,'anchors':dr.count('<xdr:oneCellAnchor>'),'names':z.namelist()[:3]}))
`],{input:xl.b64,encoding:'utf-8',maxBuffer:1<<26}));
assert.equal(xlChk.media,6);assert.equal(xlChk.jpeg,true);assert.equal(xlChk.anchors,6);assert.equal(xlChk.rows.length,3);
assert.equal(xlChk.rows[0][7],'Color');assert.match(xlChk.rows[0][8],/^Gray Crop/);assert.match(xlChk.rows[0][9],/^Gray 프레임/);
assert.deepEqual(xlChk.rows.slice(1).map(r=>r[2]),['W01','W01']);
assert.equal(xlChk.rows[0][26],'흑백 GL 평균 (원)');assert.ok(xlChk.rows.slice(1).every(r=>Number.isFinite(+r[26])&&/^\d+(\.\d+)? px · \d+픽셀$/.test(r[27])),JSON.stringify(xlChk.rows.map(r=>r.slice(26))));   // rev6: 측정 안 했어도 저장 때 잼
if(process.env.CW_XL_OUT)(await import('node:fs')).writeFileSync(process.env.CW_XL_OUT,Buffer.from(xl.b64,'base64'));   // 손으로 열어 보기(LibreOffice · Excel)
assert.ok(xlChk.rows.slice(1).every(r=>/\.c\.\d\.jpeg$/.test(r[20])&&/\.t\.\d\.jpeg$/.test(r[22])&&/^Y:\\/.test(r[21])),JSON.stringify(xlChk.rows));
// 다시 확인(5-2)을 해도 같은 Defect 의 ☑ 는 남음
await page.evaluate(()=>window.__cw.b5Pair());await page.waitForFunction(()=>document.getElementById('busy').hidden);assert.equal(await page.evaluate(()=>window.__cw.pickList().length),2);
await page.locator('#c5pickNone').click();assert.equal(await pickN(),'☑ 0개');
// 5-3 사진 상태 체크(소유자 "Color 만 · 짝 매칭 · 흑백만 구분해서 볼 수 있게"): 기본 = 짝 완료 · Color 만 · Gray 만, 하나씩 켜면 그 상태만, 개수 표시
const stBox=k=>page.locator(`#c5stF [data-st5="${k}"]`),stOf=()=>page.evaluate(()=>window.__cw.C5.items.map(p=>p.st));
const n5=await page.$$eval('#c5stF [data-n5]',x=>Object.fromEntries(x.map(e=>[e.dataset.n5,+e.textContent.replace(/[(),]/g,'')])));
const want5=await page.evaluate(()=>{const n={ok:0,color:0,gray:0,none:0};for(const p of window.__cw.BIG.pairs)if(p.st!=='skip')n[p.st]++;return n});
assert.deepEqual(n5,want5);assert.equal(Object.values(n5).reduce((a,b)=>a+b),7);assert.ok(n5.ok>0&&n5.none>0,JSON.stringify(n5));
assert.deepEqual(await Promise.all(['ok','color','gray','none'].map(k=>stBox(k).isChecked())),[true,true,true,false]);
assert.match(await page.locator('#c5cnt').innerText(),/\(사진 있는 것만\)/);
for(const only of ['ok','color','gray','none']){for(const k of ['ok','color','gray','none'])await stBox(k).setChecked(k===only);
  const st=await stOf();assert.equal(st.length,n5[only]);assert.ok(st.every(x=>x===only),only+' '+st);assert.equal(await page.locator('#c5list .br').count(),n5[only]);
  assert.match(await page.locator('#c5cnt').innerText(),new RegExp(`^Defect ${n5[only]}개 \\(${{ok:'짝 완료',color:'Color 만',gray:'Gray 만',none:'둘 다 없음'}[only]}\\)`))}
await stBox('ok').check();await stBox('color').check();await stBox('gray').check();assert.equal(await page.locator('#c5list .br').count(),7);assert.match(await page.locator('#c5cnt').innerText(),/^Defect 7개 · /);
// ── rev6 흑백 GL(원)(소유자 "실제 흑백 이미지 픽셀의 gray level · 원형 · 크기만 · 원을 그려 정함 · 최대 64 px · 두 손잡이 바를 끌면 바로 정렬") ──
// ① 계산 = 원본 픽셀 원 안(픽셀 가운데가 원 안) 단순 평균: 무작위 흑백 그림 · 소수 좌표 · 가장자리 · 반지름 0.5 ~ 64 를 하나하나 센 값과 같음
const gl1=await page.evaluate(async()=>{const c=window.__cw,W=400,H=300,cv=new OffscreenCanvas(W,H),x=cv.getContext('2d'),im=x.createImageData(W,H);let seed=7;const rnd=()=>(seed=(seed*1103515245+12345)&0x7fffffff)/0x7fffffff;
  const G=new Uint8Array(W*H);for(let i=0;i<W*H;i++){const v=(rnd()*256)|0;G[i]=v;im.data[i*4]=im.data[i*4+1]=im.data[i*4+2]=v;im.data[i*4+3]=255}x.putImageData(im,0,0);const bm=await createImageBitmap(cv);
  const bad=[];let cases=0;for(const [px,py] of [[200.3,150.7],[200,150],[3.2,4.9],[399.5,299.1],[120.5,60.5]])for(const r of [0.5,1,1.5,2.5,5.5,10,20.5,64]){
    const P=c.glProfile(bm,{px:px*c.CG.GW/W,py:py*c.CG.GH/H}),k=Math.round(r*2);let S=0,N=0;
    for(let y=0;y<H;y++)for(let xx=0;xx<W;xx++){const dx=xx+.5-px,dy=y+.5-py;if(Math.sqrt(dx*dx+dy*dy)<=r+1e-9){S+=G[y*W+xx];N++}}
    cases++;const m=P.N[k]?P.S[k]/P.N[k]:null,e=N?S/N:null;if(P.N[k]!==N||(m==null)!==(e==null)||(m!=null&&Math.abs(m-e)>1e-9))bad.push({px,py,r,n:P.N[k],N,m,e})}
  return {bad,cases}});
assert.deepEqual(gl1.bad,[]);assert.equal(gl1.cases,40);
// ② [흑백 GL 측정] = 흑백 사진이 있는 Defect(짝 완료 · Gray 만) 전부, Color 만 · 둘 다 없음은 '흑백 없음', 값 = 원본 프레임 픽셀을 직접 센 것과 같음, 측정 뒤 GL 높은 순
assert.equal(await page.locator('#glR').inputValue(),'5.5');
await page.evaluate(()=>window.__cw.BIG.pairs.forEach(p=>{p.glp=null;p.glv=null}));   // 엑셀 저장 때 잰 것을 지우고 처음부터
await page.locator('#glRun').click();await page.waitForFunction(()=>document.getElementById('glSt').textContent.length>0,null,{timeout:30000}).catch(async e=>{console.log('glSt?',await page.evaluate(()=>({st:document.getElementById('glSt').textContent,vis:!!document.getElementById('glSt').offsetParent,n:(window.__cw.BIG.pairs||[]).map(p=>p.st+':'+!!p.glp+':'+(p.glErr||''))})));throw e});assert.match(await page.locator('#glSt').innerText(),/측정/);await page.waitForFunction(()=>document.getElementById('busy').hidden);
const gl2=await page.evaluate(async()=>{const c=window.__cw,P=c.BIG.pairs.filter(p=>p.st!=='skip'),out={can:0,val:0,other:[],brute:[]};
  for(const p of P){const can=p.st==='ok'||p.st==='gray';if(can){out.can++;if(p.glv!=null)out.val++}else out.other.push(p.glv==null)}
  for(const p of P.filter(p=>p.glv!=null).slice(0,3)){const r=p.r||c.cgOf(p.s,p.i),b=await c.cgBitmap(p.s,r.hit.frame.file),cv=new OffscreenCanvas(b.width,b.height),x=cv.getContext('2d');x.drawImage(b,0,0);const D=x.getImageData(0,0,b.width,b.height).data;
    const cx=r.hit.px*b.width/c.CG.GW,cy=r.hit.py*b.height/c.CG.GH;let S=0,N=0;for(let y=0;y<b.height;y++)for(let xx=0;xx<b.width;xx++){const dx=xx+.5-cx,dy=y+.5-cy;if(Math.sqrt(dx*dx+dy*dy)<=5.5){S+=D[(y*b.width+xx)*4];N++}}
    out.brute.push([+(p.glv).toFixed(9),+(S/N).toFixed(9),c.glCount(p),N])}
  out.cells=[...document.querySelectorAll('#c5list .br')].map(r=>r.children[8].textContent);out.sort=c.GLC.sort;out.items=c.C5.items.map(p=>p.glv);return out});
assert.ok(gl2.can>0&&gl2.val===gl2.can,JSON.stringify(gl2));assert.ok(gl2.other.every(Boolean));
for(const [a,b,n,N] of gl2.brute){assert.equal(a,b);assert.equal(n,N)}
assert.equal(gl2.sort,'gl-d');{const v=gl2.items.filter(x=>x!=null);for(let k=1;k<v.length;k++)assert.ok(v[k-1]>=v[k],v.join())}
assert.ok(gl2.cells.some(t=>/^\d+\.\d$/.test(t))&&gl2.cells.some(t=>t==='흑백 없음'),gl2.cells.join('|'));
await page.locator('#c5list .bh [data-sort="gl"]').click();assert.equal(await page.evaluate(()=>window.__cw.GLC.sort),'gl-a');   // 열 제목 = 오름 · 내림
// ③ 두 손잡이 바: 끄는 동안 바로 거름(측정 안 된 · 흑백 없는 것은 숨김), [범위 풀기] = 전부
const setRng=(lo,hi)=>page.evaluate(([lo,hi])=>{for(const [id,v] of [['glLo',lo],['glHi',hi]]){const e=document.getElementById(id);e.value=v;e.dispatchEvent(new Event('input',{bubbles:true}))}},[lo,hi]);
{const vals=gl2.items.filter(x=>x!=null),v0=Math.floor(Math.min(...vals));await setRng(v0,v0);
  const want=vals.filter(v=>v>=v0&&v<v0+1).length,got=await page.evaluate(()=>window.__cw.C5.items.map(p=>p.glv));
  assert.equal(got.length,want);assert.ok(got.every(v=>v>=v0&&v<v0+1));assert.match(await page.locator('#glRngT').innerText(),new RegExp(`^GL ${v0} ~ ${v0}$`));assert.match(await page.locator('#c5cnt').innerText(),new RegExp(` · GL ${v0} ~ ${v0}`));
  await setRng(250,255);assert.equal(await page.evaluate(()=>window.__cw.C5.items.length),vals.filter(v=>v>=250).length);
  // 숫자 칸으로도 범위(바와 같은 값), 정렬 칸 = 높은 순 · 낮은 순 · 5-2 순서
  await page.locator('#glLoN').fill('250');assert.equal(await page.locator('#glLo').inputValue(),'250');assert.equal(await page.evaluate(()=>window.__cw.C5.items.length),vals.filter(v=>v>=250).length);
  await page.locator('#glRngAll').click();assert.equal(await page.evaluate(()=>window.__cw.C5.items.length),7);assert.equal(await page.locator('#glLoN').inputValue(),'0');
  await page.locator('#glSort').selectOption('gl-d');{const v=(await page.evaluate(()=>window.__cw.C5.items.map(p=>p.glv))).filter(x=>x!=null);for(let k=1;k<v.length;k++)assert.ok(v[k-1]>=v[k])}
  await page.locator('#glSort').selectOption('gl-a');{const v=(await page.evaluate(()=>window.__cw.C5.items.map(p=>p.glv))).filter(x=>x!=null);for(let k=1;k<v.length;k++)assert.ok(v[k-1]<=v[k])}
  await page.locator('#glSort').selectOption('');assert.deepEqual(await page.evaluate(()=>window.__cw.C5.items.map(p=>p.k)),await page.evaluate(()=>window.__cw.C5.items.map(p=>p.k).sort((a,b)=>a-b)))}
if(process.env.CW_SHOT)await page.locator('#b5p3').screenshot({path:process.env.CW_SHOT+'/p53.png'});
// ④ 원 크기를 바꾸면 사진을 다시 읽지 않고 바로 다시 계산(같은 기억 glp)
{const r=await page.evaluate(()=>{const c=window.__cw,p=c.BIG.pairs.find(p=>p.glp),g=p.glp,a=p.glv;c.glSetR(2);const b=p.glv,same=p.glp===g;c.glSetR(64);const d=p.glv;return {a,b,d,same,n2:c.glCount(p,2),n64:c.glCount(p,64)}});
  assert.ok(r.same);assert.ok(r.n2>0&&r.n2<=16&&r.n64>r.n2,JSON.stringify(r));assert.equal(await page.evaluate(()=>localStorage.getItem('cw.glR')),'64')}
// ⑤ 측정 원 그리기 창: Defect 가운데에서 끄는 거리 = 반지름(원본 픽셀, ×8 이면 8 화면 픽셀 = 1 px), 0.5 단위, [적용] → 저장 · 다시 계산 · 표시
await page.locator('#c5list .br').first().click();await page.locator('#glSet').click();await page.locator('#glDlg').waitFor();
{const b=await page.locator('#glCv').boundingBox(),k=b.width/528,cx=b.x+b.width/2,cy=b.y+b.height/2;
  await page.mouse.move(cx,cy);await page.mouse.down();await page.mouse.move(cx+20*k,cy,{steps:3});await page.mouse.move(cx+24*k,cy+18*k,{steps:3});   // 거리 30 화면 px ÷ 8 = 3.75 → 3.5 또는 4
  assert.match(await page.locator('#glDN').innerText(),/^원 안 \d+픽셀 · 이 Defect 평균 GL [\d.]+/);await page.mouse.up();
  const r=+(await page.locator('#glDR').inputValue());assert.ok(r===3.5||r===4,String(r));
  await page.locator('#glCv').hover();await page.mouse.wheel(0,-100);await page.waitForTimeout(50);assert.equal(+(await page.locator('#glDR').inputValue()),r+0.5);   // 휠 = 0.5 px
  await page.locator('#glZ').selectOption('4');assert.equal(await page.evaluate(()=>window.__cw.GLD.z),4);
  if(process.env.CW_SHOT)await page.screenshot({path:process.env.CW_SHOT+'/dlg.png'});   // 손으로 보기
  await page.locator('#glDOk').click();assert.equal(await page.locator('#glDlg').isHidden(),true);
  assert.equal(await page.evaluate(()=>window.__cw.GLC.r),r+0.5);assert.equal(await page.evaluate(()=>localStorage.getItem('cw.glR')),String(r+0.5));assert.equal(await page.locator('#glR').inputValue(),String(r+0.5))}
// 취소는 그대로, Esc 도 취소
await page.locator('#glSet').click();await page.locator('#glDlg').waitFor();{const b=await page.locator('#glCv').boundingBox();await page.mouse.click(b.x+b.width/2+100,b.y+b.height/2)}
await page.keyboard.press('Escape');assert.equal(await page.locator('#glDlg').isHidden(),true);assert.notEqual(await page.evaluate(()=>window.__cw.GLC.r),12.5);
// ⑥ 사진에 측정 원(하늘색) 표시 — 5-3 Gray Crop 에 하늘색 픽셀이 있음(재는 값은 원본 픽셀이라 무관)
{const gi=await page.evaluate(()=>window.__cw.C5.items.findIndex(p=>p.st==='ok'));await page.locator(`#c5list .br[data-k="${gi}"]`).click()}await page.locator('#c5Gray canvas').waitFor();await page.locator('#c5St',{hasText:'이 Defect 끝'}).waitFor();
assert.ok(await page.evaluate(()=>{const cv=document.querySelector('#c5Gray canvas');if(!cv)return 0;const d=cv.getContext('2d').getImageData(0,0,cv.width,cv.height).data;let k=0;for(let i=0;i<d.length;i+=4)if(d[i]<90&&d[i+1]>170&&d[i+2]>190)k++;return k})>20);
await page.evaluate(()=>window.__cw.glSetR(5.5));
// 모두 미리 준비(로딩창) → 격자
await page.evaluate(()=>window.__cw.THUMB.clear());await page.locator('#b5prep').click();
await page.waitForFunction(()=>document.getElementById('busy').hidden&&window.__cw.THUMB.size===7);
await page.locator('[data-v5="grid"]').click();await page.locator('#c5gst',{hasText:'준비돼 있습니다'}).waitFor();
assert.equal(await page.locator('#c5grid .g5').count(),7);assert.equal(await page.locator('#c5grid .g5.st-ok img').count(),4);
assert.deepEqual(await page.locator('#c5grid .g5.st-ok .gn').first().locator('span').allInnerTexts(),['C1.c.1.jpeg','F1.t.1.jpeg']);   // 격자 카드에도 사진 파일명(마우스를 올리면 전체 경로)
assert.match(await page.locator('#c5grid .g5.st-ok .gn span').first().getAttribute('title'),/^Y:\\AOI\\SR\\RCP\\SETUP1\\LOT_CA\d+\\W01\\C1\.c\.1\.jpeg$/);
await page.locator('#c5grid .g5').first().click();assert.equal(await page.locator('#c5one').isHidden(),false);
// 많은 Defect: 합성 30만 개(Slot 3개)도 열 배열로 바로 필터 · 정렬(표는 보이는 줄만 그림) — 매칭 파일이 없는 Slot 은 '매칭 파일 없음'
await page.locator('[data-b5="1"]').click();
const perf=await page.evaluate(async()=>{const c=window.__cw,REC=c.REC,N=100000,mk=seed=>{const b=new ArrayBuffer(N*REC),dv=new DataView(b);for(let i=0;i<N;i++){const o=i*REC;dv.setFloat64(o+8,i%1000*300,true);dv.setFloat64(o+16,(i/1000|0)*3000,true);dv.setInt32(o+40,i,true);dv.setFloat64(o+80,(i*7+seed)%500+1,true);dv.setFloat64(o+88,(i%90)/10,true);dv.setFloat64(o+136,((i*31+seed)%6000)/100,true)}return b};
  const es=[];for(let k=0;k<3;k++)es.push({path:`HUGE/S1/LOT${k}/W0${k}/Surface.flt`,file:new File([mk(k)],'Surface.flt')});
  const t0=performance.now();await c.addBigEntries(es);const t1=performance.now();
  document.querySelector('#bigFlt [data-f="c0"]').value='59.9';c.bigRefresh();const t2=performance.now();
  return {load:t1-t0,flt:t2-t1,m:c.BIG.view.m,total:c.BIG.view.total,rows:document.querySelectorAll('#bigList .br').length,first:+document.querySelector('#bigList .br').children[6].textContent,
    cell:document.querySelector('#bigList .br').children[14].textContent,msg:document.getElementById('bigMsg').innerText}});
assert.equal(perf.total,300007);assert.ok(perf.m>0&&perf.m<perf.total/50,JSON.stringify(perf));assert.ok(perf.rows<80,JSON.stringify(perf));assert.ok(perf.first>=59.9);
assert.ok(perf.load<15000&&perf.flt<5000,JSON.stringify(perf));assert.equal(perf.cell,'✖ 매칭 파일 없음');assert.match(perf.msg,/매칭 파일이 없는 Slot 3개: W00\(없음: ColorImageGrabingInfo\.ini — Slot 폴더 파일 1개 중 이 이름\(대소문자 무시\) 없음 · 하위 폴더 0개 · 위쪽 폴더 3개도 찾아봄 · 전체 경로 \d+자\)/);   // [원본 폴더 경로]를 적어 두면 전체 경로 길이도(260자 제한 점검)
console.log('step5 30만 Defect:',JSON.stringify({load:perf.load,flt:perf.flt,m:perf.m}));
// 중지: 5-2 를 시작하자마자 [중지] → 처리 못 한 것 = '확인 안 함', 자동 CSV 저장 안 함
const stop=await page.evaluate(async()=>{const c=window.__cw;const p=c.b5Pair({h:null});c.BIG.stop=true;await p;const P=c.BIG.pairs;return {n:P.length,skip:P.filter(x=>x.st==='skip').length}});
assert.equal(stop.n,500);assert.ok(stop.skip>0,JSON.stringify(stop));
await page.locator('[data-b5="2"]').click();assert.match(await page.locator('#b5pairSt').innerText(),/중지로 확인 안 함 \d+[\s\S]*중지해서 CSV 를 자동 저장하지 않았습니다/);

// ── 실제 결과 폴더(사진 제외.zip, Slot 1개 · Defect 353) = Para colorgray.py 와 Defect 마다 같은 짝 ───────────────
//    zip 에 사진은 없어 이름만 있는 빈 파일로 채운다(5-1 · 5-2 는 사진을 읽지 않음). 기대값 = 이 브랜치의 param_manager/colorgray.py(choose_frame).
const real=JSON.parse(execFileSync('python3',['-c',`
import base64, io, json, os, re, struct, sys, zipfile
sys.path.insert(0, ${JSON.stringify(root)})
from param_manager import colorgray as cg
z = zipfile.ZipFile(os.path.join(${JSON.stringify(root)}, '\uc0ac\uc9c4 \uc81c\uc678.zip'))
files = {}
for i in z.infolist():
    if i.is_dir(): continue
    rel = i.filename.split('/', 1)[1]
    if '/' in rel: continue                       # Slot 바로 안 파일만(하위 폴더 자료는 매칭과 무관)
    b = z.read(i)
    files[rel] = b if (len(b) < 2_000_000 or rel.startswith('s_FrameData')) else b[:1024]   # Zones.dat 만 줄임(크기만 봄)
tmp = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'cw_rev6_real'); os.makedirs(tmp, exist_ok=True)
for k in ('ColorImageGrabingInfo.ini', 'ScanResultImageList.txt', 'frameToChuckPlane.ini'): open(os.path.join(tmp, k), 'wb').write(files[k])
colors = cg.parse_colors(os.path.join(tmp, 'ColorImageGrabingInfo.ini')); frames = cg.parse_frames(os.path.join(tmp, 'ScanResultImageList.txt'))
inv, off = cg.parse_transform(os.path.join(tmp, 'frameToChuckPlane.ini'))
exp = {}
for c in colors:
    fr, px, py, n = cg.choose_frame(c, frames, inv, off)
    exp[int(c['Index'])] = [c['file'], fr['file'], px, py, n]
sys.path.insert(0, os.path.join(${JSON.stringify(root)}, 'tests'))
from colorgray_fixture import COLOR_JPEG, GRAY_JPEG       # 사진 자리에 작은 진짜 JPEG(새 창 · 5-3 에서 그릴 수 있게)
for c in colors: files[c['file']] = COLOR_JPEG
for f in frames: files[f['file']] = GRAY_JPEG
# 좌표 기준 시험용: Fault · Surface.flt 좌표를 프레임 직사각형의 좌측 하단 원점으로 옮긴 판(프로그램 frames_rect 와 같은 식)
a, b2, c2, d = inv[0][0], inv[0][1], inv[1][0], inv[1][1]; det = a * d - b2 * c2; fw = ((d / det, -b2 / det), (-c2 / det, a / det))
xs = [f['x'] + off[0] + fw[0][0] * px + fw[0][1] * py for f in frames for px, py in ((0, 0), (cg.GW, 0), (0, cg.GH), (cg.GW, cg.GH))]
ys = [f['y'] + off[1] + fw[1][0] * px + fw[1][1] * py for f in frames for px, py in ((0, 0), (cg.GW, 0), (0, cg.GH), (cg.GW, cg.GH))]
x0, y0 = min(xs), min(ys)
flt = bytearray(files['Surface.flt'])
for o in range(0, len(flt) - 151, 152):
    for k, dd in ((8, x0), (16, y0), (24, x0), (32, y0)): struct.pack_into('<d', flt, o + k, struct.unpack_from('<d', flt, o + k)[0] - dd)
ci = files['ColorImageGrabingInfo.ini'].decode('utf-8', 'replace')
ci = re.sub(r'^(X|FaultX)=(.+)$', lambda q: f'{q.group(1)}={float(q.group(2)) - x0!r}', ci, flags=re.M)
ci = re.sub(r'^(Y|FaultY)=(.+)$', lambda q: f'{q.group(1)}={float(q.group(2)) - y0!r}', ci, flags=re.M)
shift = {'Surface.flt': bytes(flt), 'ColorImageGrabingInfo.ini': ci.encode()}
f0 = bytearray(files['Surface.flt']); struct.pack_into('<hh', f0, 0, 0, 28)   # 첫 Defect: 현재 0(Accept) · 원래 28(B R Other) — 소유자 Slot 29126432EWE3 모양
shift_cls = {'Surface.flt': bytes(f0)}
enc = lambda d: {k: base64.b64encode(v).decode() for k, v in d.items()}
print(json.dumps({'files': enc(files), 'shift': enc(shift), 'cls0': enc(shift_cls), 'exp': exp}))
`],{encoding:'utf-8',maxBuffer:1<<28}));
const realRun=async(name,opt)=>{const pg=await browser.newPage();const er=[];pg.on('pageerror',e=>er.push(String(e)));
  await pg.goto('file://'+resolve(root,'AOI_Contrast_Wizard_rev6.html'));await pg.evaluate(src=>{(0,eval)(src)},fakeTree);
  const r=await pg.evaluate(async ({real,opt})=>{const c=window.__cw,f={...real.files};if(opt.shift)Object.assign(f,real.shift);
    for(const k of opt.drop||[])delete f[k];if(opt.cls0)Object.assign(f,real.cls0);const extra=opt.extra||{};for(const [k,v] of Object.entries(extra))f[k]=v;
    const root=window.__mkTree(f,p=>p.startsWith('@')?p.slice(1).split('/'):['SETUP1','LOT_A','W01',p],opt);
    await c.bigPickHandle(root);await c.b5Pair(null);
    const SN=opt.slot||'RCP/SETUP1/LOT_A/W01';let cls=null;if(opt.cls){const s=c.BIG.scans.find(s=>s.name===SN);
      const at=k=>{const V=c.BIG.view,j=V.ord[k];return [V.src[V.gs[j]],V.gi[j]]},ck=(g,k)=>document.querySelector(`#bigCls [data-cls${g}="${k}"]`).click(),m=()=>c.BIG.view.m;
      cls={chips:document.getElementById('bigCls').innerText.replace(/\s+/g,' '),t0:c.clsText(s,0),f0:c.clsFirst(s,0),r0:c.clsName(s,0),
        names1:[...new Set(Array.from({length:s.cols.n},(_,i)=>c.clsFirst(s,i)))].sort(),names2:[...new Set(Array.from({length:s.cols.n},(_,i)=>c.clsName(s,i)))].sort(),
        csv1:c.bigCsv().join('').split('\r\n').slice(0,2),csv2:c.pairCsv().join('').split('\r\n').slice(0,2)};
      const n12=(a,b)=>{let k=0;for(let i=0;i<s.cols.n;i++)if((a==null||c.clsFirst(s,i)===a)&&(b==null||c.clsName(s,i)===b))k++;return k};
      cls.n={first:{Other:n12('B R Other',null),Dark:n12('B R Surface Dark',null)},re:{Other:n12(null,'B R Other'),Dark:n12(null,'B R Surface Dark'),Accept:n12(null,'Accept')},otherAccept:n12('B R Other','Accept')};
      c.BIG.sort='k1-a';c.bigRefresh();cls.sort1=c.clsFirst(...at(0));c.BIG.sort='k2-a';c.bigRefresh();cls.sort2=c.clsName(...at(0));c.BIG.sort='k2-d';c.bigRefresh();cls.sort2d=c.clsName(...at(0));
      cls.mAll=m();ck(1,'B R Surface Dark');cls.mOff1=m();ck(2,'B R Other');cls.mAnd=m();   // 첫번째 분류 Surface Dark 끔 + 재분류 Other 끔 → 둘 다 통과한 것만
      cls.andRows=Array.from({length:m()},(_,k)=>{const [ss,i]=at(k);return c.clsFirst(ss,i)+'→'+c.clsName(ss,i)});
      ck(1,'B R Surface Dark');cls.mOff2=m();cls.chipsOff=document.getElementById('bigCls').innerText.replace(/\s+/g,' ');
      document.querySelector('#bigCls [data-clsall="2"]').click();cls.mClear=m();cls.off=[c.BIG.clsOff1.size,c.BIG.clsOff2.size];
      document.querySelector('#bigCls [data-clsall="1"]').click();cls.mNone=m();document.querySelector('#bigCls [data-clsall="1"]').click();cls.mBack=m();c.BIG.sort='c-d';c.bigRefresh()}
    return {scans:c.BIG.scans.map(s=>[s.name,s.cols.n,s.cg&&s.cg.plan?c.CG.MODES[s.cg.plan.mode]:(s.cg&&(s.cg.err||s.cg.missing.join(',')))]),
      pairs:c.BIG.pairs.filter(p=>p.s.name===SN).map(p=>[p.i,p.st,p.c&&p.c.file,p.c&&p.c.how,p.g&&p.g.file,p.g&&p.g.px,p.g&&p.g.py,p.g&&p.g.n]),warns:c.BIG.scans.flatMap(s=>s.warns),
      src:(c.BIG.scans.find(s=>s.name===SN)||{}).cg?.src,alt:((c.BIG.scans.find(s=>s.name===SN)||{}).cg?.tfAlt||[]).map(a=>[a.name,a.hits]),
      at:(c.BIG.scans.find(s=>s.name===SN)||{}).cg?.at,cgPath:(c.BIG.scans.find(s=>s.name===SN)||{}).cg?.path,askErr:window.__fsLog.err||[],
      cls,msg:document.getElementById('bigMsg').innerText,row:[...document.querySelectorAll('#b5slotTbl tbody tr')].map(x=>x.innerText).join('\n'),csv:c.pairCsv().join('')}},{real,opt});
  if(opt.view){   // 5-2 줄 더블 클릭 → 사진 새 창 · 5-3 하나씩 크게 (Color 만인 Slot: Color 를 창 · 칸 전체에)
    await pg.locator('nav button[data-step="5"]').click();await pg.locator('[data-b5="2"]').click();const [w]=await Promise.all([pg.waitForEvent('popup'),pg.locator('#b5list .br').nth(0).dblclick()]);await w.locator('#fc canvas').waitFor();
    r.pop=await w.evaluate(()=>({conly:document.querySelector('.pv').classList.contains('conly'),hd:document.getElementById('hd').textContent,color:!!document.querySelector('#fc canvas'),
      fcW:document.getElementById('fc').getBoundingClientRect().width,bodyW:document.body.getBoundingClientRect().width,grayShown:getComputedStyle(document.getElementById('fx')).display!=='none'}));await w.close();
    await pg.locator('#toB3').click();await pg.locator('#c5Color canvas').waitFor();await pg.locator('#c5St',{hasText:'이 Defect 끝'}).waitFor();
    r.c5={n:await pg.evaluate(()=>window.__cw.C5.items.length),conly:await pg.locator('#c5one .rvimgs.conly').count(),gray:await pg.locator('#c5Gray').isVisible(),cnt:await pg.locator('#c5cnt').innerText()}}
  await pg.close();assert.ok(r.scans.length,name);return {...r,er}};
const cmpReal=(name,r,tol=1e-6)=>{let ok=0,dmax=0;for(const [i,st,cf,how,gf,px,py,n] of r.pairs){const e=real.exp[i];
    assert.equal(st,'ok',name+' '+i);assert.equal(cf,e[0],name+' '+i);assert.equal(how,'Index = 기록 순서',name+' '+i);assert.equal(gf,e[1],name+' '+i);
    const dd=Math.hypot(px-e[2],py-e[3]);dmax=Math.max(dmax,dd);assert.ok(dd<tol,`${name} ${i}: ${px},${py} ≠ ${e[2]},${e[3]}`);if(tol<1e-3)assert.equal(n,e[4],name+' '+i);ok++}
  assert.equal(ok,353,name);assert.deepEqual(r.er,[],name);return dmax};
const real0=await realRun('base',{cls:true});cmpReal('실제 결과 폴더',real0);
// Classify(소유자 "classify 열 · 필터 · 정렬"): Surface.flt reclassify → ManReClassify.ini 이름 — 실제 자료 29 = B R Surface Dark 334 · 28 = B R Other 19
// 소유자 "첫번째 분류, 재분류 2열 — 각각 AND 필터": 재분류 안 된 자료(org 0)는 두 열이 같음
assert.equal(real0.cls.chips,'첫번째 분류 B R Surface Dark 334 B R Other 19 모두 끄기 재분류 B R Surface Dark 334 B R Other 19 모두 끄기');
assert.deepEqual([real0.cls.names1,real0.cls.names2],[['B R Other','B R Surface Dark'],['B R Other','B R Surface Dark']]);
assert.deepEqual([real0.cls.sort1,real0.cls.sort2,real0.cls.sort2d],['B R Other','B R Other','B R Surface Dark']);
assert.deepEqual([real0.cls.mAll,real0.cls.mOff1,real0.cls.mAnd,real0.cls.mOff2],[353,19,0,334]);   // 1 끔 → Other 19, + 2 Other 끔 → 0(AND), 1 다시 켬 → 334
assert.match(real0.cls.chipsOff,/재분류 B R Surface Dark 334 B R Other 19 모두 켜기$/);
assert.deepEqual([real0.cls.mClear,real0.cls.off,real0.cls.mNone,real0.cls.mBack],[353,[0,0],0,353]);   // 모두 켜기 · 모두 끄기 → 0 · 다시 켜기
assert.match(real0.cls.csv1[0],/,Contrast,첫번째분류,재분류$/);assert.match(real0.cls.csv1[1],/,(B R Surface Dark|B R Other),\1$/);
assert.match(real0.cls.csv2[0],/,ID,resultID,첫번째분류,재분류,Contrast,/);
// 재분류된 Defect(첫 Defect: 원래 28 B R Other → 지금 0 Accept, 소유자 Slot 29126432EWE3 모양): 열이 갈리고 AND 가 둘을 함께 봄
const realC=await realRun('cls0',{cls:true,cls0:true});cmpReal('재분류된 Defect',realC);const cn=realC.cls.n;
assert.deepEqual([realC.cls.f0,realC.cls.r0,realC.cls.t0],['B R Other','Accept','B R Other → Accept']);
assert.deepEqual([realC.cls.names1,realC.cls.names2],[['B R Other','B R Surface Dark'],['Accept','B R Other','B R Surface Dark']]);
assert.equal(cn.otherAccept,1);assert.equal(cn.first.Other+cn.first.Dark,353);assert.equal(cn.re.Other+cn.re.Dark+cn.re.Accept,353);assert.equal(cn.re.Other,cn.first.Other-1);
assert.deepEqual([realC.cls.mAll,realC.cls.mOff1,realC.cls.mAnd,realC.cls.mOff2],[353,cn.first.Other,1,353-cn.re.Other]);   // 첫번째 B R Other 중 재분류 Other 아닌 것 = Accept 1개
assert.deepEqual(realC.cls.andRows,['B R Other→Accept']);assert.equal(realC.cls.sort2,'Accept');
assert.ok(realC.csv.split('\r\n').some(l=>/,B R Other,Accept,/.test(l)));assert.deepEqual(real0.scans,[['RCP/SETUP1/LOT_A/W01',353,'그대로']]);
// rev3 · rev4 에서 Slot 을 0 으로 만들던 조건: Slot 안 · Setup 폴더의 관계없는 파일 하나를 열 수 없음 → rev5 는 그 파일을 열지 않아 그대로 353
const real1=await realRun('bad',{bad:['RCP/SETUP1/LOT_A/W01/ManReClassify.ini','RCP/SETUP1/setup_note.ini'],extra:{'@SETUP1/setup_note.ini':btoa('[a]\nb=1\n')}});cmpReal('열 수 없는 파일',real1);
// Lot 폴더에도 Surface.flt(매칭 파일 없음) → 그 아래 실제 Slot 도 찾음(Step 1 과 같음), Lot 폴더 Slot 은 '매칭 파일 없음'(아래 Slot 파일을 빌려 쓰지 않음)
const real2=await realRun('lotflt',{extra:{'@SETUP1/LOT_A/Surface.flt':real.files['Surface.flt'],'@SETUP1/LOT_A/Surface.flt.md':real.files['Surface.flt.md']}});cmpReal('Lot 폴더 Surface.flt',real2);
assert.deepEqual(real2.scans,[['RCP/SETUP1/LOT_A',353,'ColorImageGrabingInfo.ini'],['RCP/SETUP1/LOT_A/W01',353,'그대로']]);
// ── 소유자 "ColorImageGrabingInfo.ini 파일 자체를 못 찾는다"(2026-11-11): 종전 rev5 는 이름으로 한 번만 물었다 → 아래 넷은 모두 '매칭 파일 없음'이었다 ──────────
//    지금: 이름으로 바로 → 폴더 목록(대소문자 무시, 프로그램 #48 · Step 1 과 같음) · 일시 오류 한 번 더 · 이 Slot 하나만 있는 위쪽 폴더. 그래도 없으면 까닭을 알림에.
const lowCI={drop:['ColorImageGrabingInfo.ini','ScanResultImageList.txt','frameToChuckPlane.ini'],extra:{'colorimagegrabinginfo.ini':real.files['ColorImageGrabingInfo.ini'],'SCANRESULTIMAGELIST.TXT':real.files['ScanResultImageList.txt'],'FrameToChuckPlane.ini':real.files['frameToChuckPlane.ini']}};
const realCs=await realRun('case',{...lowCI,cs:true});cmpReal('NAS: 이름 대소문자가 다름',realCs);assert.deepEqual(realCs.scans,[['RCP/SETUP1/LOT_A/W01',353,'그대로']]);
const realFl=await realRun('flaky1',{flaky:{'ColorImageGrabingInfo.ini':1}});cmpReal('이름으로 묻기 일시 오류(한 번)',realFl);assert.ok(realFl.askErr.length>=1);
const realFl2=await realRun('flakyAll',{flaky:{'ColorImageGrabingInfo.ini':Infinity}});cmpReal('이름으로 묻기가 늘 오류 → 폴더 목록',realFl2);assert.deepEqual(realFl2.scans,[['RCP/SETUP1/LOT_A/W01',353,'그대로']]);
// Surface.flt 가 Slot 하위 폴더에 있고 매칭 파일 · 사진은 그 위(그 아래 Slot 은 이것 하나) → 위쪽 폴더를 매칭 폴더로
const upF={drop:['Surface.flt'],extra:{'@SETUP1/LOT_A/W01/Result/Surface.flt':real.files['Surface.flt']},slot:'RCP/SETUP1/LOT_A/W01/Result'};
const realUp=await realRun('up',upF);cmpReal('매칭 파일이 위쪽 폴더',realUp);assert.deepEqual([realUp.at,realUp.cgPath],['up','RCP/SETUP1/LOT_A/W01']);
assert.ok(realUp.warns.some(w=>/위쪽 폴더에 있어 그 폴더를 매칭 폴더로 씀: RCP\/SETUP1\/LOT_A\/W01 \(그 아래 Slot 은 이것 하나\)/.test(w)),realUp.warns.join('\n'));
// 위쪽 폴더의 매칭 파일을 Slot 둘이 같이 씀 → 쓰지 않음(Index = 기록 순서가 Slot 마다 다름) + 알림에 까닭
const realSh=await realRun('shared',{...upF,extra:{...upF.extra,'@SETUP1/LOT_A/W01/Other/Surface.flt':real.files['Surface.flt']}});
assert.equal(realSh.scans.find(x=>x[0]==='RCP/SETUP1/LOT_A/W01/Result')[2],'ColorImageGrabingInfo.ini');
assert.match(realSh.msg,/Result\(없음: ColorImageGrabingInfo\.ini — Slot 폴더 파일 1개 중 이 이름\(대소문자 무시\) 없음 · 하위 폴더 0개 · 위쪽 폴더 1개도 찾아봄 · 위쪽 폴더 RCP\/SETUP1\/LOT_A\/W01 에 있지만 그 아래 Slot 이 2개라 쓰지 않음\)/);
// 정말 없음 → 까닭: 파일 수 · 비슷한 이름 · 이름으로 묻기 오류 · 찾아본 폴더(전체 경로 길이는 [원본 폴더 경로]를 적었을 때)
const realNo=await realRun('noCI',{drop:['ColorImageGrabingInfo.ini'],extra:{'ColorImageGrabbingInfo.ini':real.files['ColorImageGrabingInfo.ini']},flaky:{'ColorImageGrabingInfo.ini':Infinity}});
assert.equal(realNo.scans[0][2],'ColorImageGrabingInfo.ini');
assert.match(realNo.msg,/W01\(없음: ColorImageGrabingInfo\.ini — Slot 폴더 파일 [\d,]+개 중 이 이름\(대소문자 무시\) 없음 · 비슷한 이름: ColorImageGrabbingInfo\.ini · 이름으로 묻기 오류: ColorImageGrabingInfo\.ini: NotReadableError The I\/O operation has been aborted · 하위 폴더 0개 · 위쪽 폴더 3개도 찾아봄\)/);
// 파일 목록(webkitdirectory)으로 골라도 위쪽 폴더 · 여러 Slot 규칙이 같음
const pgL=await browser.newPage();await pgL.goto('file://'+resolve(root,'AOI_Contrast_Wizard_rev6.html'));
const listUp=await pgL.evaluate(async ({real})=>{const c=window.__cw,b=s=>new File([Uint8Array.from(atob(s),ch=>ch.charCodeAt(0))],'x');const es=[];
  for(const [k,v] of Object.entries(real.files)){if(k==='Surface.flt'||/\.jpe?g$/i.test(k))continue;es.push({path:'L/S/LOT/W01/'+k,file:b(v)})}
  es.push({path:'L/S/LOT/W01/Result/Surface.flt',file:b(real.files['Surface.flt'])});c.BIG.scans=[];await c.addBigEntries(es);const s=c.BIG.scans[0];
  return {name:s.name,at:s.cg.at,path:s.cg.path,col:s.cg.colors.length,hits:s.cg.plan&&s.cg.plan.hits}},{real});await pgL.close();
assert.deepEqual(listUp,{name:'L/S/LOT/W01/Result',at:'up',path:'L/S/LOT/W01',col:353,hits:353});
// 좌표 기준(프로그램 v12.9.30 COORD_MODES): Fault · Defect 좌표가 프레임 직사각형의 좌측 하단 원점 기준이면 '좌측 하단 원점'으로 같은 짝
const real3=await realRun('shift',{shift:true});cmpReal('좌측 하단 원점 좌표',real3);assert.deepEqual(real3.scans,[['RCP/SETUP1/LOT_A/W01',353,'좌측 하단 원점']]);
// ── 소유자 확정(2026-11-10): ColorImageGrabingInfo.ini 는 항상 있음 · ScanResultImageList.txt 는 없을 수 있음 · frameToChuckPlane.1.ini · .2.ini 둘이면 .2 기준 ──────────
//    프로그램 파일이 없을 때만 대신 계산(실제 결과 폴더에서 확인한 관계: Gray 사진 이름 = 프레임 가운데 Table 좌표, 목록 좌표 = 프레임 가운데)
const real4=await realRun('noList',{drop:['ScanResultImageList.txt']});const d4=cmpReal('목록 없음 → 사진 이름 + Wafer2Table',real4,3);
assert.equal(real4.src.frames,'Gray 사진 이름 + Wafer2Table.ini');assert.match(real4.msg,/프로그램 파일 대신 계산한 Slot 1개[\s\S]*W01: Gray 사진 이름 \+ Wafer2Table\.ini/);
assert.match(real4.row,/436\s*Gray 사진 이름 \+ Wafer2Table\.ini/);assert.match(real4.csv,/,Gray 사진 이름 \+ Wafer2Table\.ini,frameToChuckPlane\.ini,/);
const real5=await realRun('noListW2T',{drop:['ScanResultImageList.txt','Wafer2Table.ini']});const d5=cmpReal('목록 · Wafer2Table 없음 → 사진 이름 + s_FrameData',real5,0.2);
assert.equal(real5.src.frames,'Gray 사진 이름 + s_FrameData.dat');
// 변환 파일 .1 · .2 둘(공통 파일 없음) → 레시피 번호가 같은 파일, 없으면 큰 번호 .2(소유자). 이 자료 Color 는 RecipeNumber 0 → .2. .1 은 일부러 500 µm 어긋나게 — 점검 칸에 '.1 이면 몇 개'
const tfTxt=atob(real.files['frameToChuckPlane.ini']),tf1=tfTxt.replace(/(Scan_X=\s*\S+\s+\S+\s+)(\S+)/,(m,a,b)=>a+(+b+500));
const real6=await realRun('tf12',{drop:['frameToChuckPlane.ini'],extra:{'frameToChuckPlane.2.ini':real.files['frameToChuckPlane.ini'],'frameToChuckPlane.1.ini':btoa(tf1)}});cmpReal('변환 .1 · .2 → .2',real6);
assert.equal(real6.src.tf,'frameToChuckPlane.1.ini · frameToChuckPlane.2.ini(레시피 번호가 같은 파일, 없으면 큰 번호 frameToChuckPlane.2.ini)');assert.match(real6.msg,/프로그램 파일 대신 계산한 Slot 1개[\s\S]*없으면 큰 번호 frameToChuckPlane\.2\.ini/);assert.equal(real6.alt.length,1);assert.equal(real6.alt[0][0],'frameToChuckPlane.1.ini');assert.ok(real6.alt[0][1]<353,JSON.stringify(real6.alt));
assert.match(real6.row,/없으면 큰 번호 frameToChuckPlane\.2\.ini\)[\s\S]*frameToChuckPlane\.1\.ini 이면 Gray 위치 \d+ \/ 353/);
// 레시피마다 변환 파일 · Gray 사진(소유자 예 29126432EWE3: Color RecipeNumber 1 · 2, Gray X.Y.t.1 · t.2.jpeg) → 레시피 번호가 같은 파일(프로그램과 같음) — Color 를 레시피 1 로 바꾸면 .1(어긋난 것)을 써서 일부가 달라짐
const ci1=atob(real.files['ColorImageGrabingInfo.ini']).replace(/RecipeNumber=0/g,'RecipeNumber=1');
const real6b=await realRun('tfRecipe',{drop:['frameToChuckPlane.ini'],extra:{'frameToChuckPlane.2.ini':real.files['frameToChuckPlane.ini'],'frameToChuckPlane.1.ini':btoa(tf1),'ColorImageGrabingInfo.ini':btoa(ci1)}});
assert.ok(real6b.pairs.filter(p=>p[1]==='ok'&&Math.abs(p[5]-real.exp[p[0]][2])<1e-6).length<353,'recipe 1 → .1');assert.doesNotMatch(real6b.msg,/프로그램 파일 대신 계산한 Slot/);
// 변환 파일 없음 → 가운데 모델(픽셀 크기 = s_FrameData) · 목록과 변환 파일 둘 다 없음
const real7=await realRun('noTf',{drop:['frameToChuckPlane.ini']});const d7=cmpReal('변환 파일 없음 → 가운데 모델',real7,0.2);assert.match(real7.src.tf,/가운데 모델\(목록 좌표 = 프레임 가운데, 픽셀 0\.7699\d* µm\)/);
const real8=await realRun('noListTf',{drop:['ScanResultImageList.txt','frameToChuckPlane.ini']});const d8=cmpReal('목록 · 변환 파일 없음',real8,3);
// 대신할 것도 없음(목록 · Wafer2Table · s_FrameData 없음) → Gray 위치는 어림셈 안 함, Color 는 그대로 연결('Color 만')
const real9=await realRun('nothing',{drop:['ScanResultImageList.txt','Wafer2Table.ini','s_FrameData.dat','s_FrameData.dat.md']});
assert.equal(real9.src.frames,'Gray 없음(Wafer2Table.ini · s_FrameData.dat 가 없음)');assert.ok(real9.pairs.every(p=>p[1]==='color'&&p[2]===real.exp[p[0]][0]),'nothing');
assert.match(real9.row,/Gray 위치를 못 구함 — ScanResultImageList\.txt 가 없고 대신할 것도 없음/);
// Color 사진만 있는 Slot(소유자 예: Gray 사진 · 목록이 저장되지 않음) → Color 353 개는 연결해 보여 주고 Gray 는 '없음'
const noGray=Object.keys(real.files).filter(k=>/\.t\.jpeg$/i.test(k)).concat(['ScanResultImageList.txt']);
const real10=await realRun('colorOnly',{drop:noGray,view:true});
assert.equal(real10.pop.conly,true);assert.equal(real10.pop.color,true);assert.equal(real10.pop.grayShown,false);assert.ok(real10.pop.fcW>real10.pop.bodyW*0.9,JSON.stringify(real10.pop));   // 새 창 = Color 가 창 전체
assert.match(real10.pop.hd,/Gray 없음 — Color 만 크게 \(Gray 사진 없음 — 이 Slot 에는 Gray 프레임 사진/);
assert.deepEqual([real10.c5.n,real10.c5.conly,real10.c5.gray],[353,1,false]);assert.match(real10.c5.cnt,/Defect 353개 \(사진 있는 것만\)/);   // 5-3: Color 만인 Defect 도 기본으로 보임
assert.ok(real10.pairs.every(p=>p[1]==='color'&&p[2]===real.exp[p[0]][0]&&p[3]==='Index = 기록 순서'),'colorOnly');
assert.match(real10.msg,/Gray 사진이 없는 Slot 1개\(Color 사진만 저장됨[\s\S]*W01/);assert.match(real10.row,/Gray 사진 없음 — 이 Slot 에는 Gray 프레임 사진\(X\.Y\.t\.jpeg\)/);
assert.match(real10.csv,/Color 만 \(Gray 없음\),.*Gray 사진 없음 — 이 Slot 에는 Gray 프레임 사진/);
console.log(`step5 실제 결과 폴더: 프로그램 파일 4가지 조건 353/353 = colorgray.py · 대체 계산 5가지 353/353 같은 프레임(픽셀 차 최대 ${[d4,d5,d7,d8].map(v=>v.toFixed(2)).join(' · ')} px)`);

// ── rev4 의 Surface.flt.md 찾기(Step 1 순서)는 그대로 — md 가 Lot 폴더 · Slot 하위 폴더에 있고 x · y 자리가 바뀌어도 5-1 좌표 · 짝이 같음 ─────────────
const scen=async opt=>{const pg=await browser.newPage();const er=[];pg.on('pageerror',e=>er.push(String(e)));
  await pg.goto('file://'+resolve(root,'AOI_Contrast_Wizard_rev6.html'));
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
    const r={mdAt:s.mdAt,mdPath:s.mdPath,xOk:[...s.cols.x].every((v,i)=>v===exp.x[i])&&[...s.cols.y].every((v,i)=>v===exp.y[i]),n:s.cols.n,msg:document.getElementById('bigMsg').innerText};
    await c.b5Pair(null);r.pairs=c.BIG.pairs.map(p=>[p.i,p.st,p.c&&p.c.file,p.g&&p.g.file,p.g&&+p.g.px.toFixed(2)]).sort((a,b)=>a[0]-b[0]);return r},{fx:fixture,opt});
  await pg.close();return {...r,er}};
const base=await scen({md:'slot'});
assert.equal(base.mdAt,'slot');assert.equal(base.xOk,true);assert.equal(base.n,4);assert.ok(!/Surface\.flt\.md 위치/.test(base.msg),base.msg);assert.deepEqual(base.er,[]);
assert.deepEqual(base.pairs,[[0,'none',null,null,null],[1,'ok','C1.c.1.jpeg','F1.t.1.jpeg',1100],[2,'none',null,null,null],[3,'none',null,null,null]]);
const lotSw=await scen({md:'lot',swap:true});
assert.equal(lotSw.mdAt,'up');assert.equal(lotSw.mdPath,'RCP/SETUP1/LOT_CA20/Surface.flt.md');assert.equal(lotSw.xOk,true,JSON.stringify(lotSw));
assert.match(lotSw.msg,/Surface\.flt\.md 위치\(Step 1 과 같은 순서로 찾음\): 위쪽 폴더 1/);assert.deepEqual(lotSw.pairs,base.pairs);assert.deepEqual(lotSw.er,[]);
const subSw=await scen({md:'sub',swap:true});
assert.equal(subSw.mdAt,'sub');assert.equal(subSw.mdPath,'RCP/SETUP1/LOT_CA20/W01/Sub/Surface.flt.md');assert.equal(subSw.xOk,true);
assert.match(subSw.msg,/Slot 하위 폴더 1/);assert.deepEqual(subSw.pairs,base.pairs);assert.deepEqual(subSw.er,[]);
// #66: 회사 PC Chrome 이 폴더 핸들로 .ini 를 막음(getFileHandle TypeError 'Name is not allowed' · 목록에도 .ini 없음) → 파일 목록 방식으로 바꾸고 기억, 그 방식이면 매칭 됨
{const pg=await browser.newPage();const er=[];pg.on('pageerror',e=>er.push(String(e)));
  await pg.goto('file://'+resolve(root,'AOI_Contrast_Wizard_rev6.html'));await pg.evaluate(src=>{(0,eval)(src)},fakeTree);
  const r=await pg.evaluate(async real=>{const c=window.__cw;let picks=0,inputs=0;try{localStorage.removeItem('cw.bigList')}catch(e){}
    const root=window.__mkTree(real.files,p=>['SETUP1','LOT_A','W01',p],{blockIni:true});window.showDirectoryPicker=async()=>{picks++;return root};
    document.getElementById('bigInput').click=()=>{inputs++};
    document.getElementById('bigAdd').click();const el=document.getElementById('busy');
    await new Promise(r=>{const t0=Date.now(),t=setInterval(()=>{if((/파일 목록 방식/.test(document.getElementById('bigMsg').innerText)&&el.hidden)||Date.now()-t0>20000){clearInterval(t);r()}},20)});
    const first={msg:document.getElementById('bigMsg').innerText,scans:c.BIG.scans.length,flag:localStorage.getItem('cw.bigList'),picks,inputs};
    document.getElementById('bigAdd').click();await new Promise(r=>setTimeout(r,50));const second={picks,inputs};busy(null);
    const ents=Object.entries(real.files).map(([k,b])=>({path:'RCP/SETUP1/LOT_A/W01/'+k,file:new File([Uint8Array.from(atob(b),ch=>ch.charCodeAt(0))],k)}));
    await c.addBigEntries(ents);const s=c.BIG.scans[0];return {first,second,n:c.BIG.scans.length,hits:s&&s.cg&&s.cg.plan?s.cg.plan.hits:null,miss:s?c.cgMiss(s.cg):null}},real);
  await pg.close();
  assert.deepEqual(er,[]);assert.match(r.first.msg,/Name is not allowed/);assert.match(r.first.msg,/\[폴더 추가\]를 한 번 더/);
  assert.equal(r.first.scans,0);assert.equal(r.first.flag,'1');assert.equal(r.first.picks,1);
  assert.ok(r.first.inputs<=1);assert.deepEqual(r.second,{picks:1,inputs:r.first.inputs+1});   // 누른 직후면 바로 파일 목록 창, 두 번째는 폴더 핸들을 묻지 않고 webkitdirectory
  assert.equal(r.n,1);assert.equal(r.hits,353,JSON.stringify(r))}
assert.deepEqual(errors,[]);assert.deepEqual(requests,[]);
await browser.close();
console.log('test_contrast_wizard_rev6: passed');
