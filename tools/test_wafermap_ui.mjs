// Wafer Map 전용판(특수 버전) 화면 검사 — 빌드된 frontend/dist-wafermap 을 실제 Python 엔진
// (param_manager.wafermap_ipc)에 붙여 TXT → Excel → TXT 를 끝까지 돌린다. HTTP 서버 없음(본 앱 검사와 같은 방식).
//   cd frontend && npm run build:wafermap && cd .. && node tools/test_wafermap_ui.mjs [스크린샷 폴더]
import {createRequire} from 'node:module';
import {mkdtemp, readFile, rm, mkdir, writeFile, readdir} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve, extname} from 'node:path';
import {spawn} from 'node:child_process';
import {createInterface} from 'node:readline';
import assert from 'node:assert/strict';

const require=createRequire(import.meta.url);
const {chromium}=require(require.resolve('playwright',{paths:[process.env.PARA_TEST_NODE_MODULES||process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES||process.cwd()]}));
const root=resolve(new URL('..',import.meta.url).pathname);
const dist=resolve(root,'frontend/dist-wafermap');
const shots=process.argv[2]||'';
const fixture=await mkdtemp(join(tmpdir(),'para-wm-'));
const python=process.env.CODEX_PRIMARY_RUNTIME_PYTHON||'python';
// 8x8 맵 2장(CRLF · LF), 하위 폴더 포함 — tests/test_wafermap.py 의 예시와 같은 모양.
const rows=['___ ___ 000 000 000 000 ___ ___','___ 000 000 003 000 000 000 ___','000 000 000 000 000 007 000 000','000 000 022 000 000 000 000 000',
  '000 000 000 000 000 000 014 000','000 000 000 031 000 000 000 000','___ 000 000 000 000 000 000 ___','___ ___ 000 000 090 000 ___ ___'];
const map=(w,nl)=>[`WAFER:${w}`,'DEVICE:DEV-A','LOT:LOT01','ROWCT:8','COLCT:8',...rows.map(r=>'RowData:'+r)].join(nl)+nl;
await mkdir(join(fixture,'maps','sub'),{recursive:true});
await writeFile(join(fixture,'maps','W01.txt'),map('W01','\r\n'));
await writeFile(join(fixture,'maps','sub','W02.txt'),map('W02','\n'));
const browser=await chromium.launch({headless:true});
const engine=spawn(python,['-m','param_manager.wafermap_ipc'],{cwd:root,stdio:['pipe','pipe','pipe'],
  env:{...process.env,LOCALAPPDATA:join(fixture,'local'),PYTHONUTF8:'1',PYTHONPATH:root}});
let channel=0,index=0,delivery=Promise.resolve(),stderr='';engine.stderr.on('data',d=>stderr+=d);
const sent=[];
const page=await browser.newPage({viewport:{width:1280,height:900}});
const errors=[];page.on('pageerror',e=>errors.push(e.message));
createInterface({input:engine.stdout}).on('line',line=>{const message=JSON.parse(line);const sequence=index++;
  delivery=delivery.then(()=>page.evaluate(({channel,message,sequence})=>window.__callbacks[channel]({index:sequence,message}),{channel,message,sequence}));});
const shot=async name=>{if(shots)await page.screenshot({path:join(shots,name),fullPage:true});};
try{
  await page.exposeBinding('nativeInvoke',async(_,command,args)=>{
    if(command==='desktop_connect'){channel=Number(args.onEvent.split(':')[1]);index=0;return;}
    assert.equal(command,'desktop_send',`이 판이 부르면 안 되는 명령: ${command}`);   // 트레이 · 업데이트 · 파일 고르기 없음
    sent.push(args.request.method);engine.stdin.write(JSON.stringify(args.request)+'\n');
  });
  await page.addInitScript(()=>{
    window.isTauri=true;window.__callbacks={};let next=0;
    window.__TAURI_INTERNALS__={transformCallback:fn=>{const id=++next;window.__callbacks[id]=fn;return id;},
      unregisterCallback:id=>delete window.__callbacks[id],invoke:(command,args)=>window.nativeInvoke(command,JSON.parse(JSON.stringify(args)))};
  });
  await page.route('**/*',async route=>{
    const url=new URL(route.request().url());
    assert.equal(url.origin,'https://wafermap.test','External request must never occur');
    const file=resolve(dist,url.pathname==='/'?'index.html':url.pathname.slice(1));
    assert(file.startsWith(dist+'/'));
    await route.fulfill({body:await readFile(file),contentType:({'.html':'text/html','.js':'text/javascript','.css':'text/css'})[extname(file)]||'application/octet-stream'});
  });
  await page.goto('https://wafermap.test/');
  await page.getByText('로컬 엔진 연결됨',{exact:true}).waitFor();
  assert.equal(await page.title(),'Wafer Map 변환');
  // 문구는 'Wafer Map 변환' — 본 앱 이름이 화면에 없다. 개발자 표시는 창 왼쪽 아래(아래 줄 왼쪽 칸, 창 바닥에 붙음).
  const body=await page.locator('body').innerText();
  assert(!/Manager|Camtek AOI/.test(body),'본 앱 이름이 화면에 있음');
  const credit=page.locator('footer span').first();
  assert.match(await credit.innerText(),/^Wafer Map 변환 v[\d.]+ · 개발: 김민규$/);
  const box=await credit.boundingBox(),vp=page.viewportSize();
  assert(box.x<60&&box.y+box.height>vp.height-40,`개발자 표시 위치 ${JSON.stringify(box)}`);
  // 다른 기능의 화면 · 메뉴가 없다(탭 줄 자체가 없음).
  assert.equal(await page.locator('nav.navigation').count(),0);
  for(const other of ['Recipe 관리','Batch Report 분석','Commonality 조사','자동 감시','Color·Gray 매칭','설정'])
    assert.equal(await page.getByRole('button',{name:other,exact:true}).count(),0,other);
  await shot('wm_01_start.png');
  // 1/4 TXT → Excel: 폴더 → 파일 찾기 → 선택 → 저장 위치 → 검토 → 변환
  await page.getByLabel('폴더 경로').fill(join(fixture,'maps'));
  await page.getByRole('button',{name:'파일 찾기'}).click();
  await page.getByText('TXT 파일 2개를 찾았습니다.').waitFor();
  await shot('wm_02_files.png');
  await page.getByRole('button',{name:'다음 ▶'}).click();
  await page.getByRole('button',{name:'다음 ▶'}).click();
  await page.getByRole('button',{name:'▶ 변환 시작'}).click();
  await page.getByText('Wafer Map 변환을 마쳤습니다.').waitFor({timeout:60000});
  await page.getByText('성공 2',{exact:false}).waitFor();
  // 맵 이미지: 행마다 Bin Code · Bin Meaning 썸네일 2장(같은 이름 두 번 · 빈 썸네일이면 실패).
  assert.equal(await page.locator('.wm-thumbbtn img').count(),4);
  assert.equal(await page.getByText('Bin Code',{exact:true}).count(),2);
  await shot('wm_03_done.png');
  const made=(await readdir(join(fixture,'maps'))).sort();
  for(const f of ['W01_Map_Edit.xlsx','W01_Map_Edit_BinCode_Map.png','W01_Map_Edit_BinMeaning_Map.png'])assert(made.includes(f),`${f} 없음: ${made}`);
  // 2/4 Excel → TXT: 새 작업 → 방향 바꾸기 → 원본과 바이트 동일
  await page.getByRole('button',{name:'새 작업'}).click();
  await page.getByRole('radio',{name:/Excel → TXT/}).click();
  await page.getByRole('button',{name:'파일 찾기'}).click();
  await page.getByText('Excel 파일 2개를 찾았습니다.').waitFor();
  await page.getByRole('button',{name:'다음 ▶'}).click();
  await page.getByRole('button',{name:'다음 ▶'}).click();
  await page.getByRole('button',{name:'▶ 변환 시작'}).click();
  // 앞 작업의 완료 알림이 아직 떠 있을 수 있어, 결과 표(성공 2)로 끝을 확인한다.
  await page.getByText('성공 2',{exact:false}).waitFor({timeout:60000});
  assert.deepEqual(await readFile(join(fixture,'maps','W01_Map_Edit_Converted.txt')),await readFile(join(fixture,'maps','W01.txt')),'왕복 바이트 동일(CRLF)');
  assert.deepEqual(await readFile(join(fixture,'maps','sub','W02_Map_Edit_Converted.txt')),await readFile(join(fixture,'maps','sub','W02.txt')),'왕복 바이트 동일(LF)');
  await shot('wm_04_back.png');
  const allowed=new Set(['configuration','diag_client','wm_scan','wm_start','wm_convert','wm_image','wm_reset','open_path']);
  assert.deepEqual([...new Set(sent)].filter(m=>!allowed.has(m)),[],'Wafer Map 밖의 요청을 보냄');
  assert.deepEqual(errors,[]);
  console.log('Wafer Map edition UI: OK', [...new Set(sent)].join(','));
}catch(e){console.error(stderr);await shot('wm_fail.png');throw e;}
finally{engine.stdin.end();await delivery.catch(()=>{});await browser.close();await rm(fixture,{recursive:true,force:true});}
