import {useEffect,useState} from 'react';
import {desktop} from './desktop';
import {Stepper,StepNav,notify,fail} from './ui';
import {OpenPath} from './OpenPath';

type Files={save_dir:boolean;catalog:string|null;files:{id:string;name:string}[]};
type Pair={index:number;old:string;new:string;changes:number;added:number;removed:number};
type Diff={snapshot:string;machines:string[];pairs:Pair[]};
type Change={sheet:string;recipe:string;zone:string;alg:string;param:string;machine:string;old:string;new:string;kind:string};
type Page={total:number;offset:number;rows:Change[]};
const KINDS=['','값변경','추가','삭제','행 추가','행 삭제'];
const STEPS=['취합 파일 선택','변경 결과'];

export function History(){
  const [step,setStep]=useState(0);
  const [files,setFiles]=useState<Files>(),[chosen,setChosen]=useState<string[]>([]);
  const [diff,setDiff]=useState<Diff>(),[pair,setPair]=useState(0),[page,setPage]=useState<Page>();
  const [offset,setOffset]=useState(0),[kind,setKind]=useState(''),[query,setQuery]=useState(''),[filter,setFilter]=useState('');
  const [busy,setBusy]=useState(false),[loading,setLoading]=useState(false),[saved,setSaved]=useState('');
  async function refresh(){
    setBusy(true);
    try{await desktop.connect();const r=(await desktop.request('history_files').promise).history as Files;
      setFiles(r);setDiff(undefined);setPage(undefined);
      // Default: the two newest files (list is newest first).
      setChosen(r.files.slice(0,2).map(f=>f.id));}
    catch(e){fail(e);}finally{setBusy(false);}
  }
  useEffect(()=>{void refresh();},[]);
  useEffect(()=>{const t=setTimeout(()=>setFilter(query),180);return()=>clearTimeout(t);},[query]);
  useEffect(()=>{setOffset(0);},[kind,filter,pair]);
  useEffect(()=>{
    if(!diff)return;let active=true;setLoading(true);
    desktop.request('history_page',{snapshot:diff.snapshot,pair,offset,limit:100,kind,query:filter}).promise
      .then(r=>{if(active)setPage(r.history as Page);})
      .catch(e=>{if(active)fail(e);}).finally(()=>{if(active)setLoading(false);});
    return()=>{active=false;};
  },[diff,pair,offset,kind,filter]);
  // Compare in time order (oldest → newest) regardless of click order.
  const ordered=(files?.files||[]).filter(f=>chosen.includes(f.id)).reverse().map(f=>f.id);
  async function compare(){
    if(!files?.catalog||ordered.length<2)return;setBusy(true);setOffset(0);setSaved('');
    try{const r=await desktop.request('history_diff',{catalog:files.catalog,files:ordered}).promise;
      setPair(0);setDiff(r.history as Diff);setStep(1);}
    catch(e){fail(e);setDiff(undefined);}finally{setBusy(false);}
  }
  async function exportExcel(){
    if(!diff)return;setBusy(true);
    try{const r=await desktop.request('history_export',{snapshot:diff.snapshot,pair}).promise;
      setSaved((r.history as {path:string}).path);notify('변경내역 Excel 저장 완료','ok');}
    catch(e){fail(e);}finally{setBusy(false);}
  }
  if(files&&!files.save_dir)
    return <section className="panel"><p className="table-empty">먼저 [설정] 탭에서 저장폴더를 지정하세요.</p></section>;
  const current=diff?.pairs[pair];

  return <section className="panel">
    <div className="section-heading"><div><span className="step">HISTORY</span><h2>이력 확인 — 취합 파일 비교</h2></div>
      <button disabled={busy} onClick={refresh}>목록 새로고침</button></div>
    <Stepper labels={STEPS} current={step} onJump={i=>setStep(i)}/>

    <div className="step-body">
    {step===0&&<>
      <p className="hint">저장폴더의 '파라미터 값 취합' 파일을 2개 이상(최대 10개) 고르면 시간 순서대로 이웃한 파일끼리 비교합니다(읽기 전용).</p>
      {(files?.files.length||0)<2
        ? <p className="table-empty">비교할 취합 파일이 2개 이상 필요합니다. 값 업데이트를 먼저 하세요.</p>
        : <><div className="cm-files">{files!.files.map(f=><label key={f.id} className="cm-file">
            <input type="checkbox" disabled={busy} checked={chosen.includes(f.id)}
              onChange={e=>setChosen(c=>e.target.checked?[...c,f.id]:c.filter(i=>i!==f.id))}/><span>{f.name}</span></label>)}</div>
          <p className="hint">{ordered.length}개 선택{ordered.length>10?' — 최대 10개까지 비교할 수 있습니다.':ordered.length>=2?` · ${ordered.length-1}개 구간 비교`:''}</p></>}
    </>}

    {step===1&&diff&&current&&<>
      <div className="section-heading"><div><h3>{current.old} → {current.new}</h3></div>
        <span className="count">값변경 {current.changes} · 추가행 {current.added} · 삭제행 {current.removed}</span></div>
      <div className="form-filter" style={{marginTop:12}}>
        {diff.pairs.length>1&&<label className="field">비교 구간<select value={pair} onChange={e=>setPair(Number(e.target.value))}>
          {diff.pairs.map(p=><option key={p.index} value={p.index}>{p.index+1}. {p.old} → {p.new} ({p.changes}건)</option>)}</select></label>}
        <label className="field">종류<select value={kind} onChange={e=>setKind(e.target.value)}>
          {KINDS.map(k=><option key={k} value={k}>{k||'값 변경 전체'}</option>)}</select></label>
        <label className="field">검색<input value={query} maxLength={256} placeholder="파라미터·레시피·호기" onChange={e=>setQuery(e.target.value)}/></label>
        <button disabled={busy} onClick={exportExcel}>변경내역 Excel 저장</button>
      </div>
      {saved&&<OpenPath label="저장된 변경내역" path={saved}/>}
      <div className="table-scroll" aria-busy={loading}><table><thead><tr>
        <th>레시피</th><th>Zone</th><th>Alg</th><th>파라미터</th><th>호기</th><th>이전</th><th>최신</th><th>종류</th></tr></thead>
        <tbody>{(page?.rows||[]).map((c,i)=><tr key={i}>
          <td>{c.recipe}</td><td>{c.zone}</td><td>{c.alg}</td><td>{c.param}</td><td>{c.machine||'—'}</td>
          <td>{c.old||'—'}</td><td>{c.new||'—'}</td><td>{c.kind}</td></tr>)}</tbody></table>
        {(loading||!(page?.rows||[]).length)&&<p className="table-empty">{loading?'불러오는 중…':'표시할 변경이 없습니다.'}</p>}</div>
      <div className="pagination"><span>{page?.total?`${offset+1}–${Math.min(offset+100,page.total)} / ${page.total}건`:'0건'}</span>
        <div><button disabled={loading||offset===0} onClick={()=>setOffset(n=>Math.max(0,n-100))}>이전</button>
          <button disabled={loading||offset+100>=(page?.total||0)} onClick={()=>setOffset(n=>n+100)}>다음</button></div></div>
    </>}
    {step===1&&!diff&&<p className="table-empty">먼저 1단계에서 파일을 골라 비교하세요.</p>}
    </div>

    <StepNav step={step} total={STEPS.length} onBack={()=>setStep(0)} onNext={()=>step===0?compare():setStep(0)}
      nextLabel={step===0?'비교':'파일 다시 고르기'} nextDisabled={step===0&&(ordered.length<2||ordered.length>10)} busy={busy}/>
  </section>;
}
