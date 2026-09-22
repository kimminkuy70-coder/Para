import {useEffect,useState} from 'react';
import {desktop} from './desktop';
import {Stepper,StepNav,notify,fail} from './ui';
import {OpenPath} from './OpenPath';

type SurveyMachine={id:string;root:string};
type PlanRow={device:string;process:string;sm:string;fail:boolean};
type Lot={id:number;label:string;device:string;lot:string;sm:string;exists:boolean;fail:boolean;scan_time:string;created:string;reason:string;wafers:string[];wafer:string};
type Unit={unit:number;device:string;recipe:string;lots:number;files:{global_:boolean;optic:boolean;zones:number};thin:boolean;config_dir:string;title:string;result:string};
type Scale={variant:string;coef:number;source:string;confidence:string;reason:string};
type Opened={version:string;total:number;used:number;variants:string[]};
type Row={id:number;use:boolean;variant:string;zone:string;alg:string;orig:string;name:string;transform:string;raw:string;display:string};
type Page={rows:Row[];total:number;used:number;offset:number};
type Variants={rows:[string,string][];parsed:string[];unmatched:string[]}|null;
const STEPS=['조사 계획','S/M·슬롯 선택','안전 복사','변환계수','양식 편집','값 조사'];
const TRANSFORMS=['RAW','LINEAR','AREA'];
const emptyRow=():PlanRow=>({device:'',process:'',sm:'',fail:false});

/** New Commonality investigation, one machine at a time (tkinter 수동 조사 1~5단계). */
export function CmRun({onFinished}:{onFinished:()=>void}){
  const [step,setStep]=useState(0),[busy,setBusy]=useState(false);
  const [machines,setMachines]=useState<SurveyMachine[]>([]),[machine,setMachine]=useState('');
  const [rows,setRows]=useState<PlanRow[]>([emptyRow()]),[paste,setPaste]=useState('');
  const [lots,setLots]=useState<Lot[]>([]),[picked,setPicked]=useState<Record<number,string[]>>({});
  const [units,setUnits]=useState<Unit[]>([]),[unit,setUnit]=useState(0),[staging,setStaging]=useState('');
  const [base,setBase]=useState(''),[title,setTitle]=useState(''),[scales,setScales]=useState<Scale[]>([]),[scaleEdit,setScaleEdit]=useState<Record<string,string>>({});
  const [similar,setSimilar]=useState<{recipe:string;match:number;total:number}[]>([]),[baseForm,setBaseForm]=useState('');
  const [opened,setOpened]=useState<Opened>(),[page,setPage]=useState<Page>(),[offset,setOffset]=useState(0),[usedOnly,setUsedOnly]=useState(false);
  const [variants,setVariants]=useState<Variants>(),[mapping,setMapping]=useState<Record<string,string>>({}),[formPath,setFormPath]=useState('');

  useEffect(()=>{(async()=>{
    try{await desktop.connect();const r=(await desktop.request('cmsurvey_config').promise).cmsurvey as {machines:SurveyMachine[]};
      setMachines(r.machines);setMachine(m=>m||(r.machines[0]?.id||''));}
    catch(e){fail(e);}
  })();},[]);
  async function call<T>(method:string,params:object){
    setBusy(true);
    try{return (await desktop.request(method,params).promise).cmrun as T;}
    catch(e){fail(e);return undefined;}finally{setBusy(false);}
  }
  const setRow=(i:number,patch:Partial<PlanRow>)=>setRows(rs=>rs.map((r,j)=>j===i?{...r,...patch}:r));
  // Paste rows copied from the plan Excel (디바이스명 · 공정번호 · S/M · [AOI호기] · [fail여부]).
  function applyPaste(){
    const parsed=paste.split(/\r?\n/).map(l=>l.split('\t').map(c=>c.trim())).filter(c=>c.length>=3&&c.slice(0,3).some(Boolean))
      .filter(c=>!/디바이스/.test(c[0])).map(c=>({device:c[0],process:c[1],sm:c[2],fail:/^(y|yes|o|1|true|fail)$/i.test(c[4]||'')}));
    if(!parsed.length){notify('붙여넣은 내용에서 행을 찾지 못했습니다. 엑셀에서 디바이스명·공정번호·S/M 열을 복사하세요.','error');return;}
    setRows(rs=>[...rs.filter(r=>r.device||r.process||r.sm),...parsed]);setPaste('');notify(`${parsed.length}행을 추가했습니다.`,'ok');
  }
  async function resolve(){
    const plan=rows.filter(r=>r.device.trim()||r.process.trim()||r.sm.trim())
      .map(r=>({디바이스명:r.device.trim(),공정번호:r.process.trim(),'S/M':r.sm.trim(),AOI호기:machine,fail여부:r.fail?'Y':''}));
    const r=await call<{lots:Lot[]}>('cmrun_plan',{machine,plan});
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
    setOpened(r.form);setSimilar(r.similar);setBaseForm(r.base_form);setOffset(0);setStep(4);
  }
  useEffect(()=>{
    if(step!==4||!opened)return;let active=true;
    desktop.request('cmrun_page',{snapshot:opened.version,variant:'',query:'',used_only:usedOnly,offset,limit:100}).promise
      .then(r=>{if(active)setPage(r.cmrun as Page);}).catch(e=>{if(active)fail(e);});
    return()=>{active=false;};
  },[step,opened,offset,usedOnly]);
  async function edit(row:Row,kind:'use'|'name'|'transform',value:boolean|string){
    if(!opened)return;
    try{await desktop.request('cmrun_edit',{snapshot:opened.version,row:row.id,kind,value}).promise;
      const r=(await desktop.request('cmrun_page',{snapshot:opened.version,variant:'',query:'',used_only:usedOnly,offset,limit:100}).promise).cmrun as Page;
      setPage(r);setOpened(o=>o&&{...o,used:r.used});}
    catch(e){fail(e);}
  }
  async function confirmForm(){
    if(!opened)return;
    const r=await call<{form:string;kept:number;variants:Variants}>('cmrun_confirm',{unit,snapshot:opened.version});
    if(!r)return;
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
    setOpened(undefined);setPage(undefined);setVariants(undefined);
    if(next>=0){setUnit(next);setStep(2);}else{setStep(2);onFinished();}
  }
  async function restart(){await call('cmrun_reset',{});setStep(0);setLots([]);setUnits([]);setOpened(undefined);}

  if(machines.length===0)
    return <section className="panel"><div className="section-heading"><div><span className="step">NEW SURVEY</span><h2>신규 Commonality 조사</h2></div></div>
      <p className="hint">Scanresult 루트가 설정된 호기가 없습니다. [설정] 탭에서 호기별 Scanresult 루트를 먼저 등록하세요.</p></section>;
  const current=units[unit];
  const allDone=units.length>0&&units.every(u=>u.result);
  return <section className="panel">
    <div className="section-heading"><div><span className="step">NEW SURVEY</span><h2>신규 Commonality 조사 — 호기 1대씩</h2></div>
      {step>0&&<button disabled={busy} onClick={restart}>처음부터</button>}</div>
    <Stepper labels={STEPS} current={step}/>
    <div className="step-body">
    {step===0&&<>
      <p className="hint">조사할 Lot 계획을 입력하면 그 호기의 Scanresult(백업본 포함)에서 S/M 폴더를 찾습니다. 원본은 읽기만 합니다.</p>
      <div className="form-filter" style={{marginTop:12}}><label className="field">호기<select value={machine} onChange={e=>setMachine(e.target.value)}>
        {machines.map(m=><option key={m.id} value={m.id}>{m.id}</option>)}</select></label></div>
      <div className="table-scroll"><table><thead><tr><th>디바이스명</th><th>공정번호</th><th>S/M</th><th>fail</th><th></th></tr></thead>
        <tbody>{rows.map((r,i)=><tr key={i}>
          <td><input aria-label={`${i+1}행 디바이스명`} value={r.device} maxLength={256} onChange={e=>setRow(i,{device:e.target.value})}/></td>
          <td><input aria-label={`${i+1}행 공정번호`} value={r.process} maxLength={256} onChange={e=>setRow(i,{process:e.target.value})}/></td>
          <td><input aria-label={`${i+1}행 S/M`} value={r.sm} maxLength={256} onChange={e=>setRow(i,{sm:e.target.value})}/></td>
          <td style={{textAlign:'center'}}><input type="checkbox" checked={r.fail} onChange={e=>setRow(i,{fail:e.target.checked})}/></td>
          <td><button className="linklike" disabled={rows.length===1} onClick={()=>setRows(rs=>rs.filter((_,j)=>j!==i))}>삭제</button></td></tr>)}</tbody></table></div>
      <div className="toolbar"><button onClick={()=>setRows(rs=>[...rs,emptyRow()])}>행 추가</button></div>
      <label className="field">엑셀 계획에서 붙여넣기 (디바이스명 · 공정번호 · S/M · AOI호기 · fail여부 열을 복사)<textarea rows={3} value={paste} onChange={e=>setPaste(e.target.value)} placeholder="엑셀에서 행을 복사해 여기에 붙여넣으세요"/></label>
      <div className="toolbar"><button disabled={!paste.trim()} onClick={applyPaste}>붙여넣은 행 추가</button></div>
    </>}
    {step===1&&<>
      <p className="hint">조사할 S/M 폴더를 고르세요(기본: 찾은 폴더 전체). 슬롯(웨이퍼)을 여러 개 고르면 슬롯마다 따로 조사하고 열 이름 뒤에 슬롯명이 붙습니다. '수정' = Scan 일자.</p>
      <div className="table-scroll"><table><thead><tr><th>선택</th><th>S/M 폴더</th><th>디바이스</th><th>공정</th><th>슬롯</th><th>수정(Scan)</th><th>상태</th></tr></thead>
        <tbody>{lots.map(l=><tr key={l.id} className={(l.exists?'':'muted ')+(l.fail?'fail-row':'')}>
          <td><input type="checkbox" aria-label={`${l.label} 선택`} disabled={!l.exists} checked={l.id in picked} onChange={e=>setPicked(p=>{const n={...p};if(e.target.checked)n[l.id]=l.wafer?[l.wafer]:[];else delete n[l.id];return n;})}/></td>
          <td>{l.label}{l.fail?' · Fail':''}</td><td>{l.device}</td><td>{l.lot}</td>
          <td>{l.wafers.length>1&&l.id in picked?<div className="slot-picks">{l.wafers.map(w=><label key={w}><input type="checkbox" aria-label={`${l.label} 슬롯 ${w}`} checked={picked[l.id]?.includes(w)} onChange={e=>setPicked(p=>{const cur=p[l.id]||[];const next=e.target.checked?[...cur,w]:cur.filter(x=>x!==w);return next.length?{...p,[l.id]:next}:p;})}/>{w}</label>)}</div>:(l.wafer||'—')}</td>
          <td>{l.scan_time||'—'}</td><td>{l.exists?'발견':l.reason||'없음'}</td></tr>)}</tbody></table></div>
      <p className="hint">{Object.keys(picked).length}개 선택 · 복사본은 로컬 작업 폴더의 Commonality 아래에 둡니다.</p>
    </>}
    {step===2&&<>
      {staging&&<OpenPath label="안전 복사 위치" path={staging} folder/>}
      <p className="hint">디바이스·레시피마다 양식을 따로 만들어 순서대로 조사합니다(파일 이름: 조사제목[_디바이스][_레시피]).</p>
      <table className="tbl"><thead><tr><th>#</th><th>디바이스</th><th>레시피</th><th>S/M</th><th>읽을 파일</th><th>결과</th></tr></thead><tbody>{units.map(u=><tr key={u.unit} className={u.unit===unit&&!allDone?'row-now':''}>
        <td>{u.unit+1}</td><td>{u.device||'—'}</td><td>{u.recipe||'(단일)'}</td><td>{u.lots}</td>
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
        <option value="">(파서 기본 추천)</option>{similar.map(s=><option key={s.recipe} value={s.recipe}>{s.recipe} — 일치 {s.match}/{s.total}</option>)}</select></label>
        <label className="field checkbox"><input type="checkbox" checked={usedOnly} onChange={e=>{setUsedOnly(e.target.checked);setOffset(0);}}/>사용 항목만</label></div>}
      <div className="table-scroll"><table><thead><tr><th>사용</th><th>변형</th><th>Zone</th><th>Alg</th><th>원본 항목</th><th>표시 이름</th><th>변환</th><th>값</th></tr></thead>
        <tbody>{(page?.rows||[]).map(row=><tr key={row.id} className={row.use?'':'muted'}>
          <td><input type="checkbox" checked={row.use} aria-label={`${row.orig} 사용`} onChange={e=>edit(row,'use',e.target.checked)}/></td>
          <td>{row.variant||'(기본)'}</td><td>{row.zone}</td><td>{row.alg}</td><td>{row.orig}</td>
          <td><input value={row.name} maxLength={200} aria-label={`${row.orig} 표시 이름`} onChange={e=>setPage(p=>p&&{...p,rows:p.rows.map(r=>r.id===row.id?{...r,name:e.target.value}:r)})} onBlur={e=>void edit(row,'name',e.target.value)}/></td>
          <td><select value={row.transform} aria-label={`${row.orig} 변환`} onChange={e=>edit(row,'transform',e.target.value)}>{TRANSFORMS.map(t=><option key={t}>{t}</option>)}</select></td>
          <td>{row.display||row.raw}</td></tr>)}</tbody></table></div>
      <div className="pagination"><span>{page?.total?`${offset+1}–${Math.min(offset+100,page.total)} / ${page.total}개`:'0개'}</span>
        <div><button disabled={offset===0} onClick={()=>setOffset(n=>Math.max(0,n-100))}>이전</button><button disabled={offset+100>=(page?.total||0)} onClick={()=>setOffset(n=>n+100)}>다음</button></div></div>
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
      nextDisabled={(step===0&&(!machine||!rows.some(r=>r.device.trim()&&r.process.trim()&&r.sm.trim())))||(step===1&&!Object.keys(picked).length)
        ||(step===2&&!base.trim())||(step===3&&scaleBad)||(step===4&&!opened?.used)}/>}
  </section>;
}
