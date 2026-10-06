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
// Recipe 관리 holds the recipe workflows as tabs (값 확인 · 업데이트 · 신규 · 양식 편집 · 날짜별 비교).
async function recipeTab(name){await page.getByRole('button',{name:'Recipe 관리',exact:true}).click();await page.getByRole('tab',{name,exact:true}).click();}
let stderr='',background={enabled:false,tooltip:''};engine.stderr.on('data',d=>stderr+=d);
try{
  await page.exposeBinding('nativeInvoke',async(_,command,args)=>{
    if(command==='set_background'){background=args;return;}   // tray residency request
    if(command==='pick_file')return join(fixture,'old_plan.xlsx');   // native Excel picker → fixture plan
    if(command==='desktop_connect'){channel=Number(args.onEvent.split(':')[1]);index=0;return;}  // a new Channel counts from 0, as in Tauri
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
  // Self-update: the published package is announced; a dev run cannot install it.
  const banner=page.locator('.update-banner');
  await banner.getByText('새 버전 99.1.0').waitFor();
  assert(await banner.getByRole('button',{name:'지금 업데이트'}).isDisabled());
  await banner.getByRole('button',{name:'이 버전 건너뛰기'}).click();
  await banner.waitFor({state:'detached'});
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
  const extra=join(fixture,'equipment-04');await mkdir(join(extra,'Reports'),{recursive:true});
  await page.getByRole('button',{name:'설정',exact:true}).click();
  // 설정 tabs in the requested order.
  assert.deepEqual(await page.getByRole('tab').allInnerTexts(),['저장 폴더','로컬 작업 폴더','AOI 장비 호기 루트','Batch Report 분석 주기 설정','정보']);
  // 현재 설정 is folded by default, above the tabs.
  assert.equal(await page.getByLabel('현재 설정').evaluate(d=>d.open),false);
  // 튜토리얼(v12.2.6): 설정 › [초기 설정 튜토리얼] — 말풍선 · 강조 테두리, 설정 하위 탭을 스스로 열고, 아무것도 저장하지 않는다.
  await page.getByRole('button',{name:'초기 설정 튜토리얼',exact:true}).click();
  const tb=page.locator('.tour-bubble');
  await tb.getByRole('heading',{name:'초기 설정 튜토리얼'}).waitFor();
  const tourNext=async title=>{await tb.getByRole('button',{name:'다음 →'}).click();await tb.getByRole('heading',{name:title}).waitFor();};
  await tourNext('설정 탭');await tourNext('① 저장 폴더 = 공유 OneDrive 폴더');await tourNext('먼저 OneDrive 에 공유 폴더 연결');
  assert.equal(await page.getByRole('tab',{name:'저장 폴더'}).getAttribute('aria-selected'),'true');
  await page.locator('.tour-spot').waitFor();
  await tourNext('OneDrive 폴더 경로 넣기');await tourNext('[저장]');await tourNext('② 장비 연결 — AOI 장비 호기 루트');
  await tourNext('호기 이름 + 호기 폴더 → [추가]');
  assert.equal(await page.getByRole('tab',{name:'AOI 장비 호기 루트'}).getAttribute('aria-selected'),'true');
  // 말풍선과 강조가 화면 안에 있다(화살표가 가리키는 대상).
  await page.waitForTimeout(500);   // 강조 테두리 이동 애니메이션(0.25초)이 끝난 뒤
  const sb=await page.locator('.tour-spot').boundingBox(),bb=await tb.boundingBox(),tg=await page.locator('[data-tour="settings:aoi-form"]').boundingBox();
  assert(sb&&tg&&Math.abs(sb.x+6-tg.x)<3&&Math.abs(sb.y+6-tg.y)<3&&Math.abs(sb.width-12-tg.width)<3,'spotlight must sit on the target '+JSON.stringify([sb,tg]));
  assert(sb&&bb&&bb.x>=0&&bb.y>=0&&bb.x+bb.width<=1441&&bb.y+bb.height<=1001,'tour bubble off screen');
  await page.screenshot({path:join(root,'docs/screenshots/rev1-tour.png')});
  await page.keyboard.press('ArrowRight');await tb.getByRole('heading',{name:'등록 확인'}).waitFor();
  await page.keyboard.press('Escape');await tb.waitFor({state:'detached'});
  await page.getByRole('tab',{name:'AOI 장비 호기 루트'}).click();
  // One machine folder registers both its Reports (batch) and Scanresult (Commonality).
  await page.getByLabel('호기',{exact:true}).fill('AOI-04');await page.getByLabel('호기 폴더',{exact:true}).fill(extra);
  await page.getByRole('button',{name:'추가',exact:true}).click();
  await page.getByText(/AOI-04 등록 — AOI-04: Batch Report: Reports/).waitFor();
  await page.getByText(extra,{exact:true}).waitFor();
  // Machines are listed in name order (AOI-01 … AOI-04).
  assert.deepEqual(await page.locator('.subtab-body table').first().locator('tbody tr td:first-child').allInnerTexts(),['AOI-01','AOI-02','AOI-03','AOI-04']);
  await page.getByRole('button',{name:'Batch Report 분석',exact:true}).click();
  await page.getByLabel('AOI-04 선택').waitFor();
  // 설정: current-settings summary and '수정' (rename + keep folder) of a Batch Report root.
  await page.getByRole('button',{name:'설정',exact:true}).click();
  const summary=page.getByLabel('현재 설정');
  await summary.locator('summary').click();
  await summary.getByText(/AOI 장비 호기 루트/).first().waitFor();
  assert(/AOI-04/.test(await summary.innerText()),'summary lists registered roots');
  await page.getByRole('tab',{name:'AOI 장비 호기 루트'}).click();
  await page.getByRole('button',{name:'AOI-04 수정'}).click();
  await page.getByLabel('AOI-04 새 호기 이름').fill('AOI-05');
  await page.getByRole('button',{name:'저장',exact:true}).click();
  await page.getByText(/AOI-05 호기 루트를 수정했습니다/).waitFor();
  await page.getByRole('button',{name:'AOI-05 수정'}).waitFor();
  assert(/AOI-05/.test(await summary.innerText())&&!/AOI-04/.test(await summary.innerText()));
  // 이슈 #8: Scanresult 백업본 포함 조사 스위치(모든 Scanresult 조사 기능 공통 설정) — 기본 켬, 끄면 원본만.
  const scanSwitch=page.locator('.sbk:visible').getByRole('switch',{name:'백업본 포함해서 조사'});
  await page.locator('.sbk:visible').filter({hasText:'원본 + 백업본'}).waitFor();
  assert(await scanSwitch.isChecked());
  await scanSwitch.click();
  await page.locator('.sbk.off:visible').filter({hasText:'원본만'}).waitFor();
  assert(!(await scanSwitch.isChecked()));
  await scanSwitch.click();
  await page.locator('.sbk.on:visible').filter({hasText:'원본 + 백업본'}).waitFor();
  await page.getByRole('button',{name:'Batch Report 분석',exact:true}).click();
  await page.getByLabel('AOI-05 선택').waitFor();
  // Batch Report 분석 (가동률 조사 및 분석 · 찾기 · 취합): fixed machine grid, no page overflow.
  for(const [width,height] of [[1920,1080],[2880,1800],[1280,720],[960,640]]){
    await page.setViewportSize({width,height});
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`page overflow ${width}`);
  }
  await page.setViewportSize({width:1440,height:1000});
  // The last investigation's machines are restored (AOI-01); the old saved M07 metric must not block a run (A1).
  assert(await page.getByLabel('AOI-01 선택').isChecked());
  await page.getByRole('button',{name:'조사 시작 →'}).click();
  await page.locator('.toast').filter({hasText:'조사를 완료했습니다.'}).waitFor({timeout:60000});
  await page.locator('.scope-status').filter({hasText:'Batch Report 205개'}).waitFor();
  // Every investigation also writes the Lot 추적 HTML; ? next to 조사 explains the Lot criteria.
  await page.getByText(/저장된 결과 파일/).click();
  assert((await page.getByLabel('Lot 추적 HTML',{exact:true}).inputValue()).endsWith('BatchReport_Lot추적.html'));
  await page.getByRole('button',{name:'Lot 판정 기준',exact:true}).click();
  await page.locator('dialog[open]').getByText('Lot 코드',{exact:true}).waitFor();
  await page.locator('dialog[open]').getByRole('button',{name:'닫기',exact:true}).click();
  // Lot 추적: 205 reports → 69 Lots (3 reports each, one wafer per report).
  const kpi=page.locator('.kpib button');
  assert.match(await kpi.nth(0).innerText(),/69/);
  assert.match(await kpi.nth(1).innerText(),/205/);
  await kpi.nth(1).click();
  // The list title above the table names the list the clicked KPI shows.
  await page.locator('.listtitle').filter({hasText:'Batch Report 목록'}).waitFor();
  // Batch Report list → 원문: source text is shown as text, never executed.
  await page.locator('.tabpanel tbody tr').filter({hasText:'BatchReport_000.htm'}).click();
  await page.locator('dialog[open]').getByText('<script>window.injected=true</script>',{exact:true}).first().waitFor();
  await page.locator('dialog[open]').getByText('Batch Report 원문 — 스캔 1번(Batch Report 1장)의 표 그대로').waitFor();
  // A modal window scrolls alone — the page behind it does not (whole program).
  assert.equal(await page.evaluate(()=>getComputedStyle(document.documentElement).overflow),'hidden');
  assert.equal(await page.evaluate(()=>window.injected),undefined);
  await page.locator('dialog[open]').getByRole('button',{name:'닫기',exact:true}).click();
  assert.notEqual(await page.evaluate(()=>getComputedStyle(document.documentElement).overflow),'hidden');
  // Lot window: Lot History (timeline) and 취합 tabs, Excel export to the local result folder.
  await kpi.nth(0).click();
  await page.locator('.listtitle').filter({hasText:'Lot 단위 Scan List'}).waitFor();
  // 이슈 #8: 목록 카드 — 상태 세그먼트(개수 포함) · 조건 토글 · 표시 개수.
  const stateSeg=page.locator('.lotlist').getByRole('group',{name:'상태'});
  await stateSeg.getByRole('button',{name:/^재스캔으로 완료/}).click();
  assert.equal(await stateSeg.getByRole('button',{name:/^재스캔으로 완료/}).getAttribute('aria-pressed'),'true');
  await stateSeg.getByRole('button',{name:/^전체/}).click();
  assert.match(await page.locator('.lotlist .ll-count').innerText(),/69\s*\/\s*69 Lot/);
  const moveTg=page.locator('.lotlist .ll-tg').filter({hasText:'호기 이동'});
  await moveTg.click();assert.equal(await moveTg.getAttribute('aria-pressed'),'true');await moveTg.click();
  // Weekly bars: WW number on the first line, the date range on the second; tooltip rows aligned.
  await page.locator('.chartcard').first().getByRole('button',{name:'주',exact:true}).click();
  assert.match(await page.locator('svg[aria-label="기간별 Lot Scan 현황"] text').filter({hasText:/^WW\d+/}).first().textContent(),/^WW\d+\(\d\d\/\d\d~\d\d\/\d\d\)$/);
  await page.locator('svg[aria-label="기간별 Lot Scan 현황"] rect.hit').first().hover();
  await page.locator('.bv-tip.rich .tg b').first().waitFor();
  await page.locator('.tabpanel tbody tr.clickable').first().click();
  await page.locator('dialog.lotwin[open] svg[aria-label="시간순 Batch Report 요약"]').waitFor();
  assert.equal(await page.locator('dialog.lotwin').getByRole('tab',{name:'Lot History',exact:true}).getAttribute('aria-selected'),'true');
  assert.equal(await page.locator('dialog.lotwin .lw-sec h3.boxed').count(),3);
  await page.locator('dialog.lotwin').getByRole('tab',{name:'Lot · wafer 취합'}).click();
  await page.locator('dialog.lotwin').getByRole('button',{name:'Excel로 저장',exact:true}).click();
  assert((await page.locator('dialog.lotwin').getByLabel('저장된 Excel').inputValue()).includes('취합'));
  await page.locator('dialog.lotwin').getByRole('button',{name:'닫기',exact:true}).click();
  await mkdir(join(root,'docs/screenshots'),{recursive:true});
  await page.screenshot({path:join(root,'docs/screenshots/rev1-batch.png'),fullPage:true});
  // 이슈 #14: 레시피 비교 — 엔진이 준 레시피 목록 → A에 넣기 → B가 비어 있으면 [비교]가 잠김.
  await page.getByRole('tab',{name:'레시피 비교',exact:true}).click();
  await page.getByRole('button',{name:'JOB · R1 A에 넣기'}).click();
  await page.locator('.cmp-box.a .chip').filter({hasText:'JOB · R1'}).waitFor();
  assert(await page.getByRole('button',{name:'비교 →'}).isDisabled());
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'compare tab overflow');
  await page.getByRole('button',{name:'비우기',exact:true}).click();
  await page.getByRole('tab',{name:'Lot 추적',exact:true}).click();
  // 가동률: 시간 3칸 숫자 · ? 설명 창(지금 숫자로 계산한 예) · 기간 상세 창 · 24시간 시간표 (사용자 확정 2026-10-05).
  await page.getByRole('tab',{name:'가동률',exact:true}).click();
  assert.equal(await page.locator('.kpis.k4 article').count(),4);
  await page.getByRole('button',{name:'가동률 설명',exact:true}).click();
  await page.locator('dialog.qhelp[open] ul.calc li').filter({hasText:'달력 시간'}).waitFor();
  await page.locator('dialog.qhelp[open]').getByRole('button',{name:'닫기',exact:true}).click();
  await page.getByRole('button',{name:'기간별',exact:true}).click();
  await page.locator('.prow:not(.head)').first().click();
  await page.locator('dialog.lotwin[open]').getByRole('tab',{name:'손실 이유'}).click();
  await page.locator('dialog.lotwin[open]').getByRole('tab',{name:'24시간 시간표'}).click();
  await page.locator('dialog.lotwin[open] svg[aria-label="24시간 시간표"]').waitFor();
  await page.locator('dialog.lotwin[open]').getByRole('button',{name:'닫기',exact:true}).click();
  await page.getByRole('button',{name:'24시간 시간표',exact:true}).click();
  await page.locator('svg[aria-label="24시간 시간표"]').waitFor();
  // WPH · 생산능력: 레시피 비교(호기별로 쌓은 하루 생산능력) → 레시피 상세 창, 표에 레시피 합계 줄.
  await page.getByRole('tab',{name:'WPH · 생산능력',exact:true}).click();
  await page.locator('.caprow').first().waitFor();
  // 이슈 #7: 호기 색 범례(같은 호기 = 같은 색) · 레시피를 고르면 그 줄 강조 + 정상 WPH 유무 문장(하위 레시피끼리 바꿔도 바뀐 게 보임).
  await page.getByText('같은 호기 = 같은 색').waitFor();
  const rsel=page.locator('select').filter({has:page.locator('optgroup')});
  await rsel.selectOption({index:1});
  await page.locator('.caprow.sel').waitFor();
  assert.match(await page.locator('p.capsel').innerText(),/고른 레시피: .*(정상 WPH \d|정상 WPH 없음)/);
  await rsel.selectOption({index:0});
  // 이슈 #10: 상위 레시피(Job) 묶음 상자 · 하위 레시피 줄 구분 + 상위 레시피 필터(여러 개 고르기).
  const jf=page.getByRole('group',{name:'상위 레시피 필터'});
  const chips=jf.locator('button.jf-chip');
  assert.ok(await chips.count()>0);
  assert.ok(await page.locator('.capgrp .capjob .lv.up').count()>0);
  assert.ok(await page.locator('.caprow.sub .lv.dn').count()>0);
  const nGrp=await page.locator('.capgrp').count();
  await chips.first().click();
  assert.equal(await chips.first().getAttribute('aria-pressed'),'true');
  assert.equal(await page.locator('.capgrp').count(),1);
  if(await chips.count()>1){await chips.nth(1).click();assert.equal(await page.locator('.capgrp').count(),Math.min(2,nGrp));}
  await jf.getByRole('button',{name:'전체 보기',exact:true}).click();
  assert.equal(await page.locator('.capgrp').count(),nGrp);
  await page.getByRole('button',{name:'호기 × 레시피 표',exact:true}).click();
  assert.ok(await page.locator('tr.grouphead.job .lv.up').count()>0);
  assert.ok(await page.locator('td.subr .lv.dn').count()>0);
  await page.locator('tr.total').first().click();
  await page.locator('dialog.lotwin[open]').getByText('정상 WPH에서 실제 WPH까지').waitFor();
  await page.locator('dialog.lotwin[open]').getByRole('tab',{name:'1장 처리 시간'}).click();
  await page.locator('dialog.lotwin[open]').getByRole('tab',{name:'Lot별 실제 WPH'}).click();
  await page.locator('dialog.lotwin[open] svg[aria-label="Lot별 실제 WPH"]').waitFor();
  await page.locator('dialog.lotwin[open]').getByRole('button',{name:'닫기',exact:true}).click();
  // 이슈 #9: WPH · 생산능력 기간별 추이(일 · 주 · 월) — 단위 · 그래프 값을 바꾸고, 레시피를 고르면 기간 행이 그 기간의 레시피 상세 창을 연다.
  await page.getByRole('button',{name:'기간별 추이',exact:true}).click();
  const wseg=page.getByRole('group',{name:'기간 단위'});
  await page.locator('svg[aria-label="기간별 실제 WPH"]').waitFor();
  for(const u of ['일','월','주']){await wseg.getByRole('button',{name:u,exact:true}).click();assert.ok(await page.locator('table.wphper tbody tr').count()>0);}
  await page.getByRole('group',{name:'그래프 값'}).getByRole('button',{name:'하루 생산능력',exact:true}).click();
  await page.locator('svg[aria-label="기간별 하루 생산능력"]').waitFor();
  await rsel.selectOption({index:1});
  await page.locator('table.wphper tbody tr.clickable').first().click();
  await page.locator('dialog.lotwin[open]').getByText('정상 WPH에서 실제 WPH까지').waitFor();
  await page.locator('dialog.lotwin[open]').getByRole('button',{name:'닫기',exact:true}).click();
  await rsel.selectOption({index:0});
  // Defect 과다 판정 설명 창(기준값 · 판정 목록)은 Lot 추적 › 멈춘 이유 요약에서도 열린다.
  await page.getByRole('tab',{name:'Lot 추적',exact:true}).click();
  await page.getByRole('button',{name:/작업자 중단 \d+건/}).click();
  await page.locator('.card2').getByRole('button',{name:'Defect 과다 판정 기준 · 목록 보기'}).click();
  await page.locator('#defTitle').waitFor();
  await page.locator('dialog[open]').filter({has:page.locator('#defTitle')}).getByRole('button',{name:'닫기',exact:true}).click();
  // Developer mode lives in 설정 › 정보; the Batch screen shows its bar while it is on.
  await page.getByRole('button',{name:'설정',exact:true}).click();
  await page.getByRole('tab',{name:'정보'}).click();
  await page.getByLabel('개발자 기능',{exact:true}).check();
  await page.getByRole('button',{name:'Batch Report 분석',exact:true}).click();
  await page.locator('.devbar').getByText('개발자 기능 켜짐').waitFor();
  await page.getByRole('button',{name:'설정',exact:true}).click();
  await page.getByRole('tab',{name:'정보'}).click();
  await page.getByLabel('개발자 기능',{exact:true}).uncheck();
  await page.getByRole('button',{name:'Batch Report 분석',exact:true}).click();
  await page.locator('.devbar').waitFor({state:'detached'});
  // 찾기 · 취합: file-name search → Lot groups → aggregate → Excel.
  await page.getByRole('tab',{name:/Batch Report 찾기/}).click();
  await page.getByLabel('Batch Report 키워드').fill('BatchReport_00');
  await page.getByRole('button',{name:'검색 →'}).click();
  await page.locator('.groups .group').first().waitFor({timeout:60000});
  await page.locator('.group .gh input[type=checkbox]').first().check();
  await page.getByRole('button',{name:'선택한 Batch Report 취합 →'}).click();
  await page.locator('.stamp').filter({hasText:'최신 스캔 자동'}).waitFor();
  await page.getByRole('button',{name:'Excel로 저장',exact:true}).click();
  assert((await page.locator('.kept-screen:not([hidden])').getByLabel('저장된 Excel').inputValue()).includes('BatchReport_취합_'));
  await page.getByRole('tab',{name:/가동률 조사 및 분석/}).click();
  await page.getByRole('button',{name:'Recipe 관리',exact:true}).click();
  // Zone → Alg title lines take two of the first 100 lines.
  await page.waitForFunction(()=>document.querySelectorAll('.comparison-row').length===98&&document.querySelectorAll('.comparison-group').length===2);
  await page.getByRole('button',{name:'Min Defect Bright 0 색상 변경',exact:true}).click();
  await page.locator('dialog input[type=text], dialog input:not([type])').fill('#1267AB');
  await page.getByRole('button',{name:'저장',exact:true}).click();
  await page.waitForFunction(()=>!document.querySelector('dialog').open);
  await page.locator('.comparison-viewport').evaluate(el=>{el.scrollTop=42042;});
  await page.waitForFunction(()=>[...document.querySelectorAll('.comparison-row')].some(r=>r.textContent.includes('Min Defect Bright 1000')));
  assert.equal(await page.locator('.comparison-row').count(),100);
  // Up to 100 comparison machines on one screen: all 20 fit, so 다음 호기 is off.
  await page.waitForFunction(()=>document.querySelector('.comparison-header')?.textContent.includes('AOI-20'));
  assert.equal(await page.getByRole('button',{name:'다음 호기',exact:true}).isDisabled(),true);
  // The ★ baseline column is wide enough for a long value.
  assert((await page.locator('.equipment-value').first().evaluate(el=>el.getBoundingClientRect().width))>=125);
  // Collapse / expand the Zone title.
  await page.locator('.comparison-viewport').evaluate(el=>{el.scrollTop=0;});
  await page.getByRole('button',{name:'Zone Surface 접기',exact:true}).click();
  await page.waitForFunction(()=>document.querySelectorAll('.comparison-row').length===0&&document.querySelectorAll('.comparison-group').length===1);
  await page.getByRole('button',{name:'모두 펼치기',exact:true}).click();
  await page.waitForFunction(()=>document.querySelectorAll('.comparison-row').length===98);
  await page.getByRole('button',{name:'Alg GlobalRTP 접기',exact:true}).click();
  await page.waitForFunction(()=>document.querySelectorAll('.comparison-row').length===0&&document.querySelectorAll('.comparison-group').length===2);
  await page.getByRole('button',{name:'Alg GlobalRTP 펼치기',exact:true}).click();
  await page.waitForFunction(()=>document.querySelectorAll('.comparison-row').length===98);
  await page.screenshot({path:join(root,'docs/screenshots/rev1-recipe-groups.png'),fullPage:true});
  await page.getByLabel('값 없는 호기 제외').check();
  await page.getByLabel('값 없는 호기 제외').uncheck();
  await page.screenshot({path:join(root,'docs/screenshots/rev1-recipe.png'),fullPage:true});
  // B: Recipe tools — Zone filter, paint mode (shared cell colors), export.
  await page.getByLabel('Zone',{exact:true}).selectOption('Surface');
  await page.getByLabel('🖌 셀 색칠 모드').check();
  await page.locator('.comparison-viewport').evaluate(el=>{el.scrollTop=0;});
  const firstCell=page.locator('.comparison-row').first().locator('span[data-machine]').first();
  await firstCell.waitFor();
  await firstCell.click();
  await page.waitForFunction(()=>getComputedStyle(document.querySelector('.comparison-row span[data-machine]')).backgroundColor==='rgb(255, 242, 204)');
  await page.getByLabel('🖌 셀 색칠 모드').uncheck();
  await page.getByRole('button',{name:'내보내기…',exact:true}).click();
  await page.locator('dialog[open]').getByRole('button',{name:'Excel로 내보내기',exact:true}).click();
  assert((await page.locator('dialog[open]').getByLabel('저장된 Excel').inputValue()).includes('내보내기'));
  await page.locator('dialog[open]').getByRole('button',{name:'닫기',exact:true}).click();
  // 특이사항 · 참고자료 · 장비 IP 는 상단 '메모' 탭의 하위 탭(Memo.tsx).
  await page.getByRole('button',{name:'메모',exact:true}).click();
  await page.getByRole('tab',{name:'장비 IP',exact:true}).click();
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
  // B: 장비종류 is a fixed choice; rows can be deleted.
  await page.getByRole('row').filter({hasText:'10.0.0.3'}).getByRole('button',{name:'—',exact:true}).click();
  await page.locator('dialog[open] select').selectOption('KLA');
  await page.locator('dialog[open]').getByRole('button',{name:'저장',exact:true}).click();
  await page.getByRole('row').filter({hasText:'10.0.0.3'}).getByRole('button',{name:'KLA',exact:true}).waitFor();
  await page.getByRole('button',{name:'2행 삭제',exact:true}).click();
  await page.locator('dialog[open]').getByRole('button',{name:'삭제',exact:true}).click();
  await page.getByRole('button',{name:'10.0.0.3',exact:true}).waitFor({state:'detached'});
  // B: 특이사항 종료 여부 toggles with one click.
  await page.getByRole('tab',{name:'특이사항',exact:true}).click();
  const done=page.getByRole('checkbox',{name:'1행 종료 여부'});
  await done.waitFor();assert.equal(await done.getAttribute('aria-checked'),'false');
  await done.click();
  await page.waitForFunction(()=>document.querySelector('[aria-label="1행 종료 여부"]')?.getAttribute('aria-checked')==='true');
  // B: daily auto-run switch and an extra Report folder in 설정.
  await page.getByRole('button',{name:'설정',exact:true}).click();
  await page.getByRole('tab',{name:'Batch Report 분석 주기 설정'}).click();
  await page.getByLabel('자동 분석 사용 (기본 꺼짐)').click();
  await page.getByText('자동 분석을 켰습니다').waitFor();
  await page.getByLabel('분석 주기').selectOption('12');
  await page.getByText('분석 주기를 저장했습니다').waitFor();
  await page.getByRole('tab',{name:'AOI 장비 호기 루트'}).click();
  const archive=join(fixture,'archive-01');await mkdir(archive);
  await page.getByLabel('추가 폴더 호기').selectOption('AOI-01');
  await page.getByLabel('추가 폴더',{exact:true}).fill(archive);
  await page.getByRole('button',{name:'추가 폴더 등록',exact:true}).click();
  await page.getByText(archive,{exact:true}).waitFor();
  await page.screenshot({path:join(root,'docs/screenshots/rev1-settings-aoi.png'),fullPage:true});
  await page.getByRole('tab',{name:'정보'}).click();
  await page.getByLabel('오류 로그 폴더').waitFor();
  await page.getByRole('button',{name:'업데이트 확인',exact:true}).click();
  await page.getByText('새 버전 99.1.0이 있습니다.').waitFor();
  await page.getByRole('tab',{name:'로컬 작업 폴더'}).click();
  await page.getByLabel('현재 위치').waitFor();
  await page.getByRole('button',{name:'오래된 임시 폴더 정리',exact:true}).click();
  await page.getByText(/오래된 임시 폴더 \d+개 정리/).waitFor();
  await page.getByRole('button',{name:'Batch Report 분석',exact:true}).click();
  // The extra Report folder is part of the machine box (its tooltip lists every folder).
  await page.waitForFunction(a=>[...document.querySelectorAll('.mbox')].some(b=>(b.getAttribute('data-tip')||'').includes('+ '+a)),archive);
  await page.getByText('자동 분석: 켜짐',{exact:false}).waitFor();
  await page.getByRole('button',{name:'Commonality 조사',exact:true}).click();
  await page.locator('.cm-file input').first().check();
  await page.getByRole('button',{name:'선택 결과 비교 ▶',exact:true}).click();
  await page.waitForFunction(()=>document.querySelectorAll('.cm-outlier').length===12);
  assert.equal(await page.locator('section.panel').last().locator('.table-scroll tbody tr').count(),3);
  await page.getByRole('button',{name:'다음 파라미터',exact:true}).click();
  await page.getByRole('button',{name:'비교 Excel 저장',exact:true}).click();
  // Kept (hidden) screens such as Batch Report 분석 may hold their own '저장된 Excel' field.
  const visibleScreen=page.locator('.kept-screen:not([hidden])');
  await visibleScreen.getByLabel('저장된 Excel').waitFor();
  assert((await visibleScreen.getByLabel('저장된 Excel').inputValue()).endsWith('.xlsx'));
  // B: 신규 Commonality 조사 — plan → slots → safe copy → coefficients → form → values → compare list.
  // Plan Excel import (old headers fail여부/생성일자 → 이슈 Lot), unregistered machine → 설정 jump.
  await page.getByRole('button',{name:'📂 계획 엑셀 불러오기',exact:true}).click();
  await page.getByText('계획 3행을 불러왔습니다',{exact:false}).waitFor();
  assert.equal(await page.getByLabel('1행 이슈 Lot').isChecked(),true);
  await page.screenshot({path:join(root,'docs/screenshots/rev1-cm-plan.png'),fullPage:true});
  await page.getByRole('button',{name:'AOI-21 경로 지정 ▶',exact:true}).click();
  await page.getByRole('tab',{name:'AOI 장비 호기 루트',selected:true}).waitFor();
  assert.equal(await page.getByLabel('호기',{exact:true}).inputValue(),'AOI-21');
  // Back to Commonality: the imported plan is still there (screen kept alive).
  await page.getByRole('button',{name:'Commonality 조사',exact:true}).click();
  assert.equal(await page.getByLabel('1행 디바이스명').inputValue(),'DEVA-1');
  // Row selection delete / delete all.
  await page.getByLabel('2행 선택').check();await page.getByLabel('3행 선택').check();
  await page.getByRole('button',{name:'선택 삭제 (2)',exact:true}).click();
  assert.equal(await page.getByLabel('2행 디바이스명').count(),0);
  page.once('dialog',d=>d.accept());
  await page.getByRole('button',{name:'전체 삭제',exact:true}).click();
  assert.equal(await page.getByLabel('1행 디바이스명').inputValue(),'');
  await page.getByLabel('1행 디바이스명').fill('DEVA-1');
  await page.getByLabel('1행 공정번호').fill('6321');
  await page.getByLabel('1행 S/M').fill('HPG');
  await page.getByLabel('1행 이슈 Lot').check();
  await page.getByRole('button',{name:'S/M 폴더 찾기 ▶',exact:true}).click();
  await page.getByText('HPG · 이슈 Lot',{exact:true}).waitFor();
  await page.getByLabel('HPG 슬롯 CX02').check();
  await page.getByRole('button',{name:'안전 복사 ▶',exact:true}).click();
  await page.getByLabel('안전 복사 위치').waitFor();
  // [S/M] cell → which Lot folders this unit covers.
  await page.getByRole('button',{name:/1번 조사 단위 S\/M 2개 보기/}).click();
  await page.locator('dialog[open]').getByText('HPG·CX02',{exact:true}).waitFor();
  await page.locator('dialog[open]').getByRole('button',{name:'닫기',exact:true}).click();
  await page.getByLabel(/조사 제목/).fill('PI3');
  await page.getByRole('button',{name:'변환계수 확인 ▶',exact:true}).click();
  await page.getByText('[PI3] 변형별 변환계수').waitFor();
  await page.getByRole('button',{name:'양식 편집 ▶',exact:true}).click();
  await page.getByText('PI3 · 조사 양식').waitFor();
  // Zone-grouped editor with keyboard: Enter toggles 사용 of the cursor row.
  await page.locator('.zone-tabs [role=tab]').first().waitFor();
  await page.locator('.form-editor:not([hidden] *)').screenshot({path:join(root,'docs/screenshots/rev1-cm-editor.png')});
  const grid=page.locator('.editor-grid:not([hidden] *)');
  const firstUse=grid.locator('tbody tr').first().locator('input[type=checkbox]');
  const was=await firstUse.isChecked();
  await grid.focus();await page.keyboard.press('Enter');
  await page.waitForFunction(w=>document.querySelector('.editor-grid:not([hidden] *) tbody tr input[type=checkbox]').checked!==w,was);
  assert.equal(await grid.locator('tbody tr').nth(1).getAttribute('aria-selected'),'true');   // Enter moved down
  await page.keyboard.press('ArrowUp');await page.keyboard.press('Enter');     // back to the original state
  await page.waitForFunction(w=>document.querySelector('.editor-grid:not([hidden] *) tbody tr input[type=checkbox]').checked===w,was);
  // 전체 해제 / 전체 선택 over every Zone.
  await page.getByRole('button',{name:'모든 Zone 전체 해제',exact:true}).click();
  await page.getByText('사용 0 / 전체',{exact:false}).first().waitFor();
  await page.getByRole('button',{name:'모든 Zone 전체 선택',exact:true}).click();
  await page.waitForFunction(()=>!/사용 0 \//.test(document.body.innerText));
  await page.getByRole('button',{name:'양식 확정 ▶',exact:true}).click();
  await page.getByLabel('확정 양식').waitFor();
  await page.getByRole('button',{name:'값 조사 실행',exact:true}).click();
  await page.getByText('모든 조사 단위를 마쳤습니다').waitFor();
  await page.getByLabel('조사 결과').waitFor();
  await page.waitForFunction(()=>document.querySelectorAll('.cm-file').length===2);
  // B: 양식 확정 — registered machine list, coefficient table, value inheritance.
  await recipeTab('Recipe 양식 편집하기');
  await page.locator('select:not([hidden] *)').first().selectOption('PI2');
  // The inline button now opens the Excel original; the editor opens from [원본 열기 ▶].
  const excelBtn=page.locator('button:not([hidden] *)',{hasText:'📊 엑셀 원본 열기'});
  await page.waitForFunction(()=>[...document.querySelectorAll('button')].some(b=>b.textContent.includes('엑셀 원본 열기')&&!b.disabled));
  assert.equal(await page.locator('.form-picker:not([hidden] *)').getByRole('button',{name:'원본 열기 ▶',exact:true}).count(),0);
  assert(await excelBtn.isEnabled());
  await page.locator('.stepnav:not([hidden] *)').getByRole('button',{name:'원본 열기 ▶',exact:true}).click();
  await page.getByText('사용 3 / 전체 3',{exact:true}).waitFor();
  await page.getByRole('button',{name:'확정 단계로 ▶',exact:true}).click();
  // No machine picker: the machine comes from the form itself.
  assert.equal(await page.locator('[aria-label="확정 호기"]:not([hidden] *)').count(),0);
  await page.locator('.hint:not([hidden] *)',{hasText:'기준 호기: AOI-01'}).first().waitFor();
  const coef=page.getByLabel('R1-x20 변환계수');
  await coef.waitFor();
  await page.getByText('원본 라벨',{exact:true}).or(page.getByText('기본값',{exact:true})).first().waitFor();
  await coef.fill('0');
  await page.getByText('변환계수는 0보다 큰 숫자여야 합니다.').waitFor();
  await coef.fill('1.5');
  await page.locator('.runbar').getByRole('button',{name:'양식 확정 ▶'}).click();
  await page.getByLabel('이전 값을 이어받은 취합 파일').waitFor();
  assert((await page.getByLabel('확정 양식').inputValue()).endsWith('.xlsx'));
  // B: 값 업데이트 — equipment collection asks for the Job folder, then variants → preview → write.
  await recipeTab('Recipe 업데이트');
  // Row lists with a real '전체 선택' checkbox; clicking a row toggles it.
  const upRecipes=page.locator('[role=group][aria-label="레시피"]:not([hidden] *)');
  await upRecipes.locator('tr',{hasText:'PI2'}).click();
  assert(await upRecipes.getByLabel('PI2 선택').isChecked());
  const upMachines=page.locator('[role=group][aria-label="호기"]:not([hidden] *)');
  await upMachines.getByLabel('호기 전체 선택').check();
  await upMachines.getByLabel('호기 전체 선택').uncheck();
  await upMachines.getByLabel('AOI-01 선택').check();
  await page.getByRole('button',{name:'수집 시작 ▶',exact:true}).click();
  const ask=page.locator('dialog[open]');
  await ask.getByText('AOI-01 · 레시피 ↔ Job 폴더').waitFor();
  assert(await ask.locator('.pick-item').filter({hasText:'R_TB500_PI2 - Enhanced'}).locator('input').isChecked());
  await ask.getByRole('button',{name:'확인하고 계속',exact:true}).click();
  await page.getByText('결과 확인',{exact:true}).waitFor();
  await page.waitForFunction(()=>[...document.querySelectorAll('.stepper:not([hidden] *) .st')].findIndex(e=>e.classList.contains('now'))>=2);
  if(await page.getByRole('button',{name:'매칭 확인 ▶',exact:true}).isVisible())await page.getByRole('button',{name:'매칭 확인 ▶',exact:true}).click();
  await page.getByRole('button',{name:'취합 저장 ▶',exact:true}).waitFor();
  const keep=page.getByLabel('그래도 포함');
  if(await keep.count())await keep.first().check();
  await page.getByRole('button',{name:'취합 저장 ▶',exact:true}).click();
  // 결과 확인 stays on its own step: per-recipe table, then the file path, then [처음으로].
  await page.locator('.update-result tbody tr').filter({hasText:'PI2'}).waitFor();
  await page.getByLabel('취합 파일 경로',{exact:true}).waitFor();
  assert.equal(await page.getByRole('button',{name:'수집 시작 ▶',exact:true}).count(),0);
  await page.screenshot({path:join(root,'docs/screenshots/rev1-update-result.png'),fullPage:true});
  await page.getByRole('button',{name:'⟲ 처음으로',exact:true}).click();
  await page.getByRole('button',{name:'수집 시작 ▶',exact:true}).waitFor();
  await page.screenshot({path:join(root,'docs/screenshots/rev1-update-select.png'),fullPage:true});
  // B: 이력 — the inherited collation is a second file; row lists and Excel export.
  await recipeTab('레시피 날짜별 비교하기');
  await page.locator('.cm-file:not([hidden] *) input').nth(2).waitFor();
  // Newest first: [값 업데이트, 이어받기, fixture]. Compare the fixture with the inherited one.
  await page.locator('.cm-file:not([hidden] *) input').nth(0).uncheck();
  await page.locator('.cm-file:not([hidden] *) input').nth(2).check();
  await page.getByRole('button',{name:'비교 ▶',exact:true}).click();
  await page.getByText(/값변경 \d+ · 추가행 \d+ · 삭제행 \d+/).waitFor();
  await page.getByLabel('종류').selectOption('행 삭제');
  await page.waitForFunction(()=>document.querySelector('.table-scroll:not([hidden] *) tbody tr td:last-child')?.textContent==='행 삭제');
  await page.getByRole('button',{name:'변경내역 Excel 저장',exact:true}).click();
  assert((await page.getByLabel('저장된 변경내역').inputValue()).includes('이력비교'));
  // B: 양식 만들기 — 새로 만들기 from equipment (Job question → coefficients → editor → confirm).
  // The edit tab keeps its finished state (keep-alive) while the new-recipe tab is separate.
  await recipeTab('신규 Recipe 만들기');
  await page.getByLabel('새 레시피 이름').fill('PI2');
  await page.locator('[role=group][aria-label="수집 호기"]:not([hidden] *)').getByLabel('AOI-01 선택').check();
  await page.getByRole('button',{name:'수집 시작',exact:true}).click();
  await page.locator('dialog[open]').getByRole('button',{name:'확인하고 계속',exact:true}).click();
  await page.getByText('변형별 변환계수',{exact:true}).waitFor();
  await page.getByRole('button',{name:'파라미터 불러오기 ▶',exact:true}).first().click();
  await page.locator('.count:not([hidden] *)').filter({hasText:/사용 \d+ \/ 전체 \d+/}).first().waitFor();
  await page.getByRole('button',{name:'확정 단계로 ▶',exact:true}).click();
  await page.locator('.hint:not([hidden] *)',{hasText:'기준 호기: AOI-01'}).first().waitFor();
  await page.locator('.runbar:not([hidden] *)').getByRole('button',{name:'양식 확정 ▶'}).click();
  await page.locator('.open-path:not([hidden] *)').filter({hasText:'확정 양식'}).first().waitFor();
  // 자동 감시: pick a Job folder on the (fake) equipment, turn the watch on, run once.
  await page.getByRole('button',{name:'자동 감시',exact:true}).click();
  const pw=page.locator('section.panel',{has:page.getByRole('heading',{name:'파라미터 자동 감시'})});
  // 최근 알림 first, then one tab per watch; status table above the wizard.
  await page.getByRole('heading',{name:'최근 알림'}).waitFor();
  await pw.getByLabel('파라미터 자동 감시 현황').waitFor();
  // Selected sub-tab is highlighted green like the top tabs.
  assert.equal(await page.getByRole('tab',{name:'파라미터 자동 감시'}).evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(234, 250, 243)');
  await pw.getByRole('button',{name:'다음 ▶',exact:true}).click();          // ① 주기·시간대 → ② 장비 연결 확인
  const conn=pw.locator('[role=group][aria-label="연결 확인 호기"]');
  await conn.getByLabel('AOI-01 선택').check();
  await pw.getByRole('button',{name:/선택 호기 연결 확인/}).click();
  await conn.getByText('✓ 연결됨').first().waitFor();
  await pw.getByRole('button',{name:'다음 ▶',exact:true}).click();          // ③ 감시 대상
  await pw.getByLabel('호기').selectOption('AOI-01');
  await pw.locator('[role=group][aria-label="감시할 레시피"]').getByText('PI2',{exact:true}).click();
  await pw.getByRole('button',{name:/📁 장비에서 폴더 고르기/}).click();
  const fp=pw.getByRole('dialog',{name:'Job 폴더 선택'});
  await fp.getByRole('button',{name:'📁 R_TB500_PI2 - Enhanced'}).click();
  await fp.getByRole('button',{name:"이 폴더를 'PI2'에 지정"}).click();
  await pw.getByRole('cell',{name:'R_TB500_PI2 - Enhanced'}).waitFor();
  // ON/OFF works without finishing the wizard; OFF is red.
  const pOff=pw.getByRole('button',{name:/파라미터 자동 감시 OFF/});
  assert.equal(await pOff.evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(220, 38, 38)');
  await pOff.click();
  await pw.getByRole('button',{name:/파라미터 자동 감시 ON/}).waitFor();
  await pw.getByLabel('파라미터 자동 감시 현황').getByText('ON',{exact:true}).waitFor();
  await pw.getByRole('button',{name:'다음 ▶',exact:true}).click();          // ④ 확인·저장
  await pw.getByRole('button',{name:'▶ 즉시 확인'}).click();
  await page.locator('.toast').filter({hasText:/즉시 확인 완료|취합된 레시피가 없습니다/}).first().waitFor({timeout:60000});
  await page.locator('.notice-list li').filter({hasText:'파라미터 자동 감시 — 시작'}).first().waitFor();
  assert(background.enabled&&background.tooltip.includes('장비 ✓'),'watch on must keep the app resident in the tray');
  await page.screenshot({path:join(root,'docs/screenshots/rev1-watch.png'),fullPage:true});
  // The Commonality watch is its own tab with its own wizard.
  await page.getByRole('tab',{name:'Commonality 자동 감시 (여러 호기 무인)'}).click();
  await page.getByRole('heading',{name:'Commonality 자동 감시 (여러 호기 무인)'}).waitFor();
  const cw=page.locator('section.panel',{has:page.getByRole('heading',{name:'Commonality 자동 감시 (여러 호기 무인)'})});
  await cw.getByLabel('Commonality 자동 감시 현황').waitFor();
  await cw.getByRole('button',{name:'다음 ▶',exact:true}).click();
  await cw.locator('[role=group][aria-label="감시 호기"]').waitFor();
  await page.screenshot({path:join(root,'docs/screenshots/rev1-watch-cm.png'),fullPage:true});
  await page.getByRole('tab',{name:'파라미터 자동 감시'}).click();
  await pw.getByRole('button',{name:/파라미터 자동 감시 ON/}).click();
  await pw.getByRole('button',{name:/파라미터 자동 감시 OFF/}).waitFor();
  await page.waitForFunction(()=>true);assert.equal(background.enabled,false);
  // Color·Gray 매칭: scan a Lot folder, process both wafers (canvas crop/thumbnails), Excel per wafer.
  await page.getByRole('button',{name:'Color·Gray 매칭',exact:true}).click();
  const cg=page.locator('section.panel',{has:page.getByRole('heading',{name:'Color · Gray 매칭'})});
  await cg.getByLabel('Lot 또는 Wafer 폴더').fill(join(fixture,'cglot'));
  await cg.getByRole('button',{name:'Wafer 찾기'}).click();
  await cg.locator('[role=group][aria-label="처리할 Wafer"]').getByText('2개 선택').waitFor();
  await page.getByText('AOI Color 이미지와 같은 위치의 Gray 스캔 이미지를 찾아').waitFor();
  await cg.getByRole('button',{name:'다음 ▶',exact:true}).click();          // → 저장 위치 (기본 = 로컬)
  const outs=cg.getByRole('radiogroup',{name:'결과 저장 위치'});
  assert.equal(await outs.getByRole('radio',{name:'로컬 작업 폴더 (기본)'}).getAttribute('aria-checked'),'true');
  await outs.getByRole('radio',{name:'다른 로컬 폴더'}).click();
  assert.equal(await outs.getByRole('radio',{name:'다른 로컬 폴더'}).getAttribute('aria-checked'),'true');
  await page.waitForTimeout(400);   // let the button colour transition finish
  await page.screenshot({path:join(root,'docs/screenshots/rev1-colorgray-output.png'),fullPage:true});
  await outs.getByRole('radio',{name:'로컬 작업 폴더 (기본)'}).click();
  await cg.getByRole('button',{name:'다음 ▶',exact:true}).click();          // → 실행 검토
  await cg.getByLabel('실행 전 검토').waitFor();
  await cg.getByRole('button',{name:'▶ 처리 시작'}).click();
  await cg.getByLabel('Wafer별 결과').getByRole('row').nth(2).waitFor({timeout:60000});
  await cg.getByText('완료',{exact:true}).first().waitFor();
  const cgRows=await cg.getByLabel('Wafer별 결과').getByRole('row').allInnerTexts();
  assert(cgRows.slice(1).every(t=>/\t1\t2\t/.test(t)),'each wafer: 1 matched, 2 failed — '+JSON.stringify(cgRows));
  await page.screenshot({path:join(root,'docs/screenshots/rev1-colorgray.png'),fullPage:true});
  // 기능 둘러보기: 주요 탭을 차례로 옮겨 다니며 끝까지(오류 없이) — 마지막은 설정 탭.
  await page.getByRole('button',{name:'설정',exact:true}).click();
  await page.getByRole('button',{name:'기능 둘러보기',exact:true}).click();
  const fb=page.locator('.tour-bubble');
  const total=Number((await fb.locator('.tour-count').innerText()).split('/')[1]);
  for(let k=1;k<total;k++){await fb.getByRole('button',{name:'다음 →'}).click();await fb.locator('.tour-count').filter({hasText:new RegExp('^'+(k+1)+' /')}).waitFor();}
  await fb.getByRole('heading',{name:'끝!'}).waitFor();
  await fb.getByRole('button',{name:'완료',exact:true}).click();await fb.waitFor({state:'detached'});
  assert.equal(await page.locator('.navigation button[aria-current="page"]').innerText(),'설정');
  // A7: a reloaded page re-attaches to the same engine (ids keep increasing, no 'already connected').
  await page.reload();
  await page.getByText('로컬 엔진 연결됨',{exact:true}).waitFor();
  await recipeTab('레시피 날짜별 비교하기');
  await page.locator('.cm-file input').first().waitFor();
  assert.deepEqual(errors,[]);
  assert.equal(stderr,'');
  console.log(JSON.stringify({passed:true,viewports:4,pythonReports:205,lots:69,scriptEscaped:true,serverPortsOpened:0}));
}finally{
  lines.close();engine.stdin.end();
  await new Promise(resolve=>engine.exitCode!==null?resolve():engine.once('exit',resolve));
  await delivery.catch(()=>{});await browser.close();await rm(fixture,{recursive:true,force:true});
}
