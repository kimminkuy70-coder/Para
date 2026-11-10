import {useEffect,useState} from 'react';
import {desktop,pickFolder,pickFile} from './desktop';
import {notify,fail,LoadFailed} from './ui';
import {errorText} from './desktop';
import {takeSettingsIntent} from './nav';
import {OpenPath,openPath} from './OpenPath';
import {installUpdate,openProgramDir} from './AppUpdate';
import type {AppUpdate} from './desktop';
import {useDev,setDevOn,saveDrafts,dropDrafts} from './devmode';
import {DevHelp,DevOff} from './DevHelp';
import {ScanBackupBar,useScanBackup} from './ScanBackup';
import {startTour} from './Tour';
import {openBatchAutoSettings} from './batchAuto';
import {periodLabel} from './BatchAutoPanel';
import {KlaRootsSettings,useKlaState} from './KlaSettings';
import {MemoPick,type MemoMachine} from './MemoPick';
import {AoiDriveScan} from './AoiDriveScan';

type Auto={enabled:boolean;interval_hours:number;time?:string;last_run:string;last_result:string;next_run:string};
type Aoi={machine:string;root:string;report:string;scanresult:string;legacy:boolean;extra:{report:string[];scanresult:string[]}};
type State={save_dir:string;share_root?:string;program_dir?:string;cache_share_dir?:string;local_dir:string;aoi:Aoi[];batch_auto:boolean;batch?:Auto;batch_intervals?:number[];local_root?:string;config_file?:string;memo_machines?:MemoMachine[]};
type ExtraKind='report'|'scanresult';
type Edit={kind:'aoi'|'extra';machine:string;newMachine:string;path:string;orig?:string;extraKind?:ExtraKind};
// Batch Report 분석 주기 설정은 CAMTEK › 자동 분석 및 취합 › [Batch Report 자동 분석] 탭으로 옮겼다(#39).
const TABS:[string,string][]=[['save','저장 폴더'],['local','로컬 작업 폴더'],['aoi','AOI 장비 호기 루트'],['about','정보']];
const EXTRA_LABEL:Record<ExtraKind,string>={report:'Batch Report',scanresult:'Scanresult'};
const baseName=(p:string)=>p.split(/[\\/]/).filter(Boolean).pop()||p;
// 이전 화면 이름('report'·'scan')으로 들어와도 통합 탭을 연다. 'kla' = AOI 장비 호기 루트 › KLA(#32).
const subOf=(s?:string)=>s==='report'||s==='scan'||s==='kla'?'aoi':s&&TABS.some(([id])=>id===s)?s:'save';
type AoiVendor='CAMTEK'|'KLA';

export function Settings(){
  const [scanBackup]=useScanBackup();
  // Another screen may open 설정 on a given tab with a machine to register (nav.ts).
  const [intent]=useState(()=>takeSettingsIntent());
  const [sub,setSub]=useState(subOf(intent?.sub));
  // AOI 장비 호기 루트 = 장비 회사별 하위 탭(#32): CAMTEK(호기 루트 · 추가 폴더) / KLA(장비 폴더 · Defect 이미지 백업본).
  const [aoiVendor,setAoiVendor]=useState<AoiVendor>(intent?.sub==='kla'?'KLA':'CAMTEK');
  const [kla]=useKlaState();
  const [st,setSt]=useState<State>();
  const [saveDir,setSaveDir]=useState('');
  const [busy,setBusy]=useState(false);
  const [aMachine,setAMachine]=useState(subOf(intent?.sub)==='aoi'?intent?.machine||'':''),[aPath,setAPath]=useState('');
  const [xMachine,setXMachine]=useState(''),[xKind,setXKind]=useState<ExtraKind>('report'),[xPath,setXPath]=useState('');
  type Local={root:string;summary:string;onedrive:boolean;default:string;removed?:number};
  type About={version:string;user:string;config:string;local_root:string;logs:string;diag_log?:string};
  const [upd,setUpd]=useState<AppUpdate>(),[pubPath,setPubPath]=useState(''),[pubNotes,setPubNotes]=useState('');
  async function checkUpdate(){
    try{const r=(await desktop.request('appupdate_check').promise).appupdate as AppUpdate;setUpd(r);
      notify(r.newer?`새 버전 ${r.available}이 있습니다.`:r.available?`최신 버전입니다(${r.current}).`:`확인할 수 있는 릴리스가 없습니다${r.error?` (${r.error})`:''}.`,'info');}
    catch(e){fail(e);}
  }
  async function publishPackage(){
    setBusy(true);
    try{const r=(await desktop.request('appupdate_publish',{path:pubPath.trim(),notes:pubNotes}).promise).appupdate as {version:string;file:string};
      notify(`${r.version} 게시 완료 (${r.file}). GitHub 에 연결되지 않는 PC는 다음 실행 때 알림을 받습니다.`,'ok');setPubNotes('');setPubPath('');}
    catch(e){fail(e);}finally{setBusy(false);}
  }
  const [diagZip,setDiagZip]=useState('');
  // 개발자 기능(Batch Report 중복 Pass 직접 선택): 저장 안 한 선택이 있으면 끄기 전에 묻고, 조사 중에는 잠근다.
  const dev=useDev();
  const [devOff,setDevOff]=useState(false),[devHelp,setDevHelp]=useState(false);
  function toggleDev(on:boolean){
    if(!on&&dev.drafts){setDevOff(true);return;}
    setDevOn(on);
    notify(on?'개발자 기능을 켰습니다 — Batch Report Lot 창에서 중복 Pass를 직접 고칠 수 있습니다. 저장해야 결과에 반영됩니다.'
      :'개발자 기능을 껐습니다 — 결과 숫자는 그대로입니다(저장된 사람 선택은 계속 적용).','info');
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
      setSt(r);setSaveDir(r.share_root&&r.save_dir&&/[\\/]docs$/i.test(r.save_dir)?r.share_root:r.save_dir||'');}
    catch(e){setLoadError(errorText(e));}
  }
  useEffect(()=>{void load();},[]);
  // 튜토리얼이 설정 하위 탭을 연다(Tour.tsx).
  useEffect(()=>{const go=(e:Event)=>{const d=(e as CustomEvent<string>).detail;setSub(subOf(d));
    if(d==='kla')setAoiVendor('KLA');else if(d==='aoi')setAoiVendor('CAMTEK');};window.addEventListener('para:settings-sub',go);return()=>window.removeEventListener('para:settings-sub',go);},[]);

  async function browse(set:(v:string)=>void){
    const p=await pickFolder();
    if(p)set(p); else notify('폴더 선택이 취소되었거나 데스크톱 앱이 아닙니다. 경로를 직접 붙여넣어 주세요.','info');
  }
  async function saveSave(){
    if(!saveDir.trim())return;setBusy(true);
    try{const r=(await desktop.request('config_set_save_dir',{path:saveDir.trim()}).promise).config as {save_dir:string;chosen:string;created:string[]};
      notify(`저장폴더 저장 완료 · 문서 폴더: ${r.save_dir}`+(r.created?.length?` · 초기 파일 생성: ${r.created.join(', ')}`:''),'ok');await load();}
    catch(e){fail(e);}finally{setBusy(false);}
  }
  async function req(method:string,params:object,ok:string,after?:()=>void){
    setBusy(true);
    try{const r=(await desktop.request(method,params).promise).config as State&{notice?:string};setSt(r);
      notify(r.notice?`${ok} — ${r.notice}`:ok,r.notice&&/찾지 못했습니다/.test(r.notice)?'info':'ok');after&&after();}
    catch(e){fail(e);}finally{setBusy(false);}
  }

  // '수정': one row at a time becomes editable (machine name + folder).
  const [edit,setEdit]=useState<Edit>();
  const aois=st?.aoi||[];
  const extrasOf=(m:string,k:ExtraKind)=>aois.find(a=>a.machine===m)?.extra[k]||[];
  async function saveEdit(){
    if(!edit||!st)return;
    if(edit.kind==='extra'){
      const k=edit.extraKind!;
      const list=extrasOf(edit.machine,k).map(p=>p===edit.orig?edit.path.trim():p);
      await req('config_set_aoi_extra',{machine:edit.machine,kind:k,paths:list},'추가 폴더를 수정했습니다',()=>setEdit(undefined));
    }else{
      await req('config_edit_aoi_root',{machine:edit.machine,new_machine:edit.newMachine.trim(),path:edit.path.trim()},
        `${edit.newMachine.trim()} 호기 루트를 수정했습니다`,()=>setEdit(undefined));
    }
  }
  function editRow(key:string,cols:number){
    if(!edit)return null;
    return <tr key={key} className="row-now"><td colSpan={cols}><div className="form-filter" style={{margin:0}}>
      {edit.kind==='aoi'?<label className="field" style={{width:130}}>호기<input value={edit.newMachine} maxLength={64} aria-label={`${edit.machine} 새 호기 이름`}
        onChange={e=>setEdit(o=>o&&{...o,newMachine:e.target.value})}/></label>
        :<b style={{alignSelf:'center'}}>{edit.machine} · {EXTRA_LABEL[edit.extraKind!]}</b>}
      <label className="field" style={{flex:1,minWidth:220}}>폴더<input value={edit.path} maxLength={4096} aria-label={`${edit.machine} 새 폴더`}
        onChange={e=>setEdit(o=>o&&{...o,path:e.target.value})}/></label>
      <button onClick={()=>browse(v=>setEdit(o=>o&&{...o,path:v}))}>📁 찾기</button>
      <button className="primary" disabled={busy||!edit.path.trim()||(edit.kind==='aoi'&&!edit.newMachine.trim())} onClick={saveEdit}>저장</button>
      <button disabled={busy} onClick={()=>setEdit(undefined)}>취소</button></div></td></tr>;
  }
  const actions=(label:string,onEdit:()=>void,onRemove:()=>void)=><td style={{width:110,whiteSpace:'nowrap'}}>
    <button className="linklike" disabled={busy} aria-label={`${label} 수정`} onClick={onEdit}>수정</button>{' '}
    <button className="linklike" disabled={busy} aria-label={`${label} 삭제`} onClick={onRemove}>삭제</button></td>;
  // A plain render function (not a component) so the edit inputs keep focus while typing.
  function aoiRow(a:Aoi){
    const key='aoi'+a.machine;
    if(edit?.kind==='aoi'&&edit.machine===a.machine)return editRow(key,4);
    return <tr key={key}><td style={{width:110,fontWeight:700}}>{a.machine}</td>
      <td><code>{a.root||'—'}</code>{a.legacy&&<div className="hint">기존 설정(따로 등록) — [수정]에서 호기 폴더를 저장하면 통합됩니다.</div>}</td>
      <td className="hint" style={{whiteSpace:'nowrap'}}>
        <div>Reports: {a.report?<code>{baseName(a.report)}</code>:<b className="warn">없음</b>}</div>
        <div>Scanresult: {a.scanresult?`자동 탐색(${scanBackup===false?'원본만':'백업본 포함'})`:<b className="warn">미등록</b>}</div></td>
      {actions(a.machine,()=>setEdit({kind:'aoi',machine:a.machine,newMachine:a.machine,path:a.root}),
        ()=>{if(window.confirm(`${a.machine} 호기 루트와 추가 폴더 등록을 모두 삭제할까요? (폴더 자체는 지우지 않습니다)`))
          void req('config_remove_aoi',{machine:a.machine},`${a.machine} 삭제됨`);})}</tr>;
  }
  function extraRow(m:string,k:ExtraKind,p:string){
    const key='x'+m+k+p;
    if(edit?.kind==='extra'&&edit.machine===m&&edit.extraKind===k&&edit.orig===p)return editRow(key,4);
    return <tr key={key}><td style={{width:110,fontWeight:700}}>{m}</td><td style={{width:120}}>{EXTRA_LABEL[k]}</td><td><code>{p}</code></td>
      {actions(`${m} ${p}`,()=>setEdit({kind:'extra',machine:m,newMachine:m,path:p,orig:p,extraKind:k}),
        ()=>void req('config_set_aoi_extra',{machine:m,kind:k,paths:extrasOf(m,k).filter(x=>x!==p)},'추가 폴더 삭제됨'))}</tr>;
  }
  const extraRows=aois.flatMap(a=>(['report','scanresult'] as ExtraKind[]).flatMap(k=>a.extra[k].map(p=>extraRow(a.machine,k,p))));
  const extraCount=aois.reduce((n,a)=>n+a.extra.report.length+a.extra.scanresult.length,0);
  return <section className="panel">
    <div className="section-heading"><div><span className="step">SETTINGS</span><h2>설정</h2></div>
      <button disabled={busy} onClick={load}>새로고침</button></div>
    <div className="tour-entry" data-tour="settings:tour"><span className="tour-entry-ic" aria-hidden="true">🎓</span><div><b>튜토리얼</b><small>처음 쓰는 PC라면 초기 설정(저장 폴더 · 장비 연결)을 화면에서 따라 하세요. 안내만 하고 아무것도 바꾸지 않습니다.</small></div>
      <span className="grow"/><button type="button" className="primary" onClick={()=>startTour('setup')}>초기 설정 튜토리얼</button><button type="button" onClick={()=>startTour('features')}>기능 둘러보기</button></div>
    <p className="hint">웹 앱과 기존 프로그램은 <b>같은 설정 파일</b>을 공유합니다. 경로는 [📁 찾기]로 고르거나 직접 붙여넣을 수 있습니다.</p>

    {loadError&&!st&&<LoadFailed message={loadError} onRetry={()=>void load()}/>}
    {st&&<details className="current-settings" aria-label="현재 설정" data-tour="settings:current">
      <summary><h3>현재 설정</h3><span className="hint">{st.save_dir?'저장 폴더 지정됨':'⚠ 저장 폴더 미지정'} · AOI 호기 {aois.length}대 · 자동 분석 {st.batch_auto?'켜짐':'꺼짐'}</span></summary>
      <table className="tbl"><tbody>
        <tr><th>저장 폴더</th><td>{st.save_dir?<code>{st.save_dir}</code>:<b className="warn">미지정 — [저장 폴더] 탭에서 지정하세요</b>}</td>
          <td>{st.save_dir&&<button className="linklike" onClick={()=>openPath(st.save_dir)}>폴더 열기</button>}</td></tr>
        <tr><th>로컬 작업 폴더</th><td><code>{st.local_root||st.local_dir||'—'}</code>{!st.local_dir&&<span className="hint"> (기본값)</span>}</td>
          <td>{st.local_root&&!st.local_root.startsWith('(')&&<button className="linklike" onClick={()=>openPath(st.local_root!)}>폴더 열기</button>}</td></tr>
        <tr><th>AOI 장비 호기 루트 · CAMTEK</th><td>{aois.length?`${aois.length}개 호기 · ${aois.map(a=>a.machine).join(', ')}`:'없음'}
          {extraCount>0&&<span className="hint"> · 추가 폴더 {extraCount}개</span>}</td>
          <td><button className="linklike" onClick={()=>{setSub('aoi');setAoiVendor('CAMTEK');}}>보기</button></td></tr>
        <tr><th>AOI 장비 호기 루트 · KLA</th><td>{kla?(kla.roots.length?`${kla.roots.length}개 장비 · ${kla.roots.map(r=>r.name).join(', ')}`:'없음'):'—'}
          {kla&&kla.roots.length>0&&<span className="hint"> · Defect 이미지 백업본 {kla.backup?`포함(백업 폴더 ${kla.roots.reduce((n,r)=>n+r.backups.length,0)}개)`:'제외'}</span>}</td>
          <td><button className="linklike" onClick={()=>{setSub('aoi');setAoiVendor('KLA');}}>보기</button></td></tr>
        <tr><th>Batch Report 자동 분석</th><td>{st.batch_auto?`켜짐 · ${periodLabel(st.batch?.interval_hours??24)}${st.batch?.time&&(st.batch.interval_hours??24)%24===0?` · ${st.batch.time}`:''}`:'꺼짐'}</td>
          <td><button className="linklike" onClick={openBatchAutoSettings} title="CAMTEK › 자동 분석 및 취합 › Batch Report 자동 분석">보기</button></td></tr>
        <tr><th>설정 파일</th><td><code>{st.config_file||'—'}</code></td><td/></tr>
      </tbody></table></details>}

    <div className="subtabs" role="tablist">{TABS.map(([id,label])=>
      <button key={id} data-tour={'settings:tab:'+id} role="tab" aria-selected={sub===id} className={sub===id?'active':''} onClick={()=>setSub(id)}>{label}</button>)}</div>

    <div className="subtab-body">
    {sub==='save'&&<>
      <h3>저장 폴더 지정 <span className="hint" style={{fontWeight:400}}>— 필수</span></h3>
      <p className="hint" data-tour="settings:onedrive"><b>다른 사람과 공유하는 산출물이 OneDrive 폴더에 저장됩니다. 팀이 함께 쓰는 OneDrive 공유 폴더(<code>docs</code> 의 상위 폴더)를 지정해 주세요.</b><br/>
        개발자가 보낸 OneDrive 공유 링크를 Edge 로 열고 [내 파일에 바로 가기 추가] → 파일 탐색기 › OneDrive - 회사이름 아래에 생긴 그 폴더를 고르면 됩니다.<br/>
        예: <code>C:\Users\이름\OneDrive - 회사\0. Camtek AOI parameter 취합\</code> 를 고르면 그 안의 <code>docs</code>(공유 문서) · <code>프로그램</code>(새 버전) · <code>캐시공유</code>(Batch Report 캐시)를 알아서 찾습니다.
        <code>docs</code> 폴더를 직접 골라도 됩니다(예전 설정 그대로).</p>
      <table className="tbl" style={{marginTop:8}}><tbody>
        <tr><th style={{width:170}}>공유 문서</th><td>장비 IP 주소 · 참고자료 · 특이사항 · 변환계수 · 장비화면이름 (.xlsx) — 처음 지정하면 장비 IP·참고자료·특이사항이 자동 생성됩니다</td></tr>
        <tr><th>Recipe 양식</th><td><code>양식\{'{레시피}'}\{'{생성시각}'}\</code> — 확정 양식 1개 + 관련파일(원본·수정본)</td></tr>
        <tr><th>파라미터 값 취합</th><td><code>파라미터 값 취합\파라미터 값 취합_{'{시각}'}.xlsx</code> — Recipe 업데이트 1회당 1개</td></tr>
        <tr><th>자동 분석 및 취합</th><td><code>감시설정.json</code> · <code>자동감시\</code> 변경보고서(변경이 있을 때만)·감시로그</td></tr>
        <tr><th>동시 접속 정보</th><td><code>_세션\</code> 접속자·작업 잠금, 편집 중인 문서 옆 <code>.editlock</code></td></tr>
        <tr><th>새 버전 게시</th><td>저장 폴더 <b>옆</b>의 <code>프로그램\</code> 폴더(개발자가 게시한 설치 파일)</td></tr>
        <tr><th>Batch Report 캐시 공유</th><td>저장 폴더 <b>옆</b>의 <code>캐시공유\</code> 폴더 — 개발자가 올린 캐시 zip(최근 3개) · <code>캐시정보.json</code></td></tr>
      </tbody></table>
      <p className="hint">Commonality 조사 결과·Batch Report 분석 결과·장비 수집 임시 파일·로그는 OneDrive 가 아니라 <b>로컬 작업 폴더</b>에 저장됩니다(대량 동기화 방지).</p>
      <div className="form-filter" style={{marginTop:14}}>
        <label className="field" style={{flex:1,minWidth:280}} data-tour="settings:save-path">OneDrive 공유 폴더 경로 (docs 의 상위 폴더)
          <input value={saveDir} placeholder="예: C:\Users\이름\OneDrive - 회사\0. Camtek AOI parameter 취합" maxLength={4096} onChange={e=>setSaveDir(e.target.value)}/></label>
        <button onClick={()=>browse(setSaveDir)}>📁 찾기</button>
        <button className="primary" data-tour="settings:save-btn" disabled={busy||!saveDir.trim()} onClick={saveSave}>저장</button></div>
      <p className="hint">고른 폴더 바로 아래에 <code>docs</code> 가 있으면 그 docs 를 씁니다. 없고 고른 폴더가 새 폴더이면 그 안에 <code>docs</code> 를 만들어 씁니다.</p>
      {st?.save_dir&&<table className="tbl" aria-label="인식한 폴더" style={{marginTop:8}}><tbody>
        <tr><th style={{width:170}}>공유 문서 (docs)</th><td><code>{st.save_dir}</code></td></tr>
        {st.program_dir&&<tr><th>새 버전 게시</th><td><code>{st.program_dir}</code></td></tr>}
        {st.cache_share_dir&&<tr><th>Batch Report 캐시 공유</th><td><code>{st.cache_share_dir}</code></td></tr>}</tbody></table>}
    </>}

    {sub==='aoi'&&<div className="subtabs vendor-sub" role="tablist" aria-label="장비 회사">{(['CAMTEK','KLA'] as AoiVendor[]).map(v=>
      <button key={v} role="tab" data-tour={'settings:aoi:'+v} aria-selected={aoiVendor===v} className={aoiVendor===v?'active':''} onClick={()=>setAoiVendor(v)}>{v}</button>)}</div>}
    {sub==='aoi'&&aoiVendor==='KLA'&&<KlaRootsSettings memo={st?.memo_machines}/>}
    {sub==='aoi'&&aoiVendor==='CAMTEK'&&<>
      <h3>AOI 장비 호기 루트 등록</h3>
      <p className="hint">호기 폴더(예: <code>W:\AOI-9</code>) 하나만 등록하면 그 아래 <b>Reports</b> 폴더는 Batch Report 분석이,
        <b> Scanresult</b> 폴더(설정에 따라 <code>Scanresult_260402</code> 같은 백업본 포함)는 Commonality 조사 · 분석 및 취합 · Batch Report 찾기가 읽습니다. 장비 폴더는 읽기만 합니다.</p>
      <ScanBackupBar note="Scanresult 를 찾는 모든 기능에 같이 적용됩니다."/>
      {aois.length>0&&<table className="tbl" data-tour="settings:aoi-table" style={{marginTop:12}}><thead><tr><th>호기</th><th>호기 루트</th><th>인식된 폴더</th><th/></tr></thead>
        <tbody>{aois.map(aoiRow)}</tbody></table>}
      <div className="form-filter" data-tour="settings:aoi-form" style={{marginTop:12}}>
        <MemoPick memo={st?.memo_machines} vendor="CAMTEK" registered={aois.map(a=>a.machine)} onPick={setAMachine} disabled={busy}/>
        <label className="field" style={{width:150}}>호기<input value={aMachine} placeholder="AOI-9" maxLength={64} onChange={e=>setAMachine(e.target.value)}/></label>
        <label className="field" style={{flex:1,minWidth:240}}>호기 폴더<input value={aPath} placeholder="예: W:\AOI-9" maxLength={4096} onChange={e=>setAPath(e.target.value)}/></label>
        <button onClick={()=>browse(setAPath)}>📁 찾기</button>
        <button className="primary" disabled={busy||!aMachine.trim()||!aPath.trim()}
          onClick={()=>req('config_set_aoi_root',{machine:aMachine.trim(),path:aPath.trim()},`${aMachine.trim()} 등록`,()=>{setAMachine('');setAPath('');})}>추가</button></div>
      <AoiDriveScan<State> disabled={busy} onState={setSt}/>

      <h3 style={{marginTop:24}}>호기별 추가 폴더 (백업·보관본)</h3>
      <p className="hint">호기 루트 밖에 있는 백업·보관 폴더를 함께 읽게 합니다. <b>Batch Report</b> 는 Batch Report 분석이 기본 Reports 와 함께 조사하고,
        <b> Scanresult</b> 는 Commonality 조사가 S/M 폴더를 찾을 때 함께 뒤집니다(그 아래 Scanresult* 폴더도 인식). 호기·종류당 최대 20개.</p>
      {aois.length===0?<p className="table-empty">먼저 위에서 AOI 장비 호기 루트를 등록하세요.</p>:<>
        {extraRows.length>0&&<table className="tbl" style={{marginTop:12}}><thead><tr><th>호기</th><th>종류</th><th>추가 폴더</th><th/></tr></thead><tbody>{extraRows}</tbody></table>}
        <div className="form-filter" style={{marginTop:12}}>
          <label className="field" style={{width:150}}>추가 폴더 호기<select value={xMachine} onChange={e=>setXMachine(e.target.value)}><option value="">선택…</option>{aois.map(a=><option key={a.machine} value={a.machine}>{a.machine}</option>)}</select></label>
          <label className="field" style={{width:160}}>추가 폴더 종류<select value={xKind} onChange={e=>setXKind(e.target.value as ExtraKind)}>
            <option value="report">Batch Report</option><option value="scanresult">Scanresult</option></select></label>
          <label className="field" style={{flex:1,minWidth:240}}>추가 폴더<input value={xPath} placeholder={xKind==='report'?'예: P:\\AOI-9\\Reports_backup':'예: W:\\보관\\AOI-9\\Scanresult_2025'} maxLength={4096} onChange={e=>setXPath(e.target.value)}/></label>
          <button onClick={()=>browse(setXPath)}>📁 찾기</button>
          <button className="primary" disabled={busy||!xMachine||!xPath.trim()}
            onClick={()=>req('config_set_aoi_extra',{machine:xMachine,kind:xKind,paths:[...extrasOf(xMachine,xKind),xPath.trim()]},'추가 폴더 등록',()=>setXPath(''))}>추가 폴더 등록</button></div></>}
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
      <div className="bv">
        <h3 style={{marginTop:24}}>개발자 기능</h3>
        <div className="devrow"><label className="switch" title={dev.locked?'Batch Report 조사 중에는 바꿀 수 없습니다(조사를 시작할 때의 기준으로 끝까지 계산)':undefined}>
            <input type="checkbox" aria-label="개발자 기능" checked={dev.on} disabled={dev.locked} onChange={e=>toggleDev(e.target.checked)}/>
            <span><b>개발자 기능 — Batch Report 중복 Pass 직접 선택</b><small>같은 wafer가 Pass를 2번 이상 받았을 때 쓸 Batch Report를 고르고 저장합니다. 켜고 끄는 것만으로는 결과 숫자가 바뀌지 않습니다.</small></span></label>
          <button type="button" className="help-btn lg" aria-label="개발자 기능 설명" title="개발자 기능은 뭐가 다른가요?" onClick={()=>setDevHelp(true)}>?</button></div>
        {dev.locked&&<p className="hint">Batch Report 조사 중에는 바꿀 수 없습니다.</p>}
        {dev.on&&dev.drafts>0&&<p className="hint">저장 안 한 선택 {dev.drafts}건 — Batch Report 화면 위 안내 막대에서 저장하거나 버릴 수 있습니다.</p>}
        <DevOff open={devOff} count={dev.drafts} onHelp={()=>setDevHelp(true)} onCancel={()=>setDevOff(false)}
          onSave={async()=>{if(await saveDrafts()){setDevOff(false);setDevOn(false);notify('선택을 저장하고 개발자 기능을 껐습니다.','ok');}}}
          onDrop={()=>{dropDrafts();setDevOff(false);setDevOn(false);notify('저장 안 한 선택을 버리고 개발자 기능을 껐습니다.','info');}}/>
        <DevHelp open={devHelp} onClose={()=>setDevHelp(false)}/>
      </div>
      <h3 style={{marginTop:24}}>진단 로그 (느림 원인 찾기)</h3>
      <p className="hint">프로그램 시작·설정 읽기·각 작업이 <b>어느 단계에서 몇 초 걸렸는지</b> 자동으로 기록합니다
        (실행파일 풀기·백신 검사 → 모듈 로딩 → 설정 파일 읽기 → 화면 요청 대기·처리, 부팅 후 경과시간·메모리).
        파일 내용·비밀번호는 기록하지 않습니다. 느렸던 직후 <b>[진단 로그 묶기]</b>를 눌러 만들어진 zip 파일 하나를 전달하면 원인을 분석할 수 있습니다.</p>
      <div className="toolbar"><button className="primary" disabled={busy} onClick={async()=>{
        try{const r=await desktop.request('diag_bundle').promise;setDiagZip((r.diag as {path:string}).path);notify('진단 로그를 묶었습니다.','ok');}
        catch(e){notify(errorText(e),'error');}}}>진단 로그 묶기 (zip)</button></div>
      {diagZip&&<OpenPath label="진단 로그 zip" path={diagZip}/>}
      {about?.diag_log&&<OpenPath label="상세 진단 로그" path={about.diag_log}/>}
      <h3 style={{marginTop:24}}>업데이트</h3>
      <div className="toolbar"><button onClick={checkUpdate}>업데이트 확인</button><button onClick={openProgramDir}>게시 폴더 열기</button>
        {upd?.newer&&!upd.pending_ready&&<button className="primary" disabled={busy||!upd.installed} onClick={()=>void installUpdate()}>지금 {upd.available}(으)로 업데이트</button>}</div>
      {upd?.pending_ready&&<p className="hint"><b>새 버전 {upd.pending}을 받아 두었습니다.</b> 프로그램을 종료하고 다시 실행하면 적용됩니다.</p>}
      {upd&&<p className="hint">현재 {upd.current} · 최신 {upd.available||'없음'}{upd.source?` (${upd.source==='github'?'GitHub':'OneDrive'})`:''}{upd.changelog?` — ${upd.changelog}`:''}</p>}
      <p className="hint">새 버전은 <b>GitHub 의 이 프로그램 릴리스</b>에서 확인하고 받습니다(인터넷은 이때만 씁니다). GitHub 에 연결되지 않으면 OneDrive 게시 폴더를 봅니다.
        받은 파일은 프로그램 글 파일(.py · .js)뿐이며 실행 파일이 들어 있으면 적용하지 않습니다.</p>
      <details style={{marginTop:16}}><summary>개발자: OneDrive 에 새 버전 게시(보조 통로)</summary>
        <p className="hint">GitHub 릴리스 페이지의 <b>Source code (zip)</b>(v13 태그)을 받아 그대로 고르세요. 이 PC의 로컬 임시 폴더에서만 풀어
          실행 파일이 없는지 · 버전이 맞는지 확인한 뒤, OneDrive 프로그램 폴더에 zip 1개와 버전 정보 1개를 씁니다.
          GitHub 에 연결되지 않는 PC는 이 파일로 업데이트합니다.</p>
        <div className="form-filter"><label className="field" style={{flex:1,minWidth:260}}>소스 zip<input value={pubPath} maxLength={4096}
          placeholder="예: C:\Users\이름\Downloads\Para-13.0.1.zip" onChange={e=>setPubPath(e.target.value)}/></label>
          <button onClick={async()=>{const p=await pickFile('zip');if(p)setPubPath(p);else notify('파일 선택이 취소되었거나 프로그램 창이 아닙니다. 경로를 직접 붙여넣어 주세요.','info');}}>📦 zip 찾기</button></div>
        <label className="field">변경 내용<textarea rows={3} maxLength={4000} value={pubNotes} onChange={e=>setPubNotes(e.target.value)}/></label>
        <div className="toolbar"><button className="primary" disabled={busy||!pubPath.trim()} onClick={publishPackage}>게시</button></div>
      </details>
      <p className="hint">문제가 생기면 오류 로그 폴더의 파일을 담당자에게 전달하세요.</p>
    </>}

    </div>
  </section>;
}
