import {useMemo,useState} from 'react';
import {num,type View,type AggGroup} from './batchData';

/* 찾기 · 취합 › Lot별 Yield (이슈 #24) — 취합한 Lot마다 Yield · 스캔된 Defect 수(Faults) · Good / Reject Die.
   Lot · 레시피(Job · Recipe(s))마다 한 줄: 같은 Lot이라도 PI → RDL처럼 레시피가 다르면 따로(엔진 aggregate 가 Job 별로 나눔).
   여러 번 스캔한 wafer는 취합 결과와 같은 선택(최신 스캔 — Pass가 있으면 가장 나중 Pass) 하나만 더한다.
   숫자는 Pass wafer만(취합 결과 표와 같은 기준). Lot을 체크하면 아래에 선택 Lot 합계 · 평균. */
type Row={gi:number;lot:string;li:number;r:string;machines:string;wafers:number;pass:number;sc:number;bad:number;good:number;fl:number;flN:number;yld:number|null};
const pct=(x:number|null)=>x==null?'—':num(x,2)+'%';
const avg=(xs:number[])=>xs.length?xs.reduce((a,b)=>a+b,0)/xs.length:null;

export function YieldTab({v,groups,choice,openLot}:{v:View;groups:AggGroup[];choice:Record<string,number>;openLot:(li:number)=>void}){
  const rows=useMemo<Row[]>(()=>groups.map((g,gi)=>{
    const t={pass:0,sc:0,bad:0,good:0,fl:0,flN:0};
    g.keys.forEach(k=>{const x=g.w[k].cells[choice[gi+'|'+k]??g.w[k].rec];if(!x||!x.ok)return;t.pass++;
      if(x.sc!=null){t.sc+=x.sc;t.bad+=x.bad||0;t.good+=x.good||0;}if(x.fl!=null){t.fl+=x.fl;t.flN++;}});
    return {gi,lot:v.lots[g.li].label,li:g.li,r:g.r,machines:[...new Set(g.att.map(x=>v.R[x].m))].join(', '),wafers:g.keys.length,...t,yld:t.sc?t.good/t.sc*100:null};
  }),[groups,choice,v]);
  const recipes=useMemo(()=>[...new Set(rows.map(x=>x.r))].sort(),[rows]);
  const [rsel,setRsel]=useState<string[]>([]),[q,setQ]=useState(''),[sel,setSel]=useState<Record<number,1>>({});
  const words=q.trim().toLowerCase().split(/\s+/).filter(Boolean);
  const shown=rows.filter(x=>(!rsel.length||rsel.includes(x.r))&&words.every(w=>(x.lot+' '+x.r+' '+x.machines).toLowerCase().includes(w)));
  const picked=shown.filter(x=>sel[x.gi]),all=!!shown.length&&shown.every(x=>sel[x.gi]);
  const flip=(r:string)=>setRsel(o=>o.includes(r)?o.filter(x=>x!==r):[...o,r]);
  const sum=picked.reduce((a,x)=>({wafers:a.wafers+x.wafers,pass:a.pass+x.pass,sc:a.sc+x.sc,bad:a.bad+x.bad,good:a.good+x.good,fl:a.fl+x.fl}),{wafers:0,pass:0,sc:0,bad:0,good:0,fl:0});
  const mean=(f:(x:Row)=>number|null)=>avg(picked.map(f).filter((n):n is number=>n!=null));
  return <div aria-label="Lot별 Yield">
    <details className="logic"><summary>로직 · Lot별 Yield</summary><ol>
      <li>한 줄 = <b>Lot · 레시피</b>(상위 레시피 Job · Recipe(s)). 같은 Lot 이름이라도 레시피가 다르면(PI · RDL을 이어서 스캔) 따로 봅니다.</li>
      <li>같은 wafer를 여러 번 스캔했으면 <b>하나로 합칩니다</b> — 취합 결과와 같은 선택(최신 스캔: Pass가 있으면 가장 나중 Pass).</li>
      <li>숫자는 그 선택이 Pass인 wafer만 더합니다. <b>Yield</b> = Good Die ÷ Scanned Die. <b>Defect</b> = Batch Report의 Faults 합(값이 없는 wafer는 빼고 셈). <b>Reject Die</b> = Bad Die.</li>
      <li>Lot을 체크하면 아래에 <b>선택 합계</b>(Yield = 합계 Good ÷ 합계 Scanned)와 <b>선택 Lot 평균</b>(Lot마다 값을 똑같은 무게로 평균)이 나옵니다.</li></ol></details>
    <div className="jobfilter" role="group" aria-label="레시피 필터">
      <div className="jf-head"><b>레시피</b><span className="jf-state">{rsel.length?`${rsel.length}개 고름 / ${recipes.length}개`:`전체 ${recipes.length}개 (고르지 않으면 전체)`}</span><span className="grow"/>
        <input type="search" placeholder="Lot · 레시피 · 호기 검색" aria-label="Yield 키워드 검색" value={q} onChange={e=>setQ(e.target.value)}/>
        <button type="button" className="linklike" disabled={!rsel.length} onClick={()=>setRsel([])}>전체 보기</button></div>
      <div className="jf-chips">{recipes.map(r=>{const on=rsel.includes(r);return <button key={r} type="button" className={'jf-chip'+(on?' on':'')} aria-pressed={on} title={r} onClick={()=>flip(r)}>
        <i aria-hidden="true">{on?'✓':''}</i><span>{r}</span><small>Lot {rows.filter(x=>x.r===r).length}</small></button>;})}</div></div>
    <div className="table-scroll" style={{maxHeight:'none'}}><table className="t-compact" aria-label="Lot별 Yield 표"><thead><tr>
      <th><input type="checkbox" aria-label="Yield 전체 선택" checked={all} disabled={!shown.length}
        onChange={e=>setSel(o=>{const n={...o};shown.forEach(x=>{if(e.target.checked)n[x.gi]=1;else delete n[x.gi];});return n;})}/></th>
      <th>Lot</th><th>레시피</th><th>호기</th><th className="num">wafer</th><th className="num">Pass</th><th className="num">Yield</th>
      <th className="num">Defect (Faults)</th><th className="num">Scanned Die</th><th className="num">Good Die</th><th className="num">Reject Die</th></tr></thead>
      <tbody>{!shown.length?<tr><td colSpan={11} className="hint">조건에 맞는 Lot이 없습니다.</td></tr>
        :shown.map(x=><tr key={x.gi}><td><input type="checkbox" aria-label={`${x.lot} ${x.r} 선택`} checked={!!sel[x.gi]}
            onChange={e=>setSel(o=>{const n={...o};if(e.target.checked)n[x.gi]=1;else delete n[x.gi];return n;})}/></td>
          <td><button type="button" className="linklike" onClick={()=>openLot(x.li)}>{x.lot}</button></td><td>{x.r}</td><td>{x.machines}</td>
          <td className="num">{x.wafers}</td><td className="num">{x.pass}</td><td className="num"><b>{pct(x.yld)}</b></td>
          <td className="num">{x.flN?num(x.fl):'—'}</td><td className="num">{num(x.sc)}</td><td className="num">{num(x.good)}</td><td className="num">{num(x.bad)}</td></tr>)}</tbody>
      {picked.length>0&&<tfoot>
        <tr><th/><th colSpan={3}>선택 합계 · Lot {picked.length}개</th><td className="num">{sum.wafers}</td><td className="num">{sum.pass}</td>
          <td className="num"><b>{pct(sum.sc?sum.good/sum.sc*100:null)}</b></td><td className="num">{num(sum.fl)}</td><td className="num">{num(sum.sc)}</td><td className="num">{num(sum.good)}</td><td className="num">{num(sum.bad)}</td></tr>
        <tr><th/><th colSpan={3}>선택 Lot 평균</th><td className="num">{num(mean(x=>x.wafers),1)}</td><td className="num">{num(mean(x=>x.pass),1)}</td>
          <td className="num"><b>{pct(mean(x=>x.yld))}</b></td><td className="num">{num(mean(x=>x.flN?x.fl:null),1)}</td><td className="num">{num(mean(x=>x.sc),1)}</td>
          <td className="num">{num(mean(x=>x.good),1)}</td><td className="num">{num(mean(x=>x.bad),1)}</td></tr></tfoot>}</table></div>
    <p className="hint">{picked.length?`선택 ${picked.length}개 / 보이는 ${shown.length}개`:'Lot을 체크하면(맨 위 칸 = 보이는 Lot 전체 선택) 선택 Lot의 합계와 평균이 표 아래에 나옵니다.'}</p>
  </div>;
}
