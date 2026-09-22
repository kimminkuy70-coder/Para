// No HTTP server. All document requests are fulfilled from the built files.
// Native Tauri is substituted by a channel adapter to the real Python process.
import {createRequire} from 'node:module';
import {mkdtemp, readFile, rm, mkdir} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve, extname} from 'node:path';
import {spawn, execFileSync} from 'node:child_process';
import {createInterface} from 'node:readline';
import assert from 'node:assert/strict';

const require=createRequire(import.meta.url);
const {chromium}=require(require.resolve('playwright',{paths:[process.env.PARA_TEST_NODE_MODULES||process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES||process.cwd()]}));
const root=resolve(new URL('..',import.meta.url).pathname);
const fixture=await mkdtemp(join(tmpdir(),'para-ui-'));
const python=process.env.CODEX_PRIMARY_RUNTIME_PYTHON||'python';
execFileSync(python,[join(root,'tests/desktop_browser_fixture.py'),'init',fixture]);
const browser=await chromium.launch({headless:true});
const engine=spawn(python,[join(root,'tests/desktop_browser_fixture.py'),'serve',fixture],{cwd:root,stdio:['pipe','pipe','pipe']});
let channel=0, index=0, delivery=Promise.resolve();
const page=await browser.newPage({viewport:{width:1440,height:1000}});
const errors=[];
page.on('pageerror',e=>errors.push(e.message));
const lines=createInterface({input:engine.stdout});
lines.on('line',line=>{const message=JSON.parse(line);const sequence=index++;delivery=delivery.then(()=>page.evaluate(({channel,message,sequence})=>window.__callbacks[channel]({index:sequence,message}),{channel,message,sequence}));});
let stderr='';engine.stderr.on('data',d=>stderr+=d);
try{
  await page.exposeBinding('nativeInvoke',async(_,command,args)=>{
    if(command==='desktop_connect'){channel=Number(args.onEvent.split(':')[1]);return;}
    assert.equal(command,'desktop_send');engine.stdin.write(JSON.stringify(args.request)+'\n');
  });
  await page.addInitScript(()=>{
    window.isTauri=true;window.__callbacks={};let next=0;
    window.__TAURI_INTERNALS__={transformCallback:fn=>{const id=++next;window.__callbacks[id]=fn;return id;},
      unregisterCallback:id=>delete window.__callbacks[id],
      invoke:(command,args)=>window.nativeInvoke(command,JSON.parse(JSON.stringify(args)))};
  });
  await page.route('**/*',async route=>{
    const url=new URL(route.request().url());
    assert.equal(url.origin,'https://para.test','External request must never occur');
    const relative=url.pathname==='/'?'index.html':url.pathname.slice(1);
    if(relative==='qa-font.otf'&&process.env.PARA_TEST_FONT_PATH){
      await route.fulfill({body:await readFile(process.env.PARA_TEST_FONT_PATH),contentType:'font/otf'});return;
    }
    const file=resolve(root,'frontend/dist',relative);
    assert(file.startsWith(resolve(root,'frontend/dist')+'/'));
    await route.fulfill({body:await readFile(file),contentType:({'.html':'text/html','.js':'text/javascript','.css':'text/css'})[extname(file)]||'application/octet-stream'});
  });
  await page.goto('https://para.test/');
  if(process.env.PARA_TEST_FONT_PATH){
    await page.addStyleTag({content:"@font-face{font-family:'Malgun Gothic';src:url('/qa-font.otf')}"});
    await page.evaluate(()=>document.fonts.ready);
  }
  await page.getByText('로컬 엔진 연결됨',{exact:true}).waitFor();
  // A3: a toast raised while a modal dialog is open must be the topmost element.
  await page.getByRole('button',{name:'Recipe 관리',exact:true}).click();
  await page.getByRole('button',{name:'Min Defect Bright 0 색상 변경',exact:true}).click();
  await page.locator('dialog[open] input:not([type])').fill('#12');
  await page.locator('dialog[open]').getByRole('button',{name:'저장',exact:true}).click();
  const toast=page.locator('.toast.error').filter({hasText:'#RRGGBB'});
  await toast.waitFor();
  // Inert (modal-blocked) nodes are skipped by hit testing, so check that the
  // toaster was (re)opened as a popover, i.e. placed above the open dialog in the top layer.
  assert(await page.evaluate(()=>document.querySelector('.toaster').matches(':popover-open')&&document.querySelector('dialog').open),'toast hidden behind modal');
  await page.keyboard.press('Escape');
  // A2: a Report folder registered in [설정] appears in the batch tab without restart.
  const extra=join(fixture,'equipment-04');await mkdir(extra);
  await page.getByRole('button',{name:'설정',exact:true}).click();
  await page.getByRole('tab',{name:'배치 Report 폴더'}).click();
  await page.getByLabel('호기').fill('AOI-04');await page.getByLabel('폴더').fill(extra);
  await page.getByRole('button',{name:'추가',exact:true}).click();
  await page.getByText(extra,{exact:true}).waitFor();
  await page.getByRole('button',{name:'배치 리포트 분석',exact:true}).click();
  await page.getByLabel('AOI-04 검색어').waitFor();
  for(const [width,height] of [[1920,1080],[2880,1800],[1280,720],[960,640]]){
    await page.setViewportSize({width,height});
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`page overflow ${width}`);
    const input=page.getByLabel('AOI-01 검색어');
    await input.fill('test');await input.fill('');
  }
  await page.setViewportSize({width:1440,height:1000});
  await page.getByRole('button',{name:'다음 ▶',exact:true}).click();
  // A1: the retired M07 from saved settings is dropped; 4 of 10 metrics restored.
  assert.equal(await page.locator('.metric-list input:checked').count(),4);
  await page.getByRole('button',{name:'전체 선택',exact:true}).click();
  await page.getByRole('button',{name:'다음 ▶',exact:true}).click();
  await page.getByRole('button',{name:'조사 시작'}).click();
  await page.getByText('조사를 완료했습니다.',{exact:true}).waitFor({timeout:60000});
  await page.getByLabel('분석 표',{exact:true}).selectOption({label:'시간순 Actual WPH · 205행'});
  await page.getByRole('img',{name:'Batch End 시간순 WPH 추이'}).waitFor();
  assert.equal(await page.locator('.table-scroll tbody tr').count(),200);
  assert.equal(await page.locator('.trend svg text[y="248"]').count(),5);
  await page.getByRole('button',{name:'다음',exact:true}).click();
  await page.waitForFunction(()=>document.querySelectorAll('.table-scroll tbody tr').length===5);
  await page.getByRole('button',{name:'이전',exact:true}).click();
  await page.waitForFunction(()=>document.querySelectorAll('.table-scroll tbody tr').length===200);
  await mkdir(join(root,'docs/screenshots'),{recursive:true});
  await page.screenshot({path:join(root,'docs/screenshots/rev1-batch.png'),fullPage:true});
  const options=await page.getByLabel('분석 표',{exact:true}).locator('option').allTextContents();
  const unknown=options.find(t=>t.startsWith('미분류 · 누락 상태'));
  assert(unknown);await page.getByLabel('분석 표',{exact:true}).selectOption({label:unknown});
  await page.locator('.table-scroll').getByText('<script>window.injected=true</script>',{exact:true}).first().waitFor();
  assert.equal(await page.evaluate(()=>window.injected),undefined);
  await page.getByRole('button',{name:'Recipe 관리',exact:true}).click();
  await page.waitForFunction(()=>document.querySelectorAll('.comparison-row').length===100);
  await page.getByRole('button',{name:'Min Defect Bright 0 색상 변경',exact:true}).click();
  await page.locator('dialog input[type=text], dialog input:not([type])').fill('#1267AB');
  await page.getByRole('button',{name:'저장',exact:true}).click();
  await page.waitForFunction(()=>!document.querySelector('dialog').open);
  await page.locator('.comparison-viewport').evaluate(el=>{el.scrollTop=42042;});
  await page.waitForFunction(()=>document.querySelector('.comparison-row')?.textContent.includes('Min Defect Bright 1000'));
  assert.equal(await page.locator('.comparison-row').count(),100);
  await page.getByRole('button',{name:'다음 호기',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('.comparison-header')?.textContent.includes('AOI-20'));
  await page.screenshot({path:join(root,'docs/screenshots/rev1-recipe.png'),fullPage:true});
  await page.getByRole('button',{name:'장비 IP',exact:true}).click();
  await page.getByRole('button',{name:'10.0.0.1',exact:true}).click();
  await page.locator('dialog textarea').fill('10.0.0.2');
  await page.locator('dialog input[type=color]').fill('#112233');
  await page.getByRole('button',{name:'저장',exact:true}).click();
  await page.getByRole('button',{name:'10.0.0.2',exact:true}).waitFor();
  assert.equal(await page.getByRole('button',{name:'10.0.0.2',exact:true}).evaluate(el=>getComputedStyle(el).color),'rgb(255, 255, 255)');
  await page.getByRole('button',{name:'새 행 추가',exact:true}).click();
  const newRow=page.locator('dialog[open]');
  await newRow.getByLabel('호기',{exact:true}).fill('AOI-02');
  await newRow.getByLabel('IP',{exact:true}).fill('10.0.0.3');
  await newRow.getByRole('button',{name:'행 저장',exact:true}).click();
  await page.getByRole('button',{name:'10.0.0.3',exact:true}).waitFor();
  await page.getByRole('button',{name:'Commonality 조사',exact:true}).click();
  await page.locator('.cm-file input').first().check();
  await page.getByRole('button',{name:'선택 결과 비교 ▶',exact:true}).click();
  await page.waitForFunction(()=>document.querySelectorAll('.cm-outlier').length===12);
  assert.equal(await page.locator('.table-scroll tbody tr').count(),3);
  await page.getByRole('button',{name:'다음 파라미터',exact:true}).click();
  await page.getByRole('button',{name:'비교 Excel 저장',exact:true}).click();
  await page.getByLabel('저장된 Excel').waitFor();
  assert((await page.getByLabel('저장된 Excel').inputValue()).endsWith('.xlsx'));
  assert.deepEqual(errors,[]);
  assert.equal(stderr,'');
  console.log(JSON.stringify({passed:true,viewports:4,pythonReports:205,maxDOMRows:200,timeTicks:5,scriptEscaped:true,serverPortsOpened:0}));
}finally{
  lines.close();engine.stdin.end();
  await new Promise(resolve=>engine.exitCode!==null?resolve():engine.once('exit',resolve));
  await delivery.catch(()=>{});await browser.close();await rm(fixture,{recursive:true,force:true});
}
