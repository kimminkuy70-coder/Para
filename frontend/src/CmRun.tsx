import {useEffect,useRef,useState} from 'react';
import {desktop,pickFile,type Reply} from './desktop';
import {Stepper,StepNav,notify,fail} from './ui';
import {OpenPath,openPath} from './OpenPath';
import {FormEditor} from './FormEditor';
import {goToSettings} from './nav';

type SurveyMachine={id:string;root:string};
// '이슈 Lot' (구 'fail여부'): 이슈가 있었던 Lot — 비교표·뷰어에서 노란색으로 표시.
type PlanRow={device:string;process:string;sm:string;machine:string;issue:boolean};
type Lot={id:number;label:string;device:string;lot:string;sm:string;exists:boolean;fail:boolean;scan_time:string;created:string;reason:string;wafers:string[];wafer:string};
type SmInfo={label:string;device?:string;lot?:string;sm?:string;slot?:string;scan_time?:string;created?:string;issue?:boolean;source?:string;copied:string};
type Unit={unit:number;device:string;recipe:string;lots:number;sm_list?:SmInfo[];files:{global_:boolean;optic:boolean;zones:number};thin:boolean;config_dir:string;title:string;result:string};
type Scale={variant:string;coef:number;source:string;confidence:string;reason:string};
type Opened={version:string;total:number;used:number;variants:string[]};
type Variants={rows:[string,string][];parsed:string[];unmatched:string[]}|null;
const STEPS=['조사 계획','S/M·슬롯 선택','안전 복사','변환계수','양식 편집','값 조사'];
const emptyRow=(machine=''):PlanRow=>({device:'',process:'',sm:'',machine,issue:false});
const ISSUE_RE=/^(y|yes|o|1|true|fail|ng|예|이슈|issue)$/i;
// Same machine-number rule as the engine (AOI-9 == AOI-09, 'AOI-4,6,9' lists several).
const machineNums=(t:string)=>new Set((t.match(/\d+/g)||[]).map(n=>Number(n)));
const forMachine=(row:PlanRow,machine:string)=>{const want=[...machineNums(machine)][0];return !row.machine.trim()||(want!==undefined&&machineNums(row.machine).has(want));};
const complete=(r:PlanRow)=>!!(r.device.trim()&&r.process.trim()&&r.sm.trim());

/** New Commonality investigation, one machine at a time (tkinter 수동 조사 1~5단계). */
export function CmRun({onFinished}:{onFinished:()=>void}){
  const [step,setStep]=useState(0),[busy,setBusy]=useState(false);
  const [machines,setMachines]=useState<SurveyMachine[]>([]),[machine,setMachine]=useState('');
  const [rows,setRows]=useState<PlanRow[]>([emptyRow()]),[paste,setPaste]=useState('');
  const [checked,setChecked]=useState<number[]>([]),[unregistered,setUnregistered]=useState<string[]>([]),[planFile,setPlanFile]=useState('');
  const [progress,setProgress]=useState('');
  // [S/M] cell → which Lot folders a unit covers (shown after the safe copy).
  const [smUnit,setSmUnit]=useState<Unit>(),smDialog=useRef<HTMLDialogElement>(null);
  useEffect(()=>{if(smUnit)smDialog.current?.showModal();else smDialog.current?.close();},[smUnit]);
  const [lots,setLots]=useState<Lot[]>([]),[picked,setPicked]=useState<Record<number,string[]>>({});
  const [units,setUnits]=useState<Unit[]>([]),[unit,setUnit]=useState(0),[staging,setStaging]=useState('');
  const [base,setBase]=useState(''),[title,setTitle]=useState(''),[scales,setScales]=useState<Scale[]>([]),[scaleEdit,setScaleEdit]=useState<Record<string,string>>({});
  const [similar,setSimilar]=useState<{recipe:string;match:number;total:number}[]>([]),[baseForm,setBaseForm]=useState('');
  const [opened,setOpened]=useState<Opened>();
  const [variants,setVariants]=useState<Variants>(),[mapping,setMapping]=useState<Record<string,string>>({}),[formPath,setFormPath]=useState('');

  async function loadMachines(){
    try{await desktop.connect();const r=(await desktop.request('cmsurvey_config').promise).cmsurvey as {machines:SurveyMachine[]};
      setMachines(r.machines);setMachine(m=>m&&r.machines.some(x=>x.id===m)?m:(r.machines[0]?.id||''));}
    catch(e){fail(e);}
  }
  useEffect(()=>{void loadMachines();},[]);
  // Coming back from 설정 (this screen stays mounted): pick up newly registered roots.
  useEffect(()=>{const again=(e:Event)=>{if((e as CustomEvent<string>).detail==='Commonality 조사')void loadMachines();};
    window.addEventListener('para:tab',again);return()=>window.removeEventListener('para:tab',again);},[]);
  async function call<T>(method:string,params:object,onStep?:(m:string)=>void){
    setBusy(true);
    try{return (await desktop.request(method,params,onStep?(v:Reply)=>{if(v.message)onStep(v.message);}:undefined).promise).cmrun as T;}
    catch(e){fail(e);return undefined;}finally{setBusy(false);}
  }
  const setRow=(i:number,patch:Partial<PlanRow>)=>setRows(rs=>rs.map((r,j)=>j===i?{...r,...patch}:r));
  const addRows=(add:PlanRow[],replace=false)=>{setRows(rs=>{const keep=replace?[]:rs.filter(r=>r.device||r.process||r.sm);const n=[...keep,...add];return n.length?n:[emptyRow(machine)];});setChecked([]);};
  // Paste rows copied from the plan Excel (디바이스명 · 공정번호 · S/M · [AOI호기] · [이슈 Lot]).
  function applyPaste(){
    const parsed=paste.split(/\r?\n/).map(l=>l.split('\t').map(c=>c.trim())).filter(c=>c.length>=3&&c.slice(0,3).some(Boolean))
      .filter(c=>!/디바이스/.test(c[0])).map(c=>({device:c[0],process:c[1],sm:c[2],machine:c[3]||machine,issue:ISSUE_RE.test(c[4]||'')}));
    if(!parsed.length){notify('붙여넣은 내용에서 행을 찾지 못했습니다. 엑셀에서 디바이스명·공정번호·S/M 열을 복사하세요.','error');return;}
    addRows(parsed);setPaste('');notify(`${parsed.length}행을 추가했습니다.`,'ok');
  }
  // 📂 계획 엑셀 불러오기 (새 양식 · 구 양식의 fail여부/생성일자 열 모두 읽음).
  async function importPlan(){
    const path=await pickFile();
    if(!path){notify('파일 선택이 취소되었거나 데스크톱 앱이 아닙니다.','info');return;}
    setBusy(true);
    try{const r=(await desktop.request('cmsurvey_read_plan',{path}).promise).cmsurvey as {path:string;rows:PlanRow[];unregistered:string[]};
      if(!r.rows.length){notify('계획 엑셀에 행이 없습니다. 디바이스명·공정번호·S/M 을 채워 주세요.','error');return;}
      addRows(r.rows,true);setPlanFile(r.path);setUnregistered(r.unregistered);
      const mine=r.rows.filter(x=>forMachine(x,machine)).length;
      notify(`계획 ${r.rows.length}행을 불러왔습니다${machine?` (현재 호기 ${machine}: ${mine}행)`:''}.`,'ok');}
    catch(e){fail(e);}finally{setBusy(false);}
  }
  // 📄 새 계획 엑셀 양식 (현재 표의 완성된 행을 채워서) — 로컬 Commonality/계획 폴더에 만들고 엽니다.
  async function makeTemplate(){
    setBusy(true);
    try{const plan=rows.filter(complete).map(r=>({디바이스명:r.device.trim(),공정번호:r.process.trim(),'S/M':r.sm.trim(),AOI호기:r.machine.trim(),'이슈 Lot':r.issue?'Y':''}));
      const r=(await desktop.request('cmsurvey_plan_template',{rows:plan}).promise).cmsurvey as {path:string;rows:number};
      notify(`계획 엑셀 양식을 만들었습니다(${r.rows}행). 채워서 저장한 뒤 [📂 계획 엑셀 불러오기]로 읽으세요.`,'ok');
      setPlanFile(r.path);await openPath(r.path);}
    catch(e){fail(e);}finally{setBusy(false);}
  }
  function removeChecked(){setRows(rs=>{const n=rs.filter((_,i)=>!checked.includes(i));return n.length?n:[emptyRow(machine)];});setChecked([]);}
  function removeAll(){if(!window.confirm(`조사 계획 ${rows.length}행을 모두 지울까요?`))return;setRows([emptyRow(machine)]);setChecked([]);setUnregistered([]);setPlanFile('');}
  async function resolve(){
    const plan=rows.filter(r=>complete(r)&&forMachine(r,machine))
      .map(r=>({디바이스명:r.device.trim(),공정번호:r.process.trim(),'S/M':r.sm.trim(),AOI호기:r.machine.trim()||machine,'이슈 Lot':r.issue?'Y':''}));
    setProgress('S/M 폴더 찾기를 시작합니다…');
    const r=await call<{lots:Lot[]}>('cmrun_plan',{machine,plan},setProgress);
    setProgress('');
    if(!r)return;
    setLots(r.lots);setPicked(Object.fromEntries(r.lots.filter(l=>l.exists).map(l=>[l.id,l.wafer?[l.wafer]:[]])));setStep(1);
  }
  async function copy(){
    const picks=Object.entries(picked).map(([id,wafers])=>({id:Number(id),wafers}));
    const r=await call<{copied:number;fails:number;staging:string;units:Unit[]}>('cmrun_copy',{picks});
    if(!r)return;
    setUnits(r.units);setStaging(r.staging);setUnit(0);setStep(2);
    notify(`${r.copied}개 S/M(슬롯) 폴더를 안전 복사했습니다(원본 수정 없음).`,'ok');
  }
  async function detect(){
    const r=await call<{scales:Scale[];title:string}>('cmrun_detect',{unit,base:base.trim()});
    if(!r)return;
    setTitle(r.title);setScales(r.scales);setScaleEdit({});setStep(3);
  }
  const scaleValue=(s:Scale)=>scaleEdit[s.variant]??String(s.coef);
  const scaleBad=scales.some(s=>!(Number(scaleValue(s))>0));
  async function parse(form=baseForm){
    const payload=Object.fromEntries(scales.map(s=>[s.variant,Number(scaleValue(s))]));
    const r=await call<{form:Opened;similar:{recipe:string;match:number;total:number}[];base_form:string}>('cmrun_parse',{unit,scales:payload,base_form:form});
    if(!r)return;
    setOpened(r.form);setSimilar(r.similar);setBaseForm(r.base_form);setStep(4);
  }
  async function confirmForm(){
    if(!opened)return;
    const r=await call<{form:string;kept:number;variants:Variants;notes?:string[]}>('cmrun_confirm',{unit,snapshot:opened.version});
    if(!r)return;
    (r.notes||[]).forEach(n=>notify(n,'error'));
    setFormPath(r.form);setVariants(r.variants);
    setMapping(Object.fromEntries((r.variants?.rows||[]).map(([form,auto])=>[form,auto])));setStep(5);
  }
  async function collate(){
    // {수집 이름: 양식 이름}; identical names need no entry.
    const map:Record<string,string>={};Object.entries(mapping).forEach(([form,copied])=>{if(copied&&copied!==form)map[copied]=form;});
    const r=await call<{result:string;matched_rows:number;filled_cells:number;mismatches:number;units:Unit[]}>('cmrun_collate',{unit,mapping:map});
    if(!r)return;
    setUnits(r.units);notify(`값 조사 완료 · 매칭 ${r.matched_rows}행 · 채운 셀 ${r.filled_cells}개${r.mismatches?` · 불일치 ${r.mismatches}건`:''}`,'ok');
    const next=r.units.findIndex(u=>!u.result);
    setOpened(undefined);setVariants(undefined);
    if(next>=0){setUnit(next);setStep(2);}else{setStep(2);onFinished();}
  }
  async function restart(){await call('cmrun_reset',{});setStep(0);setLots([]);setUnits([]);setOpened(undefined);}

  if(machines.length===0)
    return <section className="panel"><div className="section-heading"><div><span className="step">NEW SURVEY</span><h2>신규 Commonality 조사</h2></div>
      <button onClick={()=>void loadMachines()}>새로고침</button></div>
      <p className="hint">Scanresult 루트가 설정된 호기가 없습니다. 호기별 장비 폴더(Scanresult 상위 폴더)를 먼저 등록하세요.</p>
      <div className="toolbar"><button className="primary" onClick={()=>goToSettings({sub:'scan'})}>설정 › Scanresult 루트로 이동 ▶</button></div></section>;
  const current=units[unit];
  const allDone=units.length>0&&units.every(u=>u.result);
  return <section className="panel">
    <div className="section-heading"><div><span className="step">NEW SURVEY</span><h2>신규 Commonality 조사 — 호기 1대씩</h2></div>
      {step>0&&<button disabled={busy} onClick={restart}>처음부터</button>}</div>
    <Stepper labels={STEPS} current={step}/>
    <div className="step-body">
    {step===0&&<>
      <p className="hint">조사할 Lot 계획을 입력하거나 엑셀로 불러오면, 고른 호기의 Scanresult(백업본 포함)에서 S/M 폴더를 찾습니다. 원본은 읽기만 합니다.</p>
      <div className="form-filter" style={{marginTop:12}}><label className="field">조사 호기<select value={machine} onChange={e=>setMachine(e.target.value)}>
        {machines.map(m=><option key={m.id} value={m.id}>{m.id}</option>)}</select></label>
        <button onClick={()=>goToSettings({sub:'scan'})} title="목록에 없는 호기의 장비 폴더를 등록합니다">＋ 다른 호기 장비 폴더 등록…</button></div>
      {unregistered.length>0&&<div className="warn-box" role="alert"><b>장비 폴더가 등록되지 않은 호기</b>가 계획에 있습니다. 경로를 지정하면 그 호기도 조사할 수 있습니다.
        <div className="toolbar">{unregistered.map(m=><button key={m} onClick={()=>goToSettings({sub:'scan',machine:m})}>{m} 경로 지정 ▶</button>)}</div></div>}
      <div className="toolbar">
        <button disabled={busy} onClick={importPlan}>📂 계획 엑셀 불러오기</button>
        <button disabled={busy} onClick={makeTemplate}>📄 계획 엑셀 양식 만들기</button>
        <span className="spacer"/>
        <button onClick={()=>setRows(rs=>[...rs,emptyRow(machine)])}>행 추가</button>
        <button disabled={!checked.length} onClick={removeChecked}>선택 삭제{checked.length?` (${checked.length})`:''}</button>
        <button disabled={rows.length===1&&!complete(rows[0])&&!rows[0].device} onClick={removeAll}>전체 삭제</button></div>
      {planFile&&<p className="hint">계획 파일: <code>{planFile}</code></p>}
      <div className="table-scroll cm-plan"><table><thead><tr>
        <th><input type="checkbox" aria-label="모든 행 선택" checked={rows.length>0&&checked.length===rows.length}
          onChange={e=>setChecked(e.target.checked?rows.map((_,i)=>i):[])}/></th>
        <th>디바이스명</th><th>공정번호</th><th>S/M</th><th>AOI호기</th><th>이슈 Lot</th><th></th></tr></thead>
        <tbody>{rows.map((r,i)=>{const other=!forMachine(r,machine);return <tr key={i} className={other?'muted':''} title={other?`${machine} 조사에서 제외(다른 호기 행)`:''}>
          <td><input type="checkbox" aria-label={`${i+1}행 선택`} checked={checked.includes(i)} onChange={e=>setChecked(c=>e.target.checked?[...c,i]:c.filter(x=>x!==i))}/></td>
          <td><input aria-label={`${i+1}행 디바이스명`} value={r.device} maxLength={256} onChange={e=>setRow(i,{device:e.target.value})}/></td>
          <td><input aria-label={`${i+1}행 공정번호`} value={r.process} maxLength={256} onChange={e=>setRow(i,{process:e.target.value})}/></td>
          <td><input aria-label={`${i+1}행 S/M`} value={r.sm} maxLength={256} onChange={e=>setRow(i,{sm:e.target.value})}/></td>
          <td><input aria-label={`${i+1}행 AOI호기`} value={r.machine} maxLength={256} placeholder={machine} onChange={e=>setRow(i,{machine:e.target.value})}/></td>
          <td style={{textAlign:'center'}}><input type="checkbox" aria-label={`${i+1}행 이슈 Lot`} checked={r.issue} onChange={e=>setRow(i,{issue:e.target.checked})}/></td>
          <td><button className="linklike" onClick={()=>{setRows(rs=>{const n=rs.filter((_,j)=>j!==i);return n.length?n:[emptyRow(machine)];});setChecked([]);}}>삭제</button></td></tr>;})}</tbody></table></div>
      <p className="hint">{rows.filter(complete).length}행 입력 · {machine} 조사 대상 {rows.filter(r=>complete(r)&&forMachine(r,machine)).length}행 (AOI호기가 다른 행은 흐리게 표시되고 이번 조사에서 빠집니다. 비우면 조사 호기로 봅니다.)</p>
      <label className="field">엑셀에서 붙여넣기 (디바이스명 · 공정번호 · S/M · AOI호기 · 이슈 Lot 열을 복사)<textarea rows={3} value={paste} onChange={e=>setPaste(e.target.value)} placeholder="엑셀에서 행을 복사해 여기에 붙여넣으세요"/></label>
      <div className="toolbar"><button disabled={!paste.trim()} onClick={applyPaste}>붙여넣은 행 추가</button></div>
      {busy&&progress&&<div className="runbar" role="status" aria-live="polite"><div><strong>S/M 폴더 찾는 중…</strong><p>{progress}</p></div></div>}
    </>}
    {step===1&&<>
      <p className="hint">조사할 S/M 폴더를 고르세요(기본: 찾은 폴더 전체). 슬롯(웨이퍼)을 여러 개 고르면 슬롯마다 따로 조사하고 열 이름 뒤에 슬롯명이 붙습니다. '수정' = Scan 일자.</p>
      <div className="table-scroll"><table><thead><tr><th>선택</th><th>S/M 폴더</th><th>디바이스</th><th>공정</th><th>슬롯</th><th>수정(Scan)</th><th>상태</th></tr></thead>
        <tbody>{lots.map(l=><tr key={l.id} className={(l.exists?'':'muted ')+(l.fail?'fail-row':'')}>
          <td><input type="checkbox" aria-label={`${l.label} 선택`} disabled={!l.exists} checked={l.id in picked} onChange={e=>setPicked(p=>{const n={...p};if(e.target.checked)n[l.id]=l.wafer?[l.wafer]:[];else delete n[l.id];return n;})}/></td>
          <td>{l.label}{l.fail?' · 이슈 Lot':''}</td><td>{l.device}</td><td>{l.lot}</td>
          <td>{l.wafers.length>1&&l.id in picked?<div className="slot-picks">{l.wafers.map(w=><label key={w}><input type="checkbox" aria-label={`${l.label} 슬롯 ${w}`} checked={picked[l.id]?.includes(w)} onChange={e=>setPicked(p=>{const cur=p[l.id]||[];const next=e.target.checked?[...cur,w]:cur.filter(x=>x!==w);return next.length?{...p,[l.id]:next}:p;})}/>{w}</label>)}</div>:(l.wafer||'—')}</td>
          <td>{l.scan_time||'—'}</td><td>{l.exists?'발견':l.reason||'없음'}</td></tr>)}</tbody></table></div>
      <p className="hint">{Object.keys(picked).length}개 선택 · 복사본은 로컬 작업 폴더의 Commonality 아래에 둡니다.</p>
    </>}
    {step===2&&<>
      {staging&&<OpenPath label="안전 복사 위치" path={staging} folder/>}
      <p className="hint">디바이스·레시피마다 양식을 따로 만들어 순서대로 조사합니다(파일 이름: 조사제목[_디바이스][_레시피]).</p>
      <table className="tbl"><thead><tr><th>#</th><th>디바이스</th><th>레시피</th><th>S/M</th><th>읽을 파일</th><th>결과</th></tr></thead><tbody>{units.map(u=><tr key={u.unit} className={u.unit===unit&&!allDone?'row-now':''}>
        <td>{u.unit+1}</td><td>{u.device||'—'}</td><td>{u.recipe||'(단일)'}</td>
        <td><button className="linklike" aria-label={`${u.unit+1}번 조사 단위 S/M ${u.lots}개 보기`} onClick={()=>setSmUnit(u)}>{u.lots}개 보기</button></td>
        <td className={u.thin?'warn':''}>GlobalRTP {u.files.global_?'O':'X'} · OpticPreset {u.files.optic?'O':'X'} · Zones {u.files.zones}{u.thin?' — GlobalRTP만 읽힘':''}</td>
        <td>{u.result?<OpenPath label="조사 결과" path={u.result}/>:u.unit===unit?'다음 차례':'대기'}</td></tr>)}</tbody></table>
      {current?.thin&&!current.result&&<p className="warn">이 레시피는 GlobalRTP 밖에 읽을 파일이 없습니다. 이대로 진행하면 양식에 GlobalRTP 항목만 들어갑니다. 확인할 폴더: {current.config_dir}</p>}
      {allDone?<div className="outputs"><h3>모든 조사 단위를 마쳤습니다</h3><p>아래 [저장 결과 비교]에서 이번 결과와 다른 호기 결과를 골라 취합·비교하세요.</p></div>
        :<div className="form-filter" style={{marginTop:12}}><label className="field" style={{flex:1}}>조사 제목(예: PI3){units.length>1?' — 디바이스/레시피 이름이 자동으로 붙습니다':''}<input value={base} maxLength={80} onChange={e=>setBase(e.target.value)}/></label></div>}
    </>}
    {step===3&&current&&<>
      <h3>[{title}] 변형별 변환계수</h3>
      <p className="hint">변환계수.xlsx 값이 있으면 그 값, 없으면 RTP.txt 로 추정한 값을 미리 채웠습니다. 확인하고 필요하면 고치세요.</p>
      <table className="tbl"><thead><tr><th>변형</th><th>계수</th><th>출처</th><th>추정 신뢰도</th></tr></thead><tbody>{scales.map(s=><tr key={s.variant}>
        <td>{s.variant||'(기본)'}</td><td><input aria-label={`${s.variant||'기본'} 계수`} type="number" step="any" value={scaleValue(s)} onChange={e=>setScaleEdit(x=>({...x,[s.variant]:e.target.value}))}/></td>
        <td className={s.source==='기본값'?'warn':''}>{scaleEdit[s.variant]!==undefined?'직접 입력':s.source}</td><td title={s.reason}>{s.confidence||'—'}</td></tr>)}</tbody></table>
      {scaleBad&&<p role="alert">계수는 0보다 큰 숫자여야 합니다.</p>}
    </>}
    {step===4&&opened&&<>
      <div className="section-heading"><div><h3>{title} · 조사 양식</h3></div><span className="count">사용 {opened.used} / 전체 {opened.total}</span></div>
      {similar.length>0&&<div className="form-filter"><label className="field">기존 양식 기준으로 사용 항목 맞추기<select value={baseForm} disabled={busy} onChange={e=>void parse(e.target.value)}>
        <option value="">(파서 기본 추천)</option>{similar.map(s=><option key={s.recipe} value={s.recipe}>{s.recipe} — 일치 {s.match}/{s.total}</option>)}</select></label></div>}
      <p className="hint">지난번에 정한 장비 화면 이름·체크 상태(장비화면이름.xlsx)를 자동으로 적용했습니다. 확정하면 이번 설정도 기억합니다.</p>
      <FormEditor version={opened.version} pageMethod="cmrun_page" editMethod="cmrun_edit" replyKey="cmrun" variants={opened.variants}
        onUsed={n=>setOpened(o=>o&&o.used!==n?{...o,used:n}:o)}/>
    </>}
    {step===5&&<>
      <OpenPath label="확정 양식" path={formPath}/>
      {variants?<><p className="hint">양식의 하위 레시피(왼쪽)에 대응하는 복사해온 이름(오른쪽)을 고르세요. 이름이 같으면 자동으로 골라져 있습니다.</p>
        <table className="tbl"><tbody>{variants.rows.map(([form])=><tr key={form}><td>{form||'(빈칸)'}</td><td>
          <select aria-label={`${form||'빈칸'} 매칭`} value={mapping[form]??''} onChange={e=>setMapping(m=>({...m,[form]:e.target.value}))}>
            <option value="">— 없음(이 항목은 안 채움) —</option>{variants.parsed.map(p=><option key={p} value={p}>{p||'(빈칸)'}</option>)}</select></td></tr>)}</tbody></table>
        {variants.unmatched.length>0&&<p className="hint">양식에 없는 복사본 레시피(무시): {variants.unmatched.join(', ')}</p>}</>
        :<p className="hint">확인할 하위 레시피 이름이 없습니다. 값 조사를 실행하세요.</p>}
    </>}
    </div>
    {!(step===2&&allDone)&&<StepNav step={step} total={STEPS.length} busy={busy} onBack={()=>setStep(s=>s===3||s===4||s===5?2:Math.max(0,s-1))}
      onNext={()=>{if(step===0)void resolve();else if(step===1)void copy();else if(step===2)void detect();else if(step===3)void parse();else if(step===4)void confirmForm();else void collate();}}
      nextLabel={['S/M 폴더 찾기','안전 복사','변환계수 확인','양식 편집','양식 확정','값 조사 실행'][step]}
      nextDisabled={(step===0&&(!machine||!rows.some(r=>complete(r)&&forMachine(r,machine))))||(step===1&&!Object.keys(picked).length)
        ||(step===2&&!base.trim())||(step===3&&scaleBad)||(step===4&&!opened?.used)}/>}
    <dialog className="edit-dialog wide-dialog sm-dialog" ref={smDialog} onClose={()=>setSmUnit(undefined)}>{smUnit&&<>
      <h3>{smUnit.unit+1}번 조사 단위 — S/M {smUnit.sm_list?.length||smUnit.lots}개</h3>
      <p className="sub">{[smUnit.device&&`디바이스 ${smUnit.device}`,smUnit.recipe&&`레시피 ${smUnit.recipe}`].filter(Boolean).join(' · ')||'단일 디바이스·레시피'}</p>
      <div className="table-scroll"><table><thead><tr><th>S/M(열 이름)</th><th>디바이스</th><th>공정</th><th>S/M 폴더</th><th>슬롯</th><th>Scan 일자</th><th>생성일자</th><th>이슈 Lot</th></tr></thead>
        <tbody>{(smUnit.sm_list||[]).map(x=><tr key={x.label} className={x.issue?'fail-row':''} title={`원본: ${x.source||'—'}\n복사본: ${x.copied}`}>
          <td><b>{x.label}</b></td><td>{x.device||'—'}</td><td>{x.lot||'—'}</td><td>{x.sm||'—'}</td><td>{x.slot||'—'}</td>
          <td>{x.scan_time||'—'}</td><td>{x.created||'—'}</td><td>{x.issue?'Y':''}</td></tr>)}</tbody></table></div>
      <p className="hint">행에 마우스를 올리면 원본 폴더와 로컬 복사본 경로가 보입니다.</p>
      <div className="dialog-actions">{smUnit.sm_list?.[0]?.copied&&<button onClick={()=>void openPath(smUnit.sm_list![0].copied.replace(/[\\/][^\\/]+$/,''))}>복사본 폴더 열기</button>}
        <button className="primary" onClick={()=>setSmUnit(undefined)}>닫기</button></div></>}</dialog>
  </section>;
}
