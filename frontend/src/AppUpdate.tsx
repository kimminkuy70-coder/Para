import {useEffect,useRef,useState} from 'react';
import {desktop,restartForUpdate,type AppUpdate} from './desktop';
import {notify,fail} from './ui';

/** Download + check the new release, stage it, then restart: the window reconnects by itself (v13). */
export async function installUpdate(){
  try{
    const r=(await desktop.request('appupdate_apply').promise).appupdate as {version:string};
    notify(`새 버전 ${r.version}을 적용하려고 프로그램을 다시 시작합니다. 이 창은 잠시 뒤 저절로 다시 연결됩니다.`,'ok');
    await restartForUpdate();
  }catch(e){fail(e);}
}
export async function openProgramDir(){
  try{await desktop.request('appupdate_open_dir').promise;}catch(e){fail(e);}
}

/** Owner request (2026-11-10): every start, if a newer release exists, a pop-up asks to update. */
export function UpdateBanner({busy}:{busy:boolean}){
  const [info,setInfo]=useState<AppUpdate>(),[working,setWorking]=useState(false);
  const box=useRef<HTMLDialogElement>(null);
  useEffect(()=>{
    // Quiet check shortly after start; failures (no internet) never block using the app.
    const t=window.setTimeout(()=>{desktop.connect().then(()=>desktop.request('appupdate_check').promise).then(r=>{
      const u=r.appupdate as AppUpdate;
      if(u.newer)setInfo(u);
    }).catch(()=>undefined);},1500);
    return()=>window.clearTimeout(t);
  },[]);
  useEffect(()=>{if(info&&box.current&&!box.current.open)box.current.showModal();},[info]);
  if(!info)return null;
  const close=()=>{box.current?.close();setInfo(undefined);};
  return <dialog ref={box} className="update-banner" aria-label="새 버전 알림" onCancel={close}>
    <h3>새 버전 {info.available}이 있습니다</h3>
    <p>지금 버전 {info.current}{info.published_at?` · 공개 ${info.published_at}`:''} · {info.source==='github'?'GitHub 릴리스':'OneDrive 게시 폴더'}</p>
    {info.changelog&&<pre className="changelog">{info.changelog}</pre>}
    {!info.installed&&<p className="hint">설치본이 아니라 소스 폴더에서 실행 중이라 자동 업데이트는 하지 않습니다(git 으로 받으십시오).</p>}
    {busy&&<p className="hint">진행 중인 작업이 끝난 뒤 업데이트할 수 있습니다.</p>}
    <div className="actions">
      <button className="primary" disabled={busy||working||!info.installed}
        onClick={async()=>{setWorking(true);await installUpdate();setWorking(false);}}>{working?'받는 중…':'지금 업데이트'}</button>
      <button onClick={close}>나중에</button>
    </div></dialog>;
}
