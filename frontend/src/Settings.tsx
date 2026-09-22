import {useEffect,useState} from 'react';
import {desktop,pickFolder} from './desktop';
import {notify,fail} from './ui';
import {OpenPath} from './OpenPath';

type State={save_dir:string;local_dir:string;report_paths:Record<string,string>;scanresult_roots:Record<string,string>;extra_paths:Record<string,string[]>;batch_auto:boolean};
const TABS:[string,string][]=[['save','저장폴더'],['report','배치 Report 폴더'],['auto','배치 자동·추가 폴더'],['scan','Scanresult 루트'],['local','로컬 작업 폴더'],['about','정보']];

export function Settings(){
  const [sub,setSub]=useState('save');
  const [st,setSt]=useState<State>();
  const [saveDir,setSaveDir]=useState('');
  const [busy,setBusy]=useState(false);
  const [rMachine,setRMachine]=useState(''),[rPath,setRPath]=useState('');
  const [sMachine,setSMachine]=useState(''),[sPath,setSPath]=useState('');
  const [xMachine,setXMachine]=useState(''),[xPath,setXPath]=useState('');
  type Local={root:string;summary:string;onedrive:boolean;default:string;removed?:number};
  type About={version:string;user:string;config:string;local_root:string;logs:string};
  const [local,setLocal]=useState<Local>(),[localPath,setLocalPath]=useState(''),[about,setAbout]=useState<About>();
  useEffect(()=>{
    if(sub==='local')desktop.request('config_local_state').promise.then(r=>setLocal(r.config as Local)).catch(fail);
    if(sub==='about')desktop.request('config_about').promise.then(r=>setAbout(r.config as About)).catch(fail);
  },[sub]);
  async function localReq(method:string,params:object,ok:(r:Local)=>string){
    setBusy(true);
    try{const r=(await desktop.request(method,params).promise).config as Local;setLocal(r);notify(ok(r),'ok');}
    catch(e){fail(e);}finally{setBusy(false);}
  }

  async function load(){
    try{await desktop.connect();const r=(await desktop.request('config_state').promise).config as State;
      setSt(r);setSaveDir(r.save_dir||'');}
    catch(e){fail(e);}
  }
  useEffect(()=>{void load();},[]);

  async function browse(set:(v:string)=>void){
    const p=await pickFolder();
    if(p)set(p); else notify('폴더 선택이 취소되었거나 데스크톱 앱이 아닙니다. 경로를 직접 붙여넣어 주세요.','info');
  }
  async function saveSave(){
    if(!saveDir.trim())return;setBusy(true);
    try{const r=(await desktop.request('config_set_save_dir',{path:saveDir.trim()}).promise).config as {save_dir:string;created:string[]};
      notify('저장폴더 저장 완료'+(r.created?.length?` · 초기 파일 생성: ${r.created.join(', ')}`:''),'ok');await load();}
    catch(e){fail(e);}finally{setBusy(false);}
  }
  async function req(method:string,params:object,ok:string,after?:()=>void){
    setBusy(true);
    try{const r=(await desktop.request(method,params).promise).config as State;setSt(r);notify(ok,'ok');after&&after();}
    catch(e){fail(e);}finally{setBusy(false);}
  }

  const reportRows=Object.entries(st?.report_paths||{});
  const scanRows=Object.entries(st?.scanresult_roots||{});
  return <section className="panel">
    <div className="section-heading"><div><span className="step">SETTINGS</span><h2>설정</h2></div>
      <button disabled={busy} onClick={load}>새로고침</button></div>
    <p className="hint">웹 앱과 기존 프로그램은 <b>같은 설정 파일</b>을 공유합니다. 경로는 [📁 찾기]로 고르거나 직접 붙여넣을 수 있습니다.</p>

    <div className="subtabs" role="tablist">{TABS.map(([id,label])=>
      <button key={id} role="tab" aria-selected={sub===id} className={sub===id?'active':''} onClick={()=>setSub(id)}>{label}</button>)}</div>

    <div className="subtab-body">
    {sub==='save'&&<>
      <h3>저장폴더 지정 <span className="hint" style={{fontWeight:400}}>— 필수</span></h3>
      <p className="hint">모든 산출물(양식·취합·문서)이 이 폴더 아래 저장됩니다. 처음 지정하면 장비 IP·참고자료·특이사항 초기 파일이 자동 생성됩니다.</p>
      <div className="form-filter" style={{marginTop:14}}>
        <label className="field" style={{flex:1,minWidth:280}}>저장폴더 경로
          <input value={saveDir} placeholder="예: D:\AOI\저장폴더" maxLength={4096} onChange={e=>setSaveDir(e.target.value)}/></label>
        <button onClick={()=>browse(setSaveDir)}>📁 찾기</button>
        <button className="primary" disabled={busy||!saveDir.trim()} onClick={saveSave}>저장</button></div>
      {st?.save_dir&&<p className="hint">현재 저장폴더: <code>{st.save_dir}</code></p>}
    </>}

    {sub==='report'&&<>
      <h3>호기별 배치 Report 폴더 등록</h3>
      <p className="hint">배치 리포트 분석에서 각 호기의 batch report(.htm)가 쌓이는 폴더입니다.</p>
      {reportRows.length>0&&<table className="tbl" style={{marginTop:12}}><tbody>{reportRows.map(([m,p])=><tr key={m}>
        <td style={{width:110,fontWeight:700}}>{m}</td><td><code>{p}</code></td>
        <td style={{width:60}}><button className="linklike" disabled={busy} onClick={()=>req('config_remove',{kind:'report',machine:m},'삭제됨')}>삭제</button></td></tr>)}</tbody></table>}
      <div className="form-filter" style={{marginTop:12}}>
        <label className="field" style={{width:150}}>호기<input value={rMachine} placeholder="AOI-21" maxLength={64} onChange={e=>setRMachine(e.target.value)}/></label>
        <label className="field" style={{flex:1,minWidth:240}}>폴더<input value={rPath} placeholder="예: P:\AOI-21\Reports" maxLength={4096} onChange={e=>setRPath(e.target.value)}/></label>
        <button onClick={()=>browse(setRPath)}>📁 찾기</button>
        <button className="primary" disabled={busy||!rMachine.trim()||!rPath.trim()} onClick={()=>req('config_set_report_path',{machine:rMachine.trim(),path:rPath.trim()},'Report 폴더 등록',()=>{setRMachine('');setRPath('');})}>추가</button></div>
    </>}

    {sub==='auto'&&<>
      <h3>하루 1회 자동 갱신</h3>
      <p className="hint">앱이 켜져 있는 동안 마지막 조사 조건(호기·검색어·기간·지표)으로 하루 한 번 배치 분석을 다시 실행합니다. 기존 프로그램과 같은 설정을 쓰므로 둘이 같은 날 중복 실행하지 않습니다.</p>
      <label className="field checkbox" style={{marginTop:10}}><input type="checkbox" disabled={busy||!st} checked={!!st?.batch_auto}
        onChange={e=>req('config_set_batch_auto',{enabled:e.target.checked},e.target.checked?'자동 갱신을 켰습니다':'자동 갱신을 껐습니다')}/>자동 갱신 사용 (기본 꺼짐)</label>
      <h3 style={{marginTop:24}}>호기별 추가 Report 폴더</h3>
      <p className="hint">기본 Report 폴더 외에 함께 조사할 폴더(예: 백업·보관 폴더)입니다. 호기당 최대 20개.</p>
      {reportRows.length===0?<p className="table-empty">먼저 [배치 Report 폴더]에서 호기를 등록하세요.</p>:<>
        {Object.entries(st?.extra_paths||{}).length>0&&<table className="tbl" style={{marginTop:12}}><tbody>{Object.entries(st?.extra_paths||{}).flatMap(([m,list])=>list.map(p=><tr key={m+p}>
          <td style={{width:110,fontWeight:700}}>{m}</td><td><code>{p}</code></td>
          <td style={{width:60}}><button className="linklike" disabled={busy} onClick={()=>req('config_set_extra_paths',{machine:m,paths:list.filter(x=>x!==p)},'삭제됨')}>삭제</button></td></tr>))}</tbody></table>}
        <div className="form-filter" style={{marginTop:12}}>
          <label className="field" style={{width:150}}>호기<select value={xMachine} onChange={e=>setXMachine(e.target.value)}><option value="">선택…</option>{reportRows.map(([m])=><option key={m} value={m}>{m}</option>)}</select></label>
          <label className="field" style={{flex:1,minWidth:240}}>추가 폴더<input value={xPath} placeholder="예: P:\AOI-21\Reports_backup" maxLength={4096} onChange={e=>setXPath(e.target.value)}/></label>
          <button onClick={()=>browse(setXPath)}>📁 찾기</button>
          <button className="primary" disabled={busy||!xMachine||!xPath.trim()} onClick={()=>req('config_set_extra_paths',{machine:xMachine,paths:[...(st?.extra_paths[xMachine]||[]),xPath.trim()]},'추가 폴더 등록',()=>setXPath(''))}>추가</button></div></>}
    </>}

    {sub==='local'&&<>
      <h3>로컬 작업 폴더</h3>
      <p className="hint">임시 수집물·로그·캐시·분석 결과가 쌓이는 이 PC의 폴더입니다. OneDrive·네트워크 공유는 지정할 수 없습니다(대량 동기화 방지). 고른 폴더 안에 CamtekAOI 폴더가 만들어집니다.</p>
      {local&&<><OpenPath label="현재 위치" path={local.root} folder/>
        <p className="hint">{local.summary}{local.onedrive?' · ⚠ OneDrive 안입니다':''}</p></>}
      <div className="form-filter" style={{marginTop:12}}>
        <label className="field" style={{flex:1,minWidth:280}}>새 위치<input value={localPath} placeholder="예: D:\Work" maxLength={4096} onChange={e=>setLocalPath(e.target.value)}/></label>
        <button onClick={()=>browse(setLocalPath)}>📁 찾기</button>
        <button className="primary" disabled={busy||!localPath.trim()} onClick={()=>localReq('config_set_local_dir',{path:localPath.trim()},r=>`로컬 작업 폴더 변경: ${r.root}`)}>변경</button></div>
      <div className="toolbar"><button disabled={busy||!local} onClick={()=>localReq('config_purge_temp',{},r=>`오래된 임시 폴더 ${r.removed??0}개 정리`)}>오래된 임시 폴더 정리</button></div>
      <p className="hint">정리는 {`6시간`} 넘게 지난 임시 회차 폴더만 지웁니다(진행 중 작업 보호).</p>
    </>}

    {sub==='about'&&<>
      <h3>프로그램 정보</h3>
      {about?<table className="tbl" style={{marginTop:12}}><tbody>
        <tr><td style={{width:140,fontWeight:700}}>엔진 버전</td><td>{about.version}</td></tr>
        <tr><td style={{fontWeight:700}}>사용자</td><td>{about.user}</td></tr>
        <tr><td style={{fontWeight:700}}>설정 파일</td><td><code>{about.config}</code></td></tr></tbody></table>:<p className="hint">불러오는 중…</p>}
      {about?.logs&&<OpenPath label="오류 로그 폴더" path={about.logs} folder/>}
      <p className="hint">문제가 생기면 오류 로그 폴더의 파일을 담당자에게 전달하세요.</p>
    </>}

    {sub==='scan'&&<>
      <h3>호기별 Commonality Scanresult 루트 등록</h3>
      <p className="hint">Commonality 조사에서 그 호기의 Scanresult(백업본 포함)가 있는 상위 폴더입니다.</p>
      {scanRows.length>0&&<table className="tbl" style={{marginTop:12}}><tbody>{scanRows.map(([m,p])=><tr key={m}>
        <td style={{width:110,fontWeight:700}}>{m}</td><td><code>{p}</code></td>
        <td style={{width:60}}><button className="linklike" disabled={busy} onClick={()=>req('config_remove',{kind:'scanresult',machine:m},'삭제됨')}>삭제</button></td></tr>)}</tbody></table>}
      <div className="form-filter" style={{marginTop:12}}>
        <label className="field" style={{width:150}}>호기<input value={sMachine} placeholder="AOI-9" maxLength={64} onChange={e=>setSMachine(e.target.value)}/></label>
        <label className="field" style={{flex:1,minWidth:240}}>폴더<input value={sPath} placeholder="예: W:\AOI-9" maxLength={4096} onChange={e=>setSPath(e.target.value)}/></label>
        <button onClick={()=>browse(setSPath)}>📁 찾기</button>
        <button className="primary" disabled={busy||!sMachine.trim()||!sPath.trim()} onClick={()=>req('config_set_scanresult_root',{machine:sMachine.trim(),path:sPath.trim()},'Scanresult 루트 등록',()=>{setSMachine('');setSPath('');})}>추가</button></div>
    </>}
    </div>
  </section>;
}
