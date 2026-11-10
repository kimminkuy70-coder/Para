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

/** Owner request: every start, if a newer release exists, a pop-up asks to update. When the new
 * version is already downloaded (waiting for a restart), the pop-up only asks to restart. */
export function UpdateBanner({busy}:{busy:boolean}){
  const [info,setInfo]=useState<AppUpdate>(),[working,setWorking]=useState(false),[ready,setReady]=useState('');
  const box=useRef<HTMLDialogElement>(null),readyBox=useRef<HTMLDialogElement>(null);
  useEffect(()=>{
    // Quiet check shortly after start; failures (no internet) never block using the app.
    const t=window.setTimeout(()=>{desktop.connect().then(()=>desktop.request('appupdate_check').promise).then(r=>{
      const u=r.appupdate as AppUpdate;
      if(u.pending_ready)setReady(u.pending);
      else if(u.newer)setInfo(u);
    }).catch(()=>undefined);},1500);
    const onReady=(e:Event)=>{box.current?.close();setInfo(undefined);setReady(String((e as CustomEvent).detail||''));};
    window.addEventListener(READY_EVENT,onReady);
    return()=>{window.clearTimeout(t);window.removeEventListener(READY_EVENT,onReady);};
  },[]);
  useEffect(()=>{if(info&&box.current&&!box.current.open)box.current.showModal();},[info]);
  useEffect(()=>{if(ready&&readyBox.current&&!readyBox.current.open)readyBox.current.showModal();},[ready]);
  const close=()=>{box.current?.close();setInfo(undefined);};
  const closeReady=()=>{readyBox.current?.close();setReady('');};
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
      {busy&&<p className="hint">진행 중인 작업이 끝난 뒤 업데이트할 수 있습니다.</p>}
      <div className="actions">
        <button className="primary" disabled={busy||working||!info.installed}
          onClick={async()=>{setWorking(true);await installUpdate();setWorking(false);}}>{working?'받는 중…':'지금 업데이트'}</button>
        <button onClick={close}>나중에</button>
      </div></dialog>}
    {ready&&<dialog ref={readyBox} className="update-banner" aria-label="업데이트 적용 안내" onCancel={closeReady}>
      <h3>새 버전 {ready}을 받았습니다</h3>
      <p><b>프로그램을 종료한 뒤 다시 실행하면</b> 새 버전이 적용됩니다.</p>
      <p className="hint">[지금 종료]를 누른 뒤 바탕화면의 Camtek AOI Manager 바로가기로 다시 실행하십시오. [나중에]를 누르면 지금 버전으로 계속 쓰고, 다음에 실행할 때 적용됩니다.</p>
      {busy&&<p className="hint">진행 중인 작업이 끝난 뒤 종료하십시오.</p>}
      <div className="actions">
        <button className="primary" disabled={busy} onClick={()=>void quit()}>지금 종료</button>
        <button onClick={closeReady}>나중에</button>
      </div></dialog>}
  </>;
}
