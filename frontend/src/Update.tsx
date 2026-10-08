import {useEffect,useState} from 'react';
import {desktop,pickFolder,errorText} from './desktop';
import {Stepper,StepNav,notify,fail,LoadFailed} from './ui';
import {OpenPath} from './OpenPath';
import {QuestionDialog,withAnswer,withSkip,noAnswers,type Question,type Answers} from './CollectQuestion';
import {RowPick} from './RowPick';

type Machine={id:string;ip:string;type:string;local:string};
type Prepared={recipes:string[];machines:Machine[];local_source:string;local_source_ok:boolean};
type Table={rows:[string,string][];parsed:string[];unmatched:string[]};
type Collected={stage:string;collected:string[];errors:{machine:string;error:string}[];tables:Record<string,Table>;coef_missing:{machine:string;variant:string}[];rows:number};
type PreviewRow={recipe:string;missing_form:boolean;carried:boolean;matched_rows:number;filled_cells:number;mismatches:number;mismatch_names:string[]};
type DoneRecipe={recipe:string;matched_rows:number;filled_cells:number;carried:boolean;
  changed?:number;added?:number;removed?:number;new_rows?:number;gone_rows?:number;changed_machines?:string[];new_sheet?:boolean};
type Done={path:string;recipes:DoneRecipe[];notes:string[];previous?:string};
type Conn={machine:string;ip:string;unc:string;ok:boolean;reason:string};
const STEPS=['대상 선택','장비 연결 확인','수집','하위 레시피 매칭','취합 미리보기','결과 확인'];
// 단계 번호(#22 에서 '장비 연결 확인' 이 들어가며 하나씩 밀림). 로컬 복사본은 연결 확인을 건너뛴다.
const SELECT=0,CONNECT=1,COLLECT=2,VARIANTS=3,PREVIEW=4,RESULT=5;
const changedOf=(r:DoneRecipe)=>(r.changed||0)+(r.added||0)+(r.removed||0)+(r.new_rows||0)+(r.gone_rows||0)+(r.new_sheet?1:0);
const NONE='';

export function Update(){
  const [step,setStep]=useState(0);
  const [prep,setPrep]=useState<Prepared>();
  const [recipes,setRecipes]=useState<string[]>([]),[machines,setMachines]=useState<string[]>([]);
  const [source,setSource]=useState<'equipment'|'local'>('equipment'),[localPath,setLocalPath]=useState('');
  const [busy,setBusy]=useState(false),[progressText,setProgressText]=useState('');
  const [answers,setAnswers]=useState<Answers>(noAnswers());
  const [question,setQuestion]=useState<Question>();
  const [collected,setCollected]=useState<Collected>();
  const [mapping,setMapping]=useState<Record<string,Record<string,string>>>({});
  const [preview,setPreview]=useState<PreviewRow[]>(),[include,setInclude]=useState<string[]>([]);
  const [done,setDone]=useState<Done>();
  const [conns,setConns]=useState<Conn[]>(),[targets,setTargets]=useState<string[]>([]);

  const [loadError,setLoadError]=useState('');
  async function load(){
    setLoadError('');
    try{await desktop.connect();const r=(await desktop.request('update_prepare').promise).update as Prepared;
      setPrep(r);setLocalPath(r.local_source);}
    catch(e){setLoadError(errorText(e));}
  }
  useEffect(()=>{void load();},[]);

  async function cancelFlow(silent=false){
    try{await desktop.request('update_cancel').promise;if(!silent)notify('Recipe 업데이트를 취소했습니다.','info');}catch(e){fail(e);}
    setCollected(undefined);setPreview(undefined);setQuestion(undefined);setAnswers(noAnswers());setConns(undefined);setStep(SELECT);
  }
  async function checkConnections(){
    // #22: 수집 전에 고른 호기가 지금 연결돼 있는지 보고, 연결된 호기만 체크한 목록으로 진행 여부를 묻는다.
    setStep(CONNECT);setConns(undefined);setBusy(true);setProgressText('고른 호기의 장비 연결을 확인하고 있습니다…');
    try{const r=(await desktop.request('update_connections',{machines}).promise).update as {results:Conn[]};
      setConns(r.results);setTargets(r.results.filter(c=>c.ok).map(c=>c.machine));}
    catch(e){fail(e);setStep(SELECT);}
    finally{setBusy(false);setProgressText('');}
  }
  function startCollect(list:string[]){
    setTargets(list);setAnswers(noAnswers());setStep(COLLECT);void collect(noAnswers(),list);
  }
  async function collect(next:Answers,list=targets){
    setBusy(true);setProgressText(source==='equipment'?'장비에서 설정 파일을 읽기 전용으로 복사하고 있습니다…':'로컬 폴더에서 설정 파일을 읽고 있습니다…');
    try{
      const r=(await desktop.request('update_collect',{recipes,machines:list,source,answers:next}).promise).update as {stage:string;question?:Question}&Collected;
      if(r.stage==='question'&&r.question){
        setQuestion(r.question);
        return;
      }
      setCollected(r);
      // Pre-select the automatic matches (same as the tkinter confirmation window).
      setMapping(Object.fromEntries(Object.entries(r.tables).map(([rec,t])=>[rec,Object.fromEntries(t.rows.map(([form,auto])=>[form,auto]))])));
      if(r.errors.length)notify(`수집 실패 ${r.errors.length}대: `+r.errors.map(e=>`${e.machine}(${e.error})`).join(', '),'error');
      setStep(Object.keys(r.tables).length?VARIANTS:PREVIEW);
      if(!Object.keys(r.tables).length)await runPreview({});
    }catch(e){fail(e);setStep(SELECT);}
    finally{setBusy(false);setProgressText('');}
  }
  function answer(value:Record<string,string[]>|string){
    if(!question)return;
    const next=withAnswer(answers,question,value);
    setAnswers(next);setQuestion(undefined);void collect(next);
  }
  function skipMachine(){
    // 장비에 이 레시피가 없을 때: 이 호기는 수집하지 않고 다음 호기로(취합에서는 직전 값 유지).
    if(!question)return;
    const next=withSkip(answers,question.machine);
    notify(`${question.machine} 은(는) 건너뜁니다.`,'info');
    setAnswers(next);setQuestion(undefined);void collect(next);
  }
  async function runPreview(map:Record<string,string>){
    setBusy(true);
    try{const r=(await desktop.request('update_preview',{mapping:map}).promise).update as {recipes:PreviewRow[]};
      setPreview(r.recipes);setInclude([]);setStep(PREVIEW);}
    catch(e){fail(e);}finally{setBusy(false);}
  }
  function restart(){setDone(undefined);setRecipes([]);setMachines([]);setConns(undefined);setTargets([]);setStep(SELECT);}
  function mappingPayload(){
    // {수집 이름: 양식 이름}; a form variant left on 'none' is simply not filled.
    const out:Record<string,string>={};
    Object.values(mapping).forEach(rows=>Object.entries(rows).forEach(([form,copied])=>{if(copied&&copied!==form)out[copied]=form;}));
    return out;
  }
  async function commit(){
    setBusy(true);
    try{const r=(await desktop.request('update_commit',{include}).promise).update as Done;
      setDone(r);setStep(RESULT);notify('파라미터 값 취합 파일을 만들었습니다.','ok');setCollected(undefined);setPreview(undefined);setAnswers(noAnswers());}
    catch(e){fail(e);}finally{setBusy(false);}
  }
  async function saveLocal(path:string){
    try{const r=(await desktop.request('update_set_local_source',{path}).promise).update as Prepared;setPrep(r);setLocalPath(r.local_source);notify('로컬 상위 폴더 저장','ok');}
    catch(e){fail(e);}
  }
  if(!prep)return <section className="panel">{loadError?<LoadFailed message={loadError} onRetry={()=>void load()}/>:<p className="table-empty">불러오는 중…</p>}</section>;
  const available=prep.machines.filter(m=>source==='equipment'?m.ip:m.local);
  const ready=recipes.length>0&&machines.length>0&&(source==='equipment'||prep.local_source_ok);

  return <section className="panel">
    <div className="section-heading"><div><span className="step">RECIPE UPDATE</span><h2>Recipe 업데이트 — 장비 값 수집·취합</h2></div>
      <button disabled={busy} onClick={load}>목록 새로고침</button></div>
    <Stepper labels={STEPS} current={step}/>
    <div className="step-body">
    {step===SELECT&&<>
      <p className="hint">레시피 양식에 맞춰 장비(또는 로컬 복사본)의 값을 읽어 새 '파라미터 값 취합' 파일을 만듭니다. 이번에 고르지 않은 호기·레시피는 직전 취합본 값을 유지합니다. 장비 원본은 읽기만 합니다.</p>
      <h3>① 레시피</h3>
      <RowPick label="레시피" columns={['레시피']} value={recipes} onChange={setRecipes}
        rows={prep.recipes.map(r=>({id:r,cells:[r]}))}
        empty={<p className="table-empty">확정된 양식이 없습니다. [신규 Recipe 만들기]를 먼저 하세요.</p>}/>
      <h3>② 수집 방식</h3>
      <div className="source-choice" role="radiogroup" aria-label="수집 방식">
        <label><input type="radio" name="source" checked={source==='equipment'} onChange={()=>{setSource('equipment');setMachines([]);}}/>🖥 장비 IP에서 수집</label>
        <label><input type="radio" name="source" checked={source==='local'} onChange={()=>{setSource('local');setMachines([]);}}/>📁 로컬 복사본에서</label></div>
      {source==='equipment'?<p className="hint">※ 고른 장비는 먼저 탐색기(Win+R)로 \\장비IP\c$ 에 한 번 연결돼 있어야 합니다(비밀번호 입력 없음). 복사본은 로컬 작업 폴더에만 둡니다.</p>
        :<div className="form-filter"><label className="field" style={{flex:1,minWidth:260}}>로컬 상위 폴더(그 아래 호기 이름 폴더를 찾습니다)<input value={localPath} onChange={e=>setLocalPath(e.target.value)} maxLength={4096}/></label>
          <button onClick={async()=>{const p=await pickFolder();if(p){setLocalPath(p);void saveLocal(p);}}}>📁 찾기</button>
          <button disabled={!localPath.trim()} onClick={()=>saveLocal(localPath.trim())}>저장</button></div>}
      <h3>③ 호기</h3>
      <RowPick label="호기" columns={['호기',source==='equipment'?'IP':'로컬 폴더','장비 종류']} value={machines} onChange={setMachines}
        rows={prep.machines.map(m=>{const where=source==='equipment'?m.ip:m.local;
          return {id:m.id,disabled:!where,title:where||(source==='equipment'?'IP 없음':'폴더 없음'),
            cells:[<b key="m">{m.id}</b>,where?<code key="w">{where}</code>:<span key="w" className="warn">{source==='equipment'?'IP 없음':'폴더 없음'}</span>,m.type||'—']};})}
        empty={<p className="table-empty">[장비 IP] 문서에 호기가 없습니다.</p>}/>
    </>}
    {step===CONNECT&&<>
      {busy||!conns?<><div className="runbar"><div><strong>연결 확인 중…</strong><p role="status">{progressText||'고른 호기의 장비 연결을 확인하고 있습니다…'}</p></div></div>
        <div className="progress-line" role="progressbar" aria-label="연결 확인 중"><span/></div></>
      :<>
        <p className="hint" role="note">{conns.some(c=>c.ok)
          ?<>연결된 장비는 <b>{conns.filter(c=>c.ok).map(c=>c.machine).join(', ')}</b> 입니다. 이 장비들로만 업데이트를 진행할까요? 필요하면 아래에서 더 체크하거나 해제하세요.</>
          :<>고른 장비가 하나도 연결돼 있지 않습니다. 탐색기(Win+R)에서 \\장비IP\c$ 에 먼저 로그인한 뒤 [다시 확인]을 누르거나, 아래에서 직접 체크하세요.</>}</p>
        <p className="hint">연결 {conns.filter(c=>c.ok).length} / {conns.length}대 · 체크하지 않은 호기는 이번에 수집하지 않고 직전 취합본 값을 유지합니다.</p>
        <RowPick label="진행할 호기" columns={['호기','연결','주소','안내']} value={targets} onChange={setTargets}
          rows={conns.map(c=>({id:c.machine,title:c.reason||c.unc,
            cells:[<b key="m">{c.machine}</b>,c.ok?<span key="s">✅ 연결됨</span>:<span key="s" className="warn">⚠ 미연결</span>,
              c.unc?<code key="u">{c.unc}</code>:'—',c.reason||'—']}))}/>
        <div className="toolbar"><button disabled={busy} onClick={()=>void checkConnections()}>⟳ 다시 확인</button></div>
      </>}
    </>}
    {step===COLLECT&&<div className="runbar"><div><strong>{busy?'수집 중…':'대기'}</strong><p role="status">{progressText||'장비 선택이 필요하면 창이 열립니다.'}</p></div>
      <div className="actions"><button disabled={busy} onClick={()=>cancelFlow()}>취소</button></div></div>}
    {step===COLLECT&&busy&&<div className="progress-line" role="progressbar" aria-label="수집 중"><span/></div>}
    {step===VARIANTS&&collected&&<>
      <p className="hint">상위 레시피는 같아도 하위 레시피 이름이 다르면 값이 채워지지 않습니다. 왼쪽(양식의 하위 레시피)에 대응하는 오른쪽(수집한 이름)을 고르세요. 이름이 같으면 자동으로 골라져 있습니다.</p>
      <p className="hint">수집: {collected.collected.join(', ')} · 설정 {collected.rows.toLocaleString()}행{collected.coef_missing.length?` · ⚠ 변환계수 없음 ${collected.coef_missing.length}건(기본 계수로 계산)`:''}</p>
      {Object.entries(collected.tables).map(([rec,t])=><div key={rec} className="outputs"><h3>[{rec}]</h3>
        <table className="tbl"><thead><tr><th>양식의 하위 레시피</th><th>수집한 레시피 이름</th></tr></thead><tbody>{t.rows.map(([form])=><tr key={form}>
          <td>{form||'(빈칸)'}</td><td><select aria-label={`${rec} ${form||'빈칸'} 매칭`} value={mapping[rec]?.[form]??NONE} onChange={e=>setMapping(m=>({...m,[rec]:{...m[rec],[form]:e.target.value}}))}>
            <option value={NONE}>— 없음(이 항목은 안 채움) —</option>{t.parsed.map(p=><option key={p} value={p}>{p||'(빈칸)'}</option>)}</select></td></tr>)}</tbody></table>
        {t.unmatched.length>0&&<p className="hint">양식에 없는 수집 레시피(선택 안 하면 무시): {t.unmatched.join(', ')}</p>}</div>)}
    </>}
    {step===PREVIEW&&preview&&<>
      <table className="tbl"><thead><tr><th>레시피</th><th>결과</th><th>포함</th></tr></thead><tbody>{preview.map(r=><tr key={r.recipe}>
        <td>{r.recipe}</td>
        <td>{r.missing_form?'양식 없음(건너뜀)':r.carried?'이번에 안 고름 — 직전 값 유지':`매칭 ${r.matched_rows}행 · 값 ${r.filled_cells}칸`}
          {r.mismatches>0&&<p className="warn">양식과 장비 파일의 파라미터 불일치 {r.mismatches}개: {r.mismatch_names.slice(0,12).join(', ')}{r.mismatches>12?' …':''}</p>}</td>
        <td>{r.mismatches>0&&!r.missing_form?<label className="field checkbox"><input type="checkbox" checked={include.includes(r.recipe)} onChange={e=>setInclude(x=>e.target.checked?[...x,r.recipe]:x.filter(v=>v!==r.recipe))}/>그래도 포함</label>:r.missing_form?'—':'포함'}</td></tr>)}</tbody></table>
      <p className="hint">불일치 항목은 값 없이 유지됩니다. 저장하면 새 '파라미터 값 취합' 파일이 저장폴더에 만들어집니다.</p>
    </>}
    {step===RESULT&&done&&<div className="update-result">
      <h3>완료 · 새 취합 파일</h3>
      <p className="hint">{done.previous?`직전 취합본(${done.previous})과 비교한 결과입니다. 이번에 바뀐 레시피는 색으로 표시했습니다.`:'첫 취합 파일입니다(비교할 직전 취합본 없음).'}</p>
      <table className="tbl"><thead><tr><th>레시피</th><th>처리</th><th>값 변경</th><th>새로 채운 값</th><th>지워진 값</th><th>새 항목</th><th>빠진 항목</th><th>바뀐 호기</th></tr></thead>
        <tbody>{done.recipes.map(r=>{const hot=changedOf(r)>0;const n=(v?:number)=><td className={'num'+(v?' hot':'')}>{v||0}</td>;
          return <tr key={r.recipe} className={hot?'row-changed':''}>
            <td><b>{r.recipe}</b>{r.new_sheet&&<span className="badge"> 새 레시피</span>}</td>
            <td>{r.carried?'직전 값 유지(이번에 안 고름)':`매칭 ${r.matched_rows}행 · 값 ${r.filled_cells}칸`}</td>
            {n(r.changed)}{n(r.added)}{n(r.removed)}{n(r.new_rows)}{n(r.gone_rows)}
            <td>{r.changed_machines?.length?r.changed_machines.join(', '):hot?'—':'변경 없음'}</td></tr>;})}</tbody></table>
      {done.notes.length>0&&<ul>{done.notes.map(x=><li key={x}>{x}</li>)}</ul>}
      <OpenPath label="취합 파일 경로" path={done.path}/>
      <p className="hint">[Recipe 값 확인]에서 [최신 취합 새로고침]을 누르면 반영됩니다. 바뀐 칸을 자세히 보려면 [레시피 날짜별 비교하기]를 쓰세요.</p>
      <div className="stepnav"><span/><span className="stepcount">{STEPS.length} / {STEPS.length}</span>
        <button className="btn primary" onClick={restart}>⟲ 처음으로</button></div>
    </div>}
    </div>
    {step!==COLLECT&&step!==RESULT&&<StepNav step={step} total={STEPS.length} busy={busy}
      onBack={()=>{if(step===PREVIEW&&collected&&Object.keys(collected.tables).length)setStep(VARIANTS);else if(step>=VARIANTS)void cancelFlow(true);else setStep(SELECT);}}
      onNext={()=>{if(step===SELECT){if(source==='equipment')void checkConnections();else startCollect(machines);}
        else if(step===CONNECT)startCollect(targets);
        else if(step===VARIANTS)void runPreview(mappingPayload());else if(step===PREVIEW)void commit();}}
      nextLabel={step===SELECT?(source==='equipment'?'연결 확인':'수집 시작'):step===CONNECT?'이 호기들로 수집 시작':step===VARIANTS?'매칭 확인':'취합 저장'}
      nextDisabled={(step===SELECT&&!ready)||(step===CONNECT&&(!conns||!targets.length))}/>}

    <QuestionDialog question={question} onAnswer={answer} onCancel={()=>void cancelFlow()} onSkip={skipMachine}/>
  </section>;
}
