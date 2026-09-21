import {useEffect,useState} from 'react';
import {desktop,errorText} from './desktop';

type Files={save_dir:boolean;catalog:string|null;files:{id:string;name:string}[]};
type Diff={snapshot:string;machines:string[];changes:number;added:number;removed:number;old:string;new:string};
type Change={sheet:string;recipe:string;zone:string;alg:string;param:string;machine:string;old:string;new:string;kind:string};
type Page={total:number;offset:number;rows:Change[]};
const KINDS=['','값변경','추가','삭제'];

export function History(){
  const [files,setFiles]=useState<Files>(),[oldId,setOldId]=useState(''),[newId,setNewId]=useState('');
  const [diff,setDiff]=useState<Diff>(),[page,setPage]=useState<Page>();
  const [offset,setOffset]=useState(0),[kind,setKind]=useState(''),[query,setQuery]=useState(''),[filter,setFilter]=useState('');
  const [busy,setBusy]=useState(false),[error,setError]=useState('');
  async function refresh(){
    setBusy(true);setError('');
    try{await desktop.connect();const r=(await desktop.request('history_files').promise).history as Files;
      setFiles(r);setDiff(undefined);setPage(undefined);
      setOldId(r.files[1]?.id||'');setNewId(r.files[0]?.id||'');}
    catch(e){setError(errorText(e));}finally{setBusy(false);}
  }
  useEffect(()=>{void refresh();},[]);
  useEffect(()=>{const t=setTimeout(()=>setFilter(query),180);return()=>clearTimeout(t);},[query]);
  useEffect(()=>{setOffset(0);},[kind,filter]);
  useEffect(()=>{
    if(!diff)return;let active=true;setBusy(true);
    desktop.request('history_page',{snapshot:diff.snapshot,offset,limit:100,kind,query:filter}).promise
      .then(r=>{if(active)setPage(r.history as Page);})
      .catch(e=>{if(active)setError(errorText(e));}).finally(()=>{if(active)setBusy(false);});
    return()=>{active=false;};
  },[diff,offset,kind,filter]);
  async function compare(){
    if(!files?.catalog||!oldId||!newId)return;setBusy(true);setError('');setOffset(0);
    try{const r=await desktop.request('history_diff',{catalog:files.catalog,old:oldId,new:newId}).promise;
      setDiff(r.history as Diff);}
    catch(e){setError(errorText(e));setDiff(undefined);}finally{setBusy(false);}
  }
  if(files&&!files.save_dir)
    return <section className="panel"><p className="table-empty">먼저 저장폴더를 지정하세요.</p></section>;
  return <>
    <section className="panel">
      <div className="section-heading"><div><span className="step">HISTORY</span><h2>이력 확인 — 취합 파일 비교</h2></div>
        <button disabled={busy} onClick={refresh}>목록 새로고침</button></div>
      <p className="hint">저장폴더의 '파라미터 값 취합' 파일 2개를 골라 값이 달라진 부분만 비교합니다(읽기 전용).</p>
      {error&&<p className="alert" role="alert">{error}</p>}
      {(files?.files.length||0)<2
        ? <p className="table-empty">비교할 취합 파일이 2개 이상 필요합니다.</p>
        : <div className="form-picker">
            <label className="field">이전(old)<select value={oldId} onChange={e=>setOldId(e.target.value)}>
              {files!.files.map(f=><option key={f.id} value={f.id}>{f.name}</option>)}</select></label>
            <label className="field">최신(new)<select value={newId} onChange={e=>setNewId(e.target.value)}>
              {files!.files.map(f=><option key={f.id} value={f.id}>{f.name}</option>)}</select></label>
            <button className="primary" disabled={busy||!oldId||!newId||oldId===newId} onClick={compare}>비교 <span aria-hidden="true">→</span></button>
          </div>}
    </section>
    {diff&&<section className="panel">
      <div className="section-heading"><div><span className="step">CHANGES</span><h2>{diff.old} → {diff.new}</h2></div>
        <span className="count">값변경 {diff.changes} · 추가행 {diff.added} · 삭제행 {diff.removed}</span></div>
      <div className="form-filter">
        <label className="field">종류<select value={kind} onChange={e=>setKind(e.target.value)}>
          {KINDS.map(k=><option key={k} value={k}>{k||'전체'}</option>)}</select></label>
        <label className="field">검색<input value={query} maxLength={256} placeholder="파라미터·레시피·호기" onChange={e=>setQuery(e.target.value)}/></label>
      </div>
      <div className="table-scroll" aria-busy={busy}><table><thead><tr>
        <th>레시피</th><th>Zone</th><th>Alg</th><th>파라미터</th><th>호기</th><th>이전</th><th>최신</th><th>종류</th></tr></thead>
        <tbody>{(page?.rows||[]).map((c,i)=><tr key={i}>
          <td>{c.recipe}</td><td>{c.zone}</td><td>{c.alg}</td><td>{c.param}</td><td>{c.machine}</td>
          <td>{c.old||'—'}</td><td>{c.new||'—'}</td><td>{c.kind}</td></tr>)}</tbody></table>
        {(busy||!(page?.rows||[]).length)&&<p className="table-empty">{busy?'불러오는 중…':'표시할 변경이 없습니다.'}</p>}</div>
      <div className="pagination"><span>{page?.total?`${offset+1}–${Math.min(offset+100,page.total)} / ${page.total}건`:'0건'}</span>
        <div><button disabled={busy||offset===0} onClick={()=>setOffset(n=>Math.max(0,n-100))}>이전</button>
          <button disabled={busy||offset+100>=(page?.total||0)} onClick={()=>setOffset(n=>n+100)}>다음</button></div></div>
    </section>}
  </>;
}
