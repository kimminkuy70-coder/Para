import {useEffect, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {desktop, errorText, setBackground, mergeNotice, type WatchNotice, type Configuration} from './desktop';
import './styles.css';
import {startMotion} from './motion';
import {Settings} from './Settings';
import {Memo} from './Memo';
import {Commonality} from './Commonality';
import {Toaster,notify} from './ui';
import {UpdateBanner} from './AppUpdate';
import {Watch} from './Watch';
import {RecipeHub} from './RecipeHub';
import {ActivityPanel} from './Activity';
import {DefectAnalysis} from './DefectAnalysis';
import {WaferMap} from './WaferMap';
import {Batch} from './Batch';
import {useDev} from './devmode';
import {Kla} from './Kla';
import {Tb500} from './Tb500';
import {APP_NAME,isMini,hasTab,tabLabel} from './edition';

// 탭 머리 제목 · 설명(eyebrow · h1 · 설명 글)은 없앰(소유자 2026-11-25 '가독성') — 화면 읽기 프로그램용 h1 만 남김(sr-only).
document.title=APP_NAME;
// Batch Report 분석 stays mounted too: its results, Lot window and unsaved developer choices
// survive a visit to 설정 (where the developer toggle lives).
import {TourLayer} from './Tour';
const KEEP = ['Recipe 관리','Commonality 조사','자동 분석 및 취합','Batch Report 분석','Defect 분석','Wafer Map 수정하기','KLA 자재 찾기','TB500 Review 조회'];
// 맨 위 탭(#32): CAMTEK · KLA · TB500 Review 조회 · 설정 · 메모. CAMTEK / KLA = 장비 회사별 기능 묶음(#30, 아래 기능 탭 줄),
// TB500 Review 조회(v14.4.2 — Camtek · KLA 둘 다 보는 리뷰용 조회) · 설정 · 메모 = 회사 묶음 밖의 탭(아래 기능 탭 줄 없음).
// AOI Manager Mini(v14.4)는 edition.ts MINI_TABS 에 있는 탭만 보인다(없는 탭 = 줄에서 빠짐, 탭이 하나도 없는 회사 · 공통 탭도 빠짐).
const ALL_VENDORS = {CAMTEK:['Recipe 관리','자동 분석 및 취합','Commonality 조사','Batch Report 분석','Defect 분석','Wafer Map 수정하기'],
  KLA:['KLA 자재 찾기']} as const;
type Vendor = keyof typeof ALL_VENDORS;
const VENDORS:Record<Vendor,readonly string[]> = {CAMTEK:ALL_VENDORS.CAMTEK.filter(hasTab),KLA:ALL_VENDORS.KLA.filter(hasTab)};
const COMMON = ['TB500 Review 조회','설정','메모'] as const;
type Top = Vendor | typeof COMMON[number];
const TOPS:Top[] = [...(['CAMTEK','KLA'] as Vendor[]).filter(v=>VENDORS[v].length>0),...COMMON.filter(hasTab)];
const topOf = (tab:string):Top => (COMMON as readonly string[]).includes(tab)?tab as Top
  :(VENDORS.KLA as readonly string[]).includes(tab)?'KLA':'CAMTEK';

function App(){
  const [tab,setTab]=useState('설정');
  const top=topOf(tab);
  // 회사 탭을 오가도 각 회사에서 마지막에 보던 탭으로 돌아간다.
  const lastTab=useRef<Record<Vendor,string>>({CAMTEK:VENDORS.CAMTEK[0]||'설정',KLA:VENDORS.KLA[0]||'설정'});
  useEffect(()=>{if(top==='CAMTEK'||top==='KLA')lastTab.current[top]=tab;},[tab,top]);
  const navigation:readonly string[]=top==='CAMTEK'||top==='KLA'?VENDORS[top]:[];
  const [config,setConfig]=useState<Configuration>();
  const [connection,setConnection]=useState('기존 설정 연결 중');
  // While a Batch Report investigation runs the developer toggle is locked; the update waits too.
  const batchRunning=useDev().locked;
  const [engineDown,setEngineDown]=useState(false);
  useEffect(()=>desktop.onStatus((connected,code)=>{
    setEngineDown(!connected);
    if(!connected)notify(errorText(code),'error');
  }),[]);
  async function loadConfig(){
    try{
      await desktop.connect();
      const data=(await desktop.request('configuration').promise) as Configuration;
      if(!Array.isArray(data.machines))throw new Error('configuration_failed');
      setConfig(data);setConnection('로컬 엔진 연결됨');
      if(data.auto?.enabled&&!isMini)mountBatch();
    }catch(e){setConnection('연결 확인 필요');notify(errorText(e),'error');}
  }
  useEffect(()=>{void loadConfig();},[]);
  async function reconnect(){
    // A new engine starts clean (its results are gone), so the kept screens are drawn again.
    await loadConfig();
    if(!desktop.closed){setEngineDown(false);setScreenKey(k=>k+1);void syncWatch();notify('분석 엔진에 다시 연결했습니다.','ok');}
  }
  const [screenKey,setScreenKey]=useState(0);
  // Other screens can ask to open a tab (e.g. Commonality → 설정 › AOI 장비 호기 루트).
  // Mini 에 없는 탭으로 가라는 요청(예: 다른 화면의 바로 가기)은 무시한다.
  useEffect(()=>{const go=(e:Event)=>{const t=(e as CustomEvent<string>).detail;if(hasTab(t))setTab(t);};window.addEventListener('para:navigate',go);return()=>window.removeEventListener('para:navigate',go);},[]);
  // Workflow screens stay mounted after the first visit, so leaving a tab never
  // loses an in-progress step (Commonality 조사, Recipe 관리의 업데이트·양식 …). Screens
  // that hold a shared-document edit lock (문서, Recipe 관리) still unmount so the lock
  // is handed back when you leave them.
  const [visited,setVisited]=useState<string[]>([]);
  useEffect(()=>{if(KEEP.includes(tab))setVisited(v=>v.includes(tab)?v:[...v,tab]);},[tab]);
  // Batch Report 자동 분석(CAMTEK · KLA)의 1분 타이머는 Batch Report 화면 안에 있다. 종전에는 그 탭을 한 번 열어야만
  // 화면이 만들어져, 앱을 켜 두기만 하면 예약 시각이 지나도 돌지 않았다(Para #54). 자동 분석이 켜져 있으면 숨긴 채로 미리 만든다.
  const batchMounted=useRef(false);
  function mountBatch(){batchMounted.current=true;setVisited(v=>v.includes('Batch Report 분석')?v:[...v,'Batch Report 분석']);}
  useEffect(()=>{
    const check=async()=>{
      if(batchMounted.current||desktop.closed||isMini)return;   // Mini: Batch Report 자동 분석 없음
      try{const d=(await desktop.request('configuration').promise) as Configuration;if(d.auto?.enabled)mountBatch();}
      catch{/* 엔진이 다른 작업 중: 다음 분에 다시 */}
    };
    const timer=window.setInterval(()=>void check(),60000);
    const on=()=>{void check();void syncWatch();};
    window.addEventListener('para:batch-auto-changed',on);
    return()=>{window.clearInterval(timer);window.removeEventListener('para:batch-auto-changed',on);};
  },[]);
  useEffect(()=>{if(visited.includes('Batch Report 분석'))batchMounted.current=true;},[visited]);
  useEffect(()=>{window.dispatchEvent(new CustomEvent('para:tab',{detail:tab}));},[tab]);
  // Automatic watches run in the engine; the app shows their notices and keeps
  // itself resident in the tray (hide on close) while any watch is on.
  const [notices,setNotices]=useState<WatchNotice[]>([]);
  const lastNotice=useRef('');
  async function syncWatch(){
    try{
      await desktop.connect();
      const w=(await desktop.request('watch_status').promise).watch as {param:boolean;commonality:boolean;batch?:boolean;notices:WatchNotice[]};
      setNotices(w.notices);
      // Batch Report 자동 분석(CAMTEK · KLA)도 창을 닫으면 트레이에 남아야 예약 시각에 돈다(Para #54).
      const on=w.param||w.commonality||!!w.batch;
      await setBackground(on,on?`Para 자동 분석 및 취합 실행 중 — 장비 ${w.param?'✓':'✗'} · Commonality ${w.commonality?'✓':'✗'} · Batch Report ${w.batch?'✓':'✗'}${lastNotice.current?` · 최근: ${lastNotice.current}`:''}`:'');
    }catch{/* engine not ready: the next change or reconnect syncs again */}
  }
  useEffect(()=>{
    const off=desktop.onNotice(n=>{
      setNotices(old=>mergeNotice(old,n));
      if(!n.live)lastNotice.current=n.summary;
      // 진행 과정(시작·진행 중·변경 없음)은 [자동 분석 및 취합 › 최근 알림]에만, 변경·새 S/M·실패는 팝업도.
      if(!n.quiet)notify(`${n.title}: ${n.summary}`,n.kind.endsWith('_failed')?'error':'info');
      if(!n.live)void syncWatch();
    });
    void syncWatch();
    return off;
  },[]);
  return <div className={'app'+(isMini?' edition-mini':'')} data-edition={isMini?'mini':'full'}>
    <Toaster/>
    <TourLayer/>
    <ActivityPanel/>
    <header className="topbar"><a className="brand" href="#main"><span className="brand-icon" aria-hidden="true">A</span><span className="brand-name"><b>AOI Manager</b>{isMini&&<em className="edition-pill" title="AOI Manager 의 간단판 — 고른 기능만 보입니다">Mini</em>}<small>장비 데이터 작업공간</small></span></a><span className="topbar-right"><span className="environment"><span aria-hidden="true">●</span> 오프라인 · 원본 읽기 전용</span><span className="connection-box"><span className={'connection '+(config&&!engineDown?'connected':'')}>{engineDown?'엔진 연결 끊김':connection}</span>
        {engineDown&&<button onClick={reconnect}>다시 연결</button>}</span></span></header>
    <UpdateBanner busy={batchRunning}/>
    <nav className="vendor-tabs" aria-label="장비 회사 · 공통">{TOPS.map(t=><button key={t} data-tour={(t in VENDORS?'vendor:':'nav:')+t}
      className={(top===t?'active':'')+(t in VENDORS?'':' common')} aria-current={top===t?'page':undefined}
      onClick={()=>setTab(t==='CAMTEK'||t==='KLA'?lastTab.current[t]:t)}>{t}</button>)}</nav>
    {navigation.length>0&&<nav className="navigation" aria-label="주요 기능">{navigation.map(name=><button key={name} data-tour={'nav:'+name} className={tab===name?'active':''} aria-current={tab===name?'page':undefined} onClick={()=>setTab(name)}>{tabLabel(name)}</button>)}</nav>}
    <main id="main"><h1 className="sr-only">{tabLabel(tab)}</h1>
      <div key={screenKey} style={{display:'contents'}}>
      {visited.map(name=><div key={name} hidden={tab!==name} className="kept-screen">{
        name==='Commonality 조사'?<Commonality/>:name==='Recipe 관리'?<RecipeHub active={tab==='Recipe 관리'}/>
        :name==='Batch Report 분석'?<Batch active={tab==='Batch Report 분석'}/>
        :name==='Defect 분석'?<DefectAnalysis/>
        :name==='Wafer Map 수정하기'?<WaferMap/>
        :name==='KLA 자재 찾기'?<Kla/>
        :name==='TB500 Review 조회'?<Tb500/>
        :<Watch notices={notices} onChanged={()=>void syncWatch()}/>}</div>)}
      {KEEP.includes(tab)?null:tab==='설정'?<Settings/>:<Memo/>}
      </div>
    </main><footer><span>{APP_NAME}</span><span>{config?.local_root?`로컬 결과: ${config.local_root}`:'데이터는 장비 원본과 분리하여 로컬에 저장합니다.'}</span></footer>
  </div>;
}
createRoot(document.getElementById('root')!).render(<App/>);
startMotion();   // DESIGN.md 8절: 탭 밑줄 미끄러짐 · 돌림 선택(select[data-wheel])
