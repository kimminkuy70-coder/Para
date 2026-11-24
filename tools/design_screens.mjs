// 디자인 개편 전 · 후 비교용 스크린샷(DESIGN.md 1절 7번). 시험 환경(tests/desktop_browser_fixture.py)의 가짜 자료로
// 진짜 로컬 서버를 띄우고 맨 위 탭 · 기능 탭 · 하위 탭 · Mini 창을 차례로 찍는다. 화면을 바꾸지 않고 누르기만 한다.
//   PARA_TEST_NODE_MODULES=/opt/node-tools/node_modules CODEX_PRIMARY_RUNTIME_PYTHON=python3 node tools/design_screens.mjs <출력 폴더>
// 결과 = <출력 폴더>/NN_이름.jpg + shots.json([{file, title}]). 맑은 고딕이 없는 PC 에서는 대체 서체로 보인다.
import {createRequire} from 'node:module';
import {mkdtemp, mkdir, writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {spawn, execFileSync} from 'node:child_process';
import {createInterface} from 'node:readline';

const require=createRequire(import.meta.url);
const {chromium}=require(require.resolve('playwright',{paths:[process.env.PARA_TEST_NODE_MODULES||process.cwd()]}));
const root=resolve(new URL('..',import.meta.url).pathname);
const out=resolve(process.argv[2]||join(root,'design_screens'));
await mkdir(out,{recursive:true});
const fixture=await mkdtemp(join(tmpdir(),'para-shots-'));
const python=process.env.CODEX_PRIMARY_RUNTIME_PYTHON||'python';
execFileSync(python,[join(root,'tests/desktop_browser_fixture.py'),'init',fixture]);
const engine=spawn(python,[join(root,'tests/desktop_browser_fixture.py'),'web',fixture],{cwd:root,stdio:['pipe','pipe','pipe']});
let appUrl;const ready=new Promise(res=>createInterface({input:engine.stdout}).on('line',l=>{try{const m=JSON.parse(l);if(m.url){appUrl=m.url;res()}}catch{}}));
const browser=await chromium.launch({headless:true});
const shots=[];let n=0;
const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function shot(page,title,{full=true,maxH=2600}={}){
  await wait(450);
  const file=`${String(++n).padStart(2,'0')}_${title.replace(/[^\w가-힣]+/g,'_').replace(/^_|_$/g,'')}.jpg`;
  const h=await page.evaluate(()=>document.documentElement.scrollHeight);
  await page.screenshot({path:join(out,file),type:'jpeg',quality:72,fullPage:full&&h<=maxH,...(full&&h>maxH?{clip:{x:0,y:0,width:page.viewportSize().width,height:maxH},fullPage:true}:{})});
  shots.push({file,title});process.stdout.write(`${file}\n`);
}
async function open(url,mini){
  const page=await browser.newPage({viewport:{width:1440,height:960}});
  await page.goto(url);
  await page.getByText('로컬 엔진 연결됨',{exact:true}).waitFor({timeout:30000});
  const banner=page.locator('dialog.update-banner');
  try{await banner.getByRole('button',{name:'나중에'}).click({timeout:8000});await banner.waitFor({state:'detached'})}catch{}
  return page;
}
const tabsIn=async(page,scope)=>(await page.locator(scope).getByRole('tab').allInnerTexts()).map(t=>t.trim()).filter(Boolean);
async function clickTop(page,name){await page.locator('.vendor-tabs').getByRole('button',{name,exact:true}).click()}
async function clickFeature(page,name){await page.locator('.navigation').getByRole('button',{name,exact:true}).click()}
async function eachTab(page,scope,prefix,skip=[]){
  await page.locator(scope).getByRole('tab').first().waitFor({timeout:8000}).catch(()=>{});
  const names=await tabsIn(page,scope);
  for(const t of names){if(skip.includes(t))continue;await page.locator(scope).getByRole('tab',{name:t,exact:true}).first().click();await shot(page,`${prefix} - ${t}`)}
}
try{
  await Promise.race([ready,wait(30000).then(()=>{throw new Error('server did not start')})]);
  const page=await open(appUrl);
  // CAMTEK
  await clickTop(page,'CAMTEK');
  await clickFeature(page,'Recipe 관리');await eachTab(page,'main','Recipe 관리');
  await clickFeature(page,'자동 분석 및 취합');await eachTab(page,'main','자동 분석 및 취합');
  await clickFeature(page,'Commonality 조사');await shot(page,'Commonality 조사');
  await clickFeature(page,'Batch Report 분석');await shot(page,'Batch Report 분석 - 조사 범위');
  try{
    await page.getByRole('button',{name:'조사 시작 →'}).click();
    await page.locator('.toast').filter({hasText:'조사를 완료했습니다.'}).waitFor({timeout:90000});
    for(const t of ['Lot 추적','가동률','WPH · 생산능력']){await page.getByRole('tab',{name:t,exact:true}).click();await shot(page,`Batch Report 분석 - ${t}`)}
    await page.getByRole('tab',{name:'Lot 추적',exact:true}).click();
    const lot=page.locator('.bv tbody tr.clickable').first();
    if(await lot.count()){await lot.click();await page.locator('dialog.lotwin[open]').waitFor({timeout:5000}).catch(()=>{});
      if(await page.locator('dialog.lotwin[open]').count()){await shot(page,'Batch Report 분석 - Lot 창',{full:false});await page.keyboard.press('Escape')}}
  }catch(e){process.stdout.write('batch: '+e.message+'\n')}
  await page.getByRole('tab',{name:/Batch Report 찾기/}).click();await shot(page,'Batch Report 찾기 · 취합');
  await clickFeature(page,'Defect 분석');
  await page.getByRole('tab',{name:'Color·Gray 매칭',exact:true}).click();await shot(page,'Defect 분석 - Color·Gray 매칭');
  await page.getByRole('tab',{name:'Defect 분석(대규모)',exact:true}).click();
  await page.locator('iframe.defect-frame.ready[title="Defect 분석(대규모)"]').waitFor({timeout:30000});
  await shot(page,'Defect 분석(대규모) - 5-1 빈 화면');
  try{
    const wz=page.frameLocator('iframe.defect-frame[title="Defect 분석(대규모)"]');
    await writeFile(join(fixture,'pick_folder.txt'),join(fixture,'defect','RCP'));
    await wz.locator('#bigAdd').click();await wz.locator('#bigMsg',{hasText:/Slot 1개/}).waitFor({timeout:30000});
    await shot(page,'Defect 분석(대규모) - 5-1 목록');
    const wzf=page.frames().find(f=>/\/defect\/.*mode=big/.test(f.url()));
    await wz.locator('#toB2').click();await wz.locator('#b5p2:not([hidden])').waitFor();
    await wz.locator('#b5pairSt .msg').first().waitFor({timeout:30000});await shot(page,'Defect 분석(대규모) - 5-2 결과 목록');
    await wz.locator('#toB3').click();await wz.locator('#b5p3:not([hidden])').waitFor();await shot(page,'Defect 분석(대규모) - 5-3 사진 정밀 조사');
    void wzf;
  }catch(e){process.stdout.write('defect big: '+e.message+'\n')}
  await page.getByRole('tab',{name:'Defect 분석(기본)',exact:true}).click();
  await page.locator('iframe.defect-frame.ready[title="Defect 분석(기본)"]').waitFor({timeout:30000}).catch(()=>{});
  await shot(page,'Defect 분석(기본) - Step 1');
  await clickFeature(page,'Wafer Map 수정하기');await shot(page,'Wafer Map 수정하기');
  // KLA · TB500 · 설정 · 메모
  await clickTop(page,'KLA');await shot(page,'KLA 자재 찾기');
  await clickTop(page,'TB500 Review 조회');await shot(page,'TB500 Review 조회');
  await clickTop(page,'설정');await eachTab(page,'main','설정');
  await clickTop(page,'메모');await eachTab(page,'main','메모');
  // 좁은 창
  await page.setViewportSize({width:760,height:900});await clickTop(page,'CAMTEK');await clickFeature(page,'Batch Report 분석');await shot(page,'좁은 창 760 - Batch Report 분석');
  await page.close();
  // Mini
  const mini=await open(appUrl+'&e=mini');
  await clickTop(mini,'CAMTEK');await shot(mini,'Mini - Batch Report 찾기 · 취합');
  await clickTop(mini,'설정');await shot(mini,'Mini - 설정');
  await writeFile(join(out,'shots.json'),JSON.stringify(shots,null,1));
}finally{await browser.close();engine.kill()}
