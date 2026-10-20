import {useEffect,useState} from 'react';
import {desktop,errorText,pickFolder} from './desktop';
import {notify} from './ui';
import {openPath} from './OpenPath';
import {MemoPick,type MemoMachine} from './MemoPick';

/* KLA 장비 폴더 설정(이슈 #32) — 설정 › AOI 장비 호기 루트 › KLA 탭에서 등록한다(종전 #30 은 KLA 자재 찾기 화면 안).
   · KLA 장비 폴더: 이름 + 경로(바로 아래가 날짜 폴더, 또는 장비 폴더들을 담은 상위 폴더). 이 PC 설정 `kla_roots`.
   · Defect 이미지 백업본: Camtek 의 'Scanresult 백업본'에 해당. KLA 는 Scanresult 폴더 없이 장비 폴더 아래 날짜 폴더에
     Defect 이미지(.jpg)와 결과 파일을 저장하므로, 날짜 폴더째 옮겨 둔 보관 폴더를 장비마다 등록하고(`kla_backups`)
     켜고 끈다(`kla_backup`, 기본 켬). 켜면 KLA 자재 찾기가 원본 장비 폴더와 백업 폴더를 함께 찾는다.
   저장하면 'para:kla-state' 이벤트로 KLA 자재 찾기 화면도 바로 따라간다. */
export type KlaRoot={name:string;path:string;backups:string[]};
export type KlaState={roots:KlaRoot[];backup:boolean};
const EVENT='para:kla-state';
let cached:KlaState|undefined;

function publish(s:KlaState){cached=s;window.dispatchEvent(new CustomEvent(EVENT,{detail:s}));}

/** KLA 설정(장비 폴더 · 백업본 켜짐)을 읽고, 다른 화면에서 바꾸면 따라간다. */
export function useKlaState():[KlaState|undefined,string,()=>Promise<void>]{
  const [st,setSt]=useState<KlaState|undefined>(cached);
  const [error,setError]=useState('');
  async function load(){
    setError('');
    try{await desktop.connect();publish((await desktop.request('kla_state').promise).kla as KlaState);}
    catch(e){setError(errorText(e));}
  }
  useEffect(()=>{
    const sync=(e:Event)=>setSt((e as CustomEvent<KlaState>).detail);
    window.addEventListener(EVENT,sync);
    if(cached===undefined)void load();
    return ()=>window.removeEventListener(EVENT,sync);
  },[]);
  return [st,error,load];
}

async function saveRoots(roots:KlaRoot[],msg:string){
  try{publish((await desktop.request('kla_set_roots',{roots}).promise).kla as KlaState);notify(msg,'ok');return true;}
  catch(e){notify(errorText(e),'error');return false;}
}

/** Defect 이미지 백업본 포함 켜고 끄기 막대(설정 · KLA 자재 찾기 공용). */
export function KlaBackupBar({note,disabled}:{note?:string;disabled?:boolean}){
  const [st]=useKlaState();
  const [saving,setSaving]=useState(false);
  const on=st?.backup;
  const count=st?st.roots.reduce((n,r)=>n+r.backups.length,0):0;
  async function set(next:boolean){
    setSaving(true);
    try{publish((await desktop.request('kla_set_backup',{enabled:next}).promise).kla as KlaState);
      notify(next?'이제 KLA Defect 이미지 백업본까지 포함해 찾습니다':'이제 KLA 원본 장비 폴더만 찾습니다(백업본 제외)','ok');}
    catch(e){notify(errorText(e),'error');}
    finally{setSaving(false);}
  }
  return <div className={`sbk ${on===false?'off':'on'}`} role="group" aria-label="KLA 찾기 범위">
    <span className="sbk-dot" aria-hidden="true"/>
    <div className="sbk-text">
      <b>KLA 찾기 범위 · {st?(on?'원본 + Defect 이미지 백업본':'원본만'):'확인 중…'}</b>
      <small>{on===false?'장비마다 등록한 백업 폴더(Defect 이미지 · 결과 파일을 날짜 폴더째 옮겨 둔 곳)는 보지 않습니다.'
        :`원본 장비 폴더와 장비마다 등록한 백업 폴더(${count}개)를 함께 찾습니다.`}{note?` ${note}`:''}</small>
    </div>
    <label className="sbk-switch" title="KLA 자재 찾기에 적용됩니다">
      <input type="checkbox" role="switch" aria-label="Defect 이미지 백업본 포함" checked={!!on} disabled={!st||saving||disabled}
        onChange={e=>void set(e.target.checked)}/>
      <span>백업본 포함</span>
    </label>
  </div>;
}

/** 설정 › AOI 장비 호기 루트 › KLA: 장비 폴더 등록 + 장비별 Defect 이미지 백업 폴더. */
export function KlaRootsSettings({memo}:{memo?:MemoMachine[]}={}){
  const [st,error,load]=useKlaState();
  const roots=st?.roots||[];
  const [busy,setBusy]=useState(false);
  const [name,setName]=useState(''),[path,setPath]=useState('');
  const [bMachine,setBMachine]=useState(''),[bPath,setBPath]=useState('');
  async function save(next:KlaRoot[],msg:string){setBusy(true);try{return await saveRoots(next,msg);}finally{setBusy(false);}}
  async function browse(set:(v:string)=>void,after?:(v:string)=>void){
    const p=await pickFolder();
    if(p){set(p);after&&after(p);}else notify('폴더 선택이 취소되었거나 데스크톱 앱이 아닙니다. 경로를 직접 붙여넣어 주세요.','info');
  }
  const backupRows=roots.flatMap(r=>r.backups.map(b=><tr key={r.name+'\t'+b}><td style={{width:110,fontWeight:700}}>{r.name}</td><td><code>{b}</code></td>
    <td style={{whiteSpace:'nowrap',width:130}}><button className="linklike" onClick={()=>void openPath(b)}>폴더 열기</button>{' '}
      <button className="linklike" disabled={busy} aria-label={`${r.name} 백업 폴더 ${b} 삭제`}
        onClick={()=>void save(roots.map(o=>o.name===r.name?{...o,backups:o.backups.filter(x=>x!==b)}:o),`${r.name} 백업 폴더 삭제됨`)}>삭제</button></td></tr>));
  return <div className="kla-settings">
    <h3>KLA 장비 폴더 등록</h3>
    <p className="hint">KLA 장비는 스캔 결과를 <code>{'{장비 폴더}\\{날짜}\\{Lot}\\{스캔 시각}_{슬롯}'}</code> 에 저장합니다(Defect 이미지 .jpg · 결과 .001 · .pass).
      장비 폴더(바로 아래가 날짜 폴더, 예 <code>J:\2.K2</code>)를 등록하세요. 장비 폴더들을 담은 상위 폴더(예 <code>J:\</code>)를 등록하면 그 아래 장비 폴더를 모두 찾습니다.
      이 PC 설정 파일에만 저장되고, 장비 폴더는 읽기만 합니다. 탐색기에서 먼저 그 드라이브 · 공유 폴더에 연결해 두세요.</p>
    {error&&<p className="warn">{error} <button className="linklike" onClick={()=>void load()}>다시 시도</button></p>}
    {roots.length>0?<table className="tbl" data-tour="settings:kla-table" style={{marginTop:10}}><thead><tr><th>장비</th><th>장비 폴더</th><th>백업 폴더</th><th/></tr></thead><tbody>
      {roots.map(r=><tr key={r.name}><td style={{width:110,fontWeight:700}}>{r.name}</td><td><code>{r.path}</code></td>
        <td className="hint">{r.backups.length?`${r.backups.length}개`:'없음'}</td>
        <td style={{whiteSpace:'nowrap',width:130}}><button className="linklike" onClick={()=>void openPath(r.path)}>폴더 열기</button>{' '}
          <button className="linklike" disabled={busy} aria-label={`${r.name} 삭제`} onClick={()=>{
            if(window.confirm(`${r.name} 장비 폴더와 백업 폴더 등록을 모두 삭제할까요? (폴더 자체는 지우지 않습니다)`))
              void save(roots.filter(o=>o.name!==r.name),`${r.name} 삭제`);}}>삭제</button></td></tr>)}
    </tbody></table>:st&&<p className="table-empty">⚠ 등록된 KLA 장비 폴더가 없습니다 — 아래에서 등록하세요.</p>}
    <div className="form-filter" data-tour="settings:kla-form" style={{marginTop:10}}>
      <MemoPick memo={memo} vendor="KLA" registered={roots.map(r=>r.name)} onPick={setName} disabled={busy}/>
      <label className="field" style={{width:150}}>장비 이름<input value={name} placeholder="2.K2" maxLength={64} onChange={e=>setName(e.target.value)}/></label>
      <label className="field" style={{flex:1,minWidth:240}}>장비 폴더<input value={path} placeholder="예: J:\2.K2  (또는 J:\ — 아래 장비 폴더를 모두 찾음)" maxLength={4096} onChange={e=>setPath(e.target.value)}/></label>
      <button onClick={()=>void browse(setPath,p=>{if(!name.trim())setName(p.replace(/[\\/]+$/,'').split(/[\\/]/).pop()||'');})}>📁 찾기</button>
      <button className="primary" disabled={busy||!st||!name.trim()||!path.trim()} onClick={async()=>{
        const n=name.trim(),old=roots.find(o=>o.name===n);
        if(await save([...roots.filter(o=>o.name!==n),{name:n,path:path.trim(),backups:old?.backups||[]}],`${n} 등록`)){setName('');setPath('');}
      }}>추가</button></div>

    <h3 style={{marginTop:24}}>Defect 이미지 백업본</h3>
    <p className="hint">Camtek 의 Scanresult 백업본에 해당합니다. KLA 는 Scanresult 폴더 없이 장비 폴더 아래 <b>날짜 폴더</b>에 Defect 이미지와 결과 파일을 바로 저장하므로,
      장비 폴더의 날짜 폴더를 옮겨 둔 <b>백업 · 보관 폴더</b>를 장비마다 등록합니다(구조는 원본과 같게: 바로 아래가 날짜 폴더). 장비당 최대 20개.
      켜 두면 KLA 자재 찾기가 원본과 백업 폴더를 함께 찾고, 결과에 <b>백업본</b>이라고 표시합니다.</p>
    <KlaBackupBar note="KLA 자재 찾기에 적용됩니다."/>
    {roots.length===0?<p className="table-empty">먼저 위에서 KLA 장비 폴더를 등록하세요.</p>:<>
      {backupRows.length>0&&<table className="tbl" style={{marginTop:12}}><thead><tr><th>장비</th><th>백업 폴더</th><th/></tr></thead><tbody>{backupRows}</tbody></table>}
      <div className="form-filter" style={{marginTop:12}}>
        <label className="field" style={{width:150}}>백업 폴더 장비<select value={bMachine} onChange={e=>setBMachine(e.target.value)}><option value="">선택…</option>
          {roots.map(r=><option key={r.name} value={r.name}>{r.name}</option>)}</select></label>
        <label className="field" style={{flex:1,minWidth:240}}>백업 폴더<input value={bPath} placeholder="예: K:\KLA_백업\2.K2" maxLength={4096} onChange={e=>setBPath(e.target.value)}/></label>
        <button onClick={()=>void browse(setBPath)}>📁 찾기</button>
        <button className="primary" disabled={busy||!bMachine||!bPath.trim()} onClick={async()=>{
          if(await save(roots.map(o=>o.name===bMachine?{...o,backups:[...o.backups.filter(x=>x!==bPath.trim()),bPath.trim()]}:o),`${bMachine} 백업 폴더 등록`))setBPath('');
        }}>백업 폴더 등록</button></div></>}
  </div>;
}
