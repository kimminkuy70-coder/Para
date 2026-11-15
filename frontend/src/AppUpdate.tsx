import {useEffect,useRef,useState} from 'react';
import {desktop,exitApp,type AppUpdate} from './desktop';
import {notify,fail} from './ui';

/** Owner 2026-11-10: the update is applied at the next start (like the AOI Recipe Verification program);
 * after downloading, a window asks the person to close and start the program again. */
const READY_EVENT='para:update-ready';
export async function installUpdate(){
  try{
    const r=(await desktop.request('appupdate_apply').promise).appupdate as {version:string};
    window.dispatchEvent(new CustomEvent(READY_EVENT,{detail:r.version}));
  }catch(e){fail(e);}
}
export async function openProgramDir(){
  try{await desktop.request('appupdate_open_dir').promise;}catch(e){fail(e);}
}

/** v14.1.1 소유자: "프로그램 실행시 무조건 업데이트가 먼저 작업되게 해 — batch restore 가 실행돼서 업데이트를 눌러도
 * 기다리라고 떠. 어차피 업데이트할 건데 왜 그걸 로딩하는 건데?"
 * → 시작할 때 업데이트 확인이 먼저다. 시작 때 도는 작업(Batch Report 지난 결과 불러오기 · 자동 분석)은 이 문(gate)이
 * 열린 뒤에 시작한다. 문이 열리는 때 = 새 버전 없음 · 확인 실패(인터넷 없음) · 소스 폴더 실행(설치본 아님) ·
 * 알림 창에서 [나중에] · 확인이 GATE_MAX_MS 안에 안 끝남. 새 버전이 있으면 사람이 고를 때까지 시작 작업을 하지 않는다. */
const GATE_MAX_MS=15000;
let gateOpen=false;const gateWaiters:(()=>void)[]=[];
export function openUpdateGate(){if(gateOpen)return;gateOpen=true;gateWaiters.splice(0).forEach(f=>f());}
export function updateGate():Promise<void>{return gateOpen?Promise.resolve():new Promise(r=>{gateWaiters.push(r);});}
export const isUpdateGateOpen=()=>gateOpen;

/** Owner request: every start, if a newer release exists, a pop-up asks to update. When the new
 * version is already downloaded (waiting for a restart), the pop-up only asks to restart.
 * busy = 다른 작업이 진행 중 — 업데이트는 막지 않는다(받기 = app.new 에 준비만, 적용은 다음 실행). */
export function UpdateBanner({busy}:{busy:boolean}){
  const [info,setInfo]=useState<AppUpdate>(),[working,setWorking]=useState(false),[ready,setReady]=useState('');
  const box=useRef<HTMLDialogElement>(null),readyBox=useRef<HTMLDialogElement>(null);
  useEffect(()=>{
    // 시작하자마자 확인(먼저). 실패(인터넷 없음)는 프로그램 사용을 막지 않는다 — 문을 연다.
    const cap=window.setTimeout(openUpdateGate,GATE_MAX_MS);
    desktop.connect().then(()=>desktop.request('appupdate_check').promise).then(r=>{
      const u=r.appupdate as AppUpdate;
      if(u.pending_ready)setReady(u.pending);
      else if(u.newer){setInfo(u);if(!u.installed)openUpdateGate();}   // 소스 폴더 실행은 업데이트를 못 하므로 기다리지 않음
      else openUpdateGate();
    }).catch(openUpdateGate);
    const onReady=(e:Event)=>{box.current?.close();setInfo(undefined);setReady(String((e as CustomEvent).detail||''));};
    window.addEventListener(READY_EVENT,onReady);
    return()=>{window.clearTimeout(cap);window.removeEventListener(READY_EVENT,onReady);};
  },[]);
  useEffect(()=>{if(info&&box.current&&!box.current.open)box.current.showModal();},[info]);
  useEffect(()=>{if(ready&&readyBox.current&&!readyBox.current.open)readyBox.current.showModal();},[ready]);
  const close=()=>{box.current?.close();setInfo(undefined);openUpdateGate();};
  const closeReady=()=>{readyBox.current?.close();setReady('');openUpdateGate();};
  async function quit(){
    notify('프로그램을 종료합니다. 바탕화면 바로가기로 다시 실행하면 새 버전이 적용됩니다.','ok');
    window.setTimeout(()=>void exitApp(),800);
  }
  return <>
    {info&&<dialog ref={box} className="update-banner" aria-label="새 버전 알림" onCancel={close}>
      <h3>새 버전 {info.available}이 있습니다</h3>
      <p>지금 버전 {info.current}{info.published_at?` · 공개 ${info.published_at}`:''} · {info.source==='github'?'GitHub 릴리스':'OneDrive 게시 폴더'}</p>
      {info.changelog&&<pre className="changelog">{info.changelog}</pre>}
      {!info.installed&&<p className="hint">설치본이 아니라 소스 폴더에서 실행 중이라 자동 업데이트는 하지 않습니다(git 으로 받으십시오).</p>}
      {busy&&<p className="hint">진행 중인 작업이 있어도 지금 받을 수 있습니다(새 버전은 프로그램을 다시 실행할 때 적용).</p>}
      <div className="actions">
        <button className="primary" disabled={working||!info.installed}
          onClick={async()=>{setWorking(true);await installUpdate();setWorking(false);}}>{working?'받는 중…':'지금 업데이트'}</button>
        <button onClick={close}>나중에</button>
      </div></dialog>}
    {ready&&<dialog ref={readyBox} className="update-banner" aria-label="업데이트 적용 안내" onCancel={closeReady}>
      <h3>새 버전 {ready}을 받았습니다</h3>
      <p><b>프로그램을 종료한 뒤 다시 실행하면</b> 새 버전이 적용됩니다.</p>
      <p className="hint">[지금 종료]를 누른 뒤 바탕화면의 Camtek AOI Manager 바로가기로 다시 실행하십시오. [나중에]를 누르면 지금 버전으로 계속 쓰고, 다음에 실행할 때 적용됩니다.</p>
      {busy&&<p className="hint">진행 중인 작업이 있으면 그 작업은 멈추고 종료합니다.</p>}
      <div className="actions">
        <button className="primary" onClick={()=>void quit()}>지금 종료</button>
        <button onClick={closeReady}>나중에</button>
      </div></dialog>}
  </>;
}
