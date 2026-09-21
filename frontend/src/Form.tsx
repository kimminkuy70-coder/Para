import {useEffect,useRef,useState} from 'react';
import {desktop,errorText} from './desktop';

type Version={stamp:string;has_candidate:boolean;kind:string};
type Recipe={recipe:string;versions:Version[];can_edit:boolean};
type Catalog={save_dir:boolean;recipes:Recipe[]};
type Opened={version:string;recipe:string;level:string;variants:string[];total:number;used:number;source:string};
type Row={id:number;use:boolean;variant:string;zone:string;alg:string;orig:string;name:string;transform:string;raw:string;display:string};
type Page={rows:Row[];total:number;used:number;grand_total:number;offset:number};
type Confirmed={final:string;original:string;kept:number;total:number;sheet:string;name_note:string};
const TRANSFORMS=['RAW','LINEAR','AREA'];

export function Form(){
  const [catalog,setCatalog]=useState<Catalog>();
  const [recipe,setRecipe]=useState(''),[stamp,setStamp]=useState('');
  const [opened,setOpened]=useState<Opened>();
  const [variant,setVariant]=useState(''),[query,setQuery]=useState(''),[filter,setFilter]=useState('');
  const [usedOnly,setUsedOnly]=useState(false),[offset,setOffset]=useState(0);
  const [data,setData]=useState<Page>();
  const [loading,setLoading]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const [machine,setMachine]=useState(''),[result,setResult]=useState<Confirmed>();
  const [renaming,setRenaming]=useState<Row>(),[nameValue,setNameValue]=useState('');
  const dialog=useRef<HTMLDialogElement>(null),sequence=useRef(0);

  async function loadCatalog(){
    setLoading(true);setError('');
    try{await desktop.connect();const reply=await desktop.request('form_catalog').promise;
      setCatalog(reply.form as Catalog);}
    catch(e){setError(errorText(e));}finally{setLoading(false);}
  }
  useEffect(()=>{void loadCatalog();},[]);
  useEffect(()=>{const t=setTimeout(()=>setFilter(query),180);return()=>clearTimeout(t);},[query]);
  useEffect(()=>{setOffset(0);},[variant,filter,usedOnly]);
  useEffect(()=>{if(renaming){setNameValue(renaming.name);dialog.current?.showModal();}else dialog.current?.close();},[renaming]);

  async function open(r:string,s:string){
    setError('');setResult(undefined);setBusy(true);
    try{const reply=await desktop.request('form_open',{recipe:r,stamp:s}).promise;
      const o=reply.form as Opened;setOpened(o);setVariant('');setQuery('');setFilter('');setOffset(0);}
    catch(e){setOpened(undefined);setError(errorText(e));}finally{setBusy(false);}
  }
  useEffect(()=>{
    if(!opened)return;
    const current=++sequence.current;setLoading(true);
    desktop.request('form_page',{snapshot:opened.version,variant,query:filter,used_only:usedOnly,offset,limit:100})
      .promise.then(reply=>{if(current===sequence.current)setData(reply.form as Page);})
      .catch(e=>{if(current===sequence.current)setError(errorText(e));})
      .finally(()=>{if(current===sequence.current)setLoading(false);});
    return()=>{sequence.current++;};
  },[opened,variant,filter,usedOnly,offset]);

  async function edit(row:Row,kind:'use'|'name'|'transform',value:boolean|string){
    if(!opened)return;
    try{await desktop.request('form_edit',{snapshot:opened.version,row:row.id,kind,value}).promise;
      // Refresh current page and used-count without losing position.
      const reply=await desktop.request('form_page',{snapshot:opened.version,variant,query:filter,used_only:usedOnly,offset,limit:100}).promise;
      const p=reply.form as Page;setData(p);setOpened(o=>o?{...o,used:p.used}:o);}
    catch(e){setError(errorText(e));}
  }
  async function saveName(){
    if(!renaming)return;await edit(renaming,'name',nameValue.trim());setRenaming(undefined);
  }
  async function confirm(){
    if(!opened||!machine.trim())return;
    setBusy(true);setError('');setResult(undefined);
    try{const reply=await desktop.request('form_confirm',{snapshot:opened.version,machine:machine.trim()}).promise;
      setResult(reply.form as Confirmed);}
    catch(e){setError(errorText(e));}finally{setBusy(false);}
  }

  if(catalog&&!catalog.save_dir)
    return <section className="panel"><p className="table-empty">먼저 저장폴더를 지정하세요. 기존 프로그램에서 저장폴더를 정하면 이곳에서 양식을 편집할 수 있습니다.</p></section>;
  const editable=(catalog?.recipes||[]).filter(r=>r.can_edit);
  const versions=editable.find(r=>r.recipe===recipe)?.versions.filter(v=>v.has_candidate)||[];

  return <>
    {error&&<div className="alert" role="alert"><strong>확인이 필요합니다</strong><span>{error}</span><button aria-label="오류 안내 닫기" onClick={()=>setError('')}>×</button></div>}
    <section className="panel">
      <div className="section-heading"><div><span className="step">01 · 원본 선택</span><h2>양식 만들기 — 기존 원본 편집</h2></div>
        <button disabled={loading||busy} onClick={loadCatalog}>목록 새로고침</button></div>
      {editable.length===0
        ? <p className="table-empty">항목을 추가할 수 있는 원본(초안)이 있는 레시피가 없습니다. 기존 프로그램에서 원본이 저장된 버전이 필요합니다.</p>
        : <div className="form-picker">
            <label className="field">레시피<select value={recipe} onChange={e=>{setRecipe(e.target.value);setStamp('');}}>
              <option value="">레시피 선택…</option>{editable.map(r=><option key={r.recipe} value={r.recipe}>{r.recipe}</option>)}</select></label>
            <label className="field">버전<select value={stamp} disabled={!recipe} onChange={e=>setStamp(e.target.value)}>
              <option value="">최신(원본 있는 버전)</option>{versions.map(v=><option key={v.stamp} value={v.stamp}>{v.stamp} · {v.kind||'원본'}</option>)}</select></label>
            <button className="primary" disabled={!recipe||busy} onClick={()=>open(recipe,stamp)}>원본 열기 <span aria-hidden="true">→</span></button>
          </div>}
    </section>

    {opened&&<section className="panel">
      <div className="section-heading"><div><span className="step">02 · 항목 편집</span><h2>{opened.recipe} · {opened.level}</h2></div>
        <span className="count">사용 {opened.used} / 전체 {opened.total}</span></div>
      <div className="form-filter">
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
    </section>}

    {opened&&<section className="panel">
      <div className="section-heading"><div><span className="step">03 · 확정</span><h2>양식 확정</h2></div></div>
      <div className="runbar"><div><strong>사용 {opened.used}개 항목으로 확정</strong>
        <p>확정하면 저장폴더에 새 회차의 확정 양식과 편집용 원본이 함께 저장됩니다.</p></div>
        <div className="actions"><input className="in" value={machine} placeholder="호기 (예: AOI-07)" maxLength={64} onChange={e=>setMachine(e.target.value)}/>
          <button className="primary" disabled={busy||!machine.trim()||opened.used===0} onClick={confirm}>양식 확정 <span aria-hidden="true">→</span></button></div></div>
      {result&&<div className="outputs"><h3>확정 완료 · {result.kept}개 항목 (시트 {result.sheet})</h3>
        {result.name_note&&<p role="alert">장비화면이름 저장 참고: {result.name_note}</p>}
        {([['final','확정 양식'],['original','편집용 원본']] as const).map(([k,label])=>
          <label className="field" key={k}>{label}<input readOnly value={result[k]} onFocus={e=>e.target.select()}/></label>)}</div>}
    </section>}

    <dialog className="edit-dialog" ref={dialog} onClose={()=>setRenaming(undefined)}><form method="dialog" onSubmit={e=>{e.preventDefault();void saveName();}}>
      <h3>장비 화면 이름</h3><p className="sub">{renaming?.orig}</p>
      <input autoFocus value={nameValue} maxLength={200} onChange={e=>setNameValue(e.target.value)}/>
      <div className="dialog-actions"><button type="button" onClick={()=>setRenaming(undefined)}>취소</button>
        <button className="primary" type="submit">저장</button></div></form></dialog>
  </>;
}
