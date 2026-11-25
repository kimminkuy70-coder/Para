// v13: drives the real local web server (param_manager/webserver.py) on 127.0.0.1 with the
// built screen (frontend/dist) and the real Python engine. Native dialogs are answered by the
// fixture; native calls are echoed on the engine's stdout. Any other origin is refused.
import {createRequire} from 'node:module';
import {mkdtemp, readFile, rm, mkdir, writeFile} from 'node:fs/promises';
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
const engine=spawn(python,[join(root,'tests/desktop_browser_fixture.py'),'web',fixture],{cwd:root,stdio:['pipe','pipe','pipe']});
let delivery=Promise.resolve();
const page=await browser.newPage({viewport:{width:1440,height:1000}});
const errors=[],nativeCalls=[];
page.on('pageerror',e=>errors.push(e.message));
const lines=createInterface({input:engine.stdout});
let appUrl;const urlReady=new Promise(res=>{lines.on('line',line=>{const m=JSON.parse(line);
  if(m.native)nativeCalls.push(m.native);
  if(m.url){appUrl=m.url;res();}
  else if(m.native==='set_background')background=m.args;   // tray residency request
});});
// Recipe 관리 holds the recipe workflows as tabs (값 확인 · 업데이트 · 신규 · 양식 편집 · 날짜별 비교).
// 맨 위 탭(#32, v14.4.2) = CAMTEK · KLA · TB500 Review 조회 · 설정 · 메모 — 회사 탭이 아니면 기능 탭 줄이 없으므로 CAMTEK 을 먼저 누른다.
async function feature(name){
  if(!(await page.locator('.navigation button').allInnerTexts()).includes(name))await page.getByRole('button',{name:'CAMTEK',exact:true}).click();
  await page.locator('.navigation').getByRole('button',{name,exact:true}).click();
}
/** Defect 분석 칸(.dfx-host) 안에서 함수를 부른다 — 함수 안 window · document = 그 칸의 것(DefectHost.ts 의 host.__dfx). 종전 iframe Frame 과 같은 모양. */
function defectIn(title){
  const sel=`.dfx-host[data-title="${title}"]`;
  // 화면 보안 정책(script-src 'self')이 페이지 안 문자열 실행을 막으므로, 함수를 감싼 식 하나를 Playwright 가 바로 보낸다(페이지 안 eval 없음)
  const expr=(fn,arg)=>`(()=>{const h=document.querySelector(${JSON.stringify(sel)}),H=h&&h.__dfx;if(!H)return false;`+
    `return ((window,document,arg)=>(${fn.toString()})(arg))(H.win,H.doc,${JSON.stringify(arg===undefined?null:arg)})})()`;
  // waitForFunction = 여기서 되풀이(Playwright 의 문자열 waitForFunction 은 페이지 안에서 eval 을 써 막힘)
  const evaluate=(fn,arg)=>page.evaluate(expr(fn,arg));
  return {evaluate,async waitForFunction(fn,arg,opt){const end=Date.now()+((opt&&opt.timeout)||30000);
    for(;;){const v=await evaluate(fn,arg);if(v)return v;if(Date.now()>end)throw new Error('defectIn.waitForFunction timeout: '+fn.toString().slice(0,120));await new Promise(r=>setTimeout(r,60))}}};
}
async function recipeTab(name){await feature('Recipe 관리');await page.getByRole('tab',{name,exact:true}).click();}
let stderr='',background={enabled:false,tooltip:''};engine.stderr.on('data',d=>stderr+=d);
try{
  await Promise.race([urlReady,new Promise((_,rej)=>setTimeout(()=>rej(new Error('web server did not start: '+stderr)),30000))]);
  const appOrigin=new URL(appUrl).origin;
  await page.route('**/*',async route=>{
    const url=new URL(route.request().url());
    if(url.pathname==='/qa-font.otf'&&process.env.PARA_TEST_FONT_PATH){
      await route.fulfill({body:await readFile(process.env.PARA_TEST_FONT_PATH),contentType:'font/otf'});return;
    }
    assert.equal(url.origin,appOrigin,'External request must never occur');
    await route.continue();
  });
  await page.goto(appUrl);
  assert.equal(new URL(page.url()).search,'','token must be removed from the address');
  if(process.env.PARA_TEST_FONT_PATH){
    await page.addStyleTag({content:"@font-face{font-family:'Malgun Gothic';src:url('/qa-font.otf')}"});
    await page.evaluate(()=>document.fonts.ready);
  }
  await page.getByText('로컬 엔진 연결됨',{exact:true}).waitFor();
  // v13 start-up pop-up: GitHub is off in the fixture, so the OneDrive backup release is found;
  // a source copy (not installed) cannot install it. [나중에] closes it.
  const banner=page.locator('dialog.update-banner');
  await banner.getByText('새 버전 14.9.0이 있습니다').waitFor();
  // v14.3.12(소유자): '지금 버전 · 공개 · GitHub 릴리스/OneDrive 게시 폴더' 줄은 없고, 업데이트 내용은 '1. …' 번호를 붙여 한 줄씩
  await banner.locator('pre.changelog',{hasText:'1. 테스트 게시'}).waitFor();
  assert.equal(await banner.getByText(/지금 버전|OneDrive 게시 폴더|GitHub 릴리스/).count(),0);
  assert(await banner.getByRole('button',{name:'지금 업데이트'}).isDisabled());
  await banner.getByRole('button',{name:'나중에'}).click();
  await banner.waitFor({state:'detached'});
  // A3: a toast raised while a modal dialog is open must be the topmost element.
  await feature('Recipe 관리');
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
  assert.deepEqual(await page.getByRole('tab').allInnerTexts(),['저장 폴더','로컬 작업 폴더','AOI 장비 호기 루트','정보']);   // #39: 분석 주기 설정은 자동 분석 및 취합 탭으로
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
  await tourNext('먼저 장비마다 IP 폴더에 1회 로그인 (가장 중요)');
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
  await feature('Batch Report 분석');
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
  // 소유자 2026-11-25: Scanresult 는 늘 백업본까지 찾는다 — [백업본 포함해서 조사] 스위치 없음(이슈 #8 의 원본만 보기 삭제).
  assert.equal(await page.getByRole('switch',{name:'백업본 포함해서 조사'}).count(),0);
  await feature('Batch Report 분석');
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
  // 소유자 2026-11-25: 가동률 탭의 [Batch Report 캐시 가져오기] 상자 · '다시 읽지 않기' 스위치 없음(늘 캐시 재사용),
  // 날짜 옆 [캐시에서만 찾기] = 장비 접속 없이 이 PC 캐시만으로 조사.
  assert.equal(await page.getByLabel('Batch Report 캐시 가져오기').count(),0);
  assert.equal(await page.getByText('이미 읽은 Batch Report는 다시 읽지 않기').count(),0);
  await page.getByLabel('조사: 캐시에서만 찾기').check();
  await page.getByRole('button',{name:'조사 시작 →'}).click();
  await page.locator('.scope-status').filter({hasText:/Batch Report 205개.*캐시 사용 205/}).waitFor({timeout:60000});
  await page.getByLabel('조사: 캐시에서만 찾기').uncheck();
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
  // 막대 위 도움말: 앞 단계의 알림(토스트) · 다시 그리기와 겹치면 첫 hover 가 빠질 때가 있어 마우스를 뺐다가 다시(최대 4번).
  const barTip=page.locator('.bv-tip.rich .tg b').first();
  for(let k=0;k<4;k++){await page.mouse.move(5,5);await page.locator('svg[aria-label="기간별 Lot Scan 현황"] rect.hit').first().hover();
    if(await barTip.waitFor({timeout:5000}).then(()=>true,()=>false))break;}
  await barTip.waitFor();
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
  // 멈춘 이유 요약 필터(이슈 #80): 레시피 · 호기 · Error 고르기, 호기별 표, 칸 누르면 그 Lot만 목록에.
  await page.getByRole('button',{name:/^Error \d+/}).click();
  const rz=page.getByRole('group',{name:'멈춘 이유 필터'});
  // 이슈 #81: 여러 개 고르기 — 펼침 목록에서 누를 때마다 고름 / 해제, 고른 항목은 색(aria-selected), 단추에 몇 개인지.
  const pickN=async(label,n)=>{await rz.getByRole('button',{name:label,exact:true}).click();
    const lb=rz.getByRole('listbox',{name:label.replace(' 필터',' 목록')}),op=lb.getByRole('option');
    const cnt=await op.count();assert(cnt>1,label+' has options');const got=[];
    for(let i=1;i<=Math.min(n,cnt-1);i++){const o=op.nth(i);got.push((await o.locator('span').textContent()).trim());await o.click();
      assert.equal(await o.getAttribute('aria-selected'),'true',label+' option marked selected');}
    const o1=op.nth(1);await o1.click();assert.equal(await o1.getAttribute('aria-selected'),'false','second click unselects');
    assert.equal(await op.nth(0).getAttribute('aria-selected'),'true','nothing picked = all');await o1.click();
    await page.keyboard.press('Escape');await lb.waitFor({state:'detached'});return got;};
  const rcp=(await pickN('레시피 필터',1))[0];
  await pickN('Error 필터',1);
  await rz.getByRole('button',{name:'호기별 표',exact:true}).click();
  const rzGrid=page.locator('table.rz-grid');
  await rzGrid.waitFor();
  assert.equal(await rzGrid.locator('tbody tr').count(),1,'one error row after Error filter');
  await rzGrid.locator('tbody td.clickable').first().click();
  assert(await page.locator('.ll-tools .chip').filter({hasText:rcp}).count(),'lot list chip carries the recipe');
  await rz.getByRole('button',{name:/필터 지우기/}).click();
  await rz.getByRole('button',{name:'목록',exact:true}).click();
  await page.locator('.ll-tools .chip').filter({hasText:rcp}).click();
  // Developer mode lives in 설정 › 정보; the Batch screen shows its bar while it is on.
  await page.getByRole('button',{name:'설정',exact:true}).click();
  await page.getByRole('tab',{name:'정보'}).click();
  await page.getByLabel('개발자 기능',{exact:true}).check();
  await feature('Batch Report 분석');
  await page.locator('.devbar').getByText('개발자 기능 켜짐').waitFor();
  // 이슈 #39: 개발자 기능이 켜져 있을 때만 [OneDrive 에 게시](저장 폴더 옆 캐시공유/) — 받기는 [찾기 · 취합]의 [OneDrive 에서 최신 캐시 받기]
  await page.getByRole('button',{name:'OneDrive 에 게시',exact:true}).click();
  const made=page.locator('.cache-export [role=status]').filter({hasText:'게시함:'});await made.waitFor();
  assert.match(await made.locator('code').innerText(),/캐시공유[\\/]BatchReport_캐시_\d{8}_\d{6}\.zip$/);
  await page.getByRole('button',{name:'설정',exact:true}).click();
  await page.getByRole('tab',{name:'정보'}).click();
  await page.getByLabel('개발자 기능',{exact:true}).uncheck();
  await feature('Batch Report 분석');
  await page.locator('.devbar').waitFor({state:'detached'});
  assert.equal(await page.getByRole('button',{name:'OneDrive 에 게시',exact:true}).count(),0);
  // 찾기 · 취합: file-name search → Lot groups → aggregate → Excel.
  await page.getByRole('tab',{name:/Batch Report 찾기/}).click();
  // v14.1.9 [캐시에서만 찾기]: 호기 격자 = 로컬 캐시에 든 호기(이 PC 에 등록하지 않은 호기도) — 장비 없이 찾는다.
  await page.getByLabel('캐시에서만 찾기',{exact:true}).check();
  await page.locator('.mhead .lbl').filter({hasText:'캐시 호기'}).waitFor();
  await page.getByRole('checkbox',{name:'AOI-01 찾기'}).waitFor();
  assert.match(await page.getByRole('group',{name:'찾을 호기'}).locator('label.mbox').first().getAttribute('data-tip'),/^AOI-01\n캐시 Batch Report \d+개\n/);
  assert.equal(await page.getByRole('checkbox',{name:'AOI-05 찾기'}).count(),0);           // 캐시에 없는 등록 호기는 안 보임
  await page.getByRole('button',{name:'OneDrive 에서 최신 캐시 받기',exact:true}).click();
  await page.locator('.toast').filter({hasText:/Batch Report 캐시를 가져왔습니다 — 호기 \d+대 · 새 Batch Report 0개 \(이미 있던 \d+개는 그대로\)/}).waitFor();
  await page.getByLabel('Batch Report 키워드').fill('BatchReport_00');
  await page.getByRole('button',{name:'검색 →'}).click();
  await page.getByRole('table',{name:'찾은 Batch Report 목록'}).waitFor({timeout:60000});
  await page.getByText(/로컬 조사 캐시에서만 찾았습니다/).waitFor();
  await page.getByRole('button',{name:'◀ 검색으로',exact:true}).click();
  await page.getByLabel('캐시에서만 찾기',{exact:true}).uncheck();
  await page.locator('.mhead .lbl').filter({hasText:'호기 범위'}).waitFor();
  await page.getByLabel('Batch Report 키워드').fill('BatchReport_00');
  await page.getByRole('button',{name:'검색 →'}).click();
  // #19: 찾은 파일 이름 목록(원문 안 엶) → 고른 것만 읽기(앞뒤 24시간 포함).
  await page.getByRole('table',{name:'찾은 Batch Report 목록'}).waitFor({timeout:60000});
  await page.getByText('원문은 아직 열지 않았습니다',{exact:false}).waitFor({timeout:60000});
  // #25: 목록 안 키워드 검색 · 보이는 것 모두 고르기/해제 · Shift+클릭 범위.
  const ftable=page.getByRole('table',{name:'찾은 Batch Report 목록'});
  await page.getByLabel('찾은 목록 키워드 검색').fill('없는-키워드-xyz');
  await ftable.getByText('목록 안 검색에 맞는 Batch Report가 없습니다.').waitFor();
  await page.getByLabel('찾은 목록 키워드 검색').fill('');
  const fboxes=ftable.locator('tbody input[type=checkbox]');
  if((await fboxes.count())>=3){
    await fboxes.nth(0).click();await fboxes.nth(2).click({modifiers:['Shift']});
    assert(await fboxes.nth(1).isChecked());
    await page.getByRole('button',{name:'보이는 것 해제',exact:true}).click();
    assert(!(await fboxes.nth(1).isChecked()));
  }
  await page.getByRole('button',{name:'보이는 것 모두 고르기',exact:true}).click();
  await page.getByRole('button',{name:'고른 Batch Report 읽기 →'}).click();
  await page.locator('.groups .group').first().waitFor({timeout:60000});
  const nGroups=await page.locator('.groups .group').count();
  await page.getByLabel('Lot 목록 키워드 검색').fill('없는-키워드-xyz');
  await page.getByText('검색 · 태그에 맞는 Lot이 없습니다.').waitFor();
  await page.getByLabel('Lot 목록 키워드 검색').fill('');
  // #26: Lot 태그별 보기(③) — 고른 태그의 Lot만, '태그 전체'로 되돌림.
  const gtags=page.getByRole('group',{name:'Lot 태그별 보기'});
  const gchip=gtags.locator('button.jf-chip:not([disabled])').nth(1);
  await gchip.click();assert.equal(await gchip.getAttribute('aria-pressed'),'true');
  assert((await page.locator('.groups .group').count())>=1);
  await gtags.getByRole('button',{name:/태그 전체/}).click();
  assert.equal(await page.locator('.groups .group').count(),nGroups);
  // #27 · #44: Lot 레시피 탭(③) — 레시피 탭을 누르면 그 레시피(Job · Recipe(s)) 줄만 시간순, 탭 전체 선택, '전체' 탭으로 되돌림.
  const grec=page.getByRole('tablist',{name:'Lot 레시피 탭'});
  const recTab=grec.getByRole('tab').nth(1),rname=await recTab.getAttribute('title');
  await recTab.click();assert.equal(await recTab.getAttribute('aria-selected'),'true');
  const nRec=await page.locator('.groups .group').count();assert(nRec>=1&&nRec<=nGroups);
  assert.equal(await page.locator('.groups .group .gh b').filter({hasText:rname}).count(),nRec);
  const tabAll=page.getByLabel('이 탭 Lot 전체 선택');
  await tabAll.check();
  assert.equal(await page.locator('.group .gh input[type=checkbox]:checked').count(),nRec);
  await tabAll.uncheck();
  assert.equal(await page.locator('.group .gh input[type=checkbox]:checked').count(),0);
  const starts=await page.locator('.groups .group .gh .meta').allTextContents();
  assert.deepEqual([...starts].sort(),starts,'레시피 탭 안 Lot 은 시간순');
  await grec.getByRole('tab',{name:/^전체/}).click();
  assert.equal(await page.locator('.groups .group').count(),nGroups);
  await page.getByRole('button',{name:'보이는 Lot 모두 선택',exact:true}).click();
  assert.equal(await page.locator('.group .gh input[type=checkbox]:checked').count(),nGroups);
  await page.getByRole('button',{name:'모두 해제',exact:true}).click();
  assert.equal(await page.locator('.group .gh input[type=checkbox]:checked').count(),0);
  await page.locator('.group .gh input[type=checkbox]').first().check();
  await page.getByRole('button',{name:'선택한 Batch Report 취합 →'}).click();
  await page.locator('.stamp').filter({hasText:'최신 스캔 자동'}).waitFor();
  // #26: 취합 결과 태그별 보기 — 최종 선정 기준 태그 칸 + 고른 태그만.
  const rtags=page.getByRole('group',{name:'취합 결과 태그별 보기'});
  const rchip=rtags.locator('button.jf-chip:not([disabled])').nth(1);
  await rchip.click();assert.equal(await rchip.getAttribute('aria-pressed'),'true');
  assert((await page.locator('.kept-screen:not([hidden]) td .st').count())>=1);
  await rtags.getByRole('button',{name:/태그 전체/}).click();
  // #24: Lot별 Yield 탭 — 레시피 · 키워드 필터, 전체 선택 → 선택 합계 · 평균.
  await page.getByRole('tab',{name:'Lot별 Yield',exact:true}).click();
  const ytable=page.getByRole('table',{name:'Lot별 Yield 표'});
  await ytable.waitFor();
  assert((await ytable.locator('tbody tr').count())>=1);
  await page.getByLabel('Yield 전체 선택').check();
  await ytable.locator('tfoot').getByText('선택 Lot 평균').waitFor();
  await page.getByLabel('Yield 키워드 검색').fill('없는-키워드-xyz');
  await ytable.getByText('조건에 맞는 Lot이 없습니다.').waitFor();
  await page.getByLabel('Yield 키워드 검색').fill('');
  await page.getByRole('tab',{name:'Lot 취합 · wafer',exact:true}).click();
  await page.getByRole('button',{name:'Excel로 저장',exact:true}).click();
  assert((await page.locator('.kept-screen:not([hidden])').getByLabel('저장된 Excel').inputValue()).includes('BatchReport_취합_'));
  await page.getByRole('tab',{name:/가동률 조사 및 분석/}).click();
  await feature('Recipe 관리');
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
  // #35: 메모 › 장비 IP 에 적은 호기를 설정 › AOI 장비 호기 루트에서 고를 수 있다(장비종류 미지정 = CAMTEK · KLA 둘 다).
  await page.getByRole('button',{name:'새 행 추가',exact:true}).click();
  await page.locator('dialog[open]').getByLabel('호기',{exact:true}).fill('AOI-07');
  await page.locator('dialog[open]').getByLabel('IP',{exact:true}).fill('10.0.0.7');
  await page.locator('dialog[open]').getByRole('button',{name:'행 저장',exact:true}).click();
  await page.getByRole('button',{name:'10.0.0.7',exact:true}).waitFor();
  // B: 특이사항 종료 여부 toggles with one click.
  await page.getByRole('tab',{name:'특이사항',exact:true}).click();
  const done=page.getByRole('checkbox',{name:'1행 종료 여부'});
  await done.waitFor();assert.equal(await done.getAttribute('aria-checked'),'false');
  await done.click();
  await page.waitForFunction(()=>document.querySelector('[aria-label="1행 종료 여부"]')?.getAttribute('aria-checked')==='true');
  // B: daily auto-run switch (#39: CAMTEK › 자동 분석 및 취합 › Batch Report 자동 분석) and an extra Report folder in 설정.
  await feature('자동 분석 및 취합');
  await page.getByRole('tab',{name:'Batch Report 자동 분석'}).click();
  await page.getByLabel('자동 분석 사용 (기본 꺼짐)').click();
  await page.getByText('자동 분석을 켰습니다').waitFor();
  // Para #54: Batch Report 자동 분석만 켜도 창을 닫으면 트레이에 남는다(예약 시각에 돌려면 앱이 살아 있어야 함).
  await page.waitForFunction(()=>true);
  for(let i=0;i<50&&!background.enabled;i++)await page.waitForTimeout(100);
  assert(background.enabled&&background.tooltip.includes('Batch Report ✓'),'batch auto must keep the app resident: '+background.tooltip);
  // 소유자 2026-11-25: 주기 · 시각 = 돌림 선택으로 고르기만 하고 [설정 저장]으로 저장(종전 = 고르면 바로 저장)
  const saveBtn=page.getByRole('button',{name:'설정 저장',exact:true});
  assert.equal(await saveBtn.isDisabled(),true);
  {const wheel=page.locator('label.field',{hasText:'분석 주기'}).locator('.wp-col'),before=await page.getByLabel('분석 주기').inputValue();   // 휠로 한 칸
    await wheel.hover();await page.mouse.wheel(0,120);await page.waitForFunction(b=>document.querySelector('select[data-wheel]:not([disabled])')&&[...document.querySelectorAll('label.field')].find(l=>l.textContent.startsWith('분석 주기')).querySelector('select').value!==b,before);
    assert.equal(await saveBtn.isDisabled(),false);await page.getByRole('button',{name:'되돌리기',exact:true}).click();assert.equal(await page.getByLabel('분석 주기').inputValue(),before)}
  await page.getByLabel('분석 주기').selectOption('12');
  await page.getByLabel('실행 시각 (시)').waitFor({state:'detached'});   // 시간 단위 주기에는 시각 칸 없음
  await saveBtn.click();await page.getByText(/자동 분석 주기를 저장했습니다: 12시간마다/).waitFor();
  // #33: 하루 단위 주기 = 실행 시각(5분 단위) + 즉시 실행
  await page.getByLabel('분석 주기').selectOption('24');
  await page.getByLabel('실행 시각 (시)').selectOption('07');
  await page.getByLabel('분 (5분 단위)').selectOption('35');
  await saveBtn.click();await page.getByText('자동 분석 주기를 저장했습니다: 하루 1회 (24시간) · 07:35').waitFor();
  await page.getByText('하루 1회 (24시간) · 07:35 에 실행합니다',{exact:false}).waitFor();
  // Para #43: 켜거나 시각을 바꾸면 그때부터 센다 — 다음 실행 = 오늘 또는 내일 07:35(예전 마지막 실행 + 주기 · backoff 아님).
  {const p=n=>String(n).padStart(2,'0'),day=d=>`${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())} 07:35`;
    const now=new Date(),tomorrow=new Date(now.getTime()+86400000);
    const next=(await page.getByRole('row',{name:/다음 실행/}).innerText()).replace(/^다음 실행\s*/,'').trim();
    assert.ok([day(now),day(tomorrow)].includes(next),'다음 실행 '+next);}
  await page.getByRole('button',{name:'▶ 즉시 실행',exact:true}).click();
  await page.getByRole('heading',{name:'Batch Report 분석',exact:true}).waitFor();
  await page.getByText('Batch Report 분석을 지금 실행합니다(지난 조사 조건).').waitFor();
  await page.getByText('조사를 완료했습니다.',{exact:true}).last().waitFor({timeout:120000});
  // 설정 › 현재 설정 의 [보기] 는 자동 분석 및 취합 › Batch Report 자동 분석 탭을 연다.
  await page.getByRole('button',{name:'설정',exact:true}).click();
  await page.getByLabel('현재 설정').locator('summary').click();
  await page.getByRole('button',{name:'보기',exact:true}).last().click();
  await page.getByRole('heading',{name:'Batch Report 자동 분석',exact:true}).waitFor();
  // #39: 자동 분석이 끝나면 OneDrive 에 캐시 zip 올리기(체크) — 즉시 실행 뒤 게시까지.
  await page.getByLabel(/자동 분석이 끝나면 Batch Report 캐시 zip 을 OneDrive 에 올리기/).click();
  await page.getByText('자동 분석이 끝나면 캐시 zip 을 OneDrive 에 게시합니다').waitFor();
  await page.getByRole('button',{name:'▶ 즉시 실행',exact:true}).click();
  await page.getByText(/자동 분석 뒤 Batch Report 캐시를 OneDrive 에 올렸습니다/).waitFor({timeout:120000});
  await feature('자동 분석 및 취합');
  await page.getByRole('tab',{name:'Batch Report 자동 분석'}).click();
  await page.getByLabel(/자동 분석이 끝나면 Batch Report 캐시 zip 을 OneDrive 에 올리기/).click();
  await page.getByText('OneDrive 게시를 껐습니다').waitFor();
  // v14.3.18: 자동 분석 호기 현황(지난 [조사 시작] 호기 = ✓ 포함) + [⚙ 자동 분석 호기 설정] → 가동률 조사 및 분석의 조사 범위
  {const box=page.getByLabel('자동 분석 호기 현황');await box.getByText('✓ 포함').first().waitFor();
    assert.match(await box.locator('.count').innerText(),/^\d+ \/ \d+대 · /);
    await box.getByRole('button',{name:'⚙ 자동 분석 호기 설정'}).click();
    await page.getByRole('heading',{name:'Batch Report 분석',exact:true}).waitFor();
    await page.getByRole('heading',{name:'어느 호기의 어느 기간을 조사할까요?'}).waitFor();
    assert.equal(await page.getByRole('tab',{name:/가동률 조사 및 분석/}).getAttribute('aria-selected'),'true');
    await feature('자동 분석 및 취합');await page.getByRole('tab',{name:'Batch Report 자동 분석'}).click();}
  await page.getByLabel('분석 주기').selectOption('12');await page.getByRole('button',{name:'설정 저장',exact:true}).click();await page.getByText(/자동 분석 주기를 저장했습니다: 12시간마다/).last().waitFor();
  await page.getByRole('button',{name:'설정',exact:true}).click();
  await page.getByRole('tab',{name:'AOI 장비 호기 루트'}).click();
  const memoPick=page.getByLabel('CAMTEK 메모 장비 IP 에서 호기 고르기');
  assert.deepEqual(await memoPick.locator('option').allInnerTexts(),['선택… (1대)','AOI-07']);   // AOI-01 은 이미 등록
  await memoPick.selectOption('AOI-07');
  assert.equal(await page.getByLabel('호기',{exact:true}).inputValue(),'AOI-07');
  await page.getByLabel('호기',{exact:true}).fill('');
  // #36: 네트워크 드라이브 바로 아래 폴더를 AOI 호기 후보로 찾기 — 'AOI' 이름 · 메모 호기만 미리 체크, 등록된 것은 막힘.
  const nas=join(fixture,'nas-1');
  for(const d of ['AOI-08','AOI-07','Backup'])await mkdir(join(nas,d),{recursive:true});
  await mkdir(join(nas,'AOI-08','Reports'));
  await page.getByLabel('네트워크 드라이브',{exact:true}).fill(nas);
  await page.getByRole('button',{name:'호기 찾기',exact:true}).click();
  await page.getByLabel('AOI-08 고르기').waitFor();
  assert.equal(await page.getByLabel('AOI-07 고르기').isChecked(),true);
  assert.equal(await page.getByLabel('Backup 고르기').isChecked(),false);
  await page.getByLabel('AOI-07 고르기').uncheck();
  await page.getByRole('button',{name:'고른 1대 등록',exact:true}).click();
  await page.getByText(/1대 등록\(AOI-08\)/).first().waitFor();
  assert.equal(await page.getByLabel('AOI-08 고르기').isDisabled(),true);
  await page.locator('table.tbl td',{hasText:join(nas,'AOI-08')}).first().waitFor();
  const archive=join(fixture,'archive-01');await mkdir(archive);
  await page.getByLabel('추가 폴더 호기').selectOption('AOI-01');
  await page.getByLabel('추가 폴더',{exact:true}).fill(archive);
  await page.getByRole('button',{name:'추가 폴더 등록',exact:true}).click();
  await page.getByText(archive,{exact:true}).waitFor();
  // #79: 호기별 Job 폴더 열 — 기본 C:\Job, [변경]으로 D:\Job 저장 · [기본값]으로 되돌림.
  const jobCell=page.getByTestId('jobdir-AOI-08');
  assert.match(await jobCell.innerText(),/C:\\Job \(기본\)/);
  await page.getByRole('button',{name:'AOI-08 Job 폴더 변경',exact:true}).click();
  await page.getByLabel('AOI-08 Job 폴더',{exact:true}).fill('d:\\Job');
  await page.getByRole('button',{name:'저장',exact:true}).click();
  await page.getByText(/AOI-08 Job 폴더를 저장했습니다/).first().waitFor();
  assert.match(await jobCell.innerText(),/^D:\\Job/);
  await page.screenshot({path:join(root,'docs/screenshots/rev1-settings-aoi.png'),fullPage:true});
  await page.getByRole('button',{name:'AOI-08 Job 폴더 변경',exact:true}).click();
  await page.getByRole('button',{name:'기본값',exact:true}).click();
  await page.getByRole('button',{name:'저장',exact:true}).click();
  await page.waitForFunction(()=>/C:\\Job \(기본\)/.test(document.querySelector('[data-testid="jobdir-AOI-08"]')?.textContent||''));
  await page.getByRole('tab',{name:'정보'}).click();
  await page.getByLabel('오류 로그 폴더').waitFor();
  // v14.4.3(#90 소유자): 설정에는 업데이트 구역이 없다(업데이트는 시작 알림 창만) · 프로그램 화면에 GitHub 글자 없음.
  assert.equal(await page.getByRole('button',{name:'업데이트 확인',exact:true}).count(),0);
  assert.equal(await page.getByText(/GitHub|OneDrive 에 새 버전 게시|게시 폴더 열기/).count(),0);
  await page.getByRole('tab',{name:'로컬 작업 폴더'}).click();
  await page.getByLabel('현재 위치').waitFor();
  await page.getByRole('button',{name:'오래된 임시 폴더 정리',exact:true}).click();
  await page.getByText(/오래된 임시 폴더 \d+개 정리/).waitFor();
  await feature('Batch Report 분석');
  // The extra Report folder is part of the machine box (its tooltip lists every folder).
  await page.waitForFunction(a=>[...document.querySelectorAll('.mbox')].some(b=>(b.getAttribute('data-tip')||'').includes('+ '+a)),archive);
  await page.getByText('자동 분석: 켜짐',{exact:false}).waitFor();
  await feature('Commonality 조사');
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
  await feature('Commonality 조사');
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
  // 이슈 #21: 확정 결과는 창으로 뜨고, 닫은 뒤에도 같은 양식을 다시 확정하지 않는다.
  await page.locator('dialog[open]').getByRole('heading',{name:'✅ 양식 확정 완료'}).waitFor();
  await page.locator('dialog[open]').getByRole('button',{name:'닫기',exact:true}).click();
  assert.equal(await page.locator('.runbar:not([hidden] *)').getByRole('button',{name:'양식 확정 ▶'}).count(),0);
  await page.locator('.runbar:not([hidden] *)').getByRole('button',{name:'✅ 확정 완료 · 결과 보기'}).waitFor();
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
  // 이슈 #22: 수집 전에 연결 확인 → 연결된 호기만 체크한 목록 → 그대로 진행.
  await page.getByRole('button',{name:'연결 확인 ▶',exact:true}).click();
  await page.getByText('이 장비들로만 업데이트를 진행할까요?',{exact:false}).waitFor();
  const upConn=page.locator('[role=group][aria-label="진행할 호기"]:not([hidden] *)');
  assert(await upConn.getByLabel('AOI-01 선택').isChecked());
  await upConn.getByLabel('AOI-01 선택').uncheck();
  assert(await page.getByRole('button',{name:'이 호기들로 수집 시작 ▶',exact:true}).isDisabled());
  await upConn.getByLabel('AOI-01 선택').check();
  await page.getByRole('button',{name:'이 호기들로 수집 시작 ▶',exact:true}).click();
  const ask=page.locator('dialog[open]');
  await ask.getByText('AOI-01 · 레시피 ↔ Job 폴더').waitFor();
  assert(await ask.locator('.pick-item').filter({hasText:'R_TB500_PI2 - Enhanced'}).locator('input').isChecked());
  await ask.getByText('직접 찾아 고르세요',{exact:false}).waitFor();
  await ask.getByRole('button',{name:'이 호기 건너뛰기',exact:true}).waitFor();
  await ask.getByLabel('Job 폴더 이름 찾기').fill('Other');
  assert.equal(await ask.locator('.pick-item').filter({hasText:'Other job'}).count(),1);
  assert.equal(await ask.locator('.pick-item').filter({hasText:'R_TB500_PI2 - Enhanced'}).count(),1);   // 체크된 것은 계속 보임
  await ask.getByLabel('Job 폴더 이름 찾기').fill('');
  await ask.getByRole('button',{name:'확인하고 계속',exact:true}).click();
  await page.getByText('결과 확인',{exact:true}).waitFor();
  try{await page.waitForFunction(()=>[...document.querySelectorAll('.stepper:not([hidden] *) .st')].findIndex(e=>e.classList.contains('now'))>=3)}
  catch(e){console.log('DEBUG726',JSON.stringify(await page.evaluate(()=>({dlg:[...document.querySelectorAll('dialog[open]')].map(d=>d.innerText.slice(0,400)),toasts:[...document.querySelectorAll('.toast')].map(t=>t.innerText),
    act:document.querySelector('.activity')?.innerText.slice(0,300),st:[...document.querySelectorAll('.stepper:not([hidden] *) .st')].map(s=>s.className),main:document.querySelector('main').innerText.slice(0,1200)}))));throw e}
  if(await page.getByRole('button',{name:'매칭 확인 ▶',exact:true}).isVisible())await page.getByRole('button',{name:'매칭 확인 ▶',exact:true}).click();
  await page.getByRole('button',{name:'취합 저장 ▶',exact:true}).waitFor();
  const keep=page.getByLabel('그래도 포함');
  if(await keep.count())await keep.first().check();
  await page.getByRole('button',{name:'취합 저장 ▶',exact:true}).click();
  // 결과 확인 stays on its own step: per-recipe table, then the file path, then [처음으로].
  await page.locator('.update-result tbody tr').filter({hasText:'PI2'}).waitFor();
  await page.getByLabel('취합 파일 경로',{exact:true}).waitFor();
  assert.equal(await page.getByRole('button',{name:'연결 확인 ▶',exact:true}).count(),0);
  await page.screenshot({path:join(root,'docs/screenshots/rev1-update-result.png'),fullPage:true});
  await page.getByRole('button',{name:'⟲ 처음으로',exact:true}).click();
  await page.getByRole('button',{name:'연결 확인 ▶',exact:true}).waitFor();
  await page.screenshot({path:join(root,'docs/screenshots/rev1-update-select.png'),fullPage:true});
  // B: 이력 — the inherited collation is a second file; row lists and Excel export.
  await recipeTab('레시피 날짜별 비교하기');
  await page.locator('.cm-file:not([hidden] *) input').nth(2).waitFor();
  // Newest first: [값 업데이트, 이어받기, fixture]. Compare the fixture with the inherited one.
  await page.locator('.cm-file:not([hidden] *) input').nth(0).uncheck();
  await page.locator('.cm-file:not([hidden] *) input').nth(2).check();
  await page.getByRole('button',{name:'비교 ▶',exact:true}).click();
  await page.getByText(/값변경 \d+ · 추가행 \d+ · 삭제행 \d+/).waitFor();
  await page.getByRole('combobox',{name:/^종류/}).selectOption('행 삭제');
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
  // 이슈 #20: 수집 뒤 '하위 레시피 선택' 단계 — 기본은 전부 선택, 고른 것만 양식에 넣는다.
  const subPick=page.locator('[role=group][aria-label="양식에 넣을 하위 레시피"]:not([hidden] *)');
  await subPick.waitFor();
  await subPick.getByLabel('양식에 넣을 하위 레시피 전체 선택').uncheck();
  assert(await page.getByRole('button',{name:'파라미터 불러오기 ▶',exact:true}).first().isDisabled());
  await subPick.getByLabel('양식에 넣을 하위 레시피 전체 선택').check();
  await page.getByRole('button',{name:'파라미터 불러오기 ▶',exact:true}).first().click();
  await page.locator('.count:not([hidden] *)').filter({hasText:/사용 \d+ \/ 전체 \d+/}).first().waitFor();
  await page.getByRole('button',{name:'확정 단계로 ▶',exact:true}).click();
  await page.locator('.hint:not([hidden] *)',{hasText:'기준 호기: AOI-01'}).first().waitFor();
  await page.locator('.runbar:not([hidden] *)').getByRole('button',{name:'양식 확정 ▶'}).click();
  await page.locator('.open-path:not([hidden] *)').filter({hasText:'확정 양식'}).first().waitFor();
  await page.locator('dialog[open]').getByRole('button',{name:'닫기',exact:true}).click();
  // 자동 감시: pick a Job folder on the (fake) equipment, turn the watch on, run once.
  await feature('자동 분석 및 취합');
  // 탭 세 개(#39: Batch Report 자동 분석 추가) — 앞에서 Batch Report 탭을 열어 두었으므로 파라미터 탭으로.
  assert.deepEqual(await page.getByRole('tablist',{name:'자동 분석 및 취합 종류'}).getByRole('tab').allInnerTexts(),
    ['파라미터 자동 분석 및 취합','Commonality 자동 분석 및 취합 (여러 호기 무인)','Batch Report 자동 분석']);
  await page.getByRole('tab',{name:'파라미터 자동 분석 및 취합',exact:true}).click();
  await page.mouse.move(0,0);   // hover 색이 아니라 선택 색을 본다(아래 색 확인)
  // DESIGN 14절 3: 고른 탭 = 에메랄드 밑줄만(민트 바탕 없음) — 밑줄은 탭 사이를 미끄러지는 한 줄(motion.ts .tab-ink), 멈추면 고른 탭 바로 아래
  const tabInk=()=>page.evaluate(()=>{const t=[...document.querySelectorAll('[role=tab]')].find(x=>x.textContent==='파라미터 자동 분석 및 취합'),i=t.parentElement.querySelector(':scope>.tab-ink.show');
    if(!i)return null;const a=t.getBoundingClientRect(),b=i.getBoundingClientRect(),px=v=>Math.abs(v)<=1?0:Math.round(v);return [px(b.left-a.left),px(b.width-a.width),px(a.bottom-b.bottom),getComputedStyle(i).backgroundColor,getComputedStyle(t).backgroundColor]});
  await page.waitForFunction(()=>{const t=[...document.querySelectorAll('[role=tab]')].find(x=>x.textContent==='파라미터 자동 분석 및 취합'),i=t&&t.parentElement.querySelector(':scope>.tab-ink.show');
    return i&&Math.abs(i.getBoundingClientRect().left-t.getBoundingClientRect().left)<1&&Math.abs(i.getBoundingClientRect().width-t.getBoundingClientRect().width)<1});
  const pw=page.locator('section.panel',{has:page.getByRole('heading',{name:'파라미터 자동 분석 및 취합'})});
  // 최근 알림 first, then one tab per watch; status table above the wizard.
  await page.getByRole('heading',{name:'최근 알림'}).waitFor();
  await pw.getByLabel('파라미터 자동 분석 및 취합 현황').waitFor();
  // Selected sub-tab = green underline like the top tabs (DESIGN.md 14절 3 — 민트 바탕 없음).
  assert.deepEqual(await tabInk(),[0,0,0,'rgb(16, 185, 129)','rgba(0, 0, 0, 0)']);
  await pw.getByRole('button',{name:'다음 ▶',exact:true}).click();          // ① 주기·시간대 → ② 장비 연결 확인
  const conn=pw.locator('[role=group][aria-label="연결 확인 호기"]');
  await conn.getByLabel('AOI-01 선택').check();
  await pw.getByRole('button',{name:/선택 호기 연결 확인/}).click();
  await conn.getByText('✓ 연결됨').first().waitFor();
  await pw.getByRole('button',{name:'다음 ▶',exact:true}).click();          // ③ 분석 및 취합 대상
  await pw.getByLabel('호기').selectOption('AOI-01');
  await pw.locator('[role=group][aria-label="분석 및 취합할 레시피"]').getByText('PI2',{exact:true}).click();
  await pw.getByRole('button',{name:/📁 장비에서 폴더 고르기/}).click();
  const fp=pw.getByRole('dialog',{name:'Job 폴더 선택'});
  await fp.getByRole('button',{name:'📁 R_TB500_PI2 - Enhanced'}).click();
  await fp.getByRole('button',{name:"이 폴더를 'PI2'에 지정"}).click();
  await pw.getByRole('cell',{name:'R_TB500_PI2 - Enhanced'}).waitFor();
  // ON/OFF works without finishing the wizard; 스위치 모양(DESIGN.md 14절 7) — 꺼짐 = 회색 트랙, 글자 OFF 그대로.
  const pOff=pw.getByRole('button',{name:/파라미터 자동 분석 및 취합 OFF/});
  assert.deepEqual(await pOff.evaluate(el=>[getComputedStyle(el,'::before').backgroundColor,el.textContent]),['rgb(207, 216, 227)','OFF']);
  await pOff.click();
  await pw.getByRole('button',{name:/파라미터 자동 분석 및 취합 ON/}).waitFor();
  await pw.getByLabel('파라미터 자동 분석 및 취합 현황').getByText('ON',{exact:true}).waitFor();
  await pw.getByRole('button',{name:'다음 ▶',exact:true}).click();          // ④ 확인·저장
  await pw.getByRole('button',{name:'▶ 즉시 확인'}).click();
  await page.locator('.toast').filter({hasText:/즉시 확인 완료|취합된 레시피가 없습니다/}).first().waitFor({timeout:60000});
  await page.locator('.notice-list li').filter({hasText:'파라미터 자동 분석 및 취합 — 시작'}).first().waitFor();
  assert(background.enabled&&background.tooltip.includes('장비 ✓'),'watch on must keep the app resident in the tray');
  await page.screenshot({path:join(root,'docs/screenshots/rev1-watch.png'),fullPage:true});
  // The Commonality watch is its own tab with its own wizard.
  await page.getByRole('tab',{name:'Commonality 자동 분석 및 취합 (여러 호기 무인)'}).click();
  await page.getByRole('heading',{name:'Commonality 자동 분석 및 취합 (여러 호기 무인)'}).waitFor();
  const cw=page.locator('section.panel',{has:page.getByRole('heading',{name:'Commonality 자동 분석 및 취합 (여러 호기 무인)'})});
  await cw.getByLabel('Commonality 자동 분석 및 취합 현황').waitFor();
  await cw.getByRole('button',{name:'다음 ▶',exact:true}).click();
  await cw.locator('[role=group][aria-label="분석 및 취합 호기"]').waitFor();
  await page.screenshot({path:join(root,'docs/screenshots/rev1-watch-cm.png'),fullPage:true});
  await page.getByRole('tab',{name:'파라미터 자동 분석 및 취합'}).click();
  await pw.getByRole('button',{name:/파라미터 자동 분석 및 취합 ON/}).click();
  await pw.getByRole('button',{name:/파라미터 자동 분석 및 취합 OFF/}).waitFor();
  // Para #54: 앞에서 켠 Batch Report 자동 분석이 남아 있으므로 파라미터 감시를 꺼도 트레이 상주는 유지된다.
  await page.waitForFunction(()=>true);assert.equal(background.enabled,true);
  assert(background.tooltip.includes('장비 ✗')&&background.tooltip.includes('Batch Report ✓'),'batch auto keeps the app resident: '+background.tooltip);
  // v14.1 Defect 분석: 하위 탭 3개 = Color·Gray 매칭 · Defect 분류 · Defect Map — 다이어그램 체크 없음, 처음 = Color·Gray 매칭
  await feature('Defect 분석');
  await page.locator('.defect-tabs [role=tab]').first().waitFor();   // allInnerTexts 는 기다리지 않음 — 화면이 그려진 뒤
  assert.deepEqual(await page.locator('.defect-tabs [role=tab]').allInnerTexts(),['Color·Gray 매칭','Defect 분류','Defect Map']);
  assert.equal(await page.locator('.defect-tabs [role=tab][aria-selected=true]').innerText(),'Color·Gray 매칭');
  assert.equal(await page.locator('.defect-opt').count(),0);
  // 소유자 2026-11-25: 탭마다 맨 위 제목 · 설명글(PROCESS INTELLIGENCE …)은 없앰 — 제목은 화면 읽기용(sr-only)으로만
  assert.equal(await page.locator('.page-heading').count(),0);assert.equal(await page.locator('#main > h1').innerText(),'Defect 분석');
  // Color·Gray 매칭: scan a Lot folder, process both wafers (canvas crop/thumbnails), Excel per wafer.
  await page.getByRole('tab',{name:'Color·Gray 매칭',exact:true}).click();
  const cg=page.locator('section.panel',{has:page.getByRole('heading',{name:'Color · Gray 매칭'})});
  await cg.getByLabel('Lot 또는 Wafer 폴더').fill(join(fixture,'cglot'));
  await cg.getByRole('button',{name:'Wafer 찾기'}).click();
  await cg.locator('[role=group][aria-label="처리할 Wafer"]').getByText('2개 선택').waitFor();
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
  // v14 Defect 분류 = AOI Contrast Wizard(HTML rev6) — 2026-11-25 부터 화면 안 칸(종전 iframe). 폴더 고르기 · 읽기는 엔진(브라우저 '업로드' 없음 · .ini 그대로 · 읽기 전용)
  // v14.1: HTML 파일은 그대로, 프로그램이 para-skin.css · js 를 넣어 프로그램 테마(머리 · 왼쪽 막대 없음, 스텝퍼, 설명글 = [? 설명 보기])
  await page.getByRole('tab',{name:'Defect 분류',exact:true}).click();
  // 2026-11-25(소유자 "프로그램에 제대로 이식"): iframe 없이 화면 안 칸(.dfx-host, Shadow DOM — DefectHost.ts). 칸 안 = locator 가 그대로 들어감,
  // 칸 안 함수 · document = defectIn(제목).evaluate · waitForFunction(종전 iframe frame 과 같은 모양)
  assert.equal(await page.locator('iframe').count(),0);
  const wz=page.locator('.dfx-host[data-title="Defect 분류"]');
  await wz.locator('#step5.on').waitFor();
  await page.locator('.dfx-host.ready[data-title="Defect 분류"]').waitFor();
  const wzf=defectIn('Defect 분류');
  assert.equal(await wz.locator('.dfx-body.pskin.pskin-big').count(),1);
  // 로딩창 = 화면에 고정, 자리 = 이 칸의 보이는 부분(스크롤해도 아래가 잘리지 않음)
  {const v=await wz.evaluate(h=>{const s=getComputedStyle(h),b=h.shadowRoot.querySelector('#busy')||h.shadowRoot.querySelector('.busy');return {pos:b&&getComputedStyle(b).position,vh:s.getPropertyValue('--vh'),inner:innerHeight,top:h.getBoundingClientRect().top}});
    assert.equal(v.pos,'fixed',JSON.stringify(v));assert(parseInt(v.vh)>0&&parseInt(v.vh)<=v.inner,JSON.stringify(v))}
  assert.equal(await wz.locator('header h1').isVisible(),false);
  assert.equal(await wz.locator('nav').isVisible(),false);
  assert.equal(await wz.locator('#b5p1 .card>p.muted').isVisible(),false);          // 설명글은 숨김(기본)
  await wz.locator('#pHelp').check();
  assert.equal(await wz.locator('#b5p1 .card>p.muted').isVisible(),true);
  assert.equal(await wz.locator('.pguide',{hasText:'Contrast 도움말'}).isVisible(),true);
  await wz.locator('#pHelp').uncheck();
  assert.equal(await wz.locator('.pguide').isVisible(),false);
  assert.deepEqual(await wz.locator('nav button[data-step]').evaluateAll(b=>b.filter(x=>!x.hidden).map(x=>x.dataset.step)),['5']);   // Step 5 만
  const recipe=join(fixture,'defect','RCP'),slotDir=join(recipe,'SETUP1','LOT_A','W01');
  await writeFile(join(fixture,'pick_folder.txt'),recipe);
  await wz.locator('#bigAdd').click();
  await wz.locator('#bigMsg',{hasText:/Slot 1개/}).waitFor({timeout:30000});
  assert(nativeCalls.includes('defect_pick'),'folder picked through the engine: '+nativeCalls.join());
  const s51=await wzf.evaluate(()=>{const c=window.__cw,s=c.BIG.scans[0];return {name:s.name,n:s.cols.n,ci:s.cg&&s.cg.colors.length,plan:!!(s.cg&&s.cg.plan),para:!!c.PARA,warn:s.warns}});
  assert.deepEqual([s51.name,s51.n,s51.ci,s51.plan,s51.para],['RCP/SETUP1/LOT_A/W01',2,3,true,true],JSON.stringify(s51));
  assert.match(await wz.locator('#bigPix').innerText(),/^µm 환산 픽셀 : [\d.]+$/);                              // v14.4.1
  await wzf.evaluate(()=>window.__cw.b5Pair(null));
  const pairs=await wzf.evaluate(()=>window.__cw.BIG.pairs.map(p=>[p.i,p.st,p.c&&p.c.file,p.g&&p.g.file]));
  assert.deepEqual(pairs.find(p=>p[0]===0),[0,'ok','C1.jpg','F1.t.1.jpg'],JSON.stringify(pairs));
  assert.equal(await wzf.evaluate(()=>window.__cw.pcPath('RCP/SETUP1/LOT_A/W01/C1.jpg')),join(slotDir,'C1.jpg'));   // 전체 경로 = 엔진이 아는 고른 폴더
  assert.equal(await wz.locator('#bigBase').isVisible(),false);                                                      // [원본 폴더 경로] 칸 없음
  // v14.1.5 5-1 필터 = 줄마다 제목 · 내용(Lot 제외 · 분류 따로 줄), 값 범위 4개는 한 줄, 분류 이름 = 장비 스캔 분류 · 리뷰 결과
  assert.deepEqual(await wz.locator('#bigFlt .frow>.fh').allInnerTexts(),['Lot · Slot','Lot 제외','장비 스캔 분류','리뷰 결과','값 범위','Recipe','Zone','정렬']);
  const rngY=await wz.locator('#bigFltIn label.rng').evaluateAll(l=>l.map(x=>Math.round(x.getBoundingClientRect().top)));
  assert.equal(rngY.length,4);assert.equal(new Set(rngY).size,4,'값 범위 = 한 줄에 하나(막대 + 숫자 칸, 소유자 2026-11-24): '+rngY);
  assert.equal(await wz.locator('#bigFltIn label.rng .prs .prs-th[role=slider]').count(),8);
  assert.equal(await wz.locator('#bigCls .frow .chipgrid .clsck').count(),2);
  const bigHead=await wz.locator('#bigList .bh').innerText();
  assert(bigHead.includes('장비 스캔 분류')&&bigHead.includes('리뷰 결과')&&!/첫번째|재분류/.test(bigHead),bigHead);
  // v14.1.8 목록 위 검색(모든 열 값 + 사진 이름, Enter) · ☑(처음 = 모두 ☑): ☐ 는 다음 단계 · CSV 에서 빠지고, 검색으로 숨었다 다시 보여도 그대로
  assert.equal(await wz.locator('#bigLs .lsn').innerText(),'☑ 2 / 2개');
  const q=async(bar,list,v)=>{await wz.locator(`#${bar} input[type=search]`).fill(v);await wz.locator(`#${bar} input[type=search]`).press('Enter');return wz.locator(`#${list} .br`).count()};
  assert.deepEqual([await q('bigLs','bigList','45'),await q('bigLs','bigList','c1.jpg'),await q('bigLs','bigList','lot_a w01'),await q('bigLs','bigList','zzz')],[1,1,2,0]);   // 숫자 열(#83 실제 값 45 — 종전 45.00) · Color 사진 이름 · 두 단어 · 없음
  await q('bigLs','bigList','');
  // #83 후속: 5-1 Zone 고르기(번호 + Zones.ini 이름 + 개수) — 고르면 그 Zone 만, 비우면 전체
  {const zs=wz.locator('#bigFlt select[data-f="zn"]'),zo=await zs.locator('option').allInnerTexts(),n0=await wz.locator('#bigList .br').count();
    assert(zo.length>=2&&zo[0]==='전체',JSON.stringify(zo));await zs.selectOption({index:1});await new Promise(r=>setTimeout(r,400));
    const n1=await wz.locator('#bigList .br').count();assert(n1>0&&n1<=n0,`zone ${n1}/${n0}`);await zs.selectOption('');await new Promise(r=>setTimeout(r,400));
    assert.equal(await wz.locator('#bigList .br').count(),n0)}
  // 소유자 2026-11-24 양방향 막대: 막대 끝 = 자료의 실제 최소 · 최대(Contrast 30 ~ 45), 손잡이 = 숫자 칸에 적음, 끝(Home) = 칸 비움(제한 없음)
  {const th=wz.locator('#bigFltIn label.rng').first().locator('.prs-th').first(),c0=wz.locator('#bigFlt [data-f="c0"]');
    assert.deepEqual([await th.getAttribute('aria-valuemin'),await th.getAttribute('aria-valuemax')],['30','45']);
    await th.focus();await th.press('ArrowRight');assert.equal(await c0.inputValue(),'30.1');await wzf.waitForFunction(()=>document.querySelectorAll('#bigList .br').length===1);
    assert.equal(await wz.locator('#bigFltIn label.rng.on').count(),1);
    await th.press('Home');assert.equal(await c0.inputValue(),'');await wzf.waitForFunction(()=>document.querySelectorAll('#bigList .br').length===2)}
  await wz.locator('#bigList .br').first().locator('span.pk').click();
  assert.equal(await wz.locator('#bigLs .lsn').innerText(),'☑ 1 / 2개');assert.match(await wz.locator('#toB2').innerText(),/☑ 1개/);
  await q('bigLs','bigList','zzz');await q('bigLs','bigList','');assert.equal(await wz.locator('#bigLs .lsn').innerText(),'☑ 1 / 2개');
  await wz.locator('#bigLs [data-ls="none"]').click();assert.equal(await wz.locator('#toB2').isDisabled(),true);
  await wz.locator('#bigLs [data-ls="all"]').click();assert.equal(await wz.locator('#bigLs .lsn').innerText(),'☑ 2 / 2개');
  // 스크롤 한 겹: 칸 높이 = 내용 높이(칸 안 스크롤 없음 — 페이지만 스크롤)
  assert(await wz.evaluate(h=>{const b=h.shadowRoot.querySelector('.dfx-body').getBoundingClientRect().height,r=h.getBoundingClientRect().height;return b>400&&Math.abs(r-b)<=1&&h.scrollHeight<=h.clientHeight+1}),'host grows with content');
  await wz.locator('[data-b5="2"]').click();
  await wz.locator('#b5list .br',{hasText:'Color·Gray 매칭 완료'}).first().waitFor();                                // 종전 '짝 완료'
  // 소유자 2026-11-24: 대규모 필터 = 5-1 · 5-2 · 5-3 모두 — 필터 카드 한 벌이 지금 단계 목록 위로 따라가고 값은 그대로, 5-2 · 5-3 목록 = 넘어온 Defect 중 필터에 맞는 것
  {const rows=n=>wzf.waitForFunction(k=>document.querySelectorAll('#b5list .br').length===k,n);
    assert.equal(await wz.locator('#b5p2 #bigFlt').count(),1);assert.equal(await wz.locator('#bigCsv').isVisible(),false);
    await wz.locator('#bigFlt [data-f="c0"]').fill('40');await rows(1);
    assert.match(await wz.locator('#bigFltNote').innerText(),/넘어온 Defect 2개 중 필터에 맞는 것 1개/);
    await wz.locator('[data-b5="1"]').click();assert.equal(await wz.locator('#b5p1 #bigFlt [data-f="c0"]').inputValue(),'40');
    assert.equal(await wz.locator('#bigFltNote').isVisible(),false);assert.equal(await wz.locator('#bigList .br').count(),1);
    await wz.locator('[data-b5="2"]').click();assert.equal(await wz.locator('#b5p2 #bigFlt [data-f="c0"]').inputValue(),'40');await rows(1);
    await wz.locator('#bigFlt [data-f="clear"]').click();await rows(2)}
  assert.deepEqual([await q('b5Ls','b5list','f1.t.1'),await q('b5Ls','b5list','zzz')],[1,0]);await q('b5Ls','b5list','');   // Gray 프레임 이름
  assert.equal(await wz.locator('#b5Ls .lsn').innerText(),'☑ 2 / 2개');
  await wz.locator('#b5list .br',{hasText:'Color·Gray 매칭 완료'}).locator('span.pk').click();assert.match(await wz.locator('#toB3').innerText(),/☑ 1개/);   // 5-3 으로 = 보이는 ☑ 줄
  await wz.locator('#b5Ls [data-ls="all"]').click();assert.match(await wz.locator('#toB3').innerText(),/☑ 2개/);
  await wz.locator('#toB3').click();await wz.locator('#c5Color canvas').waitFor({timeout:30000});   // 사진 = 엔진에서
  {const rows=n=>wzf.waitForFunction(k=>document.querySelectorAll('#c5list .br').length===k,n);   // 5-3 도 같은 필터(값 유지)
    assert.equal(await wz.locator('#b5p3 #bigFlt').count(),1);await wz.locator('#bigFlt [data-f="c0"]').fill('50');await rows(0);   // Contrast 45 · 30 둘 다 빠짐
    await wz.locator('[data-b5="2"]').click();assert.equal(await wz.locator('#b5p2 #bigFlt [data-f="c0"]').inputValue(),'50');assert.equal(await wz.locator('#b5list .br').count(),0);
    assert.equal(await wz.locator('[data-b5="3"]').isDisabled(),true);   // 필터에 맞는 Defect 가 없으면 5-3 으로 갈 것이 없음
    await wz.locator('#bigFlt [data-f="c0"]').fill('45');await wzf.waitForFunction(()=>document.querySelectorAll('#b5list .br').length===1);
    await wz.locator('[data-b5="3"]').click();await rows(1);assert.equal(await wz.locator('#b5p3 #bigFlt [data-f="c0"]').inputValue(),'45');
    await wz.locator('#bigFlt [data-f="c0"]').fill('');await rows(1);await wz.locator('#c5Color canvas').waitFor()}
  // v14.1.5 흑백 GL 측정 = 따로 박스, [⭕ 측정 원 보기] 를 끄면 5-3 사진에서 측정 원만 빠짐(켜면 다시)
  for(const id of ['glShow','glR','glSet','glRun','glHist'])assert.equal(await wz.locator(`#glBox #${id}`).count(),1,id);
  await wz.locator('#c5Gray canvas').waitFor();
  const grayPx=()=>wzf.evaluate(()=>document.querySelector('#c5Gray canvas').toDataURL());
  const ringOn=await grayPx();await wz.locator('#glShow').uncheck();
  await wzf.waitForFunction(o=>{const c=document.querySelector('#c5Gray canvas');return c&&c.toDataURL()!==o},ringOn);
  await wz.locator('#glShow').check();await wzf.waitForFunction(o=>{const c=document.querySelector('#c5Gray canvas');return c&&c.toDataURL()===o},ringOn);
  const [pop]=await Promise.all([page.waitForEvent('popup'),wz.locator('#c5list .br').nth(0).dblclick()]);
  await pop.locator('#fx canvas').waitFor();
  // v14.1.5 새 창 [Defect 박스](v14.4.1 이름 — 종전 빨간 네모): 끄면 Gray Crop · Gray 프레임에서 Defect 박스만 빠지고(같은 캔버스 — 확대 그대로), B 키로 다시 켬
  assert.equal(await pop.locator('#pwBox').isChecked(),true);
  const popPx=()=>pop.evaluate(()=>[...document.querySelectorAll('#fx canvas,#ff canvas')].map(c=>c.toDataURL()));
  await pop.locator('#fx canvas').click();                                                           // 2배 확대
  const zoomed=await pop.evaluate(()=>document.querySelector('#fx canvas').style.width);assert(zoomed,'zoomed in');
  const boxOn=await popPx();await pop.locator('#pwBox').uncheck();
  const boxOff=await popPx();assert(boxOff[0]!==boxOn[0]&&boxOff[1]!==boxOn[1],'red box removed from both gray pictures');
  assert.equal(await pop.evaluate(()=>document.querySelector('#fx canvas').style.width),zoomed);      // 확대 그대로
  assert.match(await pop.locator('#ff figcaption .lg').innerText(),/Defect 박스 끔/);
  await pop.keyboard.press('b');await pop.waitForFunction(()=>document.getElementById('pwBox').checked);
  assert.deepEqual(await popPx(),boxOn);
  await pop.close();
  // v14.1.6 5-3: [리스트 | 격자 구조] · [사진 모두 불러오기] · 보기 박스 · [전체 선택/해제] · 개수 배지, [← 5-2] · 화면 테마 · 같은 창 보기 없음
  assert.deepEqual(await wz.locator('#b5p3 .viewtabs button').allInnerTexts(),['리스트','격자 구조']);
  assert.match(await wz.locator('#b5prep.c5load').innerText(),/사진 모두 불러오기/);
  assert.equal(await wz.locator('.c5stbox #c5stF [data-st5]').count(),4);
  assert.deepEqual([await wz.locator('#c5pickAll').innerText(),await wz.locator('#c5pickNone').innerText()],['전체 선택','전체 해제']);
  assert.equal(await wz.locator('#toB2b').count(),0);
  assert.equal(await wz.locator('#themeBtn').isVisible(),false);assert.equal(await wz.locator('#inWin').isVisible(),false);
  assert.equal(await wz.locator('#pHelp').isVisible(),true);
  assert.equal(await wz.locator('#c5pickN.on').innerText(),'☑ 1 / 1개');   // v14.1.8: 5-3 최종 목록도 처음 = 모두 ☑(소유자)
  assert.deepEqual([await q('c5Ls','c5list','c1.jpg'),await q('c5Ls','c5list','zzz')],[1,0]);await q('c5Ls','c5list','');
  // v14.1.7 측정 원 그리기 창: 보이는 부분 안에 다 들어오고(잘리지 않음), 사진 양옆 ‹ › · ← → 로 다른 예시 사진
  await wzf.evaluate(()=>{const c=window.__cw.C5;c.items.push(Object.assign({},c.items[0],{k:c.items.length}))});   // 예시 후보 2개
  await wz.locator('#glSet').click();await wz.locator('#glDlg:not([hidden])').waitFor();
  const dlgFit=await wzf.evaluate(()=>{const b=document.querySelector('#glDlg .bx').getBoundingClientRect(),o=document.querySelector('#glDlg').getBoundingClientRect();return b.top>=o.top-1&&b.bottom<=o.bottom+1});
  assert(dlgFit,'measure-circle dialog fits the visible part');
  assert.match(await wz.locator('#glDPos').innerText(),/예시 사진 1 \/ 2/);
  await wz.locator('#glNext').click();await wz.locator('#glDPos',{hasText:'예시 사진 2 / 2'}).waitFor();
  await wz.locator('#glCv').press('ArrowLeft');await wz.locator('#glDPos',{hasText:'예시 사진 1 / 2'}).waitFor();
  await wz.locator('#glDNo').click();await wzf.evaluate(()=>window.__cw.C5.items.pop());
  await wz.locator('#c5list').focus();await wz.locator('#c5list').press('Home');await wz.locator('#c5list').press(' ');
  await wz.locator('#c5pickN',{hasText:'☑ 0 / 1개'}).waitFor();await wz.locator('#c5list').press(' ');
  await wz.locator('#c5pickN.on',{hasText:'☑ 1 / 1개'}).waitFor();
  // #84 흑백 GL 측정 = 최종 목록(☑) 중 흑백 사진이 있는 Defect 만(5-3 목록 전체가 아님)
  const glT=await wzf.evaluate(async()=>{const cw=window.__cw,C=cw.C5,old=C.base;
    C.base=[{pick:true,st:'ok'},{pick:false,st:'ok'},{pick:true,st:'color'},{pick:true,st:'gray'},{pick:false,st:'gray'}];const n=cw.glTargets().length;
    C.base=[{pick:false,st:'ok'}];await cw.glRun();const msg=document.querySelector('#glSt').textContent;C.base=old;document.querySelector('#glSt').textContent='';return {n,msg}});
  assert.equal(glT.n,2,'GL targets = picked rows with a gray image');
  assert.match(glT.msg,/최종 목록\(☑\)에 흑백 사진이 있는 Defect 가 없습니다/);
  await wzf.evaluate(()=>{window.showSaveFilePicker=async o=>({name:o.suggestedName,createWritable:async()=>({write:async b=>{window.__flc=await b.text()},close:async()=>{}})})});
  await wz.locator('#c5saveCsv').click();await wzf.waitForFunction(()=>typeof window.__flc==='string');
  // #86 [🗂 최종 목록 사진 파일.zip 저장] = color · gray · gray crop 폴더(원본 바이트 그대로) + 엑셀 [원본 이미지로 저장] = Color 열 원본 · 흑백 원본 2열 추가
  await wzf.evaluate(()=>{window.showSaveFilePicker=async o=>({name:o.suggestedName,createWritable:async()=>({write:async b=>{window.__bin=Array.from(new Uint8Array(await b.arrayBuffer()))},close:async()=>{}})})});
  await wz.locator('#c5saveZip').click();await wzf.waitForFunction(()=>Array.isArray(window.__bin));
  const zipPath=join(fixture,'final_photos_test.zip');await writeFile(zipPath,Buffer.from(await wzf.evaluate(()=>window.__bin)));
  const zl=JSON.parse(execFileSync(python,['-c','import sys,json,zipfile;z=zipfile.ZipFile(sys.argv[1]);print(json.dumps(z.namelist()))',zipPath],{encoding:'utf-8'}));
  assert(zl.some(n=>n.startsWith('color/'))&&zl.some(n=>n.startsWith('gray/'))&&zl.some(n=>n.startsWith('gray crop/')),'zip has color, gray, gray crop folders: '+zl);
  assert(zl.some(n=>n.toLowerCase()==='color/c1.jpg'),'color file keeps the original name: '+zl);
  const zsame=execFileSync(python,['-c',`
import sys,os,zipfile
z=zipfile.ZipFile(sys.argv[1]);d=sys.argv[2];bad=[]
for n in z.namelist():
    if n.startswith('color/') or n.startswith('gray/'):
        src=[os.path.join(r,f) for r,_,fs in os.walk(d) for f in fs if f==n.split('/')[-1]]
        if not src or open(src[0],'rb').read()!=z.read(n): bad.append(n)
print('ok' if not bad else 'bad '+','.join(bad))`,zipPath,slotDir],{encoding:'utf-8'}).trim();
  assert.equal(zsame,'ok','zip color/gray = original file bytes');
  await wzf.evaluate(()=>{window.__bin=null;window.__cw.xlOrigSet(true)});await wz.locator('#c5save').click();await wzf.waitForFunction(()=>Array.isArray(window.__bin));
  const xlo=join(fixture,'final_orig_test.xlsx');await writeFile(xlo,Buffer.from(await wzf.evaluate(()=>window.__bin)));await wzf.evaluate(()=>window.__cw.xlOrigSet(false));
  const xs=execFileSync(python,['-c','import sys,zipfile;print(zipfile.ZipFile(sys.argv[1]).read("xl/worksheets/sheet1.xml").decode("utf-8"))',xlo],{encoding:'utf-8'});
  assert(xs.includes('Color 원본 (파일 그대로)')&&xs.includes('Gray Crop 원본')&&xs.includes('Gray 프레임 원본')&&xs.includes('Gray Crop (Defect 박스'),'excel original columns');
  await wzf.evaluate(()=>{window.showSaveFilePicker=async o=>({name:o.suggestedName,createWritable:async()=>({write:async b=>{window.__flc=await b.text()},close:async()=>{}})})});
  const finalCsv=join(fixture,'final_list_test.csv');await writeFile(finalCsv,'\ufeff'+await wzf.evaluate(()=>window.__flc),'utf-8');
  assert((await readFile(finalCsv,'utf-8')).includes(slotDir),'final list CSV carries the absolute matching folder');
  // 기존 Color·Gray 매칭이 최종 목록 CSV 를 인식 → 그 Defect 만 + 최종 목록 엑셀(사진 3장)
  await page.getByRole('tab',{name:'Color·Gray 매칭',exact:true}).click();
  await cg.getByRole('button',{name:'새 작업'}).click();
  await cg.getByLabel('Lot 또는 Wafer 폴더').fill('');
  // 사람처럼: 단추 → 파일 고르기 창(이 시험 Playwright 는 한글 파일 이름을 못 넣어 영문 이름). 앞에서 켠 Batch Report 자동 분석이 장비 접근 자리를
  // 쓰는 중이면 엔진이 '진행 중'으로 거절한다(Wafer 찾기와 같은 규칙) — 그때는 조금 뒤 다시.
  const wafersShown=()=>cg.locator('[role=group][aria-label="처리할 Wafer"]').getByText('1개 선택').waitFor({timeout:4000}).then(()=>true,()=>false);
  let csvOk=false;
  for(let k=0;k<10&&!csvOk;k++){const [fc]=await Promise.all([page.waitForEvent('filechooser'),cg.getByRole('button',{name:'📄 최종 목록 CSV 고르기…'}).click()]);await fc.setFiles(finalCsv);
    csvOk=await wafersShown();if(!csvOk)await page.waitForTimeout(3000);}
  assert(csvOk,'final list CSV recognised by Color·Gray 매칭');
  await cg.getByRole('button',{name:'다음 ▶',exact:true}).click();
  await cg.getByRole('button',{name:'다음 ▶',exact:true}).click();
  await cg.getByLabel('실행 전 검토').getByText('final_list_test.csv').waitFor();
  await cg.getByRole('button',{name:'▶ 처리 시작'}).click();
  await cg.getByText(/최종 목록 엑셀 — 1줄 중 사진 1줄/).waitFor({timeout:60000});
  const finalBook=await cg.locator('p',{hasText:'최종 목록 엑셀'}).locator('code').first().innerText().catch(()=>'');
  const xl=JSON.parse(execFileSync(python,['-c',`
import sys,glob,json,zipfile,openpyxl
p=sorted(glob.glob(sys.argv[1]+'/**/최종목록_*.xlsx',recursive=True))[-1]
ws=openpyxl.load_workbook(p).active;rows=[[c.value for c in r] for r in ws.iter_rows()]
z=zipfile.ZipFile(p);print(json.dumps({'n':len(rows),'head':rows[0][8:11],'state':rows[1][11],'calc':rows[1][27],'media':len([x for x in z.namelist() if x.startswith('xl/media/')])}))`,join(fixture,'local')],{encoding:'utf-8',env:{...process.env,PYTHONPATH:join(root,'vendor')}}));
  assert.deepEqual([xl.n,xl.state,xl.calc,xl.media],[2,'추출 완료','Para 프로그램',3],JSON.stringify(xl)+finalBook);
  assert.equal(xl.head[0],'Color');
  // Defect Map = Step 1 ~ 4(종전 체크로 켜던 다이어그램 분석), Step 1 도 엔진 목록(이름 · 크기)으로
  await page.getByRole('tab',{name:'Defect Map',exact:true}).click();
  const dg=page.locator('.dfx-host[data-title="Defect Map"]');
  await dg.locator('#step1.on').waitFor();
  await page.locator('.dfx-host.ready[data-title="Defect Map"]').waitFor();   // 겉모습(para-skin)을 넣은 뒤
  assert.equal(await dg.locator('.dfx-body.pskin.pskin-diagram').count(),1);
  assert.deepEqual(await dg.locator('nav button[data-step]').evaluateAll(b=>b.filter(x=>!x.hidden).map(x=>x.dataset.step)),['1','2','3','4']);
  await writeFile(join(fixture,'pick_folder.txt'),join(recipe,'SETUP1','LOT_A'));
  await dg.locator('#addBtn').click();
  const dgf=defectIn('Defect Map');
  await dgf.waitForFunction(()=>window.__cw.state.scans.length===1,null,{timeout:30000});
  assert.deepEqual(await dgf.evaluate(()=>window.__cw.state.scans.map(s=>[s.defects.length,s.colors.length,s.frames.length])),[[2,3,2]]);
  // v14.3.12: Wafer Map = 웨이퍼 맵 기준(샘플 올리기 · Notch 고르기 · 지름/Edge 입력 없음), 안내 = X 왼쪽부터 0 · Y 아래부터 0
  assert.deepEqual(await dgf.evaluate(()=>['mapBtn','notch','waferD','edgeEx'].map(i=>!!document.getElementById(i)).concat(/아래부터 0/.test(document.getElementById('mapHelp').textContent))),[false,false,false,false,true]);
  // v14.1.8 Step 3 목록 · 쌍별 상세 표: 검색 · ☑(☐ = 흐리게 · ↑↓ 건너뜀 · CSV 에서 뺌)
  await dg.locator('#to2').click();await dg.locator('#runBtn').click();await dgf.waitForFunction(()=>window.__cw.state.cmp,null,{timeout:30000});
  await dg.locator('nav button[data-step="3"]').click();await dg.locator('#setPick input').first().check();await dg.locator('#vennBtn').click();
  await dg.locator('#p3List .br').nth(1).waitFor();
  assert.equal(await dg.locator('#p3Ls .lsn').innerText(),'☑ 2 / 2개');
  await dg.locator('#p3List .br').first().locator('span.pk').click();
  assert.deepEqual([await dg.locator('#p3Ls .lsn').innerText(),await dg.locator('#p3Ls [data-ls="csv"]').innerText(),await dg.locator('#p3List .br.off').count()],['☑ 1 / 2개','CSV 저장 (☑ 1개)',1]);
  await dg.locator('#p3Ls input[type=search]').fill('c1.jpg');await dg.locator('#p3Ls input[type=search]').press('Enter');
  assert.equal(await dg.locator('#p3List .br').count(),1);
  await dg.locator('#p3Ls input[type=search]').fill('');await dg.locator('#p3Ls input[type=search]').press('Enter');
  // 2026-11-25(소유자 "기본 · 대규모 차이는 wafer map 유무만, 이미지 관련 필터와 리스트 모두 동일"): 목록 = 대규모와 같은 표 · 열, 필터 = 같은 줄(사진 · 분류 칩)
  await dg.locator('#p3List .br').nth(1).waitFor();
  assert.deepEqual((await dg.locator('#p3List .bh span').allInnerTexts()).slice(0,12),['☑','#','구분','사진','Lot','Slot','ID','장비 스캔 분류','리뷰 결과','Recipe','Contrast(실제)','Area (µm²)']);
  assert.deepEqual(await dg.locator('#p3Flt .fh').allInnerTexts(),['사진','장비 스캔 분류','리뷰 결과','값 범위','Recipe','Zone','정렬']);
  assert.match(await dg.locator('#p3Flt [data-pclsbox]').innerText(),/Accept/);   // Defect 코드 표 이름(0 = Accept)
  {const st=await dgf.evaluate(()=>window.__cw.PANELS.p3.items.map(it=>window.__cw.panelPh(it).st));
    await dg.locator('#p3Flt [data-pst="ok"]').uncheck();await dgf.waitForFunction(n=>document.querySelectorAll('#p3List .br').length===n,st.filter(x=>x!=='ok').length);
    await dg.locator('#p3Flt [data-pst="ok"]').check();await dgf.waitForFunction(()=>document.querySelectorAll('#p3List .br').length===2);
    await dg.locator('#p3List .bh span[data-sort="c"]').click();assert.equal(await dg.locator('#p3Flt [data-f="sort"]').inputValue(),'c-d');   // 열 제목 = 정렬 칸
    await dg.locator('#p3Flt [data-f="sort"]').selectOption('');await dgf.waitForFunction(()=>window.__cw.PANELS.p3.el('Flt').querySelector('[data-f="sort"]').value==='')}
  // v14.4.1 µm 환산 픽셀(Slot 기준) · [µm 로 보기](처음 = 켬, 한 곳을 바꾸면 모든 목록 · 필터 · 열 제목이 같이)
  assert.match(await dg.locator('#p3Pix').innerText(),/^µm 환산 픽셀 : [\d.]+$/);
  // 소유자 2026-11-24: 기본 모드 필터도 같은 양방향 막대(막대 끝 = 이 목록 자료의 최소 · 최대, End = 최대 값을 최소 칸에, Home = 비움)
  {const th=dg.locator('#p3Flt label.rng').first().locator('.prs-th').first(),c0=dg.locator('#p3Flt [data-f="c0"]');
    assert.equal(await dg.locator('#p3Flt label.rng .prs').count(),4);
    await th.focus();await th.press('End');assert.notEqual(await c0.inputValue(),'');await dgf.waitForFunction(()=>document.querySelectorAll('#p3List .br').length===1);
    await th.press('Home');assert.equal(await c0.inputValue(),'');await dgf.waitForFunction(()=>document.querySelectorAll('#p3List .br').length===2)}
  assert.deepEqual(await dg.locator('#p3Flt [data-umu]').allInnerTexts(),['µm²','µm']);
  await dg.locator('#p3Flt input[data-um]').uncheck();assert.deepEqual(await dg.locator('#p3Flt [data-umu]').allInnerTexts(),['','']);
  assert.deepEqual(await dgf.evaluate(()=>[...document.querySelectorAll('#detTbl th[data-umh]')].map(x=>x.textContent)),['Area','Width']);
  await dg.locator('#p3Flt input[data-um]').check();
  assert.deepEqual(await dgf.evaluate(()=>[...document.querySelectorAll('#detTbl th[data-umh]')].map(x=>x.textContent)),['Area (µm²)','Width (µm)']);
  assert.match(await dg.locator('#p3Rv').innerText(),/µm 환산 픽셀: /);
  // v14.4.1(#89): 기본 모드 새 창 = 대규모와 같은 창(한 창 · Color · Gray Crop · Gray 프레임 · 🔒 고정 · Defect 박스 B · ↑↓ = ☑ 줄만 · Space ☑), 측정 원 없음(소유자)
  const [bp]=await Promise.all([page.waitForEvent('popup'),dg.locator('#p3List .br').nth(0).dblclick()]);   // 첫 줄 = C1(Color · Gray 있음, ☐)
  await bp.locator('#ff canvas').waitFor();await bp.locator('#fx canvas').waitFor();await bp.locator('#fc canvas').waitFor();
  assert.deepEqual(await bp.evaluate(()=>['pwBox','pwLock'].map(i=>!!document.getElementById(i))),[true,true]);
  assert.match(await bp.locator('#hd').innerText(),/^1 \/ 2 · /);
  assert.doesNotMatch(await bp.locator('#ff figcaption .lg').innerText(),/측정 원/);
  await bp.locator('#pwBox').uncheck();assert.match(await bp.locator('#ff figcaption .lg').innerText(),/Defect 박스 끔/);
  await bp.keyboard.press('b');await bp.waitForFunction(()=>document.getElementById('pwBox').checked);
  // v14.4.1 크기 측정(소유자): [크기 측정 (M)] → 사진 원래 픽셀 + 직선 · 원 · 사각형(µm · µm²), 사진 픽셀 크기는 이 화면에만, 보기만(저장 없음), Esc = 끝
  await bp.locator('#pwMz').click();await bp.locator('#mz').waitFor();assert.equal(await bp.locator('.pv').isVisible(),false);
  await bp.locator('#mzSide',{hasText:'사진 픽셀 크기'}).waitFor();assert.match(await bp.locator('#mzSide').innerText(),/Gray 사진 · Recipe/);
  {const bb=await bp.locator('#mzCv canvas').boundingBox();await bp.mouse.move(bb.x+bb.width/2-60,bb.y+bb.height/2);await bp.mouse.down();
    await bp.mouse.move(bb.x+bb.width/2+60,bb.y+bb.height/2,{steps:5});await bp.mouse.up()}
  await bp.locator('#mzSide',{hasText:'(1개)'}).waitFor();assert.match(await bp.locator('#mzSide li').first().innerText(),/직선 · [\d.]+ px\s+[\d.]+ µm/);
  await bp.keyboard.press('2');assert.equal(await bp.locator('[data-mzt="circle"]').getAttribute('class'),'on');
  await bp.keyboard.press('Control+z');await bp.locator('#mzSide',{hasText:'(0개)'}).waitFor();
  await bp.keyboard.press('Escape');await bp.locator('.pv').waitFor();assert.equal(await bp.locator('#mz').isVisible(),false);
  await bp.keyboard.press(' ');await dg.locator('#p3Ls .lsn',{hasText:'☑ 2 / 2개'}).waitFor();            // Space = ☑/☐(목록과 같음)
  await bp.keyboard.press(' ');await dg.locator('#p3Ls .lsn',{hasText:'☑ 1 / 2개'}).waitFor();
  await bp.keyboard.press('ArrowDown');await bp.locator('#hd',{hasText:/^2 \/ 2 · /}).waitFor();          // 새 창 ↓ = 목록도 따라감
  assert.equal(await dgf.evaluate(()=>window.__cw.PANELS.p3.sel),1);
  await bp.locator('#fx .ms',{hasText:'Gray'}).waitFor();                                                // C2 = 어느 프레임에도 없음 · Color 사진도 없음(시험 자료) → 칸에 이유
  await bp.keyboard.press('ArrowUp');await bp.waitForTimeout(200);                                       // 첫 줄은 ☐ → 건너뜀(목록 ↑↓ 와 같음)
  assert.equal(await dgf.evaluate(()=>window.__cw.PANELS.p3.sel),1);
  const nPages=page.context().pages().length;await dg.locator('#p3List').press('Enter');await bp.waitForTimeout(300);
  assert.equal(page.context().pages().length,nPages);                             // Enter 를 다시 눌러도 같은 창
  await bp.close();
  await dg.locator('#step3 details.card summary').click();
  assert.equal(await dg.locator('#detLs .lsn').innerText(),'☑ 2 / 2개');
  await dg.locator('#detTbl tbody tr td.pk').first().click();assert.equal(await dg.locator('#csvBtn').innerText(),'CSV 내보내기 (☑ 1개)');
  await rm(join(fixture,'pick_folder.txt'));
  // KLA 자재 찾기(#30): 상단 회사 탭 CAMTEK / KLA. KLA 장비 폴더 등록 → Lot 키워드로 폴더 이름만 찾기.
  const klaRoot=join(fixture,'J','2.K2');
  for(const d of ['2025-05-21/RINT63@6324/2025-05-21-09-08_16','2025-05-21/RINT63@6324/2025-05-21-09-30_2','2025-05-22/ABC11@1111/2025-05-22-02-00_1'])
    await mkdir(join(klaRoot,...d.split('/')),{recursive:true});
  // #32: 맨 위 탭 = CAMTEK · KLA · TB500 Review 조회(v14.4.2) · 설정 · 메모. KLA 장비 폴더는 설정 › AOI 장비 호기 루트 › KLA 에서 등록.
  assert.deepEqual(await page.locator('.vendor-tabs button').allInnerTexts(),['CAMTEK','KLA','TB500 Review 조회','설정','메모']);
  await page.getByRole('button',{name:'KLA',exact:true}).click();
  assert.deepEqual(await page.locator('.navigation button').allInnerTexts(),['KLA 자재 찾기']);
  const kla=page.locator('section.kla');
  // v14.1.9: KLA 장비를 등록하지 않은 PC 는 처음부터 [KLA 캐시에서만 찾기](캐시가 아직 없어도 잠그지 않음) + [OneDrive 에서 최신 캐시 받기].
  await kla.getByText(/이 PC 에 KLA 캐시가 없습니다/).waitFor();
  assert.equal(await kla.getByRole('checkbox',{name:'KLA 캐시에서만 찾기'}).isChecked(),true);
  await kla.getByRole('button',{name:'OneDrive 에서 최신 캐시 받기',exact:true}).click();
  await page.locator('.toast').filter({hasText:'OneDrive 에 게시된 KLA 캐시가 아직 없습니다.'}).waitFor();
  await kla.getByRole('checkbox',{name:'KLA 캐시에서만 찾기'}).uncheck();
  await kla.getByText(/⚠ 등록된 KLA 장비 폴더가 없습니다/).waitFor();
  await kla.getByRole('button',{name:/설정 › AOI 장비 호기 루트 › KLA/}).click();
  assert.equal(await page.locator('.navigation').count(),0);                      // 설정 = 공통 탭(아래 기능 탭 줄 없음)
  const klaSet=page.locator('.kla-settings');
  await klaSet.getByLabel('KLA 메모 장비 IP 에서 호기 고르기').selectOption('AOI-07');
  assert.equal(await klaSet.getByLabel('장비 이름').inputValue(),'AOI-07');
  await klaSet.getByLabel('장비 이름').fill('2.K2');
  await klaSet.getByLabel('장비 폴더').fill(klaRoot);
  await klaSet.getByRole('button',{name:'추가',exact:true}).click();
  await klaSet.getByRole('cell',{name:klaRoot,exact:true}).waitFor();
  // Defect 이미지 백업본: 장비별 백업 폴더 등록(켜짐이 기본)
  const klaBackup=join(fixture,'K','KLA_backup','2.K2');
  await mkdir(join(klaBackup,'2025-04-01','RINT63@5555','2025-04-01-08-00_3'),{recursive:true});
  await klaSet.getByLabel('백업 폴더 장비').selectOption('2.K2');
  await klaSet.getByLabel('백업 폴더',{exact:true}).fill(klaBackup);
  await klaSet.getByRole('button',{name:'백업 폴더 등록',exact:true}).click();
  await klaSet.getByRole('cell',{name:klaBackup,exact:true}).waitFor();
  assert.equal(await klaSet.getByRole('switch',{name:'Defect 이미지 백업본 포함'}).isChecked(),true);
  await page.getByRole('button',{name:'KLA',exact:true}).click();
  // Para #43: 찾기 화면 = Batch Report 찾기 · 취합과 같은 모양(장비 상자 격자 · 모든 장비 · 캐시에서만 찾기 체크).
  await kla.getByRole('checkbox',{name:'2.K2 찾기'}).waitFor();
  assert.equal(await kla.getByRole('checkbox',{name:'찾기 모든 장비'}).isChecked(),true);
  // v14.4.2 TB500 Review 조회: 맨 위 탭(KLA 와 설정 사이). Conder Scan 폴더는 이름만 읽고(쓰기 없음), 호기 · 시각은 로컬 Batch Report · KLA 캐시에서.
  // 브라우저 허용 창 없음 — 폴더는 Windows 고르기 창(시험 = pick_folder.txt)이나 경로 입력으로 정한다.
  const conder=join(fixture,'conder','129. 4DT-TB500-H-M1'),t5lot=join(conder,'976. TB500.INT1041 (CMS)');
  for(const [d,f] of [['1. RDL4','TB500_a.jpg'],['1-1. RDL4_재리뷰','m1.txt'],['7. RDL1','TB500_RDL1 - Multi_x.jpg'],['★ 메모','x.txt']]){
    await mkdir(join(t5lot,d),{recursive:true});await writeFile(join(t5lot,d,f),'x');}
  const t5cache=join(fixture,'local','배치분석','누적');await mkdir(t5cache,{recursive:true});
  const t5file='TB500_RDL1-Multi_Setup1_CMS-RDL1_26-Oct-20_(09.10.00)_BatchReport.htm';
  const t5wafers=Array.from({length:25},(_,i)=>({'Lot':'CMS-RDL1','Wafer ID':'W'+String(i).padStart(2,'0'),'Pass/Fail':i<3?'Scan 2D Error. Aborted.':'Pass','Recipe(s)':'TB500_RDL1-Multi'}));
  await writeFile(join(t5cache,'AOI-21_tb500ui0.json'),JSON.stringify({schema:1,machine:'AOI-21',folder:join(fixture,'AOI-21','Reports'),
    entries:{[t5file]:{signature:[1,1],digest:'x'.repeat(64),report:{file_name:t5file,metadata:[['Batch Start','20-Oct-26 09:10:00 AM'],['Job/Setup','TB500_RDL1-Multi/Setup1']],wafers:t5wafers}}}}));
  await page.getByRole('button',{name:'TB500 Review 조회',exact:true}).click();
  assert.equal(await page.locator('.navigation').count(),0);                      // 회사 묶음 밖의 탭(아래 기능 탭 줄 없음)
  assert.equal(await page.locator('#main > h1').innerText(),'TB500 Review 조회');
  const t5=page.locator('section.tb5');
  await t5.getByText(/기본 경로입니다/).waitFor();
  assert.equal(await t5.getByLabel('Conder Scan 폴더').inputValue(),'\\\\k5cifsn2\\k5tsvdata$\\1. Conder Scan\\531. NVIDIA INT\\129. 4DT-TB500-H-M1');
  await t5.getByText(/OneDrive 에서 캐시를 아직 받지 않았습니다/).waitFor();
  await writeFile(join(fixture,'pick_folder.txt'),conder);
  await t5.getByRole('button',{name:'폴더 고르기',exact:true}).click();
  await page.locator('.toast').filter({hasText:'Conder Scan 폴더를 바꿨습니다'}).waitFor();
  assert.equal(await t5.getByLabel('Conder Scan 폴더').inputValue(),conder);
  await rm(join(fixture,'pick_folder.txt'));
  await t5.getByLabel('Lot 목록').fill('TB500.INT1041\nTB500.INT948\ntb500.int1041');
  await t5.getByRole('button',{name:'조회 (2)',exact:true}).click();               // 같은 Lot 은 한 번만(대소문자 무시)
  await page.locator('.toast').filter({hasText:'조회 완료: Lot 2개 · 재리뷰 필요 Layer 1개'}).waitFor();
  const t5rows=(await t5.locator('table.tb5-table tbody tr').allInnerTexts()).map(x=>x.replace(/\s+/g,' ').trim());
  assert.equal(t5rows.length,5,t5rows.join('\n'));
  assert.match(t5rows[0],/^TB500\.INT1041 976\. TB500\.INT1041 \(CMS\) S\/M CMS Lot History ★ 메모$/);   // ★ 폴더 = 이름만(경로 버튼도 없음), 맨 위(이름 순)
  assert.match(t5rows[1],/^1-1\. RDL4_재리뷰 재리뷰 RDL4 6305 AOI 6412 2D\/RE 재리뷰 결과 맵\(\.txt\) 1개 경로 복사/);
  assert.match(t5rows[2],/^1\. RDL4 RDL4 .* 재리뷰 완료 Camtek 캐시에 없음 경로 복사/);
  assert.match(t5rows[3],/^7\. RDL1 RDL1 6316 AOI7 6326 2D\/R7 재리뷰 필요 Camtek Pass하지 못한 wafer 존재 wafer 25 · 한 번에 Pass 22 · Pass 없음 3 AOI-21 · 2026-10-20 09:10:00 Error Pass 22 · Error 3 Lot History/);
  assert.match(t5rows[4],/^TB500\.INT948 Conder Scan 에서 Lot 폴더를 찾지 못했습니다$/);
  assert.equal(await t5.locator('tr.tb5-rowneed').count(),1);
  await t5.locator('tr',{hasText:'7. RDL1'}).getByRole('button',{name:'Lot History',exact:true}).click();
  const t5h=page.locator('dialog.tb5-win[open]');
  await t5h.getByRole('heading',{name:'TB500.INT1041 · Lot History'}).waitFor();
  assert.equal(await t5h.locator('.tb5-chip.on').innerText(),'RDL1 1');
  assert.equal(await t5h.locator('li.tb5-hrow').count(),1);
  assert.match(await t5h.locator('.tb5-kpi').innerText(),/1\s*스캔\s*1\s*호기 · AOI-21\s*0\s*호기 이동/);
  await t5h.locator('details.tb5-vgrp > summary').click();
  const t5v=await t5h.locator('table.tb5-vtab tbody tr').allInnerTexts();
  assert.equal(t5v.length,25);
  assert.deepEqual(t5v[0].split('\t').map(x=>x.trim()),['25','W00','Scan 2D Error. Aborted.','Pass 없음']);
  await t5h.getByRole('button',{name:t5file,exact:true}).click();                // Batch Report 보기(캐시의 원문 표)
  const t5r=page.locator('dialog.tb5-win[open]').last();
  await t5r.getByRole('heading',{name:t5file}).waitFor();
  assert.equal(await t5r.locator('.tb5-wafers tbody tr').count(),25);
  assert.equal(await t5r.locator('.tb5-wafers td.ve').count(),3);
  await t5r.getByRole('button',{name:'닫기',exact:true}).click();
  await t5h.getByRole('button',{name:'닫기',exact:true}).click();
  assert.equal(await page.locator('dialog.tb5-win[open]').count(),0);
  // OneDrive 에서 최신 캐시 받기 = Batch Report · KLA [OneDrive 에서 불러오기]를 한 번에(위에서 Camtek 만 게시함)
  await t5.getByRole('button',{name:'OneDrive 에서 최신 캐시 받기',exact:true}).click();
  const t5toast=page.locator('.toast').filter({hasText:'KLA: OneDrive 에 게시된 캐시가 없습니다'});
  await t5toast.waitFor();
  assert.match(await t5toast.innerText(),/Camtek: BatchReport_캐시_\d{8}_\d{6}\.zip 받음/);
  await t5.getByText(/OneDrive 에서 캐시를 아직 받지 않았습니다/).waitFor();       // 하나라도 못 받으면 받은 시각을 적지 않는다
  await page.getByRole('button',{name:'KLA',exact:true}).click();                   // 아래 KLA 자재 찾기 단계로 돌아감(TB500 결과는 탭을 옮겨도 남음)
  assert.equal(await kla.getByRole('checkbox',{name:'KLA 캐시에서만 찾기'}).isChecked(),false);   // 장비 폴더를 등록했으므로 장비에서 찾기
  await kla.getByLabel(/Lot 키워드/).fill('rint63');
  await kla.getByRole('button',{name:'검색 →',exact:true}).click();
  await kla.getByText(/Lot 폴더 2개\(Lot 2개\)/).waitFor();
  const klaRow=kla.locator('tr.kla-row');
  assert.equal(await klaRow.count(),2);
  assert.match(await klaRow.nth(1).innerText(),/2\.K2\t2025-04-01\tRINT63@5555\s*백업본\t▸ 3/);
  // 백업본 끄기 → 원본만
  await kla.getByRole('switch',{name:'Defect 이미지 백업본 포함'}).click();        // 엔진 저장 뒤에 바뀜
  await kla.getByText('KLA 찾기 범위 · 원본만').waitFor();
  await kla.getByRole('button',{name:'검색 →',exact:true}).click();
  await kla.getByText(/Lot 폴더 1개\(Lot 1개\)/).waitFor();
  assert.equal(await klaRow.count(),1);
  assert.match(await klaRow.innerText(),/2\.K2\t2025-05-21\tRINT63@6324\t▸ 16, 2/);
  await klaRow.click();
  assert.equal(await kla.locator('tr.kla-slot').count(),2);
  assert.match(await kla.locator('tr.kla-slot').first().innerText(),/2025-05-21 09:08\t슬롯 16/);
  // Para #40: KLA 캐시 — 개발자 기능 › 캐시 갱신 → OneDrive 게시 → 불러오기 → 찾을 곳 'KLA 캐시'로 찾기.
  // Para #41: KLA 캐시 상자는 접었다 폈다 한다(처음엔 접힘 — 버튼이 안 보임).
  const klaCache=kla.locator('details.kla-cache');
  assert.equal(await klaCache.evaluate(d=>d.open),false);
  assert.equal(await kla.getByRole('button',{name:'🛠 개발자 기능',exact:true}).isVisible(),false);
  await klaCache.locator('summary').click();
  assert.equal(await klaCache.evaluate(d=>d.open),true);
  await kla.getByRole('button',{name:'🛠 개발자 기능',exact:true}).click();
  await kla.getByRole('button',{name:'캐시 갱신 (장비 폴더 이름 읽기)',exact:true}).click();
  await kla.getByText(/갱신함: 장비 1대 · Lot 폴더 2개/).waitFor();
  await kla.getByRole('button',{name:'OneDrive 에 게시',exact:true}).click();
  await kla.getByText(/게시함: .*KLA_캐시_\d{8}_\d{6}\.zip/).waitFor();
  await kla.getByRole('button',{name:'OneDrive 에서 불러오기',exact:true}).click();
  await kla.getByRole('button',{name:'고른 캐시 받아서 불러오기',exact:true}).click();
  await page.getByText(/\[KLA 캐시에서만 찾기\]를 켰습니다/).waitFor();
  assert.equal(await kla.getByRole('checkbox',{name:'KLA 캐시에서만 찾기'}).isChecked(),true);    // 불러오면 켜짐
  await kla.getByRole('button',{name:'검색 →',exact:true}).click();
  await kla.getByText(/KLA 캐시에서 찾음/).waitFor();
  assert.equal(await klaRow.count(),1);
  assert.match(await klaRow.innerText(),/2\.K2\t2025-05-21\tRINT63@6324\t▸ 16, 2/);
  await kla.getByRole('checkbox',{name:'KLA 캐시에서만 찾기'}).uncheck();
  // Para #43: 자동 분석 › [KLA] 탭 — 자동 분석(▶ 즉시 실행)에 KLA 캐시 갱신을 넣는다.
  await page.getByRole('button',{name:'CAMTEK',exact:true}).click();
  await feature('자동 분석 및 취합');
  await page.getByRole('tab',{name:'Batch Report 자동 분석'}).click();
  await page.getByRole('tab',{name:/^KLA · KLA 캐시/}).click();
  await page.getByLabel('자동 분석에 KLA 캐시 갱신 넣기').click();
  await page.getByText('자동 분석에 KLA 캐시 갱신을 넣었습니다').waitFor();
  await page.getByRole('button',{name:'▶ 즉시 실행',exact:true}).click();
  await page.getByText(/KLA 캐시 자동 갱신: 장비 1대/).waitFor({timeout:120000});
  await feature('자동 분석 및 취합');
  await page.getByRole('tab',{name:/^KLA · KLA 캐시/}).click();
  await page.getByLabel('자동 분석에 KLA 캐시 갱신 넣기').click();
  await page.getByText('자동 분석에서 KLA 캐시 갱신을 뺐습니다').waitFor();
  await page.getByRole('tab',{name:/^CAMTEK · Batch Report/}).click();
  await page.getByRole('button',{name:'CAMTEK',exact:true}).click();
  assert.equal(await page.locator('.navigation button').first().innerText(),'Recipe 관리');
  // 기능 둘러보기: 주요 탭을 차례로 옮겨 다니며 끝까지(오류 없이) — 마지막은 설정 탭.
  await page.getByRole('button',{name:'설정',exact:true}).click();
  await page.getByRole('button',{name:'기능 둘러보기',exact:true}).click();
  const fb=page.locator('.tour-bubble');
  const total=Number((await fb.locator('.tour-count').innerText()).split('/')[1]);
  for(let k=1;k<total;k++){await fb.getByRole('button',{name:'다음 →'}).click();await fb.locator('.tour-count').filter({hasText:new RegExp('^'+(k+1)+' /')}).waitFor();}
  await fb.getByRole('heading',{name:'끝!'}).waitFor();
  await fb.getByRole('button',{name:'완료',exact:true}).click();await fb.waitFor({state:'detached'});
  assert.equal(await page.locator('.vendor-tabs button[aria-current="page"]').innerText(),'설정');
  // A7: a reloaded page re-attaches to the same engine (ids keep increasing, no 'already connected').
  await page.reload();
  await page.getByText('로컬 엔진 연결됨',{exact:true}).waitFor();
  // v14.1.1: 시작하면 업데이트 확인이 먼저 — 새 버전 알림이 곧바로 뜬다(소스 폴더라 [나중에]).
  await page.locator('dialog.update-banner').getByText('새 버전 14.9.0이 있습니다').waitFor();
  await page.locator('dialog.update-banner').getByRole('button',{name:'나중에'}).click();
  await recipeTab('레시피 날짜별 비교하기');
  await page.locator('.cm-file input').first().waitFor();
  // v14.4: 프로그램 이름 = AOI Manager(전체판) — 머리 막대 · 창 제목 · 바닥글.
  assert.equal(await page.title(),'AOI Manager');
  assert.equal(await page.locator('.topbar .brand-name b').innerText(),'AOI Manager');
  assert.equal(await page.locator('.edition-pill').count(),0);
  assert.deepEqual(await page.locator('.vendor-tabs button').allInnerTexts(),['CAMTEK','KLA','TB500 Review 조회','설정','메모']);
  // v14.4 AOI Manager Mini: 같은 엔진 · 같은 화면 파일, 주소의 e=mini(AOI_Manager_Mini.bat = 시작 파일 + --mini)만 다르다.
  // 보이는 기능 = Batch Report 찾기 · 취합 · Defect 분석 · Wafer Map 수정하기 · KLA 자재 찾기 · TB500 Review 조회(v14.4.2) · 설정(소유자 2026-11-23).
  const mini=await browser.newPage({viewport:{width:1440,height:1000}});
  const miniErrors=[];mini.on('pageerror',e=>miniErrors.push(e.message));
  await mini.route('**/*',async route=>{assert.equal(new URL(route.request().url()).origin,appOrigin,'External request must never occur');await route.continue();});
  await mini.goto(appUrl+'&e=mini');
  assert.equal(new URL(mini.url()).search,'','token · edition must be removed from the address');
  await mini.getByText('로컬 엔진 연결됨',{exact:true}).waitFor();
  await mini.locator('dialog.update-banner').getByText('새 버전 14.9.0이 있습니다').waitFor();
  await mini.locator('dialog.update-banner').getByRole('button',{name:'나중에'}).click();
  assert.equal(await mini.title(),'AOI Manager Mini');
  assert.equal(await mini.locator('.app').getAttribute('data-edition'),'mini');
  assert.equal(await mini.locator('.edition-pill').innerText(),'Mini');
  assert.match(await mini.locator('footer').innerText(),/^AOI Manager Mini/);
  assert.deepEqual(await mini.locator('.vendor-tabs button').allInnerTexts(),['CAMTEK','KLA','TB500 Review 조회','설정']);   // v14.4.2: Mini 에도
  await mini.getByRole('button',{name:'CAMTEK',exact:true}).click();
  assert.deepEqual(await mini.locator('.navigation button').allInnerTexts(),['Batch Report 찾기 · 취합','Defect 분석','Wafer Map 수정하기']);
  assert.equal(await mini.locator('#main > h1').innerText(),'Batch Report 찾기 · 취합');
  // Batch Report = 찾기 · 취합만: 가동률 조사 및 분석 탭 · 조사 범위 · 즉시 실행이 없다.
  await mini.getByLabel('캐시에서만 찾기').waitFor();
  assert.equal(await mini.getByRole('tab',{name:/가동률 조사 및 분석/}).count(),0);
  assert.equal(await mini.locator('[aria-label="조사 범위"]').count(),0);
  assert.equal(await mini.getByRole('button',{name:'▶ 즉시 실행'}).count(),0);
  await mini.locator('.navigation').getByRole('button',{name:'Defect 분석',exact:true}).click();
  await mini.getByRole('tab',{name:/Color·Gray 매칭/}).waitFor();
  await mini.locator('.navigation').getByRole('button',{name:'Wafer Map 수정하기',exact:true}).click();
  assert.equal(await mini.locator('#main > h1').innerText(),'Wafer Map 수정하기');
  await mini.getByRole('button',{name:'KLA',exact:true}).click();
  assert.deepEqual(await mini.locator('.navigation button').allInnerTexts(),['KLA 자재 찾기']);
  // 다른 화면이 Mini 에 없는 탭으로 가라고 해도 그대로 있다.
  await mini.evaluate(()=>window.dispatchEvent(new CustomEvent('para:navigate',{detail:'Recipe 관리'})));
  assert.equal(await mini.locator('#main > h1').innerText(),'KLA 자재 찾기');
  await mini.getByRole('button',{name:'TB500 Review 조회',exact:true}).click();       // v14.4.2: Mini 에도 같은 화면
  await mini.locator('section.tb5').getByLabel('Lot 목록').waitFor();
  // 설정: 자동 분석 줄 · Job 폴더 열이 없다(Mini 에 없는 기능).
  await mini.getByRole('button',{name:'설정',exact:true}).click();
  await mini.locator('.current-settings summary').click();
  assert.equal(await mini.locator('.current-settings th',{hasText:'Batch Report 자동 분석'}).count(),0);
  await mini.getByRole('tab',{name:'AOI 장비 호기 루트',exact:true}).click();
  await mini.locator('[data-tour="settings:aoi-table"]').waitFor();
  assert.equal(await mini.locator('[data-tour="settings:aoi-table"] th',{hasText:'Job 폴더'}).count(),0);
  // v14.4.3(#90): Mini 도 정보 탭에 업데이트 구역 · GitHub 글자가 없다(시작 알림 창만).
  await mini.getByRole('tab',{name:'정보'}).click();
  await mini.getByLabel('오류 로그 폴더').waitFor();
  assert.equal(await mini.getByRole('button',{name:'업데이트 확인',exact:true}).count(),0);
  assert.equal(await mini.getByText(/GitHub|OneDrive 에 새 버전 게시|게시 폴더 열기|오류 로그 폴더의 파일을 담당자/).count(),0);
  assert.equal(await mini.locator('body').evaluate(b=>/github/i.test(b.innerText)),false);
  // 기능 둘러보기 = Mini 탭만, 끝까지 오류 없이.
  await mini.getByRole('button',{name:'기능 둘러보기',exact:true}).click();
  const mb=mini.locator('.tour-bubble');
  const mtotal=Number((await mb.locator('.tour-count').innerText()).split('/')[1]);
  const seen=[];
  for(let k=1;k<=mtotal;k++){seen.push(await mb.locator('h3').innerText());if(k<mtotal){await mb.getByRole('button',{name:'다음 →'}).click();await mb.locator('.tour-count').filter({hasText:new RegExp('^'+(k+1)+' /')}).waitFor();}}
  assert(!seen.some(t=>/Recipe 관리|Commonality|자동 분석 및 취합|메모|\[조사 시작\]/.test(t)),'Mini tour shows a full-only step: '+seen.join(' | '));
  assert(seen.includes('Batch Report 찾기 · 취합'));
  await mb.getByRole('button',{name:'완료',exact:true}).click();
  assert.deepEqual(miniErrors,[]);
  await mini.close();
  assert.deepEqual(errors,[]);
  assert.equal(stderr,'');
  console.log(JSON.stringify({passed:true,viewports:4,pythonReports:205,lots:69,scriptEscaped:true,localServer:'127.0.0.1'}));
}finally{
  lines.close();engine.kill();
  await new Promise(resolve=>engine.exitCode!==null||engine.signalCode!==null?resolve():engine.once('exit',resolve));
  await delivery.catch(()=>{});await browser.close();await rm(fixture,{recursive:true,force:true});
}
