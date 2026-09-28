import {useEffect,useState} from 'react';
import {desktop,pickFolder} from './desktop';
import {notify,fail,LoadFailed} from './ui';
import {errorText} from './desktop';
import {takeSettingsIntent} from './nav';
import {OpenPath,openPath} from './OpenPath';
import {installUpdate,openProgramDir} from './AppUpdate';
import type {AppUpdate} from './desktop';

type Auto={enabled:boolean;interval_hours:number;last_run:string;last_result:string;next_run:string};
type State={save_dir:string;local_dir:string;report_paths:Record<string,string>;scanresult_roots:Record<string,string>;extra_paths:Record<string,string[]>;batch_auto:boolean;batch?:Auto;batch_intervals?:number[];local_root?:string;config_file?:string};
type Edit={kind:'report'|'scanresult'|'extra';machine:string;newMachine:string;path:string;orig?:string};
const TABS:[string,string][]=[['save','저장 폴더'],['local','로컬 작업 폴더'],['report','Batch Report 루트'],['auto','Batch Report 분석 주기 설정'],['scan','Scanresult 루트'],['about','정보']];
const periodLabel=(h:number)=>h%24===0?(h===24?'하루 1회 (24시간)':h===168?'일주일 1회':`${h/24}일마다`):`${h}시간마다`;

export function Settings(){
  // Another screen may open 설정 on a given tab with a machine to register (nav.ts).
  const [intent]=useState(()=>takeSettingsIntent());
  const [sub,setSub]=useState(intent?.sub||'save');
  const [st,setSt]=useState<State>();
  const [saveDir,setSaveDir]=useState('');
  const [busy,setBusy]=useState(false);
  const [rMachine,setRMachine]=useState(''),[rPath,setRPath]=useState('');
  const [sMachine,setSMachine]=useState(intent?.sub==='scan'?intent.machine||'':''),[sPath,setSPath]=useState('');
  const [xMachine,setXMachine]=useState(''),[xPath,setXPath]=useState('');
  type Local={root:string;summary:string;onedrive:boolean;default:string;removed?:number};
  type About={version:string;user:string;config:string;local_root:string;logs:string};
  const [upd,setUpd]=useState<AppUpdate>(),[pubPath,setPubPath]=useState(''),[pubNotes,setPubNotes]=useState('');
  async function checkUpdate(){
    try{const r=(await desktop.request('appupdate_check').promise).appupdate as AppUpdate;setUpd(r);
      notify(r.newer?`새 버전 ${r.available}이 있습니다.`:r.available?`최신 버전입니다(${r.current}).`:'게시된 웹 버전이 없습니다.','info');}
    catch(e){fail(e);}
  }
  async function publishPackage(){
    setBusy(true);
    try{const r=(await desktop.request('appupdate_publish',{path:pubPath.trim(),notes:pubNotes}).promise).appupdate as {version:string;filename:string};
      notify(`${r.version} 게시 완료 (${r.filename}). 다른 PC는 다음 실행 때 알림을 받습니다.`,'ok');setPubNotes('');}
    catch(e){fail(e);}finally{setBusy(false);}
  }
  const [local,setLocal]=useState<Local>(),[localPath,setLocalPath]=useState(''),[about,setAbout]=useState<About>();
  const [subError,setSubError]=useState(''),[subTry,setSubTry]=useState(0);
  useEffect(()=>{
    setSubError('');
    if(sub==='local')desktop.request('config_local_state').promise.then(r=>setLocal(r.config as Local)).catch(e=>setSubError(errorText(e)));
    if(sub==='about')desktop.request('config_about').promise.then(r=>setAbout(r.config as About)).catch(e=>setSubError(errorText(e)));
  },[sub,subTry]);
  async function localReq(method:string,params:object,ok:(r:Local)=>string){
    setBusy(true);
    try{const r=(await desktop.request(method,params).promise).config as Local;setLocal(r);notify(ok(r),'ok');}
    catch(e){fail(e);}finally{setBusy(false);}
  }

  const [loadError,setLoadError]=useState('');
  async function load(){
    setLoadError('');
    try{await desktop.connect();const r=(await desktop.request('config_state').promise).config as State;
      setSt(r);setSaveDir(r.save_dir||'');}
    catch(e){setLoadError(errorText(e));}
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

  // '수정': one row at a time becomes editable (machine name + folder).
  const [edit,setEdit]=useState<Edit>();
  async function saveEdit(){
    if(!edit||!st)return;
    if(edit.kind==='extra'){
      const list=(st.extra_paths[edit.machine]||[]).map(p=>p===edit.orig?edit.path.trim():p);
      await req('config_set_extra_paths',{machine:edit.machine,paths:list},'추가 폴더를 수정했습니다',()=>setEdit(undefined));
    }else{
      await req('config_edit_root',{kind:edit.kind,machine:edit.machine,new_machine:edit.newMachine.trim(),path:edit.path.trim()},
        `${edit.newMachine.trim()} 경로를 수정했습니다`,()=>setEdit(undefined));
    }
  }
  // A plain render function (not a component) so the edit inputs keep focus while typing.
  function rootRow(kind:Edit['kind'],machine:string,path:string,orig?:string){
    const key=kind+machine+(orig||'');
    const editing=edit&&edit.kind===kind&&edit.machine===machine&&(kind!=='extra'||edit.orig===orig);
    if(editing)return <tr key={key} className="row-now"><td colSpan={3}><div className="form-filter" style={{margin:0}}>
      {kind!=='extra'?<label className="field" style={{width:130}}>호기<input value={edit.newMachine} maxLength={64} aria-label={`${machine} 새 호기 이름`}
        onChange={e=>setEdit(o=>o&&{...o,newMachine:e.target.value})}/></label>:<b style={{alignSelf:'center'}}>{machine}</b>}
      <label className="field" style={{flex:1,minWidth:220}}>폴더<input value={edit.path} maxLength={4096} aria-label={`${machine} 새 폴더`}
        onChange={e=>setEdit(o=>o&&{...o,path:e.target.value})}/></label>
      <button onClick={()=>browse(v=>setEdit(o=>o&&{...o,path:v}))}>📁 찾기</button>
      <button className="primary" disabled={busy||!edit.path.trim()||(kind!=='extra'&&!edit.newMachine.trim())} onClick={saveEdit}>저장</button>
      <button disabled={busy} onClick={()=>setEdit(undefined)}>취소</button></div></td></tr>;
    const remove=kind==='extra'
      ?()=>req('config_set_extra_paths',{machine,paths:(st?.extra_paths[machine]||[]).filter(x=>x!==orig)},'삭제됨')
      :()=>req('config_remove',{kind:kind==='report'?'report':'scanresult',machine},'삭제됨');
    return <tr key={key}><td style={{width:110,fontWeight:700}}>{machine}</td><td><code>{path}</code></td>
      <td style={{width:110,whiteSpace:'nowrap'}}><button className="linklike" disabled={busy} aria-label={`${machine} 수정`}
        onClick={()=>setEdit({kind,machine,newMachine:machine,path,orig})}>수정</button>{' '}
        <button className="linklike" disabled={busy} aria-label={`${machine} 삭제`} onClick={remove}>삭제</button></td></tr>;
  }
  const reportRows=Object.entries(st?.report_paths||{});
  const scanRows=Object.entries(st?.scanresult_roots||{});
  return <section className="panel">
    <div className="section-heading"><div><span className="step">SETTINGS</span><h2>설정</h2></div>
      <button disabled={busy} onClick={load}>새로고침</button></div>
    <p className="hint">웹 앱과 기존 프로그램은 <b>같은 설정 파일</b>을 공유합니다. 경로는 [📁 찾기]로 고르거나 직접 붙여넣을 수 있습니다.</p>

    <div className="subtabs" role="tablist">{TABS.map(([id,label])=>
      <button key={id} role="tab" aria-selected={sub===id} className={sub===id?'active':''} onClick={()=>setSub(id)}>{label}</button>)}</div>

    {loadError&&!st&&<LoadFailed message={loadError} onRetry={()=>void load()}/>}
    {st&&<div className="current-settings" aria-label="현재 설정">
      <h3>현재 설정</h3>
      <table className="tbl"><tbody>
        <tr><th>저장 폴더</th><td>{st.save_dir?<code>{st.save_dir}</code>:<b className="warn">미지정 — [저장 폴더] 탭에서 지정하세요</b>}</td>
          <td>{st.save_dir&&<button className="linklike" onClick={()=>openPath(st.save_dir)}>폴더 열기</button>}</td></tr>
        <tr><th>로컬 작업 폴더</th><td><code>{st.local_root||st.local_dir||'—'}</code>{!st.local_dir&&<span className="hint"> (기본값)</span>}</td>
          <td>{st.local_root&&!st.local_root.startsWith('(')&&<button className="linklike" onClick={()=>openPath(st.local_root!)}>폴더 열기</button>}</td></tr>
        <tr><th>Batch Report 루트</th><td>{reportRows.length?`${reportRows.length}개 호기 · ${reportRows.map(([m])=>m).join(', ')}`:'없음'}
          {Object.keys(st.extra_paths||{}).length>0&&<span className="hint"> · 추가 폴더 {Object.values(st.extra_paths).flat().length}개</span>}</td>
          <td><button className="linklike" onClick={()=>setSub('report')}>보기</button></td></tr>
        <tr><th>Batch Report 자동 분석</th><td>{st.batch_auto?`켜짐 · ${periodLabel(st.batch?.interval_hours??24)}`:'꺼짐'}</td>
          <td><button className="linklike" onClick={()=>setSub('auto')}>보기</button></td></tr>
        <tr><th>Scanresult 루트</th><td>{scanRows.length?`${scanRows.length}개 호기 · ${scanRows.map(([m])=>m).join(', ')}`:'없음'}</td>
          <td><button className="linklike" onClick={()=>setSub('scan')}>보기</button></td></tr>
        <tr><th>설정 파일</th><td><code>{st.config_file||'—'}</code></td><td/></tr>
      </tbody></table></div>}
    <div className="subtab-body">
    {sub==='save'&&<>
      <h3>저장 폴더 지정 <span className="hint" style={{fontWeight:400}}>— 필수</span></h3>
      <p className="hint">모든 산출물(양식·취합·문서)이 이 폴더 아래 저장됩니다. 처음 지정하면 장비 IP·참고자료·특이사항 초기 파일이 자동 생성됩니다.</p>
      <div className="form-filter" style={{marginTop:14}}>
        <label className="field" style={{flex:1,minWidth:280}}>저장폴더 경로
          <input value={saveDir} placeholder="예: D:\AOI\저장폴더" maxLength={4096} onChange={e=>setSaveDir(e.target.value)}/></label>
        <button onClick={()=>browse(setSaveDir)}>📁 찾기</button>
        <button className="primary" disabled={busy||!saveDir.trim()} onClick={saveSave}>저장</button></div>
      {st?.save_dir&&<p className="hint">현재 저장폴더: <code>{st.save_dir}</code></p>}
    </>}

    {sub==='report'&&<>
      <h3>호기별 Batch Report 루트 등록</h3>
      <p className="hint">배치 리포트 분석에서 각 호기의 batch report(.htm)가 쌓이는 폴더입니다.</p>
      {reportRows.length>0&&<table className="tbl" style={{marginTop:12}}><tbody>{reportRows.map(([m,p])=>rootRow('report',m,p))}</tbody></table>}
      <div className="form-filter" style={{marginTop:12}}>
        <label className="field" style={{width:150}}>호기<input value={rMachine} placeholder="AOI-21" maxLength={64} onChange={e=>setRMachine(e.target.value)}/></label>
        <label className="field" style={{flex:1,minWidth:240}}>폴더<input value={rPath} placeholder="예: P:\AOI-21\Reports" maxLength={4096} onChange={e=>setRPath(e.target.value)}/></label>
        <button onClick={()=>browse(setRPath)}>📁 찾기</button>
        <button className="primary" disabled={busy||!rMachine.trim()||!rPath.trim()} onClick={()=>req('config_set_report_path',{machine:rMachine.trim(),path:rPath.trim()},'Report 폴더 등록',()=>{setRMachine('');setRPath('');})}>추가</button></div>
      <h3 style={{marginTop:24}}>호기별 추가 Report 폴더</h3>
      <p className="hint">기본 Report 폴더 외에 함께 조사할 폴더(예: 백업·보관 폴더)입니다. 호기당 최대 20개.</p>
      {reportRows.length===0?<p className="table-empty">먼저 위에서 호기별 Batch Report 루트를 등록하세요.</p>:<>
        {Object.entries(st?.extra_paths||{}).length>0&&<table className="tbl" style={{marginTop:12}}><tbody>{Object.entries(st?.extra_paths||{}).flatMap(([m,list])=>list.map(p=>rootRow('extra',m,p,p)))}</tbody></table>}
        <div className="form-filter" style={{marginTop:12}}>
          <label className="field" style={{width:150}}>추가 폴더 호기<select value={xMachine} onChange={e=>setXMachine(e.target.value)}><option value="">선택…</option>{reportRows.map(([m])=><option key={m} value={m}>{m}</option>)}</select></label>
          <label className="field" style={{flex:1,minWidth:240}}>추가 폴더<input value={xPath} placeholder="예: P:\AOI-21\Reports_backup" maxLength={4096} onChange={e=>setXPath(e.target.value)}/></label>
          <button onClick={()=>browse(setXPath)}>📁 찾기</button>
          <button className="primary" disabled={busy||!xMachine||!xPath.trim()} onClick={()=>req('config_set_extra_paths',{machine:xMachine,paths:[...(st?.extra_paths[xMachine]||[]),xPath.trim()]},'추가 폴더 등록',()=>setXPath(''))}>추가 폴더 등록</button></div></>}
    </>}

    {sub==='auto'&&<>
      <h3>Batch Report 자동 분석</h3>
      <p className="hint">앱이 켜져 있는 동안 마지막 조사 조건(호기·검색어·기간·지표)으로 배치 리포트 분석을 주기마다 다시 실행합니다.
        실행 기록은 기존 프로그램과 공유하므로 두 프로그램이 같은 주기 안에 중복 실행하지 않습니다(기존 프로그램은 항상 하루 1회).</p>
      <label className="field checkbox" style={{marginTop:10}}><input type="checkbox" disabled={busy||!st} checked={!!st?.batch_auto}
        onChange={e=>req('config_set_batch_auto',{enabled:e.target.checked},e.target.checked?'자동 분석을 켰습니다':'자동 분석을 껐습니다')}/>자동 분석 사용 (기본 꺼짐)</label>
      <div className="form-filter" style={{marginTop:12}}>
        <label className="field" style={{width:220}}>분석 주기<select disabled={busy||!st} value={st?.batch?.interval_hours??24}
          onChange={e=>req('config_set_batch_auto',{enabled:!!st?.batch_auto,interval_hours:Number(e.target.value)},'분석 주기를 저장했습니다')}>
          {(st?.batch_intervals||[24]).map(h=><option key={h} value={h}>{periodLabel(h)}</option>)}</select></label></div>
      <table className="tbl" style={{marginTop:12}}><tbody>
        <tr><td style={{width:140,fontWeight:700}}>마지막 실행</td><td>{st?.batch?.last_run||'—'}{st?.batch?.last_result?` · ${st.batch.last_result}`:''}</td></tr>
        <tr><td style={{fontWeight:700}}>다음 실행</td><td>{st?.batch_auto?(st?.batch?.next_run||'앱을 켜 두면 곧 실행'):'꺼짐'}</td></tr></tbody></table>
      <p className="hint">분석 조건은 [배치 리포트 분석] 탭에서 마지막으로 조사한 조건을 그대로 씁니다.</p>
    </>}

    {sub==='local'&&<>
      <h3>로컬 작업 폴더</h3>
      <p className="hint">임시 수집물·로그·캐시·분석 결과가 쌓이는 이 PC의 폴더입니다. OneDrive·네트워크 공유는 지정할 수 없습니다(대량 동기화 방지). 고른 폴더 안에 CamtekAOI 폴더가 만들어집니다.</p>
      {!local&&subError&&<LoadFailed message={subError} onRetry={()=>setSubTry(n=>n+1)}/>}
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
        <tr><td style={{fontWeight:700}}>설정 파일</td><td><code>{about.config}</code></td></tr></tbody></table>:subError?<LoadFailed message={subError} onRetry={()=>setSubTry(n=>n+1)}/>:<p className="hint">불러오는 중…</p>}
      {about?.logs&&<OpenPath label="오류 로그 폴더" path={about.logs} folder/>}
      <h3 style={{marginTop:24}}>업데이트</h3>
      <div className="toolbar"><button onClick={checkUpdate}>업데이트 확인</button><button onClick={openProgramDir}>게시 폴더 열기</button>
        {upd?.newer&&<button className="primary" disabled={busy||!upd.installed} onClick={()=>void installUpdate()}>지금 {upd.available}(으)로 업데이트</button>}</div>
      {upd&&<p className="hint">현재 {upd.current} · 게시 {upd.available||'없음'}{upd.changelog?` — ${upd.changelog}`:''}</p>}
      <details style={{marginTop:16}}><summary>개발자: 새 버전 게시</summary>
        <p className="hint">빌드된 패키지 폴더(GitHub Actions 아티팩트를 압축 해제한 폴더 또는 build_desktop.py 결과)를 고르면 zip 1개로 묶어 게시 폴더에 올립니다. 폴더 안의 package-manifest.json 으로 모든 파일을 검증하고, 버전도 그 파일에서 읽습니다.</p>
        <div className="form-filter"><label className="field" style={{flex:1,minWidth:260}}>패키지 폴더<input value={pubPath} maxLength={4096} onChange={e=>setPubPath(e.target.value)}/></label>
          <button onClick={()=>browse(setPubPath)}>📁 찾기</button></div>
        <label className="field">변경 내용<textarea rows={3} maxLength={4000} value={pubNotes} onChange={e=>setPubNotes(e.target.value)}/></label>
        <div className="toolbar"><button className="primary" disabled={busy||!pubPath.trim()} onClick={publishPackage}>게시</button></div>
      </details>
      <p className="hint">문제가 생기면 오류 로그 폴더의 파일을 담당자에게 전달하세요.</p>
    </>}

    {sub==='scan'&&<>
      <h3>호기별 Commonality Scanresult 루트 등록</h3>
      <p className="hint">Commonality 조사에서 그 호기의 Scanresult(백업본 포함)가 있는 상위 폴더입니다.</p>
      {scanRows.length>0&&<table className="tbl" style={{marginTop:12}}><tbody>{scanRows.map(([m,p])=>rootRow('scanresult',m,p))}</tbody></table>}
      <div className="form-filter" style={{marginTop:12}}>
        <label className="field" style={{width:150}}>호기<input value={sMachine} placeholder="AOI-9" maxLength={64} onChange={e=>setSMachine(e.target.value)}/></label>
        <label className="field" style={{flex:1,minWidth:240}}>폴더<input value={sPath} placeholder="예: W:\AOI-9" maxLength={4096} onChange={e=>setSPath(e.target.value)}/></label>
        <button onClick={()=>browse(setSPath)}>📁 찾기</button>
        <button className="primary" disabled={busy||!sMachine.trim()||!sPath.trim()} onClick={()=>req('config_set_scanresult_root',{machine:sMachine.trim(),path:sPath.trim()},'Scanresult 루트 등록',()=>{setSMachine('');setSPath('');})}>추가</button></div>
    </>}
    </div>
  </section>;
}
