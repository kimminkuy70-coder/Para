// TB500_Review.html 자동 시험(Para #40). 브라우저 폴더 선택창은 자동화할 수 없어
// window.__TB500_TEST__.pick 으로 가짜 폴더(File System Access API 모양)를 넘긴다.
// 실행: PARA_TEST_NODE_MODULES=<playwright 가 있는 node_modules> node tools/test_tb500_review.mjs
import {createRequire} from 'node:module';
import {execFileSync} from 'node:child_process';
import {resolve,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url);
const {chromium}=require(require.resolve('playwright',{paths:[process.env.PARA_TEST_NODE_MODULES||process.cwd()]}));
const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const fixture=execFileSync('python3',[resolve(root,'tools/tb500_review_fixture.py')],{encoding:'utf-8',maxBuffer:1<<26});
const browser=await chromium.launch();
const page=await browser.newPage();
const errors=[];page.on('pageerror',e=>errors.push(String(e)));
await page.addInitScript(({fx})=>{
  const files=JSON.parse(fx);
  const b64=s=>Uint8Array.from(atob(s),c=>c.charCodeAt(0));
  class FH{constructor(name,dir){this.kind='file';this.name=name;this.dir=dir}
    async getFile(){const d=this.dir.files.get(this.name);if(!d)throw new DOMException('gone','NotFoundError');return new File([d],this.name)}
    async createWritable(){const self=this,parts=[];return{async write(t){parts.push(typeof t==='string'?new TextEncoder().encode(t):t)},async close(){self.dir.files.set(self.name,new Uint8Array(await new Blob(parts).arrayBuffer()));self.dir.log.push('write '+self.name)}}}}
  class DH{constructor(name,log){this.kind='directory';this.name=name;this.files=new Map;this.dirs=new Map;this.log=log}
    sub(n){if(!this.dirs.has(n))this.dirs.set(n,new DH(n,this.log));return this.dirs.get(n)}
    async *entries(){for(const n of this.dirs.keys())yield [n,this.dirs.get(n)];for(const n of this.files.keys())yield [n,new FH(n,this)]}
    async getDirectoryHandle(n){if(!this.dirs.has(n))throw new DOMException('no','NotFoundError');return this.dirs.get(n)}
    async getFileHandle(n,o){if(!this.files.has(n)){if(!(o&&o.create))throw new DOMException('no','NotFoundError');this.files.set(n,new Uint8Array())}return new FH(n,this)}
    async removeEntry(n){if(!this.files.delete(n))throw new DOMException('no','NotFoundError');this.log.push('remove '+n)}}
  const log=[],top={};
  for(const [p,v] of Object.entries(files)){const parts=p.split('/');const k=parts.shift();top[k]=top[k]||new DH(k,log);let d=top[k];while(parts.length>1)d=d.sub(parts.shift());d.files.set(parts[0],b64(v))}
  window.__fs={top,log};
  window.__TB500_TEST__={now:localStorage.getItem('test-now')||'2026-11-06T12:00:00',pick:async kind=>top[kind]};
},{fx:fixture});
await page.goto('file://'+resolve(root,'TB500_Review.html'));
// SHA-256 구현 = Node crypto
for(const n of [0,3,55,56,63,64,65,200,1000]){const bytes=Array.from({length:n},(_,i)=>(i*7+3)&255);
  assert.equal(await page.evaluate(b=>window.__tb500Sha(new Uint8Array(b)),bytes),createHash('sha256').update(Buffer.from(bytes)).digest('hex'),'sha '+n)}
// 순수 함수
const fn=await page.evaluate(()=>{const t=window.__tb500;return{
  code:[t.lotCode('CMS-RDL1'),t.lotCode('0701 N SPT X'),t.lotCode('FOCUS'),t.lotCode('BBF_WBG')],
  kinds:['1-1. RDL4_재리뷰','1. RDL4_재스캔 (#24,25)','4. PIDS5_Skip (RDL3 재리뷰 결과 나오면 맵만 수정해 주세요)','3. RDL3 (#23X)'].map(t.kindOf),
  stage:[t.stageOf('4. PIDS5_Skip ').key,t.stageOf('TB500_PI4-Multi').key,t.stageOf('TB500_RDL3-Multi').key,t.stageOf('RDL12')],
  start:[t.batchStart('30-Aug-26 09:41:31 PM'),t.batchStart('01-Jan-26 12:05:00 AM'),t.fileStart('J_S_SM_26-Oct-22_(11.23.53)_BatchReport.htm')]}});
assert.deepEqual(fn.code,['CMS','SPT','','BBF']);
assert.deepEqual(fn.kinds,['rereview','rescan','skip','base']);
assert.deepEqual(fn.stage,['PIDS5','PIDS3','RDL3',null]);
assert.deepEqual(fn.start,['2026-08-30 21:41:31','2026-01-01 00:05:00','2026-10-22 11:23:53']);
// 첫 화면 = 캐시 없음 알림
await page.locator('#banner.show').waitFor();
for(const k of ['share','conder','local'])await page.locator(`[data-pick="${k}"]`).click();
await page.getByRole('button',{name:'캐시 갱신'}).click();
await page.locator('#msg').filter({hasText:'KLA 캐시: KLA_캐시_20261106_090100.zip 받음'}).waitFor();
const log=await page.evaluate(()=>window.__fs.log);
assert.ok(log.includes('remove TB500리뷰_Camtek색인_20200101_000000.json'),JSON.stringify(log));     // 최신 1개만
const localNames=await page.evaluate(()=>[...window.__fs.top.local.files.keys()].sort());
assert.deepEqual(localNames,['TB500리뷰_Camtek색인_20261106_090000.json','TB500리뷰_KLA색인_20261106_090100.json','TB500리뷰_기록.json','다른파일.txt']);
assert.ok(!log.some(l=>/^write/.test(l)&&!/^write TB500리뷰_/.test(l)));                              // 우리 파일만 씀
assert.equal(await page.locator('#banner.show').count(),0);
assert.match(await page.locator('#cache-camtek').innerText(),/호기 2 대 · Batch Report 5 개/);
// 다시 누르면 이미 최신
await page.getByRole('button',{name:'캐시 갱신'}).click();
await page.locator('#msg').filter({hasText:'Camtek 캐시: 이미 최신'}).waitFor();
// 예전 형식(schema 2 — wafer 별 Pass/Fail 없음) 색인은 같은 zip 이어도 다시 푼다.
await page.evaluate(()=>{const d=window.__fs.top.local,n='TB500리뷰_Camtek색인_20261106_090000.json',j=JSON.parse(new TextDecoder().decode(d.files.get(n)));j.schema=3;j.rows.forEach(r=>r.length=10);d.files.set(n,new TextEncoder().encode(JSON.stringify(j)))});
await page.getByRole('button',{name:'캐시 갱신'}).click();
await page.locator('#msg').filter({hasText:'Camtek 캐시: BatchReport_캐시_20261106_090000.zip 받음'}).waitFor();
assert.equal(await page.evaluate(()=>JSON.parse(new TextDecoder().decode(window.__fs.top.local.files.get('TB500리뷰_Camtek색인_20261106_090000.json'))).schema),4);
// 조회
await page.locator('#lots').fill('TB500.INT1041\nTB500.INT948');
await page.getByRole('button',{name:'조회',exact:true}).click();
await page.locator('#msg').filter({hasText:'조회 완료'}).waitFor();
const rows=(await page.locator('#tbody tr').allInnerTexts()).map(t=>t.replace(/[ \n]*\t[ \n]*/g,'\t').replace(/\n+/g,' ').trim());
// Para #41: 한 줄 = Conder Scan Lot 폴더 안의 실제 하위 폴더 하나(이름 그대로).
const find=n=>rows.find(r=>r.includes(n+'\t')||r.includes(n+' 재리뷰\t')||r.includes(n+' 재스캔\t')||r.includes(n+' Skip\t'))||'';
assert.ok(rows.every(r=>!/조사하지 않음/.test(r)),'조사하지 않음 문구 없음');
assert.match(find('1-1. RDL4_재리뷰'),/RDL4\t6305 AOI 6412 2D\/RE\t재리뷰 결과 맵\(\.txt\) 2개\t\t\t경로 복사$/);
assert.match(find('1. RDL4'),/^1\. RDL4\tRDL4\t[\s\S]*\t재리뷰 완료\t\t\t경로 복사/);
assert.match(find('1. RDL4_재스캔 (#24,25)'),/재스캔\tRDL4[\s\S]*재리뷰 완료\t\t\t/);
assert.match(find('2. PIDS3_재리뷰'),/맵\(\.txt\) 1개/);
assert.match(find('4. PIDS5_Skip (RDL3 재리뷰 결과 나오면 맵만 수정해 주세요)'),/PIDS5[\s\S]*\tSkip\t\t\t/);
assert.match(find('5. RDL2'),/재리뷰 필요\tKLA\t여러 호기 2대[\s\S]*AOI-K6 · 2026-11-05 10:00[\s\S]*AOI-K2 · 2026-11-04 07:30[\s\S]*Lot History/);
assert.match(find('7. RDL1'),/재리뷰 필요\tCamtek\t여러 호기 2대 재스캔으로 완료 wafer 25 · 한 번에 Pass 22 · 재스캔 Pass 3[\s\S]*AOI-22 · 2026-10-21 22:05:00 정상 Pass 3[\s\S]*AOI-21 · 2026-10-20 09:10:00 Error Pass 22 · Error 3/);
assert.ok(!/WGB/.test(find('7. RDL1')));
assert.match(find('메모'),/^메모\t\t\t\t\t\t경로 복사$/);                                      // Layer 모르는 폴더도 이름 그대로, 나머지는 빈칸
assert.equal(rows.filter(r=>/TB500\.INT1041/.test(r)).length,1);
assert.match(rows[0],/^TB500\.INT1041\t976\. TB500\.INT1041 \(CMS\) S\/M CMS Lot History\t1-1\. RDL4_재리뷰/);
assert.equal(rows.length,13+1);
assert.match(rows.at(-1),/TB500\.INT948\tConder Scan 에서 Lot 폴더를 찾지 못했습니다/);
// Lot History (RDL1 줄에서 열면 RDL1 만, [전체]를 누르면 모든 Layer)
await page.locator('#tbody tr').filter({hasText:'7. RDL1'}).getByRole('button',{name:'Lot History'}).click();
const body=page.locator('#dlgBody');
assert.equal(await body.locator('.chip.on').innerText(),'RDL1 2');
assert.equal(await body.locator('li.hrow').count(),2);
assert.match(await body.locator('li.gapline').innerText(),/1일 12시간 뒤 · 다시 스캔 · 호기 이동 AOI-21 → AOI-22/);
assert.equal(await body.locator('svg rect').count(),4);
// Para #42: Camtek 기록 = Camtek AOI Manager 처럼 Batch Report 결과(정상/Error/작업자 중단) + wafer 판정
assert.deepEqual(await body.locator('li.hrow .scanb').allInnerTexts(),['Error','정상']);
assert.deepEqual(await body.locator('li.hrow .scanb').evaluateAll(e=>e.map(x=>x.className)),['scanb part','scanb all']);
assert.deepEqual(await body.locator('svg text.sv-pass').allTextContents(),['22P 3E','3P']);
const vt=body.locator('table.vtab');
assert.equal(await vt.count(),1);
assert.match(await body.locator('.vgrp h5').innerText(),/RDL1 재스캔으로 완료\s*wafer 25 · 한 번에 Pass 22 · 재스캔 Pass 3/);
const vrows=await vt.locator('tbody tr').allInnerTexts();
assert.equal(vrows.length,25);
assert.deepEqual(vrows[0].split('\t').map(x=>x.trim()),['25','W00','Scan 2D Error. Aborted.','Pass','재스캔 Pass']);
assert.deepEqual(vrows[3].split('\t').map(x=>x.trim()),['22','W03','Pass','','한 번에 Pass']);
// Batch Report 이름을 누르면 실제 Batch Report 꼴로 보기(머리 정보 · 슬롯 · Scanned · Faults …)
await body.locator('button.brlink').first().click();
const br=page.locator('#brBody');
assert.match(await page.locator('#brTitle').innerText(),/^TB500_RDL1-Multi_Setup1_CMS-RDL1_26-Oct-20_\(09\.10\.00\)_BatchReport\.htm$/);
assert.match(await br.locator('.brmeta').innerText(),/Job\/Setup\s+TB500_RDL1-Multi\/Setup1[\s\S]*Wafers Scanned\s+25/);
assert.match(await br.locator('.brhead').innerText(),/AOI-21 · 2026-10-20 09:10:00 Error\s*Pass 22 · Error 3/);
const brh=(await br.locator('.brwafers thead th').allInnerTexts()).map(x=>x.trim());
assert.deepEqual(brh,['슬롯','Lot','Wafer ID','Pass/Fail','Scanned Dice','Bad Dice','Good Dice','Faults','Yield','Recipe(s)']);
const brr=await br.locator('.brwafers tbody tr').allInnerTexts();
assert.equal(brr.length,25);
assert.deepEqual(brr[0].split('\t').map(x=>x.trim()).slice(0,4),['25','CMS-RDL1','W00','Scan 2D Error. Aborted.']);
assert.deepEqual(brr[3].split('\t').map(x=>x.trim()),['22','CMS-RDL1','W03','Pass','1200','13','1187','43','98.92','TB500_RDL1-Multi']);
assert.equal(await br.locator('.brwafers td.ve').count(),3);
await page.locator('#brClose').click();
assert.ok(await page.locator('#dlg').evaluate(d=>d.open));
// 순수 함수: 작업자 중단 · 스캔 안 한 슬롯 · 연쇄(lotmodel.attempt 와 같음)
const wc=await page.evaluate(()=>{const f=window.__tb500.waferCells;return [
  f([{'Pass/Fail':'Pass'},{'Pass/Fail':'Aborted.'},{'Pass/Fail':'Skipped.'}]).map(c=>c[2]).join(''),
  f([{'Pass/Fail':'Skipped.'},{'Pass/Fail':'Pass'},{'Pass/Fail':'Alignment Error.'},{'Pass/Fail':'Aborted.'},{'Pass/Fail':''}]).map(c=>c[2]).join(''),
  f([{'Pass/Fail':'Pass.','Wafer ID':'SF14G07-A0'}]).map(c=>c[0])]});
assert.deepEqual(wc,['PAA','SPEEE',[7]]);
await body.getByRole('button',{name:/^전체/}).click();
const hrows=await body.locator('li.hrow').allInnerTexts();
assert.deepEqual(hrows.map(t=>t.split('\n').map(x=>x.trim()).filter(Boolean)[3]),['PIDS3','RDL3','RDL1','RDL1','RDL2','RDL2']);
assert.match(await body.locator('.hkpi').innerText(),/6\s*스캔\s*4\s*호기 · AOI-22, AOI-21, AOI-K2, AOI-K6\s*4\s*호기 이동/);
await page.getByRole('button',{name:'닫기'}).click();
await page.locator('#tbody td.lothead').getByRole('button',{name:'Lot History'}).click();
assert.match(await page.locator('#dlgTitle').innerText(),/TB500\.INT1041 · Lot History/);
assert.equal(await body.locator('li.hrow').count(),6);
if(process.env.TB500_SHOT){await page.setViewportSize({width:1400,height:1000});await page.locator('#dlg').screenshot({path:process.env.TB500_SHOT+'/hist.png'});}
await page.getByRole('button',{name:'닫기'}).click();
if(process.env.TB500_SHOT)await page.locator('.result').screenshot({path:process.env.TB500_SHOT+'/table.png'});
// 원본(Conder · OneDrive)에는 아무것도 쓰지 않음
assert.ok(!log.concat(await page.evaluate(()=>window.__fs.log)).some(l=>/conder|share/.test(l)));
// 오래된 캐시 알림
await page.evaluate(()=>localStorage.setItem('test-now','2026-11-09T12:00:00'));
await page.reload();
await page.locator('#banner.show').filter({hasText:'지났습니다'}).waitFor();
await page.setViewportSize({width:1500,height:1000});
assert.deepEqual(errors,[]);
await browser.close();
console.log(JSON.stringify({passed:true}));
