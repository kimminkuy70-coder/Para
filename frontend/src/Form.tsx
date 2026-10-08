import {useEffect,useRef,useState} from 'react';
import {desktop,errorText} from './desktop';
import {Stepper,StepNav,notify,fail,LoadFailed} from './ui';
import {OpenPath} from './OpenPath';
import {FormEditor} from './FormEditor';
import {QuestionDialog,withAnswer,noAnswers,type Question,type Answers} from './CollectQuestion';
import {pickFolder} from './desktop';
import {RowPick} from './RowPick';
import {openPath} from './OpenPath';

type Version={stamp:string;has_candidate:boolean;kind:string;candidate?:string;machine?:string};
type Recipe={recipe:string};
type Catalog={save_dir:boolean;recipes:Recipe[];machines?:string[]};
type Opened={version:string;recipe:string;level:string;variants:string[];total:number;used:number;source:string;machine?:string};
type Scale={variant:string;coef:number;source:string;needed:boolean};
type NewPrep={machines:{id:string;ip:string;local:string;type:string}[];local_source:string;local_source_ok:boolean;existing:string[]};
type NewScale={variant:string;coef:number;source:string;confidence:string;reason:string;machines:string[]};
type Confirmed={final:string;original:string;kept:number;total:number;sheet:string;name_note:string;
  coef:{saved:number;defaulted:string[];unregistered:string[];error:string};
  merge:{collate:string;added:number;error:string}|null};
const STEPS=['원본 선택','항목 편집','확정'];
// 신규는 수집 뒤 '하위 레시피 선택' 단계가 하나 더 있다(이슈 #20 — 공통된 하위 레시피만 양식에 넣기).
const STEPS_NEW=['원본 선택','하위 레시피 선택','항목 편집','확정'];

/** Recipe 양식 편집하기 (mode 'edit') / 신규 Recipe 만들기 (mode 'new'): two tabs of Recipe 관리.
 *  They use separate engine editors (form_* / formnew_*) so both can be open at once. */
export function Form({mode}:{mode:'edit'|'new'}){
  const api=mode==='new'?'formnew':'form';
  const steps=mode==='new'?STEPS_NEW:STEPS;
  const EDIT=steps.length-2,CONFIRM=steps.length-1;
  const [step,setStep]=useState(0);
  const [catalog,setCatalog]=useState<Catalog>();
  const [recipe,setRecipe]=useState(''),[stamp,setStamp]=useState('');
  const [opened,setOpened]=useState<Opened>();
  const [loading,setLoading]=useState(false),[busy,setBusy]=useState(false);
  const [machine,setMachine]=useState(''),[result,setResult]=useState<Confirmed>();
  // 새로 만들기(장비/로컬 수집) — tkinter _form_new.
  const [newPrep,setNewPrep]=useState<NewPrep>(),[newName,setNewName]=useState(''),[newSource,setNewSource]=useState<'equipment'|'local'>('equipment');
  const [newMachines,setNewMachines]=useState<string[]>([]),[answers,setAnswers]=useState<Answers>(noAnswers()),[question,setQuestion]=useState<Question>();
  const [newScales,setNewScales]=useState<NewScale[]>(),[newScaleEdit,setNewScaleEdit]=useState<Record<string,string>>({}),[localPath,setLocalPath]=useState('');
  const [similar,setSimilar]=useState<{recipe:string;match:number;total:number}[]>([]),[baseForm,setBaseForm]=useState('');
  const [newPick,setNewPick]=useState<string[]>([]),[newCollected,setNewCollected]=useState<string[]>([]);
  // Versions are read only for the chosen recipe (not every recipe at once — OneDrive rule).
  const [recipeVersions,setRecipeVersions]=useState<{recipe:string;versions:Version[];can_edit:boolean}>();
  useEffect(()=>{
    if(!recipe){setRecipeVersions(undefined);return;}
    let active=true;
    desktop.request('form_versions',{recipe}).promise.then(r=>{if(active)setRecipeVersions(r.form as {recipe:string;versions:Version[];can_edit:boolean});})
      .catch(e=>{if(active){fail(e);setRecipeVersions({recipe,versions:[],can_edit:true});}});   // never leave '원본 열기' stuck
    return()=>{active=false;};
  },[recipe]);
  const [scales,setScales]=useState<Scale[]>([]),[scaleEdits,setScaleEdits]=useState<Record<string,string>>({});

  async function loadCatalog(){
    setLoading(true);
    try{await desktop.connect();const reply=await desktop.request('form_catalog').promise;
      setCatalog(reply.form as Catalog);}
    catch(e){fail(e);}finally{setLoading(false);}
  }
  // The 'new' tab never loads the edit catalog: that would reset the other tab's open editor.
  useEffect(()=>{if(mode==='edit')void loadCatalog();},[mode]);

  const [newPrepError,setNewPrepError]=useState(''),[newPrepTry,setNewPrepTry]=useState(0);
  useEffect(()=>{if(mode==='new'&&!newPrep){setNewPrepError('');desktop.request('formnew_prepare').promise
    .then(r=>{const p=r.formnew as NewPrep;setNewPrep(p);setLocalPath(p.local_source);}).catch(e=>setNewPrepError(errorText(e)));}},[mode,newPrepTry]);
  async function newCollect(next:Answers){
    setBusy(true);
    try{const r=(await desktop.request('formnew_collect',{recipe:newName.trim(),machines:newMachines,source:newSource,answers:next}).promise).formnew as
        {stage:string;question?:Question;scales?:NewScale[];collected?:string[];errors?:{machine:string;error:string}[]};
      if(r.stage==='question'&&r.question){setQuestion(r.question);return;}
      setNewScales(r.scales);setNewScaleEdit({});setNewCollected(r.collected||[]);
      setNewPick((r.scales||[]).map(x=>x.variant));if(r.scales?.length)setStep(1);
      if(r.errors?.length)notify(`수집 실패 ${r.errors.length}대: `+r.errors.map(e=>`${e.machine}(${e.error})`).join(', '),'error');}
    catch(e){fail(e);}finally{setBusy(false);}
  }
  const newScaleValue=(x:NewScale)=>newScaleEdit[x.variant]??String(x.coef);
  const newPicked=(newScales||[]).filter(x=>newPick.includes(x.variant));
  const newScaleBad=newPicked.some(x=>!(Number(newScaleValue(x))>0));
  // 모든 수집 호기에서 읽힌 하위 레시피 = 공통 하위 레시피.
  const newCommon=(newScales||[]).filter(x=>newCollected.length>0&&newCollected.every(m=>x.machines.includes(m))).map(x=>x.variant);
  async function newParse(base=baseForm){
    if(!newScales||!newPicked.length)return;
    setBusy(true);
    try{const r=(await desktop.request('formnew_parse',{scales:Object.fromEntries(newPicked.map(x=>[x.variant,Number(newScaleValue(x))])),base_form:base,
        variants:newPicked.map(x=>x.variant)}).promise).formnew as
        {form:Opened;similar:{recipe:string;match:number;total:number}[];base_form:string};
      setOpened(r.form);setSimilar(r.similar);setBaseForm(r.base_form);setResult(undefined);setStep(steps.length-2);}
    catch(e){fail(e);}finally{setBusy(false);}
  }
  async function saveLocal(path:string){
    try{const r=(await desktop.request('update_set_local_source',{path}).promise).update as NewPrep;
      setNewPrep(p=>p&&{...p,...r});setLocalPath(r.local_source);notify('로컬 상위 폴더 저장','ok');}catch(e){fail(e);}
  }
  async function open(r:string,s:string){
    setResult(undefined);setBusy(true);
    try{const reply=await desktop.request('form_open',{recipe:r,stamp:s}).promise;
      const o=reply.form as Opened;setOpened(o);setStep(1);}
    catch(e){setOpened(undefined);fail(e);}finally{setBusy(false);}
  }
  // 확정 호기는 묻지 않는다: 편집 = 그 양식을 처음 만든 호기(파일 이름), 신규 = 수집한 호기.
  useEffect(()=>{setMachine(opened?.machine||'');},[opened?.version]);  // eslint-disable-line react-hooks/exhaustive-deps
  const confirmMachine=machine.trim()||'미지정';
  // Coefficients for LINEAR/AREA items of the chosen machine (변환계수.xlsx → 원본 라벨 → 기본값).
  useEffect(()=>{
    if(step!==CONFIRM||!opened){setScales([]);return;}
    let active=true;
    desktop.request(`${api}_scales`,{snapshot:opened.version,machine:confirmMachine}).promise
      .then(r=>{if(active){setScales((r[api] as {scales:Scale[]}).scales.filter(x=>x.needed));setScaleEdits({});}})
      .catch(e=>{if(active)fail(e);});
    return()=>{active=false;};
  },[step,opened,machine]);
  const scaleInvalid=Object.values(scaleEdits).some(v=>!(Number(v)>0&&Number.isFinite(Number(v))));
  // 확정 결과는 창으로 띄운다(이슈 #21 — 오른쪽 위 알림만으로는 끝났는지 알 수 없어 한 번 더 누르게 됨).
  // 확정한 뒤에는 단계를 벗어나거나 다른 원본을 열기 전까지 다시 확정하지 않는다.
  const resultDialog=useRef<HTMLDialogElement>(null),[showResult,setShowResult]=useState(false);
  useEffect(()=>{if(showResult&&result)resultDialog.current?.showModal();else resultDialog.current?.close();},[showResult,result]);
  useEffect(()=>{if(step!==CONFIRM){setResult(undefined);setShowResult(false);}},[step,CONFIRM]);
  useEffect(()=>{setResult(undefined);setShowResult(false);},[opened?.version]);
  async function confirm(){
    if(!opened||scaleInvalid||result)return;
    setBusy(true);setResult(undefined);
    const edited=Object.fromEntries(Object.entries(scaleEdits).map(([k,v])=>[k,Number(v)]));
    try{const reply=await desktop.request(`${api}_confirm`,{snapshot:opened.version,machine:confirmMachine,scales:edited}).promise;
      setResult(reply[api] as Confirmed);setShowResult(true);notify('양식 확정 완료','ok');}
    catch(e){fail(e);}finally{setBusy(false);}
  }

  if(catalog&&!catalog.save_dir)
    return <section className="panel"><p className="table-empty">먼저 [설정] 탭에서 저장폴더를 지정하세요.</p></section>;
  const editable=catalog?.recipes||[];
  const versions=(recipeVersions?.recipe===recipe?recipeVersions.versions:[]).filter(v=>v.has_candidate);
  const noCandidate=recipeVersions?.recipe===recipe&&!recipeVersions.can_edit;
  // The engine runs one job per screen: wait for the list/version reads before opening.
  const listing=loading||(!!recipe&&recipeVersions?.recipe!==recipe);
  // [엑셀 원본 열기]: 고른 버전(없으면 최신)의 Excel 원본(전체 후보 목록) 파일.
  const excelOriginal=(stamp?versions.find(v=>v.stamp===stamp):versions[0])?.candidate||'';

  return <section className="panel">
    <div className="section-heading"><div><span className="step">{mode==='new'?'NEW RECIPE':'EDIT RECIPE'}</span>
      <h2>{mode==='new'?'신규 Recipe 만들기 — 장비·로컬에서 읽어 새 양식':'Recipe 양식 편집하기 — 저장된 원본 편집·확정'}</h2></div>
      {mode==='edit'&&<button disabled={loading||busy} onClick={loadCatalog}>목록 새로고침</button>}</div>
    <Stepper labels={steps} current={step} onJump={i=>{if(i===0)setStep(0);else if(mode==='new'&&i===1&&newScales)setStep(1);else if(i===EDIT&&opened)setStep(EDIT);}}/>

    <div className="step-body">
    {step===0&&<>
      {mode==='edit'?<>
      <p className="hint">저장폴더에 이미 있는 <b>원본(초안)</b>을 골라 편집합니다.</p>
      {editable.length===0
        ? <p className="table-empty">저장폴더에 레시피 양식이 없습니다. [신규 Recipe 만들기] 탭에서 만드세요.</p>
        : <div className="form-picker" style={{marginTop:14}}>
            <label className="field">레시피<select value={recipe} onChange={e=>{setRecipe(e.target.value);setStamp('');}}>
              <option value="">레시피 선택…</option>{editable.map(r=><option key={r.recipe} value={r.recipe}>{r.recipe}</option>)}</select></label>
            <label className="field">버전<select value={stamp} disabled={!recipe} onChange={e=>setStamp(e.target.value)}>
              <option value="">최신(원본 있는 버전)</option>{versions.map(v=><option key={v.stamp} value={v.stamp}>{v.stamp} · {v.kind||'원본'}</option>)}</select></label>
            <p className="hint" style={{gridColumn:'1 / -1',margin:0}}>[📊 엑셀 원본 열기]는 원본 파일을 Excel 로 엽니다(보기용). 화면에서 항목을 편집하려면 아래 [원본 열기 ▶]를 누르세요.</p>
            {noCandidate&&<p className="warn">이 레시피는 항목을 추가할 원본(초안)이 없습니다. [신규 Recipe 만들기] 탭에서 다시 읽어 만드세요.</p>}
            <button disabled={!excelOriginal||busy||listing} title={excelOriginal||'이 버전에는 Excel 원본이 없습니다'}
              onClick={()=>void openPath(excelOriginal)}>{listing&&recipe?'버전 확인 중…':'📊 엑셀 원본 열기'}</button>
          </div>}
      </>:<>
      <p className="hint">장비(또는 로컬 복사본)의 설정 파일을 읽어 새 레시피 양식을 만듭니다. 원본은 읽기만 하고, 복사본은 로컬 작업 폴더에만 둡니다.</p>
      {!newPrep?(newPrepError?<LoadFailed message={newPrepError} onRetry={()=>setNewPrepTry(n=>n+1)}/>:<p className="hint">불러오는 중…</p>):<>
        <div className="form-filter" style={{marginTop:12}}>
          <label className="field" style={{width:200}}>레시피(레벨) 이름<input list="form-existing" aria-label="새 레시피 이름" value={newName} maxLength={64} placeholder="예: PI3" onChange={e=>{setNewName(e.target.value);setNewScales(undefined);}}/></label>
          <datalist id="form-existing">{newPrep.existing.map(r=><option key={r} value={r}/>)}</datalist>
          <div className="source-choice" role="radiogroup" aria-label="수집 방식" style={{alignSelf:'end'}}>
            <label><input type="radio" name="fsrc" checked={newSource==='equipment'} onChange={()=>{setNewSource('equipment');setNewMachines([]);setNewScales(undefined);}}/>🖥 장비 IP에서 수집</label>
            <label><input type="radio" name="fsrc" checked={newSource==='local'} onChange={()=>{setNewSource('local');setNewMachines([]);setNewScales(undefined);}}/>📁 로컬 복사본에서</label></div></div>
        {newPrep.existing.includes(newName.trim())&&<p className="warn">이미 있는 레시피입니다. 확정하면 새 회차 양식이 만들어집니다(이전 값은 이어받기).</p>}
        {newSource==='local'&&<div className="form-filter"><label className="field" style={{flex:1,minWidth:260}}>로컬 상위 폴더<input value={localPath} onChange={e=>setLocalPath(e.target.value)} maxLength={4096}/></label>
          <button onClick={async()=>{const p=await pickFolder();if(p){setLocalPath(p);void saveLocal(p);}}}>📁 찾기</button><button disabled={!localPath.trim()} onClick={()=>saveLocal(localPath.trim())}>저장</button></div>}
        <h3>호기</h3>
        <RowPick label="수집 호기" columns={['호기',newSource==='equipment'?'IP':'로컬 폴더','장비 종류']} value={newMachines}
          onChange={v=>{setNewScales(undefined);setNewMachines(v);}}
          rows={newPrep.machines.map(m=>{const where=newSource==='equipment'?m.ip:m.local;
            return {id:m.id,disabled:!where,title:where||(newSource==='equipment'?'IP 없음':'폴더 없음'),
              cells:[<b key="m">{m.id}</b>,where?<code key="w">{where}</code>:<span key="w" className="warn">{newSource==='equipment'?'IP 없음':'폴더 없음'}</span>,m.type||'—']};})}
          empty={<p className="table-empty">[장비 IP] 문서에 호기가 없습니다.</p>}/>
        {newMachines.length>1&&<p className="hint">여러 호기를 고르면 항목은 모두 합쳐 만들고, 확정 양식의 기준 호기(계수·파일 이름)는 먼저 고른 {newMachines[0]} 입니다.</p>}
        <div className="toolbar"><button className="primary" disabled={busy||!newName.trim()||!newMachines.length} onClick={()=>{const a=noAnswers();setAnswers(a);void newCollect(a);}}>{busy&&!newScales?'수집 중…':'수집 시작'}</button>
          {newScales&&<button onClick={()=>setStep(1)}>하위 레시피 선택 ▶</button>}</div>
      </>}
      </>}
    </>}

    {mode==='new'&&step===1&&newScales&&<>
      <h3>{newName.trim()} · 하위 레시피 선택</h3>
      <p className="hint">수집한 하위 레시피 {newScales.length}개 중 양식에 넣을 것을 고르세요. 같은 상위 레시피라도 호기마다 하위 레시피가 다를 수 있으니,
        값을 비교할 <b>공통 하위 레시피</b>만 고르면 그것만 항목 편집 · 확정 · 값 확인에 나옵니다. 계수는 RTP.txt 로 추정한 값을 미리 채웠습니다. 확인하고 필요하면 고치세요.</p>
      {newCollected.length>1&&<div className="toolbar"><button disabled={!newCommon.length} onClick={()=>setNewPick(newCommon)}>
        모든 호기에 있는 것만 고르기 ({newCommon.length}개)</button>{!newCommon.length&&<span className="hint">고른 호기 {newCollected.length}대 모두에 있는 하위 레시피가 없습니다.</span>}</div>}
      <RowPick label="양식에 넣을 하위 레시피" columns={['하위 레시피','읽힌 호기','변환계수','출처','추정 신뢰도']} value={newPick} onChange={setNewPick}
        rows={newScales.map(x=>({id:x.variant,cells:[<b key="v">{x.variant||'(기본)'}</b>,
          <span key="m" className={newCollected.length>1&&x.machines.length<newCollected.length?'warn':''}>{x.machines.join(', ')||'—'}{newCollected.length>1?` (${x.machines.length}/${newCollected.length}대)`:''}</span>,
          <input key="c" type="number" step="any" aria-label={`${x.variant||'기본'} 새 양식 계수`} value={newScaleValue(x)} onChange={e=>setNewScaleEdit(v=>({...v,[x.variant]:e.target.value}))}/>,
          <span key="s" className={x.source==='기본값'?'warn':''}>{newScaleEdit[x.variant]!==undefined?'직접 입력':x.source}</span>,
          <span key="r" title={x.reason}>{x.confidence||'—'}</span>]}))}/>
      {!newPick.length&&<p role="alert">하위 레시피를 한 개 이상 고르세요.</p>}
      {newScaleBad&&<p role="alert">변환계수는 0보다 큰 숫자여야 합니다.</p>}
      <div className="toolbar"><button className="primary" disabled={busy||!newPick.length||newScaleBad} onClick={()=>void newParse('')}>파라미터 불러오기 ▶</button></div>
    </>}

    {step===EDIT&&opened&&<>
      <div className="section-heading"><div><h3>{opened.recipe} · {opened.level}</h3></div>
        <span className="count">사용 {opened.used} / 전체 {opened.total}</span></div>
      {mode==='new'&&similar.length>0&&<div className="form-filter"><label className="field">기존 레시피 양식 활용(사용 항목 맞추기)<select value={baseForm} disabled={busy} onChange={e=>void newParse(e.target.value)}>
        <option value="">새로 만들기(파서 추천)</option>{similar.map(x=><option key={x.recipe} value={x.recipe}>{x.recipe} — 일치 {x.match}/{x.total}</option>)}</select></label></div>}
      <FormEditor version={opened.version} pageMethod={`${api}_page`} editMethod={`${api}_edit`} replyKey={api} variants={opened.variants}
        onUsed={n=>setOpened(o=>o&&o.used!==n?{...o,used:n}:o)}/>
    </>}
    {step===EDIT&&!opened&&<p className="table-empty">{mode==='new'?'먼저 하위 레시피를 고르고 파라미터를 불러오세요.':'먼저 1단계에서 원본을 여세요.'}</p>}

    {step===CONFIRM&&opened&&<>
      <h3>확정</h3>
      <div className="runbar"><div><strong>사용 {opened.used}개 항목으로 확정</strong>
        <p>확정하면 저장폴더에 새 회차의 확정 양식과 편집용 원본이 함께 저장됩니다.</p></div>
        <div className="actions">{result?<button onClick={()=>setShowResult(true)}>✅ 확정 완료 · 결과 보기</button>
          :<button className="primary" disabled={busy||opened.used===0||scaleInvalid} onClick={confirm}>양식 확정 ▶</button>}</div></div>
      <p className="hint">기준 호기: <b>{confirmMachine}</b> — {mode==='new'?'수집한 호기':'이 양식을 처음 만든 호기'}입니다(따로 고르지 않습니다).
        변환계수를 찾고 파일 이름({opened.recipe}_{confirmMachine}호기_참조_…)을 붙이는 데만 씁니다.</p>
      {scales.length>0&&<div className="outputs"><h3>변환계수 (LINEAR/AREA 항목)</h3>
        <p className="hint">값을 바꾸면 이 양식에 적용되고 변환계수.xlsx 에도 반영됩니다. '기본값'은 등록된 계수가 없어 기본 계수로 계산된다는 뜻입니다.</p>
        <table className="tbl"><thead><tr><th>변형</th><th>계수</th><th>출처</th></tr></thead><tbody>{scales.map(x=><tr key={x.variant}>
          <td>{x.variant||'(기본)'}</td>
          <td><input aria-label={`${x.variant||'기본'} 변환계수`} type="number" step="any" min="0" value={scaleEdits[x.variant]??String(x.coef)}
            onChange={e=>setScaleEdits(old=>{const next={...old};if(e.target.value===String(x.coef))delete next[x.variant];else next[x.variant]=e.target.value;return next;})}/></td>
          <td className={x.source==='기본값'&&scaleEdits[x.variant]===undefined?'warn':''}>{scaleEdits[x.variant]!==undefined?'직접 입력':x.source}</td></tr>)}</tbody></table>
        {scaleInvalid&&<p role="alert">변환계수는 0보다 큰 숫자여야 합니다.</p>}</div>}
      {result&&<p className="hint">확정 완료 · {result.kept}개 항목 — 같은 양식을 다시 확정하려면 항목 편집 단계로 돌아가 고친 뒤 확정하세요.</p>}
    </>}
    {step===CONFIRM&&!opened&&<p className="table-empty">먼저 원본을 열고 항목을 편집하세요.</p>}
    </div>

    <StepNav step={step} total={steps.length} onBack={()=>setStep(s=>s-1)}
      onNext={()=>{if(step===0){if(mode==='new'){if(newScales)setStep(1);}else if(recipe)open(recipe,stamp);}
        else if(mode==='new'&&step===1)void newParse('');else if(step<CONFIRM)setStep(s=>s+1);else confirm();}}
      nextLabel={step===0?(mode==='new'?'하위 레시피 선택':'원본 열기'):step<EDIT?'파라미터 불러오기':step===EDIT?'확정 단계로':result?'확정 완료':'양식 확정'}
      nextDisabled={(step===0&&(mode==='new'?!newScales:!recipe||listing||noCandidate))||(step>0&&step<EDIT&&(!newPick.length||newScaleBad))
        ||(step>=EDIT&&!opened)||(step===CONFIRM&&(opened?.used===0||scaleInvalid||!!result))} busy={busy}/>

    <dialog ref={resultDialog} className="edit-dialog" aria-label="양식 확정 결과" onCancel={e=>{e.preventDefault();setShowResult(false);}}>{result&&<>
      <h2>✅ 양식 확정 완료</h2>
      <p><b>{opened?.recipe}</b> 양식을 {result.kept}개 항목(시트 {result.sheet})으로 저장폴더에 저장했습니다. 다시 누를 필요가 없습니다.</p>
      {result.name_note&&<p role="alert">장비화면이름 저장 참고: {result.name_note}</p>}
      {([['final','확정 양식'],['original','편집용 원본']] as const).map(([k,label])=><OpenPath key={k} label={label} path={result[k]}/>)}
      {result.coef.saved>0&&<p>변환계수.xlsx 반영: {result.coef.saved}건</p>}
      {result.coef.unregistered.length>0&&<p role="alert">변환계수.xlsx 에 행이 없어 기록하지 않은 변형: {result.coef.unregistered.join(', ')} (MAG 를 알아야 새 행을 만들 수 있습니다. 파일에 직접 추가하세요.)</p>}
      {result.coef.defaulted.length>0&&<p role="alert">계수가 없어 기본 계수로 계산한 변형: {result.coef.defaulted.join(', ')}</p>}
      {result.coef.error&&<p role="alert">변환계수 저장 실패: {result.coef.error}</p>}
      {result.merge&&(result.merge.collate
        ?<><OpenPath label="이전 값을 이어받은 취합 파일" path={result.merge.collate}/>
          <p>{result.merge.added?`새로(변경) 추가된 파라미터 ${result.merge.added}개는 값이 비어 있습니다. Recipe 업데이트로 채우세요.`:'기존 파라미터 값은 이전 취합본에서 이어받았습니다.'}</p></>
        :result.merge.error?<p role="alert">이전 값 이어받기 실패: {result.merge.error}</p>:null)}
      {mode==='new'&&<p className="hint">값은 [Recipe 업데이트]에서 수집하면 채워집니다.</p>}
      <div className="dialog-actions"><button className="primary" onClick={()=>setShowResult(false)}>닫기</button></div>
    </>}</dialog>

    <QuestionDialog question={question} onAnswer={v=>{if(!question)return;const next=withAnswer(answers,question,v);setAnswers(next);setQuestion(undefined);void newCollect(next);}}
      onCancel={()=>{setQuestion(undefined);void desktop.request('formnew_cancel').promise.catch(fail);}}/>
  </section>;
}
