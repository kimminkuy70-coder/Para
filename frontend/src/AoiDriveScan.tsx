import {useState} from 'react';
import {desktop,errorText,pickFolder} from './desktop';
import {notify} from './ui';

/* 네트워크 드라이브에서 AOI 호기 자동 찾기(이슈 #36) — 설정 › AOI 장비 호기 루트 › CAMTEK.
   NAS 마다 장비 몇 대씩 나뉘어 있고(NAS1 = AOI-1~5 …) 장비 폴더는 드라이브 **바로 아래**에 있으므로,
   드라이브(예: W:\)를 고르면 엔진 `config_scan_aoi_drive` 가 바로 아래 폴더 이름만 한 번 읽어 후보로 보여 준다
   (더 아래로 들어가지 않고 아무것도 쓰지 않음). 후보는 폴더 이름 = 호기 이름, 'AOI' 가 들어간 이름 · 메모(장비 IP)의
   호기와 같은 이름을 미리 체크하고 이미 등록된 것은 뺀다. [등록] = `config_add_aoi_roots`(한 대씩 등록할 때와 같은 확인). */
type Item={name:string;path:string;likely:boolean;registered:boolean;too_long:boolean};

export function AoiDriveScan<S>({disabled,onState}:{disabled?:boolean;onState:(s:S)=>void}){
  const [drive,setDrive]=useState('');
  const [items,setItems]=useState<Item[]>();
  const [picked,setPicked]=useState<Set<string>>(new Set());
  const [busy,setBusy]=useState(false);
  const free=(i:Item)=>!i.registered&&!i.too_long;
  async function scan(path=drive){
    if(!path.trim())return;setBusy(true);
    try{const r=(await desktop.request('config_scan_aoi_drive',{path:path.trim()}).promise).config as {drive:string;items:Item[]};
      setItems(r.items);setPicked(new Set(r.items.filter(i=>free(i)&&i.likely).map(i=>i.name)));
      const n=r.items.filter(i=>free(i)&&i.likely).length;
      notify(r.items.length?`${r.drive} 바로 아래 폴더 ${r.items.length}개 — AOI 호기로 보이는 미등록 ${n}대를 골라 두었습니다.`:`${r.drive} 바로 아래에 폴더가 없습니다.`,'info');}
    catch(e){notify(errorText(e),'error');setItems(undefined);}finally{setBusy(false);}
  }
  async function browse(){
    const p=await pickFolder();
    if(p){setDrive(p);void scan(p);}else notify('폴더 선택이 취소되었거나 데스크톱 앱이 아닙니다. 경로를 직접 붙여넣어 주세요.','info');
  }
  async function add(){
    const list=(items||[]).filter(i=>free(i)&&picked.has(i.name));
    if(!list.length)return;setBusy(true);
    try{const r=(await desktop.request('config_add_aoi_roots',{items:list.map(i=>({machine:i.name,path:i.path}))}).promise).config as S&{added:string[];notice?:string};
      onState(r);notify(r.notice||`${r.added.length}대 등록`,/찾지 못했습니다|건너뜀/.test(r.notice||'')?'info':'ok');
      const done=new Set(r.added);setItems(o=>o?.map(i=>done.has(i.name)?{...i,registered:true}:i));setPicked(new Set());}
    catch(e){notify(errorText(e),'error');}finally{setBusy(false);}
  }
  const lock=disabled||busy;
  const toggle=(n:string)=>setPicked(o=>{const s=new Set(o);if(s.has(n))s.delete(n);else s.add(n);return s;});
  const count=(items||[]).filter(i=>free(i)&&picked.has(i.name)).length;
  return <div data-tour="settings:aoi-drive" style={{marginTop:12}}>
    <h4 style={{margin:'0 0 4px'}}>🔎 네트워크 드라이브에서 호기 자동 찾기</h4>
    <p className="hint">NAS 네트워크 드라이브(예: <code>W:\</code>)를 고르면 <b>바로 아래 폴더</b>를 AOI 호기로 찾아 한꺼번에 등록합니다.
      드라이브 목록만 한 번 읽고 더 아래로 들어가지 않으며, NAS 의 원본 폴더는 읽기만 합니다(아무것도 만들거나 고치지 않음). 폴더 이름이 호기 이름이 됩니다.</p>
    <div className="form-filter">
      <label className="field" style={{flex:1,minWidth:240}}>네트워크 드라이브<input value={drive} placeholder="예: W:\  또는 \\NAS1\AOI" maxLength={4096}
        onChange={e=>setDrive(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')void scan();}}/></label>
      <button disabled={lock} onClick={()=>void browse()}>📁 찾기</button>
      <button className="primary" disabled={lock||!drive.trim()} onClick={()=>void scan()}>{busy?'읽는 중…':'호기 찾기'}</button></div>
    {items&&items.length>0&&<>
      <div className="toolbar" style={{marginTop:8}}>
        <button disabled={lock} onClick={()=>setPicked(new Set(items.filter(i=>free(i)&&i.likely).map(i=>i.name)))}>AOI 로 보이는 것만 고르기</button>
        <button disabled={lock} onClick={()=>setPicked(new Set(items.filter(free).map(i=>i.name)))}>모두 고르기</button>
        <button disabled={lock} onClick={()=>setPicked(new Set())}>모두 해제</button>
        <button className="primary" disabled={lock||!count} onClick={()=>void add()}>고른 {count}대 등록</button></div>
      <table className="tbl" style={{marginTop:6}}><thead><tr><th/><th>호기 (폴더 이름)</th><th>호기 폴더</th><th>상태</th></tr></thead>
        <tbody>{items.map(i=><tr key={i.name}>
          <td><input type="checkbox" aria-label={`${i.name} 고르기`} disabled={lock||!free(i)} checked={free(i)&&picked.has(i.name)} onChange={()=>toggle(i.name)}/></td>
          <td>{i.name}</td><td><code>{i.path}</code></td>
          <td>{i.registered?'이미 등록됨':i.too_long?'이름이 너무 김(64자)':i.likely?'AOI 호기로 보임':'다른 폴더일 수 있음'}</td></tr>)}</tbody></table></>}
  </div>;
}
