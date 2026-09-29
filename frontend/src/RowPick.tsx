import type {ReactNode} from 'react';

export type PickRow={id:string;cells:ReactNode[];disabled?:boolean;title?:string};

/**
 * 행 목록 선택표: 맨 위 '전체 선택' 체크박스 + 항목마다 한 행(체크박스 + 칸들).
 * 레시피·호기처럼 여러 개를 고르는 곳에서 같은 모양으로 쓴다.
 */
export function RowPick({label,columns,rows,value,onChange,empty,single=false}:{
  label:string;columns:string[];rows:PickRow[];value:string[];onChange:(next:string[])=>void;empty?:ReactNode;single?:boolean}){
  const enabled=rows.filter(r=>!r.disabled).map(r=>r.id);
  const all=enabled.length>0&&enabled.every(id=>value.includes(id));
  const some=!all&&enabled.some(id=>value.includes(id));
  if(!rows.length)return <>{empty}</>;
  const toggle=(id:string,on:boolean)=>onChange(single?(on?[id]:[]):on?[...value.filter(v=>v!==id),id]:value.filter(v=>v!==id));
  return <div role="group" aria-label={label}><div className="row-pick">
    <table className="tbl"><thead><tr>
      <th className="row-pick-check">{single?null:<label className="row-pick-all"><input type="checkbox" aria-label={`${label} 전체 선택`} checked={all}
        ref={el=>{if(el)el.indeterminate=some;}} onChange={e=>onChange(e.target.checked?enabled:[])}/>전체 선택</label>}</th>
      {columns.map(c=><th key={c}>{c}</th>)}</tr></thead>
      <tbody>{rows.map(r=>{const on=value.includes(r.id);
        return <tr key={r.id} className={(on?'row-on ':'')+(r.disabled?'muted':'')} title={r.title}
          onClick={e=>{if(r.disabled||(e.target as HTMLElement).tagName==='INPUT')return;toggle(r.id,!on);}}>
          <td className="row-pick-check"><input type={single?'radio':'checkbox'} disabled={r.disabled} checked={on}
            aria-label={`${r.id} 선택`} onChange={e=>toggle(r.id,e.target.checked)}/></td>
          {r.cells.map((c,i)=><td key={i}>{c}</td>)}</tr>;})}</tbody></table></div>
    <p className="hint">{value.length}개 선택{enabled.length!==rows.length?` · 고를 수 없는 항목 ${rows.length-enabled.length}개`:''}</p>
  </div>;
}
