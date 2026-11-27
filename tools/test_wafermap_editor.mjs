// Wafer Map 편집기(#91) 화면 시험 — 진짜 로컬 서버(webserver.py) + 빌드한 화면(frontend/dist) + 진짜 엔진.
// 흐름: 폴더 → 목록 → 편집(클릭 · 끌기 · 사각형 · ___ 잠금 · 새 코드 · 되돌리기/다시 하기 · 좌표) → 저장(범례 · 이름 · 위치) → 비교 → 처음 화면으로 → 새로 시작하기.
// 마지막에 4만 · 100만 Die 가짜 맵으로 여는 시간 · 확대 한 번 그리는 시간을 잰다(이 PC 의 Chromium 기준 — 회사 PC 실측 아님).
// 실행: PARA_TEST_NODE_MODULES=/opt/node-tools/node_modules CODEX_PRIMARY_RUNTIME_PYTHON=python3 node tools/test_wafermap_editor.mjs
import {createRequire} from 'node:module';
import {mkdtemp, readFile, rm, mkdir, writeFile, readdir} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {spawn, execFileSync} from 'node:child_process';
import {createInterface} from 'node:readline';
import assert from 'node:assert/strict';

const require=createRequire(import.meta.url);
const {chromium}=require(require.resolve('playwright',{paths:[process.env.PARA_TEST_NODE_MODULES||process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES||process.cwd()]}));
const root=resolve(new URL('..',import.meta.url).pathname);
const fixture=await mkdtemp(join(tmpdir(),'para-wme-'));
const python=process.env.CODEX_PRIMARY_RUNTIME_PYTHON||'python';
execFileSync(python,[join(root,'tests/desktop_browser_fixture.py'),'init',fixture]);

/** 원 모양 맵: 원 밖 = ___, 안 = 000, (r+c)%97==0 인 곳 = 003. rows[0] = 맵 위쪽. */
function mapTxt(n,wafer,nl='\r\n'){
  const rows=[];for(let r=0;r<n;r++){const row=[];for(let c=0;c<n;c++){const dx=c-(n-1)/2,dy=r-(n-1)/2;
    row.push(dx*dx+dy*dy>(n/2)*(n/2)?'___':((r+c)%97===0?'003':'000'));}rows.push('RowData:'+row.join(' '));}
  return [`WAFER:${wafer}`,'DEVICE:DEV-A','LOT:LOT01',`ROWCT:${n}`,`COLCT:${n}`,...rows].join(nl)+nl;
}
const maps=join(fixture,'maps');await mkdir(join(maps,'sub'),{recursive:true});
const small=mapTxt(12,'W01');
await writeFile(join(maps,'W01.txt'),small);
await writeFile(join(maps,'sub','W40K.txt'),mapTxt(226,'W40K'));      // 원 안 약 4만 Die
await writeFile(join(maps,'sub','W1M.txt'),mapTxt(1130,'W1M'));       // 원 안 약 100만 Die

const browser=await chromium.launch({headless:true});
const engine=spawn(python,[join(root,'tests/desktop_browser_fixture.py'),'web',fixture],{cwd:root,stdio:['pipe','pipe','pipe']});
const page=await browser.newPage({viewport:{width:1440,height:1000}});
const errors=[];page.on('pageerror',e=>errors.push(e.message));
const lines=createInterface({input:engine.stdout});
let appUrl;const urlReady=new Promise(res=>lines.on('line',line=>{const m=JSON.parse(line);if(m.url){appUrl=m.url;res();}}));
let stderr='';engine.stderr.on('data',d=>stderr+=d);
const canvas=label=>page.getByLabel(label,{exact:true});
/** 맵 Die (col, row = 위에서 몇째 줄) 의 화면 위치(canvas 가 data-s/x/y 로 알려 줌). */
async function diePos(label,col,row){
  const b=await canvas(label).boundingBox();const d=await canvas(label).evaluate(c=>({s:+c.dataset.s,x:+c.dataset.x,y:+c.dataset.y}));
  return {x:b.x+d.x+(col+.5)*d.s,y:b.y+d.y+(row+.5)*d.s};
}
const status=()=>page.getByLabel('Die 정보').innerText();
// PARA_WM_SHOTS=폴더 이면 화면마다 스크린샷(디자인 전 · 후 비교용, 1440 · 1100 폭)
const shotDir=process.env.PARA_WM_SHOTS;
async function shot(name){if(!shotDir)return;await mkdir(shotDir,{recursive:true});
  for(const w of [1440,1100]){await page.setViewportSize({width:w,height:1000});await page.waitForTimeout(150);
    await page.screenshot({path:join(shotDir,`${name}_${w}.png`),fullPage:true});}
  await page.setViewportSize({width:1440,height:1000});await page.waitForTimeout(150);}
try{
  await Promise.race([urlReady,new Promise((_,rej)=>setTimeout(()=>rej(new Error('web server did not start: '+stderr)),30000))]);
  const origin=new URL(appUrl).origin;
  await page.route('**/*',async route=>{assert.equal(new URL(route.request().url()).origin,origin,'External request must never occur');await route.continue();});
  await page.goto(appUrl);
  await page.getByText('로컬 엔진 연결됨',{exact:true}).waitFor();
  const banner=page.locator('dialog.update-banner');
  await banner.getByRole('button',{name:'나중에'}).click({timeout:15000}).catch(()=>{});
  if(!(await page.locator('.navigation button').allInnerTexts()).includes('Wafer Map 수정하기'))await page.getByRole('button',{name:'CAMTEK',exact:true}).click();
  await page.locator('.navigation').getByRole('button',{name:'Wafer Map 수정하기',exact:true}).click();

  // ① 폴더 → ② 목록
  await shot('1_folder');
  await page.getByLabel('폴더 경로').fill(maps);
  await page.getByRole('button',{name:'맵 찾기',exact:true}).click();
  const list=page.getByRole('table',{name:'맵 목록'});
  await list.waitFor();
  assert.equal(await list.locator('tbody tr').count(),3);
  await shot('2_list');
  // 화면에 Excel 변환 단계가 없다(#91 1번: 새 편집기로 바꿈)
  assert.equal(await page.getByText(/Excel → TXT|_Map_Edit\.xlsx/).count(),0);

  // ③ 편집
  await list.locator('tr',{hasText:'W01'}).getByRole('button',{name:'열기'}).click();
  await canvas('Wafer Map 편집').waitFor();
  await page.waitForFunction(()=>+document.querySelector('canvas[aria-label="Wafer Map 편집"]').dataset.s>0);
  await shot('3_editor');
  const side=page.getByLabel('Bin Code 리스트');
  // 전체 Defect 코드 표(설명 없이) + 개수
  const c001=side.getByRole('button',{name:/^001/});
  assert(await side.getByRole('button',{name:/^088/}).count()===1,'전체 코드 표');
  assert.equal(await side.getByText('범프 없음').count(),0,'설명(한글 뜻) 없음');
  assert(/000[\s\S]*\d/.test(await side.getByRole('button',{name:/^000/}).innerText()));
  // 마우스 = 하단 좌표 · Bin Code (Row 는 아래가 0)
  let p=await diePos('Wafer Map 편집',5,2);await page.mouse.move(p.x,p.y);
  assert.match(await status(),/Col 5 · Row 9 · Bin 000/);
  // 클릭 = Die 하나 → 코드 누름 = 바뀜
  await page.mouse.click(p.x,p.y);
  await side.getByText(/선택 Die 1개/).waitFor();
  await c001.click();
  assert.match(await status(),/바뀐 Die 1/);
  await page.mouse.move(p.x,p.y);assert.match(await status(),/Col 5 · Row 9 · Bin 001/);
  // ___ 칸은 못 고름(잠금)
  p=await diePos('Wafer Map 편집',0,0);await page.mouse.click(p.x,p.y);
  assert.match(await status(),/Bin ___.*편집 안 됨/);
  assert.match(await status(),/선택 0/);
  // 끌기 = 지나간 Die 모두(Row 5 의 Col 3~8)
  let a=await diePos('Wafer Map 편집',3,5),b=await diePos('Wafer Map 편집',8,5);
  await page.mouse.move(a.x,a.y);await page.mouse.down();await page.mouse.move(b.x,b.y,{steps:3});await page.mouse.up();
  await side.getByText(/선택 Die 6개/).waitFor();
  // 새 코드 직접 입력
  await side.getByLabel('새 코드').fill('95');await side.getByRole('button',{name:'＋ 추가'}).click();
  await side.getByRole('button',{name:/^095/}).click();
  assert.match(await status(),/바뀐 Die 7/);
  // 사각형 = 안의 Die 모두(Col 4~6 × Row 7~8 = 6개)
  await page.getByRole('radio',{name:'⬚ 사각형'}).click();
  a=await diePos('Wafer Map 편집',4,7);b=await diePos('Wafer Map 편집',6,8);
  await page.mouse.move(a.x,a.y);await page.mouse.down();await page.mouse.move(b.x,b.y,{steps:3});await page.mouse.up();
  await side.getByText(/선택 Die 6개/).waitFor();
  await side.getByRole('button',{name:/^031/}).click();
  assert.match(await status(),/바뀐 Die 13/);
  // 되돌리기 / 다시 하기(Ctrl+Z · Ctrl+Y)
  await page.keyboard.press('Control+z');assert.match(await status(),/바뀐 Die 7/);
  await page.keyboard.press('Control+y');assert.match(await status(),/바뀐 Die 13/);
  await page.getByRole('button',{name:'↶ 되돌리기'}).click();assert.match(await status(),/바뀐 Die 7/);
  // 이동 모드 = 클릭해도 안 고름 · 끌기 = 이동, 휠 = 확대(두 모드 모두)
  await page.getByRole('radio',{name:'✋ 이동'}).click();
  const s0=+(await canvas('Wafer Map 편집').getAttribute('data-x'));
  p=await diePos('Wafer Map 편집',5,5);await page.mouse.move(p.x,p.y);await page.mouse.down();await page.mouse.move(p.x+80,p.y+20,{steps:4});await page.mouse.up();
  await page.waitForTimeout(100);
  const s1=+(await canvas('Wafer Map 편집').getAttribute('data-x'));
  assert(s1>s0+60,`이동 모드 끌기 = 이동 (${s0} → ${s1})`);
  assert.match(await status(),/선택 0/);
  const z0=+(await canvas('Wafer Map 편집').getAttribute('data-s'));
  await page.mouse.wheel(0,-400);await page.waitForTimeout(100);
  assert(+(await canvas('Wafer Map 편집').getAttribute('data-s'))>z0,'휠 확대(이동 모드)');
  await page.getByRole('radio',{name:'✏️ 편집'}).click();
  const z1=+(await canvas('Wafer Map 편집').getAttribute('data-s'));
  await page.mouse.wheel(0,300);await page.waitForTimeout(100);
  assert(+(await canvas('Wafer Map 편집').getAttribute('data-s'))<z1,'휠 축소(편집 모드)');
  await page.getByRole('button',{name:'⤢ 전체 보기'}).click();

  // 저장: 범례 = Bin Code + Defect 이름, 이름 · 다른 폴더
  await page.getByRole('button',{name:'💾 저장'}).first().click();
  const dlg=page.getByRole('dialog',{name:'저장'});
  await dlg.waitFor();await shot('4_save');
  assert.equal(await dlg.getByLabel('저장 이름').inputValue(),'W01_Edited');
  // 범례 = 두 가지를 함께 고를 수 있음(소유자 08:15) — 둘 다 끄면 [저장] 잠김
  const cCode=dlg.getByLabel(/^Bin Code 만/),cMean=dlg.getByLabel(/Bin Code \+ Defect 이름/);
  assert(await cCode.isChecked());await cCode.uncheck();
  assert(await dlg.getByRole('button',{name:'💾 저장'}).isDisabled(),'범례 0개 = 저장 잠김');
  await cCode.check();await cMean.check();
  assert(await cCode.isChecked()&&await cMean.isChecked());
  assert.match(await dlg.innerText(),/_BinCode_Map\.png[\s\S]*_BinMeaning_Map\.png/);
  await dlg.getByLabel('다른 폴더').check();
  const out=join(fixture,'out');await dlg.getByLabel('저장 폴더').fill(out);
  await dlg.getByLabel('저장 이름').fill('W01_fixed');
  await dlg.getByRole('button',{name:'💾 저장'}).click();
  // ④ 비교
  await canvas('원래 맵').waitFor();await canvas('수정 맵').waitFor();
  await shot('5_compare');
  const sum=page.getByRole('table',{name:'바뀐 Die 요약'});
  assert.match(await sum.innerText(),/000 → 095\s+6/);
  assert.match(await sum.innerText(),/000 → 001\s+1/);
  assert.deepEqual((await readdir(out)).sort(),['W01_fixed.txt','W01_fixed_BinCode_Map.png','W01_fixed_BinMeaning_Map.png']);
  const txt=await readFile(join(out,'W01_fixed.txt'),'utf8');
  const rows=txt.split('\r\n').filter(l=>l.startsWith('RowData:')).map(l=>l.slice(8).split(' '));
  assert.equal(rows[2][5],'001');assert.deepEqual(rows[5].slice(3,9),['095','095','095','095','095','095']);
  assert.equal(rows[7][4],'000','되돌린 사각형은 저장 안 됨');
  assert.equal(txt.split('\r\n').length,small.split('\r\n').length,'줄 배치 그대로');
  assert.equal(await readFile(join(maps,'W01.txt'),'utf8'),small,'원본 보존');
  for(const f of ['W01_fixed_BinCode_Map.png','W01_fixed_BinMeaning_Map.png'])assert.equal((await readFile(join(out,f))).subarray(1,4).toString(),'PNG');
  assert.equal(await page.getByRole('table',{name:'저장 파일'}).locator('tr').count(),3,'TXT + 그림 2장');
  // 확대 · 이동 연동
  const ox=await canvas('수정 맵').getAttribute('data-s');
  p=await diePos('원래 맵',6,6);await page.mouse.move(p.x,p.y);await page.mouse.wheel(0,-300);await page.waitForTimeout(100);
  assert.notEqual(await canvas('원래 맵').getAttribute('data-s'),ox);
  assert.equal(await canvas('원래 맵').getAttribute('data-s'),await canvas('수정 맵').getAttribute('data-s'),'두 맵 확대 같이');
  assert.equal(await page.getByRole('button',{name:'📂 저장 폴더 열기'}).count(),1);
  // [처음 화면으로] = 목록(저장 ✓), [새로 시작하기] = 폴더 고르기
  await page.getByRole('button',{name:'처음 화면으로'}).click();
  await list.locator('tr',{hasText:'W01'}).getByText('✓ W01_fixed.txt').waitFor();

  // 성능(이 PC Chromium): 4만 · 100만 Die 열기 + 확대 한 번 그리기
  const perf={};
  for(const w of ['W40K','W1M']){
    const t0=Date.now();
    await list.locator('tr',{hasText:w}).getByRole('button',{name:'열기'}).click();
    await page.waitForFunction(()=>{const c=document.querySelector('canvas[aria-label="Wafer Map 편집"]');return c&&+c.dataset.s>0;},null,{timeout:60000});
    const open=Date.now()-t0;
    const frame=await page.evaluate(async()=>{const c=document.querySelector('canvas[aria-label="Wafer Map 편집"]'),r=c.getBoundingClientRect(),times=[];
      for(let k=0;k<20;k++){const t=performance.now();c.dispatchEvent(new WheelEvent('wheel',{deltaY:k<12?-120:120,clientX:r.x+r.width/2,clientY:r.y+r.height/2,bubbles:true,cancelable:true}));
        await new Promise(res=>requestAnimationFrame(()=>requestAnimationFrame(res)));times.push(performance.now()-t);}
      times.sort((a,b)=>a-b);return {median:Math.round(times[10]),max:Math.round(times[19])};});
    // 사각형으로 크게 고르고 코드 바꾸기
    await page.getByRole('radio',{name:'⬚ 사각형'}).click();
    const bb=await canvas('Wafer Map 편집').boundingBox();
    const t1=Date.now();
    await page.mouse.move(bb.x+bb.width*.3,bb.y+bb.height*.3);await page.mouse.down();await page.mouse.move(bb.x+bb.width*.7,bb.y+bb.height*.7,{steps:5});await page.mouse.up();
    await side.getByRole('button',{name:/^002/}).click();
    await page.waitForFunction(()=>/바뀐 Die [1-9]/.test(document.querySelector('[aria-label="Die 정보"]').innerText));
    const edit=Date.now()-t1;
    const dies=(await page.locator('.wme-title p').innerText()).match(/Die ([\d,]+)/)[1];
    perf[w]={dies,open_ms:open,wheel_frame_median_ms:frame.median,wheel_frame_max_ms:frame.max,rect_edit_ms:edit,changed:(await status()).match(/바뀐 Die ([\d,]+)/)[1]};
    page.once('dialog',d=>d.accept());
    await page.getByRole('button',{name:'◀ 목록으로'}).click();
    await list.waitFor();
  }
  await page.getByRole('button',{name:'⟲ 새로 시작하기'}).click();
  await page.getByLabel('폴더 경로').waitFor();
  assert.deepEqual(errors,[]);
  assert.equal(stderr,'');
  console.log(JSON.stringify({passed:true,perf}));
}finally{
  lines.close();engine.kill();
  await new Promise(r=>engine.exitCode!==null||engine.signalCode!==null?r():engine.once('exit',r));
  await browser.close();await rm(fixture,{recursive:true,force:true});
}
