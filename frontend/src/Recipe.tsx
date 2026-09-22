import {useEffect,useRef,useState} from 'react';
import {desktop,errorText} from './desktop';
import {notify} from './ui';
import {OpenPath,openPath} from './OpenPath';
type Catalog={version:string|null;recipes:string[];machines:string[];source:string;path?:string;
  zones?:Record<string,string[]>;machine_types?:Record<string,string>;hide_kla?:boolean};
type Row={id:number;name:string;alg:string;zone:string;variant:string;note:string;color:string;value:string;values:Record<string,string>;cells?:Record<string,string>};
type Page={rows:Row[];total:number;machines:string[];offset:number;machine_total:number};
type Preview={recipes:string[];recipe?:string;versions?:number;files?:number;bytes?:number;watched?:string[];latest?:string};
const HEIGHT=42;
const ink=(hex?:string)=>{if(!hex||!/^#[\da-f]{6}$/i.test(hex))return undefined;
  const [r,g,b]=[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16));return r*.299+g*.587+b*.114>150?'#111827':'#ffffff';};

export function Recipe(){
  const [catalog,setCatalog]=useState<Catalog>();
  const [recipe,setRecipe]=useState(''),[machine,setMachine]=useState('');
  const [query,setQuery]=useState(''),[filter,setFilter]=useState(''),[zone,setZone]=useState('');
  const [hideKla,setHideKla]=useState(true);
  const [offset,setOffset]=useState(0),[column,setColumn]=useState(0);
  const [data,setData]=useState<Page>();
  const [loading,setLoading]=useState(false),[error,setError]=useState('');
  useEffect(()=>{if(error){notify(error,'error');setError('');}},[error]);
  const [editing,setEditing]=useState<{row:Row;kind:'color'|'note'}>();
  const [value,setValue]=useState(''),[saving,setSaving]=useState(false);
  const [selected,setSelected]=useState<Row>();
  const [paint,setPaint]=useState(false),[brush,setBrush]=useState('#FFF2CC'),[erase,setErase]=useState(false);
  const [exporting,setExporting]=useState<{recipes:string[];machines:string[];filtered:boolean;path?:string}>();
  const [removing,setRemoving]=useState<Preview&{confirm:string}>();
  const viewport=useRef<HTMLDivElement>(null),dialog=useRef<HTMLDialogElement>(null);
  const exportDialog=useRef<HTMLDialogElement>(null),removeDialog=useRef<HTMLDialogElement>(null);
  const sequence=useRef(0);
  function accept(next:Catalog){
    setCatalog(next);setRecipe(old=>next.recipes.includes(old)?old:(next.recipes[0]||''));
    setMachine(old=>next.machines.includes(old)?old:(next.machines[0]||''));
    if(typeof next.hide_kla==='boolean')setHideKla(next.hide_kla);
  }
  async function refresh(){
    setLoading(true);setError('');
    try{await desktop.connect();const reply=await desktop.request('recipe_open').promise;accept(reply.recipe as Catalog);}
    catch(e){setError(errorText(e));}finally{setLoading(false);}
  }
  useEffect(()=>{void refresh();},[]);
  useEffect(()=>{const timer=setTimeout(()=>setFilter(query),180);return()=>clearTimeout(timer);},[query]);
  useEffect(()=>{setZone('');},[recipe]);
  useEffect(()=>{setOffset(0);setSelected(undefined);if(viewport.current)viewport.current.scrollTop=0;},[recipe,machine,filter,zone]);
  useEffect(()=>{setColumn(0);},[hideKla]);
  useEffect(()=>{
    if(!catalog?.version||!machine)return;
    const current=++sequence.current;setLoading(true);
    desktop.request('recipe_page',{snapshot:catalog.version,recipe,selected_machine:machine,query:filter,zone,hide_kla:hideKla,
      offset,limit:100,machine_offset:column,machine_limit:12}).promise.then(reply=>{
        if(current===sequence.current)setData(reply.recipe as Page);
      }).catch(e=>{if(current===sequence.current)setError(errorText(e));})
      .finally(()=>{if(current===sequence.current)setLoading(false);});
    return()=>{sequence.current++;};
  },[catalog,recipe,machine,filter,zone,hideKla,offset,column]);
  useEffect(()=>{if(editing)dialog.current?.showModal();else dialog.current?.close();},[editing]);
  useEffect(()=>{if(exporting)exportDialog.current?.showModal();else exportDialog.current?.close();},[Boolean(exporting)]);
  useEffect(()=>{if(removing)removeDialog.current?.showModal();else removeDialog.current?.close();},[Boolean(removing)]);
  const begin=(row:Row,kind:'color'|'note')=>{setError('');setEditing({row,kind});setValue(row[kind]);};
  async function save(){
    if(!editing||!catalog?.version)return;
    if(editing.kind==='color'&&value&&!/^#[\da-f]{6}$/i.test(value)){setError('#RRGGBB 형식의 색상 코드를 입력하세요.');return;}
    setSaving(true);setError('');
    try{const reply=await desktop.request('recipe_edit',{snapshot:catalog.version,row:editing.row.id,kind:editing.kind,value}).promise;
      accept(reply.recipe as Catalog);setEditing(undefined);setSelected(undefined);
    }catch(e){setError(errorText(e));}finally{setSaving(false);}
  }
  // 셀 색칠 mode: a click paints (or clears) that one cell, stored in 값확인_셀색상.json.
  async function paintCell(row:Row,target:string){
    if(!catalog?.version)return;
    const color=erase?'':brush;
    try{await desktop.request('recipe_edit',{snapshot:catalog.version,row:row.id,kind:'cell',target,value:color}).promise;
      setData(d=>d&&{...d,rows:d.rows.map(r=>{if(r.id!==row.id)return r;const cells={...(r.cells||{})};
        if(color)cells[target]=color.toUpperCase();else delete cells[target];return {...r,cells};})});}
    catch(e){setError(errorText(e));}
  }
  const cellStyle=(row:Row,target:string)=>{const c=row.cells?.[target];return c?{background:c,color:ink(c)}:undefined;};
  const onCell=(row:Row,target:string,fallback?:()=>void)=>(e:React.MouseEvent)=>{
    if(paint){e.stopPropagation();void paintCell(row,target);}else fallback?.();};
  async function copy(){
    if(!selected||!data)return;
    try{await navigator.clipboard.writeText([selected.zone,selected.alg,selected.name,selected.value,selected.note,...data.machines.map(m=>selected.values[m])].join('\t'));}
    catch{setError('클립보드 복사에 실패했습니다. 셀 텍스트를 선택해 복사해 주세요.');}
  }
  async function toggleKla(next:boolean){
    setHideKla(next);
    try{await desktop.request('config_set_hide_kla',{enabled:next}).promise;}catch(e){setError(errorText(e));}
  }
  async function runExport(){
    if(!exporting||!catalog?.version)return;
    setSaving(true);
    try{const reply=await desktop.request('recipe_export',{snapshot:catalog.version,recipes:exporting.recipes,
        machines:exporting.machines,...(exporting.filtered?{query:filter,zone}:{})}).promise;
      const out=reply.recipe as {path:string;rows:number};
      setExporting(x=>x&&{...x,path:out.path});notify(`내보내기 완료 · ${out.rows.toLocaleString()}개 항목`,'ok');}
    catch(e){setError(errorText(e));}finally{setSaving(false);}
  }
  async function openRemove(){
    try{const reply=await desktop.request('recipe_delete_preview',{recipe:''}).promise;
      setRemoving({...(reply.recipe as Preview),confirm:''});}
    catch(e){setError(errorText(e));}
  }
  async function previewRemove(name:string){
    if(!name){setRemoving(r=>r&&{recipes:r.recipes,confirm:''});return;}
    try{const reply=await desktop.request('recipe_delete_preview',{recipe:name}).promise;
      setRemoving({...(reply.recipe as Preview),confirm:''});}
    catch(e){setError(errorText(e));}
  }
  async function runRemove(){
    if(!removing?.recipe)return;
    setSaving(true);
    try{const reply=await desktop.request('recipe_delete',{recipe:removing.recipe,confirm:removing.confirm}).promise;
      const out=reply.recipe as {recipe:string;moved:string;sheets:number;watch_machines:string[];note:string};
      notify(`'${out.recipe}' 레시피를 삭제했습니다.`+(out.moved?` 되돌리기용 보관: ${out.moved}`:''),'ok');
      if(out.note)notify(out.note,'error');
      setRemoving(undefined);await refresh();}
    catch(e){setError(errorText(e));}finally{setSaving(false);}
  }
  const columns=data?.machines||[];
  const zones=catalog?.zones?.[recipe]||[];
  const grid={gridTemplateColumns:`520px repeat(${columns.length}, 120px)`};
  const visibleTotal=data?.machine_total??catalog?.machines.length??0;
  return <section className="panel recipe-panel">
    <div className="section-heading"><div><span className="step">PARAMETER COMPARISON</span><h2>장비 파라미터 비교</h2></div>
      <div className="toolbar"><button disabled={loading||saving} onClick={refresh}>최신 취합 새로고침</button>
        <button disabled={!catalog?.path} onClick={()=>catalog?.path&&openPath(catalog.path)}>Excel로 열기</button>
        <button disabled={!catalog?.version} onClick={()=>setExporting({recipes:recipe?[recipe]:[],machines:[...(catalog?.machines||[])],filtered:false})}>내보내기…</button>
        <button onClick={openRemove}>레시피 삭제…</button></div></div>
    <p className="hint">좌측은 기준 호기, 우측은 비교 호기입니다. 장비 값은 읽기 전용이며 색상·비고·셀 색칠만 수정할 수 있습니다.</p>
    {!catalog?.version?<div className="empty-state"><h3>{loading?'최신 취합본을 불러오는 중…':'표시할 취합본이 없습니다.'}</h3><p>기존 프로그램에서 저장한 최신 파라미터 취합 파일을 사용합니다.</p></div>:<>
      <div className="recipe-controls">
        <label className="field">Recipe<select value={recipe} onChange={e=>setRecipe(e.target.value)}>{catalog.recipes.map(r=><option key={r}>{r}</option>)}</select></label>
        <label className="field">Zone<select aria-label="Zone" value={zone} onChange={e=>setZone(e.target.value)}><option value="">전체 Zone</option>{zones.map(z=><option key={z}>{z}</option>)}</select></label>
        <label className="field">기준 호기<select value={machine} onChange={e=>setMachine(e.target.value)}>{catalog.machines.map(m=><option key={m}>{m}</option>)}</select></label>
        <label className="field">파라미터 검색<input value={query} onChange={e=>setQuery(e.target.value)} maxLength={256} placeholder="이름 · Alg · Zone · 비고"/></label>
        <button disabled={!selected} onClick={copy}>선택 행 복사</button></div>
      <div className="recipe-tools">
        <label className="field checkbox"><input type="checkbox" checked={hideKla} onChange={e=>void toggleKla(e.target.checked)}/>KLA 장비 숨기기</label>
        <label className="field checkbox"><input type="checkbox" checked={paint} onChange={e=>setPaint(e.target.checked)}/>🖌 셀 색칠 모드</label>
        {paint&&<><input type="color" aria-label="색칠 색상" value={brush} disabled={erase} onChange={e=>setBrush(e.target.value)}/>
          <label className="field checkbox"><input type="checkbox" checked={erase} onChange={e=>setErase(e.target.checked)}/>지우개</label>
          <span className="hint">칸을 누르면 {erase?'색을 지웁니다':'색을 칠합니다'}. 모든 사용자에게 같이 보입니다.</span></>}
      </div>
      <div className="comparison-info"><span>{catalog.source} · {data?.total.toLocaleString()||0}개 항목</span><div><button disabled={column===0||loading} onClick={()=>setColumn(n=>Math.max(0,n-12))}>이전 호기</button><span>{visibleTotal?column+1:0}–{Math.min(column+12,visibleTotal)} / {visibleTotal}호기</span><button disabled={column+12>=visibleTotal||loading} onClick={()=>setColumn(n=>n+12)}>다음 호기</button></div></div>
      <div className={'comparison-viewport'+(paint?' painting':'')} ref={viewport} tabIndex={0} aria-label="장비 파라미터 비교표" aria-busy={loading} onScroll={e=>{
        const start=Math.max(0,Math.floor((e.currentTarget.scrollTop-HEIGHT)/HEIGHT));
        setOffset(Math.floor(start/40)*40);
      }}>
        <div className="comparison-header" style={grid}><div className="equipment-left"><span>색상</span><span>Parameter / Alg · Zone</span><span>★ {machine}</span><span>비고</span></div>{columns.map(m=><span key={m}>{m}</span>)}</div>
        <div className="comparison-body" style={{height:(data?.total||0)*HEIGHT,minWidth:520+columns.length*120}}>
          {data?.rows.map((row,i)=><div key={row.id} className={'comparison-row '+(selected?.id===row.id?'row-selected':'')} style={{...grid,top:(data.offset+i)*HEIGHT,height:HEIGHT}} onClick={()=>setSelected(row)}>
            <div className="equipment-left"><button className="color-button" style={{background:row.color}} aria-label={`${row.name} 색상 변경`} title={row.color} onClick={()=>begin(row,'color')}/>
              <span title={`${row.name}\n${row.alg} · ${row.zone} · ${row.variant}`} className="parameter-label" style={cellStyle(row,'param')} onClick={onCell(row,'param')}>{row.name}<small>{row.alg} · {row.zone}</small></span>
              <span className="equipment-value" title={row.value} style={cellStyle(row,machine)} onClick={onCell(row,machine)}>{row.value||'—'}</span>
              <button className="note-button" title={row.note||'비고 입력'} style={cellStyle(row,'비고')} onClick={onCell(row,'비고',()=>begin(row,'note'))}>{row.note||'비고 입력'}</button></div>
            {columns.map(m=><span key={m} data-machine={m} className={row.values[m]&&row.value&&row.values[m]!==row.value?'different':''} style={cellStyle(row,m)} title={row.values[m]} onClick={onCell(row,m)}>{row.values[m]||'—'}</span>)}
          </div>)}
        </div>
      </div><p className="hint" role="status">{loading?'표를 불러오는 중…':'현재 화면 주변 최대 100행 · 비교 호기 12개만 렌더링합니다. 색상 버튼과 비고를 눌러 수정하세요.'}</p>
    </>}
    <dialog ref={dialog} className="edit-dialog" onCancel={e=>{if(saving)e.preventDefault();else setEditing(undefined);}}>
      <h2>{editing?.kind==='color'?'파라미터 분류 색상':'비고 수정'}</h2><p>{editing?.row.name}</p>
      {editing?.kind==='color'?<><div className="color-preview" style={{background:/^#[\da-f]{6}$/i.test(value)?value:'#C9D0D2'}}/><label className="field">색상표에서 선택<input type="color" value={/^#[\da-f]{6}$/i.test(value)?value:'#C9D0D2'} onChange={e=>setValue(e.target.value)} disabled={saving}/></label><label className="field">색상 코드<input value={value} onChange={e=>setValue(e.target.value)} maxLength={7} disabled={saving}/></label><button onClick={()=>setValue('')} disabled={saving}>자동 색상으로 복원</button></>:<label className="field">비고<textarea value={value} onChange={e=>setValue(e.target.value)} maxLength={4000} rows={5} disabled={saving}/></label>}
      <div className="dialog-actions"><button disabled={saving} onClick={()=>setEditing(undefined)}>취소</button><button className="primary" disabled={saving} onClick={save}>{saving?'저장 중…':'저장'}</button></div>
    </dialog>
    <dialog ref={exportDialog} className="edit-dialog wide-dialog" onCancel={e=>{if(saving)e.preventDefault();else setExporting(undefined);}}>{exporting&&catalog&&<>
      <h2>내보내기</h2><p className="hint">고른 레시피·호기의 값을 읽기 좋은 Excel로 저장합니다(로컬 결과 폴더). 원본 취합/양식은 바뀌지 않습니다.</p>
      <h3>① 레시피</h3><div className="pick-list short">{catalog.recipes.map(r=><label key={r} className="pick-item"><input type="checkbox" checked={exporting.recipes.includes(r)} onChange={e=>setExporting(x=>x&&{...x,path:undefined,recipes:e.target.checked?[...x.recipes,r]:x.recipes.filter(v=>v!==r)})}/> {r}</label>)}</div>
      <h3>② 호기 <button type="button" className="linklike" onClick={()=>setExporting(x=>x&&{...x,machines:x.machines.length===catalog.machines.length?[]:[...catalog.machines]})}>{exporting.machines.length===catalog.machines.length?'전체 해제':'전체 선택'}</button></h3>
      <div className="pick-list short cols">{catalog.machines.map(m=><label key={m} className="pick-item"><input type="checkbox" checked={exporting.machines.includes(m)} onChange={e=>setExporting(x=>x&&{...x,path:undefined,machines:e.target.checked?[...x.machines,m]:x.machines.filter(v=>v!==m)})}/> {m}</label>)}</div>
      <label className="field checkbox"><input type="checkbox" checked={exporting.filtered} onChange={e=>setExporting(x=>x&&{...x,filtered:e.target.checked})}/>현재 Zone·검색 조건에 맞는 항목만 ({zone||'전체 Zone'}{filter?` · "${filter}"`:''})</label>
      {exporting.path&&<OpenPath label="저장된 Excel" path={exporting.path}/>}
      <div className="dialog-actions"><button disabled={saving} onClick={()=>setExporting(undefined)}>닫기</button><button className="primary" disabled={saving||!exporting.recipes.length||!exporting.machines.length} onClick={runExport}>{saving?'저장 중…':'Excel로 내보내기'}</button></div></>}
    </dialog>
    <dialog ref={removeDialog} className="edit-dialog" onCancel={e=>{if(saving)e.preventDefault();else setRemoving(undefined);}}>{removing&&<>
      <h2>레시피 삭제</h2>
      <p className="warn">⚠ 모든 호기 공통으로 적용됩니다: 양식 폴더 전체와 최신 취합본의 그 레시피 시트, 자동 감시 설정의 그 레시피.</p>
      <p className="hint">양식 폴더는 로컬 '삭제보관'으로 옮겨 되돌릴 수 있습니다. 과거 취합본·변환계수.xlsx 는 그대로 둡니다.</p>
      <label className="field">삭제할 레시피<select value={removing.recipe||''} disabled={saving} onChange={e=>void previewRemove(e.target.value)}><option value="">선택…</option>{removing.recipes.map(r=><option key={r}>{r}</option>)}</select></label>
      {removing.recipe&&<><p>양식 버전 {removing.versions}개 · 파일 {removing.files}개 · {((removing.bytes||0)/1024).toFixed(0)} KB{removing.latest?` · 최신 취합본 ${removing.latest}`:''}</p>
        {!!removing.watched?.length&&<p className="warn">자동 감시에서 제외될 호기: {removing.watched.join(', ')}</p>}
        <label className="field">확인을 위해 레시피 이름 '{removing.recipe}' 입력<input value={removing.confirm} disabled={saving} onChange={e=>setRemoving(r=>r&&{...r,confirm:e.target.value})}/></label></>}
      <div className="dialog-actions"><button disabled={saving} onClick={()=>setRemoving(undefined)}>취소</button>
        <button className="primary danger" disabled={saving||!removing.recipe||removing.confirm!==removing.recipe} onClick={runRemove}>{saving?'삭제 중…':'삭제'}</button></div></>}
    </dialog>
  </section>;
}
