import {useEffect,useRef,useState} from 'react';
import {desktop,errorText} from './desktop';
type Catalog={snapshot:string|null;headers:string[];total:number;source:string};
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
  const [editing,setEditing]=useState<{row:number;column:number;cell:Cell}>();
  const [value,setValue]=useState(''),[color,setColor]=useState(''),[saving,setSaving]=useState(false);
  const dialog=useRef<HTMLDialogElement>(null);
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
    {error&&!editing&&<p className="alert" role="alert">{error}</p>}
    {!catalog?.snapshot?<div className="empty-state">{loading?'문서를 불러오는 중…':'기존 저장 폴더에 해당 문서가 없습니다.'}</div>:<>
      <div className="table-scroll document-table" aria-busy={loading}><table><thead><tr><th>행</th>{catalog.headers.map((h,i)=><th key={i}>{h}</th>)}</tr></thead><tbody>{rows.map((row,index)=><tr key={row.id}><td>{offset+index+1}</td>{row.cells.map((cell,column)=><td key={column}><button className="document-cell" style={{background:cell.color||undefined,color:ink(cell.color)}} disabled={!cell.editable||loading} onClick={()=>{setEditing({row:row.id,column,cell});setValue(cell.value);setColor(cell.color);setError('');}}>{cell.value||'—'}</button></td>)}</tr>)}</tbody></table></div>
      <div className="pagination"><span>{catalog.total?`${offset+1}–${Math.min(offset+100,catalog.total)} / ${catalog.total}행`:'0행'}</span><div><button disabled={loading||offset===0} onClick={()=>setOffset(n=>Math.max(0,n-100))}>이전</button><button disabled={loading||offset+100>=catalog.total} onClick={()=>setOffset(n=>n+100)}>다음</button></div></div>
    </>}
    <dialog className="edit-dialog" ref={dialog} onCancel={e=>{if(saving)e.preventDefault();else setEditing(undefined);}}><h2>셀 편집 · {editing&&catalog?.headers[editing.column]}</h2><label className="field">내용<textarea rows={5} maxLength={4000} value={value} onChange={e=>setValue(e.target.value)} disabled={saving}/></label><label className="field">배경 색상<input type="color" value={color||'#ffffff'} onChange={e=>setColor(e.target.value)} disabled={saving}/></label><button disabled={saving} onClick={()=>setColor('')}>색상 제거</button>{error&&<p role="alert" className="dialog-error">{error}</p>}<div className="dialog-actions"><button disabled={saving} onClick={()=>setEditing(undefined)}>취소</button><button className="primary" disabled={saving} onClick={save}>{saving?'저장 중…':'저장'}</button></div></dialog>
  </section>;
}
