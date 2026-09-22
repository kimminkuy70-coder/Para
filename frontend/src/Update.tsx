import {useEffect,useRef,useState} from 'react';
import {desktop,pickFolder} from './desktop';
import {Stepper,StepNav,notify,fail} from './ui';
import {OpenPath} from './OpenPath';

type Machine={id:string;ip:string;type:string;local:string};
type Prepared={recipes:string[];machines:Machine[];local_source:string;local_source_ok:boolean};
type Question={kind:'match';machine:string;levels:string[];jobs:string[];suggested:Record<string,string[]>}
  |{kind:'setup';machine:string;job:string;title:string;options:string[]};
type Table={rows:[string,string][];parsed:string[];unmatched:string[]};
type Collected={stage:string;collected:string[];errors:{machine:string;error:string}[];tables:Record<string,Table>;coef_missing:{machine:string;variant:string}[];rows:number};
type PreviewRow={recipe:string;missing_form:boolean;carried:boolean;matched_rows:number;filled_cells:number;mismatches:number;mismatch_names:string[]};
type Done={path:string;recipes:{recipe:string;matched_rows:number;filled_cells:number;carried:boolean}[];notes:string[]};
type Answers={match:Record<string,Record<string,string[]>>;setup:Record<string,Record<string,string>>};
const STEPS=['대상 선택','수집','하위 레시피 매칭','결과 확인'];
const NONE='';

export function Update(){
  const [step,setStep]=useState(0);
  const [prep,setPrep]=useState<Prepared>();
  const [recipes,setRecipes]=useState<string[]>([]),[machines,setMachines]=useState<string[]>([]);
  const [source,setSource]=useState<'equipment'|'local'>('equipment'),[localPath,setLocalPath]=useState('');
  const [busy,setBusy]=useState(false),[progressText,setProgressText]=useState('');
  const [answers,setAnswers]=useState<Answers>({match:{},setup:{}});
  const [question,setQuestion]=useState<Question>(),[draft,setDraft]=useState<Record<string,string[]>|string>();
  const [collected,setCollected]=useState<Collected>();
  const [mapping,setMapping]=useState<Record<string,Record<string,string>>>({});
  const [preview,setPreview]=useState<PreviewRow[]>(),[include,setInclude]=useState<string[]>([]);
  const [done,setDone]=useState<Done>();
  const qDialog=useRef<HTMLDialogElement>(null);

  async function load(){
    try{await desktop.connect();const r=(await desktop.request('update_prepare').promise).update as Prepared;
      setPrep(r);setLocalPath(r.local_source);}
    catch(e){fail(e);}
  }
  useEffect(()=>{void load();},[]);
  useEffect(()=>{if(question)qDialog.current?.showModal();else qDialog.current?.close();},[question]);

  async function cancelFlow(silent=false){
    try{await desktop.request('update_cancel').promise;if(!silent)notify('값 업데이트를 취소했습니다.','info');}catch(e){fail(e);}
    setCollected(undefined);setPreview(undefined);setQuestion(undefined);setAnswers({match:{},setup:{}});setStep(0);
  }
  async function collect(next:Answers){
    setBusy(true);setProgressText(source==='equipment'?'장비에서 설정 파일을 읽기 전용으로 복사하고 있습니다…':'로컬 폴더에서 설정 파일을 읽고 있습니다…');
    try{
      const r=(await desktop.request('update_collect',{recipes,machines,source,answers:next}).promise).update as {stage:string;question?:Question}&Collected;
      if(r.stage==='question'&&r.question){
        const q=r.question;setQuestion(q);
        setDraft(q.kind==='match'?Object.fromEntries(q.levels.map(l=>[l,q.suggested[l]||[]])):(q.options[0]||''));
        return;
      }
      setCollected(r);
      // Pre-select the automatic matches (same as the tkinter confirmation window).
      setMapping(Object.fromEntries(Object.entries(r.tables).map(([rec,t])=>[rec,Object.fromEntries(t.rows.map(([form,auto])=>[form,auto]))])));
      if(r.errors.length)notify(`수집 실패 ${r.errors.length}대: `+r.errors.map(e=>`${e.machine}(${e.error})`).join(', '),'error');
      setStep(Object.keys(r.tables).length?2:3);
      if(!Object.keys(r.tables).length)await runPreview({});
    }catch(e){fail(e);setStep(0);}
    finally{setBusy(false);setProgressText('');}
  }
  function answer(){
    if(!question||draft===undefined)return;
    const next:Answers={match:{...answers.match},setup:{...answers.setup}};
    if(question.kind==='match'){
      const chosen=draft as Record<string,string[]>;
      if(!Object.values(chosen).some(v=>v.length)){notify('레시피별 Job 폴더를 하나 이상 고르세요.','error');return;}
      next.match[question.machine]=chosen;
    }else{
      next.setup[question.machine]={...(next.setup[question.machine]||{}),[question.job]:draft as string};
    }
    setAnswers(next);setQuestion(undefined);void collect(next);
  }
  async function runPreview(map:Record<string,string>){
    setBusy(true);
    try{const r=(await desktop.request('update_preview',{mapping:map}).promise).update as {recipes:PreviewRow[]};
      setPreview(r.recipes);setInclude([]);setStep(3);}
    catch(e){fail(e);}finally{setBusy(false);}
  }
  function mappingPayload(){
    // {수집 이름: 양식 이름}; a form variant left on 'none' is simply not filled.
    const out:Record<string,string>={};
    Object.values(mapping).forEach(rows=>Object.entries(rows).forEach(([form,copied])=>{if(copied&&copied!==form)out[copied]=form;}));
    return out;
  }
  async function commit(){
    setBusy(true);
    try{const r=(await desktop.request('update_commit',{include}).promise).update as Done;
      setDone(r);setStep(0);notify('파라미터 값 취합 파일을 만들었습니다.','ok');setCollected(undefined);setPreview(undefined);setAnswers({match:{},setup:{}});}
    catch(e){fail(e);}finally{setBusy(false);}
  }
  async function saveLocal(path:string){
    try{const r=(await desktop.request('update_set_local_source',{path}).promise).update as Prepared;setPrep(r);setLocalPath(r.local_source);notify('로컬 상위 폴더 저장','ok');}
    catch(e){fail(e);}
  }
  if(!prep)return <section className="panel"><p className="table-empty">불러오는 중…</p></section>;
  const available=prep.machines.filter(m=>source==='equipment'?m.ip:m.local);
  const ready=recipes.length>0&&machines.length>0&&(source==='equipment'||prep.local_source_ok);

  return <section className="panel">
    <div className="section-heading"><div><span className="step">VALUE UPDATE</span><h2>파라미터 값 업데이트</h2></div>
      <button disabled={busy} onClick={load}>목록 새로고침</button></div>
    <Stepper labels={STEPS} current={step}/>
    <div className="step-body">
    {step===0&&<>
      {done&&<div className="outputs"><h3>완료 · 새 취합 파일</h3><OpenPath label="취합 파일" path={done.path}/>
        <ul>{done.recipes.map(r=><li key={r.recipe}>{r.recipe}: {r.carried?'직전 취합본 값 유지':`매칭 ${r.matched_rows}행 · 값 ${r.filled_cells}칸`}</li>)}{done.notes.map(n=><li key={n}>{n}</li>)}</ul>
        <p className="hint">Recipe 관리 화면에서 [최신 취합 새로고침]을 누르면 반영됩니다.</p></div>}
      <p className="hint">레시피 양식에 맞춰 장비(또는 로컬 복사본)의 값을 읽어 새 '파라미터 값 취합' 파일을 만듭니다. 이번에 고르지 않은 호기·레시피는 직전 취합본 값을 유지합니다. 장비 원본은 읽기만 합니다.</p>
      <h3>① 레시피</h3>
      {prep.recipes.length?<div className="pick-list short cols">{prep.recipes.map(r=><label key={r} className="pick-item"><input type="checkbox" checked={recipes.includes(r)} onChange={e=>setRecipes(x=>e.target.checked?[...x,r]:x.filter(v=>v!==r))}/> {r}</label>)}</div>
        :<p className="table-empty">확정된 양식이 없습니다. [양식 만들기]를 먼저 하세요.</p>}
      <h3>② 수집 방식</h3>
      <div className="toolbar"><label className="field checkbox"><input type="radio" name="source" checked={source==='equipment'} onChange={()=>{setSource('equipment');setMachines([]);}}/>🖥 장비 IP에서 수집</label>
        <label className="field checkbox"><input type="radio" name="source" checked={source==='local'} onChange={()=>{setSource('local');setMachines([]);}}/>📁 로컬 복사본에서</label></div>
      {source==='equipment'?<p className="hint">※ 고른 장비는 먼저 탐색기(Win+R)로 \\장비IP\c$ 에 한 번 연결돼 있어야 합니다(비밀번호 입력 없음). 복사본은 로컬 작업 폴더에만 둡니다.</p>
        :<div className="form-filter"><label className="field" style={{flex:1,minWidth:260}}>로컬 상위 폴더(그 아래 호기 이름 폴더를 찾습니다)<input value={localPath} onChange={e=>setLocalPath(e.target.value)} maxLength={4096}/></label>
          <button onClick={async()=>{const p=await pickFolder();if(p){setLocalPath(p);void saveLocal(p);}}}>📁 찾기</button>
          <button disabled={!localPath.trim()} onClick={()=>saveLocal(localPath.trim())}>저장</button></div>}
      <h3>③ 호기 <button type="button" className="linklike" onClick={()=>setMachines(x=>x.length===available.length?[]:available.map(m=>m.id))}>{machines.length===available.length&&available.length?'전체 해제':'전체 선택'}</button></h3>
      {prep.machines.length?<div className="pick-list short cols">{prep.machines.map(m=>{const ok=source==='equipment'?!!m.ip:!!m.local;
        return <label key={m.id} className={'pick-item'+(ok?'':' muted')} title={source==='equipment'?m.ip||'IP 없음':m.local||'폴더 없음'}>
          <input type="checkbox" disabled={!ok} checked={machines.includes(m.id)} onChange={e=>setMachines(x=>e.target.checked?[...x,m.id]:x.filter(v=>v!==m.id))}/> {m.id}{m.type==='KLA'?' (KLA)':''}</label>;})}</div>
        :<p className="table-empty">[장비 IP] 문서에 호기가 없습니다.</p>}
    </>}
    {step===1&&<div className="runbar"><div><strong>{busy?'수집 중…':'대기'}</strong><p role="status">{progressText||'장비 선택이 필요하면 창이 열립니다.'}</p></div>
      <div className="actions"><button disabled={busy} onClick={()=>cancelFlow()}>취소</button></div></div>}
    {step===1&&busy&&<div className="progress-line" role="progressbar" aria-label="수집 중"><span/></div>}
    {step===2&&collected&&<>
      <p className="hint">상위 레시피는 같아도 하위 레시피 이름이 다르면 값이 채워지지 않습니다. 왼쪽(양식의 하위 레시피)에 대응하는 오른쪽(수집한 이름)을 고르세요. 이름이 같으면 자동으로 골라져 있습니다.</p>
      <p className="hint">수집: {collected.collected.join(', ')} · 설정 {collected.rows.toLocaleString()}행{collected.coef_missing.length?` · ⚠ 변환계수 없음 ${collected.coef_missing.length}건(기본 계수로 계산)`:''}</p>
      {Object.entries(collected.tables).map(([rec,t])=><div key={rec} className="outputs"><h3>[{rec}]</h3>
        <table className="tbl"><thead><tr><th>양식의 하위 레시피</th><th>수집한 레시피 이름</th></tr></thead><tbody>{t.rows.map(([form])=><tr key={form}>
          <td>{form||'(빈칸)'}</td><td><select aria-label={`${rec} ${form||'빈칸'} 매칭`} value={mapping[rec]?.[form]??NONE} onChange={e=>setMapping(m=>({...m,[rec]:{...m[rec],[form]:e.target.value}}))}>
            <option value={NONE}>— 없음(이 항목은 안 채움) —</option>{t.parsed.map(p=><option key={p} value={p}>{p||'(빈칸)'}</option>)}</select></td></tr>)}</tbody></table>
        {t.unmatched.length>0&&<p className="hint">양식에 없는 수집 레시피(선택 안 하면 무시): {t.unmatched.join(', ')}</p>}</div>)}
    </>}
    {step===3&&preview&&<>
      <table className="tbl"><thead><tr><th>레시피</th><th>결과</th><th>포함</th></tr></thead><tbody>{preview.map(r=><tr key={r.recipe}>
        <td>{r.recipe}</td>
        <td>{r.missing_form?'양식 없음(건너뜀)':r.carried?'이번에 안 고름 — 직전 값 유지':`매칭 ${r.matched_rows}행 · 값 ${r.filled_cells}칸`}
          {r.mismatches>0&&<p className="warn">양식과 장비 파일의 파라미터 불일치 {r.mismatches}개: {r.mismatch_names.slice(0,12).join(', ')}{r.mismatches>12?' …':''}</p>}</td>
        <td>{r.mismatches>0&&!r.missing_form?<label className="field checkbox"><input type="checkbox" checked={include.includes(r.recipe)} onChange={e=>setInclude(x=>e.target.checked?[...x,r.recipe]:x.filter(v=>v!==r.recipe))}/>그래도 포함</label>:r.missing_form?'—':'포함'}</td></tr>)}</tbody></table>
      <p className="hint">불일치 항목은 값 없이 유지됩니다. 저장하면 새 '파라미터 값 취합' 파일이 저장폴더에 만들어집니다.</p>
    </>}
    </div>
    {step!==1&&<StepNav step={step} total={STEPS.length} busy={busy}
      onBack={()=>{if(step===3&&collected&&Object.keys(collected.tables).length)setStep(2);else if(step>=2)void cancelFlow(true);else setStep(0);}}
      onNext={()=>{if(step===0){setDone(undefined);setAnswers({match:{},setup:{}});setStep(1);void collect({match:{},setup:{}});}
        else if(step===2)void runPreview(mappingPayload());else if(step===3)void commit();}}
      nextLabel={step===0?'수집 시작':step===2?'매칭 확인':'취합 저장'} nextDisabled={step===0&&!ready}/>}

    <dialog className="edit-dialog wide-dialog" ref={qDialog} onCancel={e=>{e.preventDefault();}}>{question&&<>
      {question.kind==='match'?<>
        <h2>{question.machine} · 레시피 ↔ Job 폴더</h2>
        <p className="hint">레시피마다 장비 Job 폴더를 고르세요(복수 선택). 이름이 맞는 폴더는 미리 체크했습니다. 고른 Job 안의 Recipe 를 전부 수집합니다. 다음 호기는 같은 Job 이름으로 자동 매칭합니다.</p>
        {question.levels.map(l=><div key={l}><h3>{l}</h3><div className="pick-list short">{question.jobs.map(j=>{const cur=(draft as Record<string,string[]>)?.[l]||[];
          return <label key={j} className="pick-item"><input type="checkbox" checked={cur.includes(j)} onChange={e=>setDraft(d=>{const o={...(d as Record<string,string[]>)};o[l]=e.target.checked?[...cur,j]:cur.filter(v=>v!==j);return o;})}/> {j}{question.suggested[l]?.includes(j)?'  ◀ 추천':''}</label>;})}
          {question.jobs.length===0&&<p className="table-empty">장비에서 Job 폴더를 찾지 못했습니다.</p>}</div></div>)}
      </>:<>
        <h2>{question.machine} · Setup 선택</h2><p className="hint">{question.title}</p>
        <div className="pick-list short">{question.options.map(o=><label key={o} className="pick-item"><input type="radio" name="setup" checked={draft===o} onChange={()=>setDraft(o)}/> {o}</label>)}</div>
      </>}
      <div className="dialog-actions"><button onClick={()=>void cancelFlow()}>수집 취소</button><button className="primary" onClick={answer}>확인하고 계속</button></div></>}
    </dialog>
  </section>;
}
