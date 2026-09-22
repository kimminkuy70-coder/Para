import {useEffect,useRef,useState} from 'react';
import {desktop} from './desktop';
import {Stepper,StepNav,notify,fail} from './ui';
import {OpenPath} from './OpenPath';

type Version={stamp:string;has_candidate:boolean;kind:string};
type Recipe={recipe:string;versions:Version[];can_edit:boolean};
type Catalog={save_dir:boolean;recipes:Recipe[];machines?:string[]};
type Opened={version:string;recipe:string;level:string;variants:string[];total:number;used:number;source:string};
type Row={id:number;use:boolean;variant:string;zone:string;alg:string;orig:string;name:string;transform:string;raw:string;display:string};
type Page={rows:Row[];total:number;used:number;grand_total:number;offset:number};
type Scale={variant:string;coef:number;source:string;needed:boolean};
type Confirmed={final:string;original:string;kept:number;total:number;sheet:string;name_note:string;
  coef:{saved:number;defaulted:string[];unregistered:string[];error:string};
  merge:{collate:string;added:number;error:string}|null};
const TRANSFORMS=['RAW','LINEAR','AREA'];
const STEPS=['원본 선택','항목 편집','확정'];

export function Form(){
  const [step,setStep]=useState(0);
  const [catalog,setCatalog]=useState<Catalog>();
  const [recipe,setRecipe]=useState(''),[stamp,setStamp]=useState('');
  const [opened,setOpened]=useState<Opened>();
  const [variant,setVariant]=useState(''),[query,setQuery]=useState(''),[filter,setFilter]=useState('');
  const [usedOnly,setUsedOnly]=useState(false),[offset,setOffset]=useState(0);
  const [data,setData]=useState<Page>();
  const [loading,setLoading]=useState(false),[busy,setBusy]=useState(false);
  const [machine,setMachine]=useState(''),[result,setResult]=useState<Confirmed>();
  const [renaming,setRenaming]=useState<Row>(),[nameValue,setNameValue]=useState('');
  const [scales,setScales]=useState<Scale[]>([]),[scaleEdits,setScaleEdits]=useState<Record<string,string>>({});
  const dialog=useRef<HTMLDialogElement>(null),sequence=useRef(0);

  async function loadCatalog(){
    setLoading(true);
    try{await desktop.connect();const reply=await desktop.request('form_catalog').promise;
      setCatalog(reply.form as Catalog);}
    catch(e){fail(e);}finally{setLoading(false);}
  }
  useEffect(()=>{void loadCatalog();},[]);
  useEffect(()=>{const t=setTimeout(()=>setFilter(query),180);return()=>clearTimeout(t);},[query]);
  useEffect(()=>{setOffset(0);},[variant,filter,usedOnly]);
  useEffect(()=>{if(renaming){setNameValue(renaming.name);dialog.current?.showModal();}else dialog.current?.close();},[renaming]);

  async function open(r:string,s:string){
    setResult(undefined);setBusy(true);
    try{const reply=await desktop.request('form_open',{recipe:r,stamp:s}).promise;
      const o=reply.form as Opened;setOpened(o);setVariant('');setQuery('');setFilter('');setOffset(0);setStep(1);}
    catch(e){setOpened(undefined);fail(e);}finally{setBusy(false);}
  }
  useEffect(()=>{
    if(!opened)return;
    const current=++sequence.current;setLoading(true);
    desktop.request('form_page',{snapshot:opened.version,variant,query:filter,used_only:usedOnly,offset,limit:100})
      .promise.then(reply=>{if(current===sequence.current)setData(reply.form as Page);})
      .catch(e=>{if(current===sequence.current)fail(e);})
      .finally(()=>{if(current===sequence.current)setLoading(false);});
    return()=>{sequence.current++;};
  },[opened,variant,filter,usedOnly,offset]);

  async function edit(row:Row,kind:'use'|'name'|'transform',value:boolean|string){
    if(!opened)return;
    try{await desktop.request('form_edit',{snapshot:opened.version,row:row.id,kind,value}).promise;
      const reply=await desktop.request('form_page',{snapshot:opened.version,variant,query:filter,used_only:usedOnly,offset,limit:100}).promise;
      const p=reply.form as Page;setData(p);setOpened(o=>o?{...o,used:p.used}:o);}
    catch(e){fail(e);}
  }
  async function saveName(){if(!renaming)return;await edit(renaming,'name',nameValue.trim());setRenaming(undefined);}
  const machines=catalog?.machines||[];
  // Coefficients for LINEAR/AREA items of the chosen machine (변환계수.xlsx → 원본 라벨 → 기본값).
  useEffect(()=>{
    if(step!==2||!opened||!machine.trim()){setScales([]);return;}
    let active=true;
    desktop.request('form_scales',{snapshot:opened.version,machine:machine.trim()}).promise
      .then(r=>{if(active){setScales((r.form as {scales:Scale[]}).scales.filter(x=>x.needed));setScaleEdits({});}})
      .catch(e=>{if(active)fail(e);});
    return()=>{active=false;};
  },[step,opened,machine]);
  const scaleInvalid=Object.values(scaleEdits).some(v=>!(Number(v)>0&&Number.isFinite(Number(v))));
  async function confirm(){
    if(!opened||!machine.trim()||scaleInvalid)return;
    setBusy(true);setResult(undefined);
    const edited=Object.fromEntries(Object.entries(scaleEdits).map(([k,v])=>[k,Number(v)]));
    try{const reply=await desktop.request('form_confirm',{snapshot:opened.version,machine:machine.trim(),scales:edited}).promise;
      setResult(reply.form as Confirmed);notify('양식 확정 완료','ok');}
    catch(e){fail(e);}finally{setBusy(false);}
  }

  if(catalog&&!catalog.save_dir)
    return <section className="panel"><p className="table-empty">먼저 [설정] 탭에서 저장폴더를 지정하세요.</p></section>;
  const editable=(catalog?.recipes||[]).filter(r=>r.can_edit);
  const versions=editable.find(r=>r.recipe===recipe)?.versions.filter(v=>v.has_candidate)||[];

  return <section className="panel">
    <div className="section-heading"><div><span className="step">FORM</span><h2>양식 만들기 — 원본 편집·확정</h2></div>
      <button disabled={loading||busy} onClick={loadCatalog}>목록 새로고침</button></div>
    <Stepper labels={STEPS} current={step} onJump={i=>{if(i===0)setStep(0);else if(i===1&&opened)setStep(1);}}/>

    <div className="step-body">
    {step===0&&<>
      <p className="hint">저장폴더에 이미 있는 <b>원본(초안)</b>을 골라 편집합니다. 장비에서 새로 수집해 만드는 흐름은 준비 중입니다.</p>
      {editable.length===0
        ? <p className="table-empty">항목을 추가할 수 있는 원본(초안)이 있는 레시피가 없습니다.</p>
        : <div className="form-picker" style={{marginTop:14}}>
            <label className="field">레시피<select value={recipe} onChange={e=>{setRecipe(e.target.value);setStamp('');}}>
              <option value="">레시피 선택…</option>{editable.map(r=><option key={r.recipe} value={r.recipe}>{r.recipe}</option>)}</select></label>
            <label className="field">버전<select value={stamp} disabled={!recipe} onChange={e=>setStamp(e.target.value)}>
              <option value="">최신(원본 있는 버전)</option>{versions.map(v=><option key={v.stamp} value={v.stamp}>{v.stamp} · {v.kind||'원본'}</option>)}</select></label>
            <button className="primary" disabled={!recipe||busy} onClick={()=>open(recipe,stamp)}>원본 열기 ▶</button>
          </div>}
    </>}

    {step===1&&opened&&<>
      <div className="section-heading"><div><h3>{opened.recipe} · {opened.level}</h3></div>
        <span className="count">사용 {opened.used} / 전체 {opened.total}</span></div>
      <div className="form-filter" style={{marginTop:8}}>
        <label className="field">변형<select value={variant} onChange={e=>setVariant(e.target.value)}>
          <option value="">전체 변형</option>{opened.variants.map(v=><option key={v} value={v}>{v||'(기본)'}</option>)}</select></label>
        <label className="field">검색<input value={query} maxLength={256} placeholder="항목·이름·Zone·Alg" onChange={e=>setQuery(e.target.value)}/></label>
        <label className="field checkbox"><input type="checkbox" checked={usedOnly} onChange={e=>setUsedOnly(e.target.checked)}/>사용 항목만</label>
      </div>
      <div className="table-scroll" aria-busy={loading}><table><thead><tr>
        <th>사용</th><th>변형</th><th>Zone</th><th>Alg</th><th>원본 항목</th><th>장비 화면 이름</th><th>변환</th><th>원본값</th></tr></thead>
        <tbody>{(data?.rows||[]).map(row=><tr key={row.id} className={row.use?'':'muted'}>
          <td><input type="checkbox" checked={row.use} onChange={e=>edit(row,'use',e.target.checked)} aria-label={`${row.orig} 사용`}/></td>
          <td>{row.variant||'(기본)'}</td><td>{row.zone}</td><td>{row.alg}</td><td>{row.orig}</td>
          <td><button className="linklike" onClick={()=>setRenaming(row)}>{row.name||'(이름 없음)'}</button></td>
          <td><select value={row.transform} onChange={e=>edit(row,'transform',e.target.value)} aria-label={`${row.orig} 변환`}>
            {TRANSFORMS.map(t=><option key={t} value={t}>{t}</option>)}</select></td>
          <td>{row.display||row.raw}</td></tr>)}</tbody></table>
        {(loading||!(data?.rows||[]).length)&&<p className="table-empty">{loading?'불러오는 중…':'표시할 항목이 없습니다.'}</p>}</div>
      <div className="pagination"><span>{data?.total?`${offset+1}–${Math.min(offset+100,data.total)} / ${data.total}개`:'0개'}</span>
        <div><button disabled={loading||offset===0} onClick={()=>setOffset(n=>Math.max(0,n-100))}>이전</button>
          <button disabled={loading||offset+100>=(data?.total||0)} onClick={()=>setOffset(n=>n+100)}>다음</button></div></div>
    </>}
    {step===1&&!opened&&<p className="table-empty">먼저 1단계에서 원본을 여세요.</p>}

    {step===2&&opened&&<>
      <h3>확정</h3>
      <div className="runbar"><div><strong>사용 {opened.used}개 항목으로 확정</strong>
        <p>확정하면 저장폴더에 새 회차의 확정 양식과 편집용 원본이 함께 저장됩니다.</p></div>
        <div className="actions">{machines.length
            ?<select aria-label="확정 호기" value={machine} onChange={e=>setMachine(e.target.value)}><option value="">호기 선택…</option>{machines.map(m=><option key={m} value={m}>{m}</option>)}</select>
            :<input className="in" aria-label="확정 호기" value={machine} placeholder="호기 (예: AOI-07)" maxLength={64} onChange={e=>setMachine(e.target.value)}/>}
          <button className="primary" disabled={busy||!machine.trim()||opened.used===0||scaleInvalid} onClick={confirm}>양식 확정 ▶</button></div></div>
      {!machines.length&&<p className="hint">[장비 IP] 문서에 호기가 없어 직접 입력합니다. 호기를 등록하면 목록에서 고를 수 있습니다.</p>}
      {scales.length>0&&<div className="outputs"><h3>변환계수 (LINEAR/AREA 항목)</h3>
        <p className="hint">값을 바꾸면 이 양식에 적용되고 변환계수.xlsx 에도 반영됩니다. '기본값'은 등록된 계수가 없어 기본 계수로 계산된다는 뜻입니다.</p>
        <table className="tbl"><thead><tr><th>변형</th><th>계수</th><th>출처</th></tr></thead><tbody>{scales.map(x=><tr key={x.variant}>
          <td>{x.variant||'(기본)'}</td>
          <td><input aria-label={`${x.variant||'기본'} 변환계수`} type="number" step="any" min="0" value={scaleEdits[x.variant]??String(x.coef)}
            onChange={e=>setScaleEdits(old=>{const next={...old};if(e.target.value===String(x.coef))delete next[x.variant];else next[x.variant]=e.target.value;return next;})}/></td>
          <td className={x.source==='기본값'&&scaleEdits[x.variant]===undefined?'warn':''}>{scaleEdits[x.variant]!==undefined?'직접 입력':x.source}</td></tr>)}</tbody></table>
        {scaleInvalid&&<p role="alert">변환계수는 0보다 큰 숫자여야 합니다.</p>}</div>}
      {result&&<div className="outputs"><h3>확정 완료 · {result.kept}개 항목 (시트 {result.sheet})</h3>
        {result.name_note&&<p role="alert">장비화면이름 저장 참고: {result.name_note}</p>}
        {([['final','확정 양식'],['original','편집용 원본']] as const).map(([k,label])=><OpenPath key={k} label={label} path={result[k]}/>)}
        {result.coef.saved>0&&<p>변환계수.xlsx 반영: {result.coef.saved}건</p>}
        {result.coef.unregistered.length>0&&<p role="alert">변환계수.xlsx 에 행이 없어 기록하지 않은 변형: {result.coef.unregistered.join(', ')} (MAG 를 알아야 새 행을 만들 수 있습니다. 파일에 직접 추가하세요.)</p>}
        {result.coef.defaulted.length>0&&<p role="alert">계수가 없어 기본 계수로 계산한 변형: {result.coef.defaulted.join(', ')}</p>}
        {result.coef.error&&<p role="alert">변환계수 저장 실패: {result.coef.error}</p>}
        {result.merge&&(result.merge.collate
          ?<><OpenPath label="이전 값을 이어받은 취합 파일" path={result.merge.collate}/>
            <p>{result.merge.added?`새로(변경) 추가된 파라미터 ${result.merge.added}개는 값이 비어 있습니다. 값 업데이트로 채우세요.`:'기존 파라미터 값은 이전 취합본에서 이어받았습니다.'}</p></>
          :result.merge.error?<p role="alert">이전 값 이어받기 실패: {result.merge.error}</p>:null)}</div>}
    </>}
    {step===2&&!opened&&<p className="table-empty">먼저 원본을 열고 항목을 편집하세요.</p>}
    </div>

    <StepNav step={step} total={STEPS.length} onBack={()=>setStep(s=>s-1)}
      onNext={()=>{if(step===0){if(recipe)open(recipe,stamp);}else if(step<STEPS.length-1)setStep(s=>s+1);else confirm();}}
      nextLabel={step===0?'원본 열기':step===1?'확정 단계로':'양식 확정'}
      nextDisabled={(step===0&&!recipe)||(step>=1&&!opened)||(step===2&&(!machine.trim()||opened?.used===0||scaleInvalid))} busy={busy}/>

    <dialog className="edit-dialog" ref={dialog} onClose={()=>setRenaming(undefined)}><form method="dialog" onSubmit={e=>{e.preventDefault();void saveName();}}>
      <h3>장비 화면 이름</h3><p className="sub">{renaming?.orig}</p>
      <input autoFocus value={nameValue} maxLength={200} onChange={e=>setNameValue(e.target.value)}/>
      <div className="dialog-actions"><button type="button" onClick={()=>setRenaming(undefined)}>취소</button>
        <button className="primary" type="submit">저장</button></div></form></dialog>
  </section>;
}
