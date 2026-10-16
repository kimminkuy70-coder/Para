import {useEffect,useState} from 'react';
import {createRoot} from 'react-dom/client';
import {desktop,errorText,overrideErrorText} from './desktop';
import './styles.css';
import {Toaster,notify} from './ui';
import {WaferMap} from './WaferMap';

/* Wafer Map 전용판(특수 버전) 화면 — 본 앱과 같은 구조(Tauri + React + Python 엔진)에서
   `Wafer Map 수정하기` 하나만 띄운다. 다른 기능 화면 · 자동 업데이트 · 트레이는 이 번들에 없다
   (wafermap/index.html → 이 파일만 진입점, tests/test_wafermap_edition.py 가 import 범위를 고정). */

overrideErrorText({
  already_running:'Wafer Map 프로그램이 이미 켜져 있습니다. 먼저 켜 둔 창을 쓰거나, 그 창을 닫은 뒤 위의 [다시 연결]을 누르세요.',
  engine_closed:'변환 엔진 연결이 종료되었습니다. 위의 [다시 연결]을 눌러 주세요.',
  engine_busy_or_closed:'변환 엔진이 응답하지 않습니다. 위의 [다시 연결]을 눌러 주세요.',
  engine_start_failed:'변환 엔진을 시작하지 못했습니다. 프로그램 폴더 안의 sidecar 폴더가 그대로 있는지 확인하세요.',
  engine_not_packaged:'변환 엔진이 포함되지 않은 빌드입니다.',
  engine_failed:'처리 중 예상하지 못한 오류가 났습니다. 화면 아래 로그 폴더의 오류_로그.txt 를 담당자에게 전달하세요.',
  desktop_required:'Wafer Map 프로그램(Camtek_AOI_WaferMap.exe)에서 열어야 합니다.',
});

type Config={product:string;app_version:string;local_root:string;logs:string};

function App(){
  const [config,setConfig]=useState<Config>();
  const [connection,setConnection]=useState('엔진 연결 중');
  const [engineDown,setEngineDown]=useState(false);
  const [screenKey,setScreenKey]=useState(0);
  useEffect(()=>desktop.onStatus((connected,code)=>{
    setEngineDown(!connected);
    if(!connected)notify(errorText(code),'error');
  }),[]);
  async function load(){
    try{
      await desktop.connect();
      const data=(await desktop.request('configuration').promise) as unknown as Config;
      setConfig(data);setConnection('로컬 엔진 연결됨');
    }catch(e){setConnection('연결 확인 필요');notify(errorText(e),'error');}
  }
  useEffect(()=>{void load();},[]);
  async function reconnect(){
    // A new engine starts clean (the previous job is gone), so the screen starts over too.
    await load();
    if(!desktop.closed){setEngineDown(false);setScreenKey(k=>k+1);notify('변환 엔진에 다시 연결했습니다.','ok');}
  }
  return <div className="app">
    <Toaster/>
    <header className="topbar"><a className="brand" href="#main"><span className="brand-icon" aria-hidden="true">W</span><span>Camtek <b>AOI Wafer Map</b><small>Wafer Map 변환 전용</small></span></a><span className="environment"><span aria-hidden="true">●</span> 오프라인 · 원본 읽기 전용</span></header>
    <main id="main"><div className="page-heading"><div><p className="eyebrow">WAFER MAP</p><h1>Wafer Map 변환</h1><p>Camtek AOI Manager 의 특수 버전입니다. 이 프로그램에는 Wafer Map 변환 기능만 들어 있으며, 원본 파일은 읽기만 하고 결과는 늘 새 파일로 저장합니다.</p></div><span className="connection-box"><span className={'connection '+(config&&!engineDown?'connected':'')}>{engineDown?'엔진 연결 끊김':connection}</span>
        {engineDown&&<button onClick={reconnect}>다시 연결</button>}</span></div>
      <div key={screenKey} style={{display:'contents'}}><WaferMap/></div>
    </main><footer><span>Camtek AOI Wafer Map{config?.app_version?` v${config.app_version}`:''}</span><span>{config?.logs?`오류 로그: ${config.logs}`:'원본은 읽기만 하고, 변환 결과는 새 파일로 저장합니다.'}</span></footer>
  </div>;
}
createRoot(document.getElementById('root')!).render(<App/>);
