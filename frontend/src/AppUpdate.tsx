import {useEffect,useState} from 'react';
import {desktop,exitApp,type AppUpdate} from './desktop';
import {notify,fail} from './ui';

/** Start the staged self-update and quit so the swap script can replace the folder. */
export async function installUpdate(){
  try{
    const r=(await desktop.request('appupdate_apply').promise).appupdate as {version:string};
    notify(`새 버전 ${r.version} 설치를 위해 앱을 종료합니다. 잠시 후 자동으로 다시 열립니다.`,'ok');
    window.setTimeout(()=>void exitApp(),1200);
  }catch(e){fail(e);}
}
export async function openProgramDir(){
  try{await desktop.request('appupdate_open_dir').promise;}catch(e){fail(e);}
}

/** Top banner shown when a newer web package is published (tkinter: 시작 시 업데이트 확인). */
export function UpdateBanner({busy}:{busy:boolean}){
  const [info,setInfo]=useState<AppUpdate>(),[working,setWorking]=useState(false);
  useEffect(()=>{
    // Quiet check shortly after start; failures never block using the app.
    const t=window.setTimeout(()=>{desktop.connect().then(()=>desktop.request('appupdate_check').promise).then(r=>{
      const u=r.appupdate as AppUpdate;
      if(u.failed)notify(`지난 업데이트(${u.available})가 적용되지 않았습니다. [직접 설치]로 게시 폴더에서 설치하거나 담당자에게 문의하세요.`,'error');
      if(u.newer&&!u.skipped)setInfo(u);
    }).catch(()=>undefined);},1500);
    return()=>window.clearTimeout(t);
  },[]);
  if(!info)return null;
  async function later(){
    try{await desktop.request('appupdate_skip',{version:info!.available}).promise;}catch(e){fail(e);}
    setInfo(undefined);
  }
  return <div className="update-banner" role="status">
    <div><b>새 버전 {info.available}</b>이 게시되었습니다 (현재 {info.current}{info.published_at?` · 게시 ${info.published_at}`:''}).
      {info.changelog&&<p className="changelog">{info.changelog}</p>}
      {!info.installed&&<p className="hint">개발 실행 중이라 자동 설치는 할 수 없습니다.</p>}</div>
    <div className="actions">
      <button className="primary" disabled={busy||working||!info.installed} title={busy?'진행 중인 작업이 끝난 뒤 설치하세요':''}
        onClick={async()=>{setWorking(true);await installUpdate();setWorking(false);}}>{working?'준비 중…':'지금 업데이트'}</button>
      <button onClick={openProgramDir}>직접 설치(게시 폴더)</button>
      <button onClick={later}>이 버전 건너뛰기</button>
    </div></div>;
}
