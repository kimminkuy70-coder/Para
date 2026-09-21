import {useEffect, useState} from 'react';
import {desktop, errorText} from './desktop';
import './commonality.css';

type Catalog = {catalog:string;files:{id:string;name:string;folder:string}[]};
type Result = {snapshot:string;total:number;parameters:number;changed:number};
type Page = {headers:string[];total:number;parameter_total:number;rows:{id:number;values:string[];outliers:number[];fail:boolean;low_match:boolean}[]};

export function Commonality() {
  const [catalog,setCatalog]=useState<Catalog>(),[selected,setSelected]=useState<string[]>([]);
  const [result,setResult]=useState<Result>(),[page,setPage]=useState<Page>();
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[output,setOutput]=useState('');
  const [offset,setOffset]=useState(0),[column,setColumn]=useState(0);
  const [query,setQuery]=useState(''),[filter,setFilter]=useState(''),[changed,setChanged]=useState(false);
  async function refresh() {
    setBusy(true);setError('');
    try {await desktop.connect();setCatalog((await desktop.request('commonality_catalog').promise).commonality as Catalog);setSelected([]);}
    catch(e) {setError(errorText(e));} finally {setBusy(false);}
  }
  useEffect(()=>{void refresh();},[]);
  useEffect(()=>{const timer=setTimeout(()=>setFilter(query),180);return()=>clearTimeout(timer);},[query]);
  useEffect(()=>{setColumn(0);},[filter,changed]);
  useEffect(()=>{
    if(!result)return;
    let active=true;setBusy(true);
    desktop.request('commonality_page',{snapshot:result.snapshot,offset,limit:100,column,query:filter,changed_only:changed}).promise
      .then(r=>{if(active)setPage(r.commonality as Page);})
      .catch(e=>{if(active)setError(errorText(e));}).finally(()=>{if(active)setBusy(false);});
    return()=>{active=false;};
  },[result,offset,column,filter,changed]);
  async function compare() {
    if(!catalog)return;
    setBusy(true);setError('');setOutput('');
    try {const r=await desktop.request('commonality_compare',{catalog:catalog.catalog,files:selected}).promise;setOffset(0);setColumn(0);setResult(r.commonality as Result);}
    catch(e) {setError(errorText(e));} finally {setBusy(false);}
  }
  async function save() {
    if(!result)return;
    setBusy(true);setError('');
    try {const r=await desktop.request('commonality_export',{snapshot:result.snapshot,changed_only:changed}).promise;setOutput((r.commonality as {path:string}).path);}
    catch(e) {setError(errorText(e));} finally {setBusy(false);}
  }
  return <section className="panel">
    <div className="section-heading"><div><span className="step">COMMONALITY</span><h2>Lot 파라미터 취합·비교</h2></div><button disabled={busy} onClick={refresh}>결과 목록 새로고침</button></div>
    <p className="hint">기존 수동 조사와 자동 감시에서 저장한 로컬 결과를 선택하세요. 원본 장비 파일은 변경하지 않습니다.</p>
    {error&&<p className="alert" role="alert">{error}</p>}
    <div className="cm-files">{catalog?.files.length?catalog.files.map(f=><label key={f.id} className="cm-file"><input type="checkbox" disabled={busy} checked={selected.includes(f.id)} onChange={e=>setSelected(s=>e.target.checked?[...s,f.id]:s.filter(i=>i!==f.id))}/><span>{f.name}<small>{f.folder}</small></span></label>):<p>저장된 조사 결과가 없습니다.</p>}</div>
    <div className="dialog-actions"><span>{selected.length}개 선택</span><button className="primary" disabled={busy||!selected.length||selected.length>100} onClick={compare}>{busy?'처리 중…':'선택 결과 비교'}</button></div>
    {result&&<>
      <div className="recipe-controls"><label className="field">파라미터 검색<input maxLength={256} value={query} disabled={busy} onChange={e=>setQuery(e.target.value)}/></label><label><input type="checkbox" disabled={busy} checked={changed} onChange={e=>setChanged(e.target.checked)}/> 값이 다른 파라미터만</label><button disabled={busy} onClick={save}>비교 Excel 저장</button></div>
      <p className="hint">{result.total}개 S/M · 전체 {result.parameters}개 파라미터 · 값 차이 {result.changed}개. 주황 셀: 기존 비교 엔진의 최빈값 이탈 · Fail/낮은 매칭은 상태로 표시합니다.</p>
      <div className="pagination"><span>파라미터 {page?.parameter_total?column+1:0}–{Math.min(column+12,page?.parameter_total||0)} / {page?.parameter_total||0}</span><div><button disabled={busy||column===0} onClick={()=>setColumn(n=>Math.max(0,n-12))}>이전 파라미터</button><button disabled={busy||column+12>=(page?.parameter_total||0)} onClick={()=>setColumn(n=>n+12)}>다음 파라미터</button></div></div>
      <div className="table-scroll" aria-busy={busy}><table><thead><tr><th>상태</th>{page?.headers.map((h,i)=><th key={i}>{h}</th>)}</tr></thead><tbody>{page?.rows.map(row=><tr key={row.id}><td>{[row.fail?'Fail':'',row.low_match?'낮은 매칭':''].filter(Boolean).join(' · ')||'—'}</td>{row.values.map((value,i)=><td key={i} className={row.outliers.includes(i)?'cm-outlier':''} title={value}>{value||'—'}</td>)}</tr>)}</tbody></table></div>
      <div className="pagination"><span>{result.total?offset+1:0}–{Math.min(offset+100,result.total)} / {result.total}행</span><div><button disabled={busy||offset===0} onClick={()=>setOffset(n=>Math.max(0,n-100))}>이전</button><button disabled={busy||offset+100>=result.total} onClick={()=>setOffset(n=>n+100)}>다음</button></div></div>
    </>}
    {output&&<label className="field">저장된 Excel<input readOnly value={output}/></label>}
  </section>;
}
