import {useEffect,useState} from 'react';
import {desktop,errorText} from './desktop';
import {notify} from './ui';

/* Scanresult 백업본 포함 조사 — Scanresult 를 찾는 모든 기능(Commonality 조사 · 감시 · Batch Report 찾기)이 같은 설정
   (`~/.pi_param_manager.json` scanresult_backup, 기본 켬)을 쓴다. 한 화면에서 바꾸면 다른 화면도 바로 따라간다. */
export type RootInfo={path:string;kind:string};
const EVENT='para:scan-backup';
let cached:boolean|undefined;

export function useScanBackup():[boolean|undefined,(next:boolean)=>Promise<void>,boolean]{
  const [on,setOn]=useState<boolean|undefined>(cached);
  const [saving,setSaving]=useState(false);
  useEffect(()=>{
    const sync=(e:Event)=>setOn((e as CustomEvent<boolean>).detail);
    window.addEventListener(EVENT,sync);
    if(cached===undefined)void (async()=>{
      try{await desktop.connect();const c=(await desktop.request('config_state').promise).config as {scan_backup?:boolean};
        cached=c.scan_backup!==false;window.dispatchEvent(new CustomEvent(EVENT,{detail:cached}));}catch{/* 표시만 비워 둔다 */}
    })();
    return ()=>window.removeEventListener(EVENT,sync);
  },[]);
  async function set(next:boolean){
    setSaving(true);
    try{await desktop.request('config_set_scan_backup',{enabled:next}).promise;cached=next;
      window.dispatchEvent(new CustomEvent(EVENT,{detail:next}));
      notify(next?'이제 Scanresult 백업본까지 포함해 조사합니다':'이제 원본 Scanresult 만 조사합니다(백업본 제외)','ok');}
    catch(e){notify(errorText(e),'error');}
    finally{setSaving(false);}
  }
  return [on,set,saving];
}

/** 지금 조사 범위(원본만 / 백업본 포함)를 보여 주고 바로 바꾸는 막대. note = 이 화면에서 무엇에 적용되는지. */
export function ScanBackupBar({note,disabled}:{note?:string;disabled?:boolean}){
  const [on,set,saving]=useScanBackup();
  const known=on!==undefined;
  return <div className={`sbk ${on===false?'off':'on'}`} role="group" aria-label="Scanresult 조사 범위">
    <span className="sbk-dot" aria-hidden="true"/>
    <div className="sbk-text">
      <b>Scanresult 조사 범위 · {known?(on?'원본 + 백업본':'원본만'):'확인 중…'}</b>
      <small>{on===false?'백업본(Scanresult_260402 같은 이름 · 설정에서 추가한 보관 폴더)은 보지 않습니다.'
        :'원본 Scanresult 와 백업본(Scanresult_260402 같은 이름 · 설정에서 추가한 보관 폴더)을 함께 찾습니다.'}{note?` ${note}`:''}</small>
    </div>
    <label className="sbk-switch" title="Scanresult 를 찾는 모든 기능에 같이 적용됩니다">
      <input type="checkbox" role="switch" aria-label="백업본 포함해서 조사" checked={!!on} disabled={!known||saving||disabled}
        onChange={e=>void set(e.target.checked)}/>
      <span>백업본 포함</span>
    </label>
  </div>;
}

/** 조사에 실제로 쓴 Scanresult 폴더 목록(원본 / 백업본 / 추가 폴더 표시). */
export function ScanRoots({info,backup}:{info?:RootInfo[];backup?:boolean}){
  if(!info?.length)return null;
  const n=(k:string)=>info.filter(r=>r.kind===k).length;
  const extra=n('백업본')+n('추가 폴더');
  return <details className="sbk-roots">
    <summary>이번에 조사한 Scanresult 폴더 {info.length}개 — {backup===false?'원본만(백업본 제외)':extra?`원본 ${n('원본')} · 백업본 ${extra}`:'원본만(백업본 없음)'}</summary>
    <ul>{info.map(r=><li key={r.path}><span className={`sbk-kind ${r.kind==='원본'?'main':'bk'}`}>{r.kind}</span><code>{r.path}</code></li>)}</ul>
  </details>;
}
