import {useEffect,useRef,useState} from 'react';
import {desktop,errorText} from './desktop';
import {notify} from './ui';
type Catalog={version:string|null;recipes:string[];machines:string[];source:string};
type Row={id:number;name:string;alg:string;zone:string;variant:string;note:string;color:string;value:string;values:Record<string,string>};
type Page={rows:Row[];total:number;machines:string[];offset:number;machine_total:number};
const HEIGHT=42;

export function Recipe(){
  const [catalog,setCatalog]=useState<Catalog>();
  const [recipe,setRecipe]=useState(''),[machine,setMachine]=useState('');
  const [query,setQuery]=useState(''),[filter,setFilter]=useState('');
  const [offset,setOffset]=useState(0),[column,setColumn]=useState(0);
  const [data,setData]=useState<Page>();
  const [loading,setLoading]=useState(false),[error,setError]=useState('');
  useEffect(()=>{if(error){notify(error,'error');setError('');}},[error]);
  const [editing,setEditing]=useState<{row:Row;kind:'color'|'note'}>();
  const [value,setValue]=useState(''),[saving,setSaving]=useState(false);
  const [selected,setSelected]=useState<Row>();
  const viewport=useRef<HTMLDivElement>(null),dialog=useRef<HTMLDialogElement>(null);
  const sequence=useRef(0);
  function accept(next:Catalog){
    setCatalog(next);setRecipe(old=>next.recipes.includes(old)?old:(next.recipes[0]||''));
    setMachine(old=>next.machines.includes(old)?old:(next.machines[0]||''));
  }
  async function refresh(){
    setLoading(true);setError('');
    try{await desktop.connect();const reply=await desktop.request('recipe_open').promise;accept(reply.recipe as Catalog);}
    catch(e){setError(errorText(e));}finally{setLoading(false);}
  }
  useEffect(()=>{void refresh();},[]);
  useEffect(()=>{const timer=setTimeout(()=>setFilter(query),180);return()=>clearTimeout(timer);},[query]);
  useEffect(()=>{setOffset(0);setSelected(undefined);if(viewport.current)viewport.current.scrollTop=0;},[recipe,machine,filter]);
  useEffect(()=>{
    if(!catalog?.version||!machine)return;
    const current=++sequence.current;setLoading(true);
    desktop.request('recipe_page',{snapshot:catalog.version,recipe,selected_machine:machine,query:filter,
      offset,limit:100,machine_offset:column,machine_limit:12}).promise.then(reply=>{
        if(current===sequence.current)setData(reply.recipe as Page);
      }).catch(e=>{if(current===sequence.current)setError(errorText(e));})
      .finally(()=>{if(current===sequence.current)setLoading(false);});
    return()=>{sequence.current++;};
  },[catalog,recipe,machine,filter,offset,column]);
  useEffect(()=>{if(editing)dialog.current?.showModal();else dialog.current?.close();},[editing]);
  const begin=(row:Row,kind:'color'|'note')=>{setError('');setEditing({row,kind});setValue(row[kind]);};
  async function save(){
    if(!editing||!catalog?.version)return;
    if(editing.kind==='color'&&value&&!/^#[\da-f]{6}$/i.test(value)){setError('#RRGGBB 형식의 색상 코드를 입력하세요.');return;}
    setSaving(true);setError('');
    try{const reply=await desktop.request('recipe_edit',{snapshot:catalog.version,row:editing.row.id,kind:editing.kind,value}).promise;
      accept(reply.recipe as Catalog);setEditing(undefined);setSelected(undefined);
    }catch(e){setError(errorText(e));}finally{setSaving(false);}
  }
  async function copy(){
    if(!selected||!data)return;
    try{await navigator.clipboard.writeText([selected.zone,selected.alg,selected.name,selected.value,selected.note,...data.machines.map(m=>selected.values[m])].join('\t'));}
    catch{setError('클립보드 복사에 실패했습니다. 셀 텍스트를 선택해 복사해 주세요.');}
  }
  const columns=data?.machines||[];
  const grid={gridTemplateColumns:`520px repeat(${columns.length}, 120px)`};
  return <section className="panel recipe-panel">
    <div className="section-heading"><div><span className="step">PARAMETER COMPARISON</span><h2>장비 파라미터 비교</h2></div><button disabled={loading||saving} onClick={refresh}>최신 취합 새로고침</button></div>
    <p className="hint">좌측은 기준 호기, 우측은 비교 호기입니다. 장비 값은 읽기 전용이며 색상과 비고만 수정할 수 있습니다.</p>
    {!catalog?.version?<div className="empty-state"><h3>{loading?'최신 취합본을 불러오는 중…':'표시할 취합본이 없습니다.'}</h3><p>기존 프로그램에서 저장한 최신 파라미터 취합 파일을 사용합니다.</p></div>:<>
      <div className="recipe-controls"><label className="field">Recipe<select value={recipe} onChange={e=>setRecipe(e.target.value)}>{catalog.recipes.map(r=><option key={r}>{r}</option>)}</select></label><label className="field">기준 호기<select value={machine} onChange={e=>setMachine(e.target.value)}>{catalog.machines.map(m=><option key={m}>{m}</option>)}</select></label><label className="field">파라미터 검색<input value={query} onChange={e=>setQuery(e.target.value)} maxLength={256} placeholder="이름 · Alg · Zone · 비고"/></label><button disabled={!selected} onClick={copy}>선택 행 복사</button></div>
      <div className="comparison-info"><span>{catalog.source} · {data?.total.toLocaleString()||0}개 항목</span><div><button disabled={column===0||loading} onClick={()=>setColumn(n=>Math.max(0,n-12))}>이전 호기</button><span>{column+1}–{Math.min(column+12,catalog.machines.length)} / {catalog.machines.length}호기</span><button disabled={column+12>=catalog.machines.length||loading} onClick={()=>setColumn(n=>n+12)}>다음 호기</button></div></div>
      <div className="comparison-viewport" ref={viewport} tabIndex={0} aria-label="장비 파라미터 비교표" aria-busy={loading} onScroll={e=>{
        const start=Math.max(0,Math.floor((e.currentTarget.scrollTop-HEIGHT)/HEIGHT));
        setOffset(Math.floor(start/40)*40);
      }}>
        <div className="comparison-header" style={grid}><div className="equipment-left"><span>색상</span><span>Parameter / Alg · Zone</span><span>★ {machine}</span><span>비고</span></div>{columns.map(m=><span key={m}>{m}</span>)}</div>
        <div className="comparison-body" style={{height:(data?.total||0)*HEIGHT,minWidth:520+columns.length*120}}>
          {data?.rows.map((row,i)=><div key={row.id} className={'comparison-row '+(selected?.id===row.id?'row-selected':'')} style={{...grid,top:(data.offset+i)*HEIGHT,height:HEIGHT}} onClick={()=>setSelected(row)}>
            <div className="equipment-left"><button className="color-button" style={{background:row.color}} aria-label={`${row.name} 색상 변경`} title={row.color} onClick={()=>begin(row,'color')}/><span title={`${row.name}\n${row.alg} · ${row.zone} · ${row.variant}`} className="parameter-label">{row.name}<small>{row.alg} · {row.zone}</small></span><span className="equipment-value" title={row.value}>{row.value||'—'}</span><button className="note-button" title={row.note||'비고 입력'} onClick={()=>begin(row,'note')}>{row.note||'비고 입력'}</button></div>
            {columns.map(m=><span key={m} className={row.values[m]&&row.value&&row.values[m]!==row.value?'different':''} title={row.values[m]}>{row.values[m]||'—'}</span>)}
          </div>)}
        </div>
      </div><p className="hint" role="status">{loading?'표를 불러오는 중…':'현재 화면 주변 최대 100행 · 비교 호기 12개만 렌더링합니다. 색상 버튼과 비고를 눌러 수정하세요.'}</p>
    </>}
    <dialog ref={dialog} className="edit-dialog" onCancel={e=>{if(saving)e.preventDefault();else setEditing(undefined);}}>
      <h2>{editing?.kind==='color'?'파라미터 분류 색상':'비고 수정'}</h2><p>{editing?.row.name}</p>
      {editing?.kind==='color'?<><div className="color-preview" style={{background:/^#[\da-f]{6}$/i.test(value)?value:'#C9D0D2'}}/><label className="field">색상표에서 선택<input type="color" value={/^#[\da-f]{6}$/i.test(value)?value:'#C9D0D2'} onChange={e=>setValue(e.target.value)} disabled={saving}/></label><label className="field">색상 코드<input value={value} onChange={e=>setValue(e.target.value)} maxLength={7} disabled={saving}/></label><button onClick={()=>setValue('')} disabled={saving}>자동 색상으로 복원</button></>:<label className="field">비고<textarea value={value} onChange={e=>setValue(e.target.value)} maxLength={4000} rows={5} disabled={saving}/></label>}
      <div className="dialog-actions"><button disabled={saving} onClick={()=>setEditing(undefined)}>취소</button><button className="primary" disabled={saving} onClick={save}>{saving?'저장 중…':'저장'}</button></div>
    </dialog>
  </section>;
}
