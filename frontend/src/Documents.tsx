import {useEffect,useRef,useState} from 'react';
import {desktop,errorText} from './desktop';
import {notify} from './ui';
type Column={type:'text'|'bool'|'choice';choices?:string[]};
type Catalog={snapshot:string|null;headers:string[];columns?:Column[];total:number;source:string};
type Cell={value:string;color:string;editable:boolean};
type Row={id:number;cells:Cell[]};
function ink(color:string){
  if(!/^#[0-9a-f]{6}$/i.test(color))return undefined;
  const channels=[1,3,5].map(i=>parseInt(color.slice(i,i+2),16)/255).map(c=>c<=.04045?c/12.92:((c+.055)/1.055)**2.4);
  return channels[0]*.2126+channels[1]*.7152+channels[2]*.0722>.179?'#111827':'#ffffff';
}
export function Documents({kind}:{kind:'ip'|'special'|'reference'}){
  const [catalog,setCatalog]=useState<Catalog>(),[rows,setRows]=useState<Row[]>([]);
  const [offset,setOffset]=useState(0),[loading,setLoading]=useState(false),[error,setError]=useState('');
  useEffect(()=>{if(error){notify(error,'error');setError('');}},[error]);
  const [editing,setEditing]=useState<{row:number;column:number;cell:Cell}>();
  const [value,setValue]=useState(''),[color,setColor]=useState(''),[saving,setSaving]=useState(false);
  const dialog=useRef<HTMLDialogElement>(null);
  const appendDialog=useRef<HTMLDialogElement>(null);
  const [newValues,setNewValues]=useState<string[]>();
  const [removing,setRemoving]=useState<{row:number;label:string}>();
  const removeDialog=useRef<HTMLDialogElement>(null);
  useEffect(()=>{if(removing)removeDialog.current?.showModal();else removeDialog.current?.close();},[removing]);
  const kindOf=(i:number)=>catalog?.columns?.[i]?.type||'text';
  async function run(method:string,params:object){
    if(!catalog?.snapshot)return false;
    setSaving(true);setError('');
    try{const reply=await desktop.request(method,{snapshot:catalog.snapshot,...params}).promise;
      setCatalog(reply.document as Catalog);return true;}
    catch(e){setError(errorText(e));return false;}finally{setSaving(false);}
  }
  // 종료 여부: one click toggles ☑/☐ and saves, like the tkinter checkbox column.
  const toggle=(row:number,column:number,cell:Cell)=>run('document_edit',{row,column,value:cell.value==='☑'?'☐':'☑',color:cell.color});
  async function remove(){if(removing&&await run('document_delete',{row:removing.row}))setRemoving(undefined);}
  useEffect(()=>{if(newValues)appendDialog.current?.showModal();else appendDialog.current?.close();},[Boolean(newValues)]);
  async function append(){
    if(!newValues||!catalog?.snapshot)return;
    setSaving(true);setError('');
    try{const reply=await desktop.request('document_append',{snapshot:catalog.snapshot,values:newValues}).promise;
      const updated=reply.document as Catalog;
      setOffset(Math.floor((updated.total-1)/100)*100);setCatalog(updated);setNewValues(undefined);
    }catch(e){setError(errorText(e));}finally{setSaving(false);}
  }
  async function refresh(){
    setLoading(true);setError('');
    try{await desktop.connect();setOffset(0);setRows([]);setCatalog((await desktop.request('document_open',{kind}).promise).document as Catalog);}
    catch(e){setError(errorText(e));}finally{setLoading(false);}
  }
  useEffect(()=>{void refresh();},[kind]);
  useEffect(()=>{
    if(!catalog?.snapshot)return;
    let active=true;setLoading(true);
    desktop.request('document_page',{snapshot:catalog.snapshot,offset,limit:100}).promise.then(reply=>{
      if(active)setRows((reply.document as {rows:Row[]}).rows);
    }).catch(e=>{if(active)setError(errorText(e));}).finally(()=>{if(active)setLoading(false);});
    return()=>{active=false;};
  },[catalog,offset]);
  useEffect(()=>{if(editing)dialog.current?.showModal();else dialog.current?.close();},[editing]);
  async function save(){
    if(!editing||!catalog?.snapshot)return;
    setSaving(true);setError('');
    try{const reply=await desktop.request('document_edit',{snapshot:catalog.snapshot,row:editing.row,column:editing.column,value,color}).promise;
      setCatalog(reply.document as Catalog);setEditing(undefined);
    }catch(e){setError(errorText(e));}finally{setSaving(false);}
  }
  return <section className="panel"><div className="section-heading"><div><span className="step">SHARED WORKBOOK</span><h2>{catalog?.source||'공유 자료'}</h2></div><button disabled={loading||saving} onClick={refresh}>새로고침</button></div>
    <p className="hint">셀을 눌러 내용과 색상을 수정하세요. 저장 시 다른 사용자의 편집과 파일 변경 여부를 확인합니다.</p>
    {!catalog?.snapshot?<div className="empty-state">{loading?'문서를 불러오는 중…':'기존 저장 폴더에 해당 문서가 없습니다.'}</div>:<>
      <button disabled={loading||saving} onClick={()=>{setError('');setNewValues(catalog.headers.map((_,i)=>kindOf(i)==='bool'?'☐':''));}}>새 행 추가</button>
      <div className="table-scroll document-table" aria-busy={loading}><table><thead><tr><th>행</th>{catalog.headers.map((h,i)=><th key={i}>{h}</th>)}<th aria-label="행 삭제"></th></tr></thead><tbody>{rows.map((row,index)=><tr key={row.id}><td>{offset+index+1}</td>{row.cells.map((cell,column)=><td key={column}>{kindOf(column)==='bool'
            ?<button className="document-cell doc-check" role="checkbox" aria-checked={cell.value==='☑'} aria-label={`${offset+index+1}행 ${catalog.headers[column]}`} style={{background:cell.color||undefined,color:ink(cell.color)}} disabled={!cell.editable||loading||saving} onClick={()=>toggle(row.id,column,cell)}>{cell.value==='☑'?'☑':'☐'}</button>
            :<button className="document-cell" style={{background:cell.color||undefined,color:ink(cell.color)}} disabled={!cell.editable||loading} onClick={()=>{setEditing({row:row.id,column,cell});setValue(cell.value);setColor(cell.color);setError('');}}>{cell.value||'—'}</button>}</td>)}
            <td><button className="linklike" aria-label={`${offset+index+1}행 삭제`} disabled={loading||saving} onClick={()=>setRemoving({row:row.id,label:row.cells.map(c=>c.value).filter(Boolean).slice(0,3).join(' · ')||`${offset+index+1}행`})}>삭제</button></td></tr>)}</tbody></table></div>
      <div className="pagination"><span>{catalog.total?`${offset+1}–${Math.min(offset+100,catalog.total)} / ${catalog.total}행`:'0행'}</span><div><button disabled={loading||offset===0} onClick={()=>setOffset(n=>Math.max(0,n-100))}>이전</button><button disabled={loading||offset+100>=catalog.total} onClick={()=>setOffset(n=>n+100)}>다음</button></div></div>
    </>}
    <dialog className="edit-dialog" ref={dialog} onCancel={e=>{if(saving)e.preventDefault();else setEditing(undefined);}}><h2>셀 편집 · {editing&&catalog?.headers[editing.column]}</h2>{editing&&kindOf(editing.column)==='choice'
      ?<label className="field">내용<select value={value} onChange={e=>setValue(e.target.value)} disabled={saving}><option value="">(비움)</option>{catalog?.columns?.[editing.column].choices?.map(c=><option key={c}>{c}</option>)}</select></label>
      :<label className="field">내용<textarea rows={5} maxLength={4000} value={value} onChange={e=>setValue(e.target.value)} disabled={saving}/></label>}<label className="field">배경 색상<input type="color" value={color||'#ffffff'} onChange={e=>setColor(e.target.value)} disabled={saving}/></label><button disabled={saving} onClick={()=>setColor('')}>색상 제거</button>{error&&<p role="alert" className="dialog-error">{error}</p>}<div className="dialog-actions"><button disabled={saving} onClick={()=>setEditing(undefined)}>취소</button><button className="primary" disabled={saving} onClick={save}>{saving?'저장 중…':'저장'}</button></div></dialog>
    <dialog className="edit-dialog" ref={appendDialog} onCancel={e=>{if(saving)e.preventDefault();else setNewValues(undefined);}}>
      <h2>새 행 추가</h2><p className="hint">문서 마지막에 추가합니다. 저장 전까지 공유 파일은 변경되지 않습니다.</p>
      <div style={{maxHeight:'55vh',overflowY:'auto'}}>{newValues?.map((v,i)=>{const set=(x:string)=>setNewValues(values=>values?.map((old,j)=>j===i?x:old));const kind=kindOf(i);
        return kind==='bool'?<label className="field checkbox" key={i}><input type="checkbox" checked={v==='☑'} disabled={saving} onChange={e=>set(e.target.checked?'☑':'☐')}/>{catalog?.headers[i]}</label>
          :kind==='choice'?<label className="field" key={i}>{catalog?.headers[i]}<select value={v} disabled={saving} onChange={e=>set(e.target.value)}><option value="">(비움)</option>{catalog?.columns?.[i].choices?.map(c=><option key={c}>{c}</option>)}</select></label>
          :<label className="field" key={i}>{catalog?.headers[i]}<textarea rows={2} maxLength={4000} value={v} disabled={saving} onChange={e=>set(e.target.value)}/></label>;})}</div>
            <div className="dialog-actions"><button disabled={saving} onClick={()=>setNewValues(undefined)}>취소</button><button className="primary" disabled={saving||!newValues?.some((v,i)=>kindOf(i)!=='bool'&&v.trim())} onClick={append}>{saving?'저장 중…':'행 저장'}</button></div>
    </dialog>
    <dialog className="edit-dialog" ref={removeDialog} onCancel={e=>{if(saving)e.preventDefault();else setRemoving(undefined);}}>
      <h2>행 삭제</h2><p>{removing?.label}</p><p className="hint">공유 문서에서 이 행을 지웁니다. 되돌리려면 다시 입력해야 합니다.</p>
      <div className="dialog-actions"><button disabled={saving} onClick={()=>setRemoving(undefined)}>취소</button><button className="primary" disabled={saving} onClick={remove}>{saving?'삭제 중…':'삭제'}</button></div>
    </dialog>
  </section>;
}
