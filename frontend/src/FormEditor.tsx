import {useEffect,useMemo,useRef,useState} from 'react';
import {desktop} from './desktop';
import {fail} from './ui';

export type EditorRow={id:number;use:boolean;variant:string;zone:string;alg:string;orig:string;name:string;transform:string;raw:string;display:string};
type Zone={zone:string;total:number;used:number};
type Page={rows:EditorRow[];total:number;used:number;zones:Zone[]};
const TRANSFORMS=['RAW','LINEAR','AREA'];
// Alg tints: every row of the same Alg in a Zone shares one colour (first-seen order).
const ALG_TINTS=['#eef4ff','#effaf1','#fff6e6','#f6efff','#e9f8f8','#fdeef0'];
const ALG_BARS=['#5b8def','#43a35a','#e0a03a','#9a6ad8','#3aa6a6','#d9607a'];
const ZONE_LIMIT=3000;

/**
 * 양식 편집 표 (tkinter 편집기와 같은 역할). Zone 하나씩 보여 주고, 같은 Alg 는 같은 색.
 * 키보드: ↑/↓ 행 이동 · Enter/Space 사용 체크 · F2 이름 편집 · Ctrl+←/→ 이전/다음 Zone ·
 * PageUp/PageDown · Home/End.
 */
export function FormEditor({version,pageMethod,editMethod,replyKey,variants,onUsed}:{
  version:string;pageMethod:string;editMethod:string;replyKey:'form'|'cmrun'|'cmwatch';variants?:string[];onUsed?:(n:number)=>void}){
  const [variant,setVariant]=useState(''),[query,setQuery]=useState(''),[filter,setFilter]=useState(''),[usedOnly,setUsedOnly]=useState(false);
  const [zones,setZones]=useState<Zone[]>([]),[zone,setZone]=useState<string>();
  const [rows,setRows]=useState<EditorRow[]>([]),[loading,setLoading]=useState(false);
  const [cursor,setCursor]=useState(0),[names,setNames]=useState<Record<number,string>>({});
  const box=useRef<HTMLDivElement>(null),seq=useRef(0);
  useEffect(()=>{const t=setTimeout(()=>setFilter(query),200);return()=>clearTimeout(t);},[query]);
  useEffect(()=>{setZone(undefined);},[version]);

  async function load(target:string|undefined){
    const my=++seq.current;setLoading(true);
    try{
      const base={snapshot:version,variant,query:filter,used_only:usedOnly,offset:0};
      let page=(await desktop.request(pageMethod,{...base,limit:100}).promise)[replyKey] as Page;
      const list=page.zones||[];
      const pick=target!==undefined&&list.some(z=>z.zone===target)?target:list[0]?.zone;
      if(pick!==undefined)page=(await desktop.request(pageMethod,{...base,limit:ZONE_LIMIT,zone:pick}).promise)[replyKey] as Page;
      if(my!==seq.current)return;
      setZones(list);setZone(pick);setRows(pick!==undefined?page.rows:[]);setNames({});
      setCursor(c=>Math.min(target===pick?c:0,Math.max(0,(page.rows||[]).length-1)));
      onUsed?.(page.used);
    }catch(e){if(my===seq.current)fail(e);}
    finally{if(my===seq.current)setLoading(false);}
  }
  useEffect(()=>{void load(zone);},[version,variant,filter,usedOnly]);  // eslint-disable-line react-hooks/exhaustive-deps
  const goZone=(z:string)=>{setCursor(0);void load(z);};

  const algIndex=useMemo(()=>{const m=new Map<string,number>();rows.forEach(r=>{if(!m.has(r.alg))m.set(r.alg,m.size);});return m;},[rows]);

  async function edit(row:EditorRow,kind:'use'|'name'|'transform',value:boolean|string){
    const before=rows.find(r=>r.id===row.id);if(!before)return;
    const patch=kind==='use'?{use:value as boolean}:kind==='name'?{name:value as string}:{transform:value as string};
    setRows(rs=>rs.map(r=>r.id===row.id?{...r,...patch}:r));                     // optimistic
    if(kind==='use')setZones(zs=>zs.map(z=>z.zone===row.zone?{...z,used:z.used+(value?1:-1)}:z));
    try{const r=(await desktop.request(editMethod,{snapshot:version,row:row.id,kind,value}).promise)[replyKey] as {used:number};onUsed?.(r.used);}
    catch(e){
      setRows(rs=>rs.map(r=>r.id===row.id?before:r));
      if(kind==='use')setZones(zs=>zs.map(z=>z.zone===row.zone?{...z,used:z.used+(value?-1:1)}:z));
      fail(e);
    }
  }
  function moveTo(i:number){
    const n=Math.max(0,Math.min(rows.length-1,i));setCursor(n);
    box.current?.querySelector<HTMLElement>(`[data-row="${n}"]`)?.scrollIntoView({block:'nearest'});
  }
  function onKey(e:React.KeyboardEvent){
    const el=e.target as HTMLElement;
    const inField=el.tagName==='INPUT'&&(el as HTMLInputElement).type!=='checkbox'||el.tagName==='SELECT';
    if(inField)return;                                              // typing in a name / choosing a transform
    const zi=zones.findIndex(z=>z.zone===zone);
    if((e.ctrlKey||e.metaKey)&&(e.key==='ArrowRight'||e.key==='ArrowLeft')){
      const next=zones[zi+(e.key==='ArrowRight'?1:-1)];if(next){e.preventDefault();goZone(next.zone);}return;
    }
    const step:{[k:string]:number}={ArrowDown:1,ArrowUp:-1,PageDown:15,PageUp:-15};
    if(e.key in step){e.preventDefault();moveTo(cursor+step[e.key]);return;}
    if(e.key==='Home'){e.preventDefault();moveTo(0);return;}
    if(e.key==='End'){e.preventDefault();moveTo(rows.length-1);return;}
    const row=rows[cursor];if(!row)return;
    if(e.key==='Enter'||e.key===' '){e.preventDefault();void edit(row,'use',!row.use);return;}
    if(e.key==='F2'){e.preventDefault();box.current?.querySelector<HTMLInputElement>(`[data-row="${cursor}"] input[data-name]`)?.focus();}
  }
  const cancelName=useRef(false);
  function nameBlur(row:EditorRow){
    const v=names[row.id];
    if(!cancelName.current&&v!==undefined&&v.trim()!==row.name)void edit(row,'name',v.trim());
    cancelName.current=false;
    setNames(n=>{const c={...n};delete c[row.id];return c;});
  }
  const multi=(variants||[]).length>1;
  const current=zones.find(z=>z.zone===zone);
  return <div className="form-editor">
    <div className="form-filter" style={{marginTop:8}}>
      {multi&&<label className="field">변형<select value={variant} onChange={e=>setVariant(e.target.value)}>
        <option value="">전체 변형</option>{variants!.map(v=><option key={v} value={v}>{v||'(기본)'}</option>)}</select></label>}
      <label className="field">검색<input value={query} maxLength={256} placeholder="항목·이름·Zone·Alg" onChange={e=>setQuery(e.target.value)}/></label>
      <label className="field checkbox"><input type="checkbox" checked={usedOnly} onChange={e=>setUsedOnly(e.target.checked)}/>사용 항목만</label>
    </div>
    <div className="zone-tabs" role="tablist" aria-label="Zone">{zones.map(z=>
      <button key={z.zone} role="tab" aria-selected={z.zone===zone} className={z.zone===zone?'active':''} onClick={()=>goZone(z.zone)}>
        {z.zone||'(Zone 없음)'} <small>{z.used}/{z.total}</small></button>)}</div>
    <p className="hint">키보드: ↑/↓ 행 이동 · <b>Enter</b>(또는 Space) 사용 체크 · F2 이름 편집 · Ctrl+←/→ 이전/다음 Zone. 같은 Alg 는 같은 색으로 묶었습니다.</p>
    <div className="table-scroll editor-grid" ref={box} tabIndex={0} onKeyDown={onKey} aria-busy={loading}
      aria-label={`양식 편집 — ${current?.zone||''} Zone`} aria-activedescendant={rows[cursor]?`row-${rows[cursor].id}`:undefined}>
      <table><thead><tr><th>사용</th>{multi&&<th>변형</th>}<th>Alg</th><th>원본 항목</th><th>장비 화면 이름</th><th>변환</th><th>값</th></tr></thead>
        <tbody>{rows.map((row,i)=>{const k=(algIndex.get(row.alg)||0)%ALG_TINTS.length;
          return <tr key={row.id} id={`row-${row.id}`} data-row={i} aria-selected={i===cursor}
            className={(row.use?'':'muted ')+(i===cursor?'cursor-row':'')} style={{background:ALG_TINTS[k]}} onMouseDown={()=>setCursor(i)}>
          <td><input type="checkbox" tabIndex={-1} checked={row.use} aria-label={`${row.orig} 사용`} onChange={e=>void edit(row,'use',e.target.checked)}/></td>
          {multi&&<td>{row.variant||'(기본)'}</td>}
          <td style={{borderLeft:`4px solid ${ALG_BARS[k]}`}}>{row.alg}</td><td>{row.orig}</td>
          <td><input data-name tabIndex={-1} value={names[row.id]??row.name} maxLength={200} aria-label={`${row.orig} 표시 이름`}
            onFocus={()=>setCursor(i)} onChange={e=>setNames(n=>({...n,[row.id]:e.target.value}))}
            onBlur={()=>nameBlur(row)}
            onKeyDown={e=>{if(e.key==='Enter'||e.key==='Escape'){e.preventDefault();cancelName.current=e.key==='Escape';box.current?.focus();}}}/></td>
          <td><select tabIndex={-1} value={row.transform} aria-label={`${row.orig} 변환`} onChange={e=>void edit(row,'transform',e.target.value)}>
            {TRANSFORMS.map(t=><option key={t} value={t}>{t}</option>)}</select></td>
          <td>{row.display||row.raw}</td></tr>;})}</tbody></table>
      {(loading||!rows.length)&&<p className="table-empty">{loading?'불러오는 중…':'표시할 항목이 없습니다.'}</p>}
    </div>
    <p className="hint">{current?`${current.zone||'(Zone 없음)'} · ${rows.length}개 항목 · 사용 ${current.used}`:''}{zones.length>1?` · Zone ${zones.findIndex(z=>z.zone===zone)+1}/${zones.length}`:''}</p>
  </div>;
}
