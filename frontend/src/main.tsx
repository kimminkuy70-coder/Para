import {useEffect, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {desktop, errorText, setBackground, mergeNotice, type WatchNotice, type Configuration} from './desktop';
import './styles.css';
import {Settings} from './Settings';
import {Memo} from './Memo';
import {Commonality} from './Commonality';
import {Toaster,notify} from './ui';
import {UpdateBanner} from './AppUpdate';
import {Watch} from './Watch';
import {RecipeHub} from './RecipeHub';
import {ActivityPanel} from './Activity';
import {ColorGray} from './ColorGray';
import {WaferMap} from './WaferMap';
import {Batch} from './Batch';
import {useDev} from './devmode';

const SUBTITLE: Record<string,string> = {
  'Batch Report 분석':'장비 Report 폴더의 Batch Report를 Lot 단위로 모아 가동률 · Lot 추적 · WPH를 보고, 필요한 Batch Report를 찾아 취합합니다.',
  'Color·Gray 매칭':'AOI Color 이미지와 같은 위치의 Gray 스캔 이미지를 찾아 잘라 붙이고, 나란히 비교하는 Excel 을 만드세요.',
  'Wafer Map 수정하기':'Wafer Map TXT 를 Excel 로 펼쳐 Bin Code 를 고치고, 원본 그대로 다시 TXT 로 되돌리세요.',
  '메모':'특이사항 · 참고자료 · 장비 IP 공유 문서를 함께 보고 고치세요.'
};
// Batch Report 분석 stays mounted too: its results, Lot window and unsaved developer choices
// survive a visit to 설정 (where the developer toggle lives).
import {TourLayer} from './Tour';
const KEEP = ['Recipe 관리','Commonality 조사','자동 감시','Batch Report 분석','Color·Gray 매칭','Wafer Map 수정하기'];
const navigation = ['설정','Recipe 관리','자동 감시','Commonality 조사','Batch Report 분석','Color·Gray 매칭','Wafer Map 수정하기','메모'];

function App(){
  const [tab,setTab]=useState('설정');
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
  useEffect(()=>{const go=(e:Event)=>setTab((e as CustomEvent<string>).detail);window.addEventListener('para:navigate',go);return()=>window.removeEventListener('para:navigate',go);},[]);
  // Workflow screens stay mounted after the first visit, so leaving a tab never
  // loses an in-progress step (Commonality 조사, Recipe 관리의 업데이트·양식 …). Screens
  // that hold a shared-document edit lock (문서, Recipe 관리) still unmount so the lock
  // is handed back when you leave them.
  const [visited,setVisited]=useState<string[]>([]);
  useEffect(()=>{if(KEEP.includes(tab))setVisited(v=>v.includes(tab)?v:[...v,tab]);},[tab]);
  useEffect(()=>{window.dispatchEvent(new CustomEvent('para:tab',{detail:tab}));},[tab]);
  // Automatic watches run in the engine; the app shows their notices and keeps
  // itself resident in the tray (hide on close) while any watch is on.
  const [notices,setNotices]=useState<WatchNotice[]>([]);
  const lastNotice=useRef('');
  async function syncWatch(){
    try{
      await desktop.connect();
      const w=(await desktop.request('watch_status').promise).watch as {param:boolean;commonality:boolean;notices:WatchNotice[]};
      setNotices(w.notices);
      const on=w.param||w.commonality;
      await setBackground(on,on?`Para 자동 감시 실행 중 — 장비 ${w.param?'✓':'✗'} · Commonality ${w.commonality?'✓':'✗'}${lastNotice.current?` · 최근: ${lastNotice.current}`:''}`:'');
    }catch{/* engine not ready: the next change or reconnect syncs again */}
  }
  useEffect(()=>{
    const off=desktop.onNotice(n=>{
      setNotices(old=>mergeNotice(old,n));
      if(!n.live)lastNotice.current=n.summary;
      // 진행 과정(시작·진행 중·변경 없음)은 [자동 감시 › 최근 알림]에만, 변경·새 S/M·실패는 팝업도.
      if(!n.quiet)notify(`${n.title}: ${n.summary}`,n.kind.endsWith('_failed')?'error':'info');
      if(!n.live)void syncWatch();
    });
    void syncWatch();
    return off;
  },[]);
  return <div className="app">
    <Toaster/>
    <TourLayer/>
    <ActivityPanel/>
    <header className="topbar"><a className="brand" href="#main"><span className="brand-icon" aria-hidden="true">C</span><span>Camtek <b>AOI Manager</b><small>장비 데이터 작업공간</small></span></a><span className="environment"><span aria-hidden="true">●</span> 오프라인 · 원본 읽기 전용</span></header>
    <UpdateBanner busy={batchRunning}/>
    <nav className="navigation" aria-label="주요 기능">{navigation.map(name=><button key={name} data-tour={'nav:'+name} className={tab===name?'active':''} aria-current={tab===name?'page':undefined} onClick={()=>setTab(name)}>{name}</button>)}</nav>
    <main id="main"><div className="page-heading"><div><p className="eyebrow">PROCESS INTELLIGENCE</p><h1>{tab}</h1><p>{SUBTITLE[tab]||'장비의 기록을 모아, 처리량과 오류 흐름을 한눈에 확인하세요.'}</p></div><span className="connection-box"><span className={'connection '+(config&&!engineDown?'connected':'')}>{engineDown?'엔진 연결 끊김':connection}</span>
        {engineDown&&<button onClick={reconnect}>다시 연결</button>}</span></div>
      <div key={screenKey} style={{display:'contents'}}>
      {visited.map(name=><div key={name} hidden={tab!==name} className="kept-screen">{
        name==='Commonality 조사'?<Commonality/>:name==='Recipe 관리'?<RecipeHub active={tab==='Recipe 관리'}/>
        :name==='Batch Report 분석'?<Batch active={tab==='Batch Report 분석'}/>
        :name==='Color·Gray 매칭'?<ColorGray/>
        :name==='Wafer Map 수정하기'?<WaferMap/>
        :<Watch notices={notices} onChanged={()=>void syncWatch()}/>}</div>)}
      {KEEP.includes(tab)?null:tab==='설정'?<Settings/>:<Memo/>}
      </div>
    </main><footer><span>Camtek AOI Manager</span><span>{config?.local_root?`로컬 결과: ${config.local_root}`:'데이터는 장비 원본과 분리하여 로컬에 저장합니다.'}</span></footer>
  </div>;
}
createRoot(document.getElementById('root')!).render(<App/>);
