import {useEffect, useState} from 'react';
import {desktop} from './desktop';
import {Stepper,StepNav,notify,fail} from './ui';
import './commonality.css';
import {OpenPath} from './OpenPath';
import {CmRun} from './CmRun';

type Catalog = {catalog:string;files:{id:string;name:string;folder:string}[]};
type Result = {snapshot:string;total:number;parameters:number;changed:number};
type Page = {headers:string[];total:number;parameter_total:number;rows:{id:number;values:string[];outliers:number[];fail:boolean;low_match:boolean}[]};
const COMPARE_STEPS=['결과 파일 선택','비교표'];

export function Commonality() {
  const [step,setStep]=useState(0);
  const [catalog,setCatalog]=useState<Catalog>(),[selected,setSelected]=useState<string[]>([]);
  const [result,setResult]=useState<Result>(),[page,setPage]=useState<Page>();
  const [busy,setBusy]=useState(false),[output,setOutput]=useState('');
  const [offset,setOffset]=useState(0),[column,setColumn]=useState(0);
  const [query,setQuery]=useState(''),[filter,setFilter]=useState(''),[changed,setChanged]=useState(false);
  async function refresh() {
    setBusy(true);
    try {await desktop.connect();setCatalog((await desktop.request('commonality_catalog').promise).commonality as Catalog);setSelected([]);setStep(0);}
    catch(e) {fail(e);} finally {setBusy(false);}
  }
  useEffect(()=>{void refresh();},[]);
  useEffect(()=>{const timer=setTimeout(()=>setFilter(query),180);return()=>clearTimeout(timer);},[query]);
  useEffect(()=>{setColumn(0);},[filter,changed]);
  useEffect(()=>{
    if(!result)return;
    let active=true;setBusy(true);
    desktop.request('commonality_page',{snapshot:result.snapshot,offset,limit:100,column,query:filter,changed_only:changed}).promise
      .then(r=>{if(active)setPage(r.commonality as Page);})
      .catch(e=>{if(active)fail(e);}).finally(()=>{if(active)setBusy(false);});
    return()=>{active=false;};
  },[result,offset,column,filter,changed]);
  async function compare() {
    if(!catalog)return;
    setBusy(true);setOutput('');
    try {const r=await desktop.request('commonality_compare',{catalog:catalog.catalog,files:selected}).promise;setOffset(0);setColumn(0);setResult(r.commonality as Result);setStep(1);}
    catch(e) {fail(e);} finally {setBusy(false);}
  }
  async function save() {
    if(!result)return;setBusy(true);
    try {const r=await desktop.request('commonality_export',{snapshot:result.snapshot,changed_only:changed}).promise;setOutput((r.commonality as {path:string}).path);notify('비교 Excel 저장 완료','ok');}
    catch(e) {fail(e);} finally {setBusy(false);}
  }
  return <><CmRun onFinished={()=>void refresh()}/>
  <section className="panel">
    <div className="section-heading"><div><span className="step">COMPARE</span><h2>저장 결과 비교</h2></div><button disabled={busy} onClick={refresh}>결과 목록 새로고침</button></div>
    <Stepper labels={COMPARE_STEPS} current={step} onJump={i=>setStep(i)}/>
    <div className="step-body">
    {step===0&&<>
      <p className="hint">기존 수동 조사와 자동 감시에서 저장한 로컬 결과를 선택하세요. 원본 장비 파일은 변경하지 않습니다.</p>
      <div className="cm-files">{catalog?.files.length?catalog.files.map(f=><label key={f.id} className="cm-file"><input type="checkbox" disabled={busy} checked={selected.includes(f.id)} onChange={e=>setSelected(s=>e.target.checked?[...s,f.id]:s.filter(i=>i!==f.id))}/><span>{f.name}<small>{f.folder}</small></span></label>):<p className="table-empty">저장된 조사 결과가 없습니다.</p>}</div>
      <p className="hint">{selected.length}개 선택</p>
    </>}
    {step===1&&result&&<>
      <div className="recipe-controls"><label className="field">파라미터 검색<input maxLength={256} value={query} disabled={busy} onChange={e=>setQuery(e.target.value)}/></label><label className="field checkbox"><input type="checkbox" disabled={busy} checked={changed} onChange={e=>setChanged(e.target.checked)}/> 값이 다른 파라미터만</label><button disabled={busy} onClick={save}>비교 Excel 저장</button></div>
      <p className="hint">{result.total}개 S/M · 전체 {result.parameters}개 파라미터 · 값 차이 {result.changed}개. 주황 셀: 최빈값 이탈 · Fail/낮은 매칭은 상태로 표시.</p>
      <div className="pagination"><span>파라미터 {page?.parameter_total?column+1:0}–{Math.min(column+12,page?.parameter_total||0)} / {page?.parameter_total||0}</span><div><button disabled={busy||column===0} onClick={()=>setColumn(n=>Math.max(0,n-12))}>이전 파라미터</button><button disabled={busy||column+12>=(page?.parameter_total||0)} onClick={()=>setColumn(n=>n+12)}>다음 파라미터</button></div></div>
      <div className="table-scroll" aria-busy={busy}><table><thead><tr><th>상태</th>{page?.headers.map((h,i)=><th key={i}>{h}</th>)}</tr></thead><tbody>{page?.rows.map(row=><tr key={row.id}><td>{[row.fail?'Fail':'',row.low_match?'낮은 매칭':''].filter(Boolean).join(' · ')||'—'}</td>{row.values.map((value,i)=><td key={i} className={row.outliers.includes(i)?'cm-outlier':''} title={value}>{value||'—'}</td>)}</tr>)}</tbody></table></div>
      <div className="pagination"><span>{result.total?offset+1:0}–{Math.min(offset+100,result.total)} / {result.total}행</span><div><button disabled={busy||offset===0} onClick={()=>setOffset(n=>Math.max(0,n-100))}>이전</button><button disabled={busy||offset+100>=result.total} onClick={()=>setOffset(n=>n+100)}>다음</button></div></div>
      {output&&<OpenPath label="저장된 Excel" path={output}/>}
    </>}
    {step===1&&!result&&<p className="table-empty">먼저 1단계에서 결과 파일을 골라 비교하세요.</p>}
    </div>
    <StepNav step={step} total={COMPARE_STEPS.length} onBack={()=>setStep(0)} onNext={()=>step===0?compare():setStep(0)}
      nextLabel={step===0?'선택 결과 비교':'파일 다시 고르기'} nextDisabled={step===0&&(!selected.length||selected.length>100)} busy={busy}/>
  </section></>;
}
