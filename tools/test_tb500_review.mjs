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
// 조회
await page.locator('#lots').fill('TB500.INT1041\nTB500.INT948');
await page.getByRole('button',{name:'조회',exact:true}).click();
await page.locator('#msg').filter({hasText:'조회 완료'}).waitFor();
const rows=await page.locator('#tbody tr').allInnerTexts();
const find=k=>rows.find(r=>new RegExp('(^|\\t)'+k+'\\t').test(r))||'';
assert.match(find('RDL4'),/재리뷰 완료[\s\S]*1-1\. RDL4_재리뷰 · 맵\(\.txt\) 2개/);
assert.match(find('PIDS3'),/재리뷰 완료[\s\S]*맵\(\.txt\) 1개/);
assert.match(find('PIDS5'),/Skip/);
assert.match(find('PIDS7'),/Skip/);
assert.match(find('RDL2'),/재리뷰 필요\tKLA\t[\s\S]*여러 호기 2대[\s\S]*AOI-K6 · 2026-11-05 10:00[\s\S]*AOI-K2 · 2026-11-04 07:30/);
assert.match(find('RDL1'),/재리뷰 필요\tCamtek\t[\s\S]*여러 호기 2대[\s\S]*AOI-22 · 2026-10-21 22:05:00[\s\S]*AOI-21 · 2026-10-20 09:10:00/);
assert.ok(!/WGB/.test(find('RDL1')));
assert.match(rows[0],/976\. TB500\.INT1041 \(CMS\)[\s\S]*S\/M CMS[\s\S]*기타 폴더: 메모/);
assert.match(rows.at(-1),/TB500\.INT948\tConder Scan 에서 Lot 폴더를 찾지 못했습니다/);
// 더보기 · Lot History
await page.locator('#tbody tr').filter({hasText:'RDL1'}).first().getByRole('button',{name:'더보기 · Lot History'}).click();
const dlg=await page.locator('#dlgBody').innerText();
assert.match(dlg,/RDL1 스캔 기록 — 2건 · 호기 2대 \(여러 호기에서 스캔됨\)/);
assert.match(dlg,/Lot History \(모든 Layer\) — 6건 · 호기 4대/);
assert.match(dlg,/호기 이동/);
const hist=await page.locator('#dlgBody table').nth(1).locator('tbody tr').allInnerTexts();
assert.deepEqual(hist.map(t=>t.split('\t')[2]),['PIDS3','RDL3','RDL1','RDL1','RDL2','RDL2']);
await page.getByRole('button',{name:'닫기'}).click();
await page.locator('#tbody').getByRole('button',{name:'Lot History',exact:true}).click();
assert.match(await page.locator('#dlgTitle').innerText(),/TB500\.INT1041 · Lot History/);
await page.getByRole('button',{name:'닫기'}).click();
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
