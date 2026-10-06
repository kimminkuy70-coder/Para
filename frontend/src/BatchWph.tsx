import {useEffect,useMemo,useRef,useState} from 'react';
import {ColChart,Scatter,Seg,type TipX,type ColItem} from './BatchCharts';
import {Q} from './BatchHelp';
import {dur,hrs,num,sumU,lossOf,wphNormal,wphActual,unitSec,avgScan,pctOf,C_OK,C_WAIT,C_ERR,C_STOP,C_DEFECT,C_IDLE,STOPK,machColors,
  addDays,bucket,shortKey,weekRange,periodName,type View,type U,type Agg,type Unit} from './batchData';

/* WPH · 생산능력 탭 — 정상 WPH(막힘없을 때 속도) · 실제 WPH(유휴만 뺀 시간 기준) · 하루 생산능력(24 × 실제 WPH).
   화면은 숫자 4개 + [레시피 비교 | 호기 × 레시피 표 | 기간별 추이(일 · 주 · 월, 이슈 #9)], 자세한 것은 레시피 상세 창, 계산식은 ? 버튼(사용자 확정 2026-10-05).
   레시피 이름 = '상위 레시피(Job) · 하위 레시피(Recipe(s))'. 비교 · 표는 상위 레시피 묶음 머리 + 들여 쓴 하위 레시피 줄로 구분하고,
   상위 레시피는 필터(여러 개 고르기)로 거른다(이슈 #10). */
const jobOf=(r:string)=>r.split(' · ')[0];
const stepOf=(r:string)=>r.slice(jobOf(r).length+3);
const f1=(x:number|null)=>num(x,1);
const pc=(x:number|null)=>x==null?'—':num(x,1)+'%';
const drop=(n:number|null,a:number|null)=>n&&a!=null?(1-a/n)*100:null;
const cap=(a:Agg)=>{const w=wphActual(a);return w==null?null:w*24;};
type Cell={r:string;m:string;a:Agg};
type Range={from:string;to:string};
/** 호기별로 따로 24 × 실제 WPH 를 구해 더한 하루 생산능력(호기 수만큼 늘어남 — 레시피 합계와 같은 꼴). */
const capSum=(us:U[])=>{const o:Record<string,U[]>={};us.forEach(u=>{(o[u.m]||=[]).push(u);});
  return Object.values(o).reduce((s,x)=>s+(cap(sumU(x))||0),0);};

export function WphTab({v,ids,range,openLot,showRaw}:{v:View;ids:string[];range:{from:string;to:string};openLot:(li:number)=>void;showRaw:(g:number)=>void}){
  const [recipe,setRecipe]=useState(''),[mach,setMach]=useState(''),[tab,setTab]=useState<'cmp'|'tbl'|'per'>('cmp'),[win,setWin]=useState<{r:string;m:string;range?:Range}|null>(null);
  const [unit,setUnit]=useState<Unit>('w'),[jobSel,setJobSel]=useState<string[]>([]);
  const rows=useMemo(()=>v.U.filter(u=>ids.includes(u.m)&&u.d>=range.from&&u.d<=range.to&&(u.n||u.p)),[v,ids,range.from,range.to]);
  const recipes=useMemo(()=>[...new Set(rows.filter(u=>u.n).map(u=>u.r))].sort(),[rows]);
  const jobs=useMemo(()=>[...new Set(recipes.map(jobOf))],[recipes]);
  const js=jobSel.filter(j=>jobs.includes(j)),inJob=(r:string)=>!js.length||js.includes(jobOf(r));   // 상위 레시피 필터(비면 전체)
  const r0=recipes.includes(recipe)&&inJob(recipe)?recipe:'';
  const shown=js.length?recipes.filter(inJob):r0?recipes.filter(r=>jobOf(r)===jobOf(r0)):recipes;      // 필터가 없으면 하위 레시피를 고를 때 같은 Job 끼리 비교
  const cells=useMemo(()=>{const o:Record<string,U[]>={};rows.forEach(u=>{if(mach&&u.m!==mach)return;(o[u.r+'||'+u.m]||=[]).push(u);});
    return Object.entries(o).map(([k,us])=>({r:k.split('||')[0],m:k.split('||')[1],a:sumU(us)}) as Cell).filter(c=>c.a.n>0);},[rows,mach]);
  const sel=useMemo(()=>rows.filter(u=>(r0?u.r===r0:!js.length||js.includes(jobOf(u.r)))&&(!mach||u.m===mach)),[rows,r0,mach,js.join('\n')]),A=sumU(sel);
  const wn=wphNormal(A),wa=wphActual(A),total=r0?cells.filter(c=>c.r===r0).reduce((s,c)=>s+(cap(c.a)||0),0):mach?cap(A):null;
  const col=useMemo(()=>machColors([...ids,...rows.map(u=>u.m)]),[ids,rows]);
  const nMach=r0?cells.filter(c=>c.r===r0&&cap(c.a)).length:0;
  const K:[string,string,string,string,string,string[]][]=[
    ['wph.normal','정상 WPH',f1(wn),'',`정상 25매 Batch Report ${num(A.w25/25)}장`,wn==null?['정상 25매 Batch Report가 없습니다.']:[`${num(A.w25)}장 × 3,600 ÷ ${num(A.s25)}초(${hrs(A.s25)}시간) = ${f1(wn)}`]],
    ['wph.actual','실제 WPH',f1(wa),'',`Pass ${num(A.ps)}장 · 유휴만 뺀 시간`,wa==null?[]:[`Pass ${num(A.ps)}장 × 3,600 ÷ (웨이퍼 처리 ${hrs(A.p)}시간 + Error · 중단 및 조치 ${hrs(lossOf(A))}시간) = ${f1(wa)}`]],
    ['wph.drop','처리량 감소',pc(drop(wn,wa)).replace('%',''),'%','1 − 실제 ÷ 정상',wn&&wa!=null?[`1 − ${f1(wa)} ÷ ${f1(wn)} = ${pc(drop(wn,wa))}`]:[]],
    ['wph.capacity',r0?'하루 생산능력 · 레시피 합계':'하루 생산능력',total==null?'—':num(total),total==null?'':'장/일',r0?`${nMach}대 합계`:mach?`${mach} · 레시피 통합`:'레시피 또는 호기를 고르세요',
      total==null?[]:r0?cells.filter(c=>c.r===r0&&cap(c.a)).map(c=>`${c.m}: 24 × ${f1(wphActual(c.a))} = ${num(cap(c.a))}장`).concat([`합계 ${num(total)}장/일`]):[`24 × ${f1(wa)} = ${num(total)}장/일`]]];
  return <section className="panel tabpanel" aria-label="WPH · 생산능력">
    <div className="section-heading"><div><span className="step">WPH · 생산능력</span><h2>레시피가 한 시간에 몇 장, 하루에 몇 장을 처리하나</h2></div>
      <div className="filters" style={{margin:0}}><label className="field" style={{minWidth:300}}>하위 레시피(Recipe(s))<select value={r0} onChange={e=>setRecipe(e.target.value)}><option value="">{js.length?`고른 상위 레시피 ${js.length}개 전체`:'전체 레시피'}</option>
          {jobs.filter(j=>!js.length||js.includes(j)).map(j=><optgroup key={j} label={'상위 · '+j}>{recipes.filter(r=>jobOf(r)===j).map(r=><option key={r} value={r}>{stepOf(r)}</option>)}</optgroup>)}</select></label>
        <label className="field">호기<select value={mach} onChange={e=>setMach(e.target.value)}><option value="">전체 호기</option>{ids.map(id=><option key={id}>{id}</option>)}</select></label></div></div>
    <JobFilter jobs={jobs} recipes={recipes} sel={js} onChange={setJobSel}/>
    <section className="kpis k4">{K.map(([id,l,val,u,s,calc],i)=><article key={id} className={'kq k'+i}><span>{l}<Q id={id} calc={calc}/></span><strong>{val}<small>{u}</small></strong><p>{s}</p></article>)}</section>
    <div className="viewbar"><Seg label="보기" value={tab} items={[['cmp','레시피 비교'],['tbl','호기 × 레시피 표'],['per','기간별 추이']]} onChange={setTab}/>
      {tab==='per'&&<Seg label="기간 단위" value={unit} items={[['d','일'],['w','주'],['m','월']]} onChange={setUnit}/>}<span className="grow"/>
      <span className="hint">{tab==='per'?(r0?`${stepOf(r0)} · ${mach||'전체 호기'}`:`${js.length?`상위 레시피 ${js.length}개`:'전체 레시피'} · ${mach?mach+' · 레시피 통합':'전체 호기'}${js.length?'':' (레시피를 고르면 그 레시피만)'}`)
        :js.length?`상위 레시피 ${js.length}개의 하위 레시피끼리 비교`:r0?`${jobOf(r0)}의 하위 레시피끼리 비교`:'상위 레시피를 고르거나 하위 레시피를 고르면 같은 상위 레시피끼리 비교합니다'}</span></div>
    {tab==='cmp'?<Compare cells={cells} recipes={shown} sel={r0} col={col} onOpen={(r,m)=>setWin({r,m})}/>
      :tab==='tbl'?<Table cells={cells} recipes={shown} col={col} onOpen={(r,m)=>setWin({r,m})}/>
      :<Periods rows={sel} unit={unit} range={range} recipe={r0} onOpen={r0?pr=>setWin({r:r0,m:mach,range:pr}):undefined}/>}
    {win&&<RecipeWindow v={v} r={win.r} m={win.m} ids={ids} range={win.range||range} openLot={openLot} showRaw={showRaw} onClose={()=>setWin(null)}/>}
  </section>;
}

/** 상위 레시피(Job) 필터 — 여러 개를 골라 레시피 비교 · 표 · 숫자 4개 · 기간별 추이를 그 상위 레시피로 거른다(이슈 #10). 비면 전체. */
function JobFilter({jobs,recipes,sel,onChange}:{jobs:string[];recipes:string[];sel:string[];onChange:(x:string[])=>void}){
  const [q,setQ]=useState('');
  if(!jobs.length)return null;
  const ql=q.trim().toLowerCase(),list=jobs.filter(j=>!ql||j.toLowerCase().includes(ql)||sel.includes(j));
  const nSub=(j:string)=>recipes.filter(r=>jobOf(r)===j).length;
  const flip=(j:string)=>onChange(sel.includes(j)?sel.filter(x=>x!==j):[...sel,j]);
  return <div className="jobfilter" role="group" aria-label="상위 레시피 필터">
    <div className="jf-head"><span className="lv up">상위 레시피</span><b>필터</b><Q id="wph.recipe"/>
      <span className="jf-state">{sel.length?`${sel.length}개 고름 / ${jobs.length}개`:`전체 ${jobs.length}개 (고르지 않으면 전체)`}</span><span className="grow"/>
      {jobs.length>8&&<input type="search" placeholder="상위 레시피 찾기" aria-label="상위 레시피 찾기" value={q} onChange={e=>setQ(e.target.value)}/>}
      {ql&&<button type="button" className="linklike" onClick={()=>onChange([...new Set([...sel,...list])])}>찾은 것 모두 고르기</button>}
      <button type="button" className="linklike" disabled={!sel.length} onClick={()=>onChange([])}>전체 보기</button></div>
    <div className="jf-chips">{list.map(j=>{const on=sel.includes(j);return <button key={j} type="button" className={'jf-chip'+(on?' on':'')} aria-pressed={on} title={j} onClick={()=>flip(j)}>
      <i aria-hidden="true">{on?'✓':''}</i><span>{j}</span><small>하위 {nSub(j)}</small></button>;})}
      {!list.length&&<span className="hint">찾는 상위 레시피가 없습니다.</span>}</div></div>;
}

/** 레시피 비교 — 레시피마다 하루 생산능력을 호기별로 쌓은 막대(가능 호기가 적어도 합계가 큰지 한눈에).
    호기 색은 레시피와 무관하게 고정(col, 이슈 #7) — 아래 범례로 확인.
    같은 Job 의 하위 레시피끼리 바꾸면 보이는 레시피 묶음이 같아 막대가 그대로라, 고른 레시피는 강조하고
    WPH · 정상 WPH 가 없는 레시피도 '없음' 행으로 남긴다(사용자 요청 2026-10-05 — 바뀐 건지 헷갈리지 않게).
    상위 레시피(Job)마다 묶음 상자 + 머리 줄(하위 레시피 수 · 호기 · Batch Report), 하위 레시피 줄은 들여 쓴다(이슈 #10).
    상위 레시피끼리는 die 수가 달라 생산능력을 더하지 않는다(머리 줄엔 막대 없음). */
function Compare({cells,recipes,sel,col,onOpen}:{cells:Cell[];recipes:string[];sel:string;col:Record<string,string>;onOpen:(r:string,m:string)=>void}){
  const rows=recipes.map(r=>{const all=cells.filter(c=>c.r===r),cs=all.filter(c=>cap(c.a)).sort((a,b)=>(cap(b.a)||0)-(cap(a.a)||0));
    return {r,cs,sum:cs.reduce((s,c)=>s+(cap(c.a)||0),0),wn:wphNormal(all.reduce((acc,c)=>addAgg(acc,c.a),sumU([])))};});
  const mx=Math.max(1,...rows.map(x=>x.sum)),cur=rows.find(x=>x.r===sel);
  if(!rows.length)return <div className="chartcard"><p className="hint">조사 범위에 WPH 자료가 없습니다.</p></div>;
  return <div className="chartcard"><div className="ch"><h3>레시피별 하루 생산능력 <small>막대 한 칸 = 호기 1대 (24 × 실제 WPH)</small></h3><Q id="wph.capacity"/><span className="grow"/>
      <span className="hint">마우스 = 호기별 값 · 누르면 레시피 상세 창</span></div>
    {cur&&<p className={'capsel'+(cur.wn==null?' none':'')}>고른 레시피: <b>{stepOf(cur.r)}</b> (상위 레시피 {jobOf(cur.r)}) — {cur.wn==null?'정상 WPH 없음 (정상 25매 Batch Report가 없습니다)':`정상 WPH ${f1(cur.wn)}`}
      {!cur.cs.length&&' · 실제 WPH 자료 없음'}</p>}
    <div className="caprows">{[...new Set(rows.map(x=>jobOf(x.r)))].map(j=>{const sub=rows.filter(x=>jobOf(x.r)===j),js=cells.filter(c=>jobOf(c.r)===j);
      return <div key={j} className={'capgrp'+(sub.some(x=>x.r===sel)?' has':'')} role="group" aria-label={'상위 레시피 '+j}>
      <div className="capjob"><span className="lv up">상위 레시피</span><b title={j}>{j}</b><small>하위 레시피 {sub.length}개 · 호기 {new Set(js.map(c=>c.m)).size}대 · Batch Report {num(js.reduce((s,c)=>s+c.a.n,0))}개</small></div>
      {sub.map(x=><div key={x.r} className={'caprow sub'+(x.r===sel?' sel':'')}>
      <button type="button" className="linklike cl" title={x.r} onClick={()=>onOpen(x.r,'')}><span className="lv dn">하위</span>{stepOf(x.r)}</button>
      <span className="capbar">{x.cs.map(c=>{const cp=cap(c.a)||0,w=cp/mx*100,tip:TipX={t:`${c.m} · ${stepOf(x.r)}`,rows:[[col[c.m],'하루 생산능력',num(cp),'장'],
          ['transparent','실제 WPH',f1(wphActual(c.a)),''],['transparent','정상 WPH',f1(wphNormal(c.a)),''],['transparent','Batch Report',num(c.a.n),'개']],f:['누르면 이 호기의 레시피 상세 창']};
        return <span key={c.m} style={{width:w.toFixed(2)+'%',background:col[c.m]}} data-tip={`${c.m}\n하루 생산능력 ${num(cp)}장`} data-tipx={JSON.stringify(tip)}
          onClick={()=>onOpen(x.r,c.m)}>{w>6?c.m:''}</span>;})}{!x.cs.length&&<span className="capnone">실제 WPH 자료 없음 (Pass한 Batch Report 없음)</span>}</span>
      <span className="capv">{x.cs.length?<><b>{num(x.sum)}</b>장/일 · {x.cs.length}대</>:'—'}<small className={x.wn==null?'none':''}>{x.wn==null?'정상 WPH 없음':`정상 WPH ${f1(x.wn)}`}</small></span></div>)}</div>;})}</div>
    <div className="keys">{[...new Set(rows.flatMap(x=>x.cs.map(c=>c.m)))].sort().map(m=><span key={m}><i style={{background:col[m]}}>　</i> {m}</span>)}<span>같은 호기 = 같은 색</span>
      <span><span className="lv up">상위 레시피</span> Job</span><span><span className="lv dn">하위</span> Recipe(s)</span></div></div>;
}

const PK=[['wa','실제 WPH','#10b981'],['wn','정상 WPH','#31517c'],['cap','하루 생산능력','#2a9d8f'],['ps','Pass 장수','#7b5ea7']] as const;
type PKey=typeof PK[number][0];
/** 기간별 추이(이슈 #9) — 일 · 주 · 월마다 정상 · 실제 WPH, 하루 생산능력, 실제 Pass 장수(하루 평균).
    rows = 위에서 고른 레시피 · 호기 · 조사 범위로 이미 거른 U 행(숫자 4개와 같은 자료). 식은 숫자 4개와 같다(기간마다 다시 더할 뿐).
    하루 생산능력 = 호기마다 24 × 그 기간 실제 WPH 의 합(레시피를 안 고르면 레시피 통합). 레시피를 고르면 기간을 눌러 그 기간의 레시피 상세 창. */
function Periods({rows,unit,range,recipe,onOpen}:{rows:U[];unit:Unit;range:Range;recipe:string;onOpen?:(r:Range)=>void}){
  const [met,setMet]=useState<PKey>('wa'),[pick,setPick]=useState<string|null>(null);
  const list=useMemo(()=>{const o:Record<string,{days:string[];us:U[]}>={};
    if(range.from&&range.to)for(let d=range.from;d<=range.to;d=addDays(d,1))(o[bucket(d,unit)]||=({days:[],us:[]})).days.push(d);
    rows.forEach(u=>{const k=bucket(u.d,unit);(o[k]||=({days:[u.d],us:[]})).us.push(u);});
    return Object.entries(o).sort((a,b)=>a[0]<b[0]?-1:1).map(([k,x])=>{const a=sumU(x.us),wn=wphNormal(a),wa=wphActual(a);
      return {k,days:x.days,a,wn,wa,cap:x.us.some(u=>u.n)?capSum(x.us):null,machines:new Set(x.us.filter(u=>u.n).map(u=>u.m)).size};});},[rows,unit,range.from,range.to]);
  const val=(x:typeof list[number])=>met==='wa'?x.wa:met==='wn'?x.wn:met==='cap'?x.cap:x.a.ps;
  const [,label,color]=PK.find(p=>p[0]===met)!;
  const fmt=(x:number|null)=>met==='wa'||met==='wn'?f1(x):num(x);
  const U_={d:'일',w:'주',m:'월'}[unit],per=(x:typeof list[number])=>x.days.length?x.a.ps/x.days.length:null;
  const open=(k:string)=>{setPick(p=>p===k?null:k);const x=list.find(y=>y.k===k);if(onOpen&&x&&x.a.n&&x.days.length)onOpen({from:x.days[0],to:x.days[x.days.length-1]});};
  const items:ColItem[]=list.map(x=>{const tip:TipX={t:periodName(x.k,unit),rows:[[PK[0][2],'실제 WPH',f1(x.wa),''],[PK[1][2],'정상 WPH',f1(x.wn),''],
      ['transparent','처리량 감소',pc(drop(x.wn,x.wa)),''],[PK[2][2],'하루 생산능력',x.cap==null?'—':num(x.cap),'장/일'+(x.machines>1?` · ${x.machines}대`:'')],
      [PK[3][2],'Pass 장수',num(x.a.ps),`장 · 하루 평균 ${num(per(x))}`],['transparent','Batch Report',num(x.a.n),'개']],f:onOpen&&x.a.n?['누르면 이 기간의 레시피 상세 창']:undefined};
    return {id:x.k,short:shortKey(x.k,unit),short2:unit==='w'?weekRange(x.k):undefined,v:{y:val(x)||0},tip:tip.t+'\n'+tip.rows.map(r=>`${r[1]} ${r[2]}${r[3]?' '+r[3]:''}`).join('\n'),tipx:tip};});
  const has=list.some(x=>x.a.n);
  return <div className="chartcard"><div className="ch"><h3>기간별 {label} <small>{U_} 단위 · 왼쪽이 오래된 기간</small></h3><Q id={met==='wa'?'wph.actual':met==='wn'?'wph.normal':met==='cap'?'wph.capacity':'wph.period'}/><span className="grow"/>
      <Seg label="그래프 값" value={met} items={PK.map(p=>[p[0],p[1]] as [PKey,string])} onChange={setMet}/></div>
    {has?<><ColChart items={items} keys={[{k:'y',label,c:color}]} h={220} minw={unit==='d'?14:26} maxw={70} sel={pick} label={`기간별 ${label}`} fy={met==='wa'||met==='wn'?(x=>num(x,1)):num} onClick={open}/>
      <div className="table-scroll" style={{maxHeight:420}}><table className="t-compact wphper"><thead><tr><th>기간</th><th className="num">정상 WPH<Q id="wph.normal"/></th><th className="num">실제 WPH<Q id="wph.actual"/></th>
        <th className="num">처리량 감소<Q id="wph.drop"/></th><th className="num">하루 생산능력<Q id="wph.capacity"/></th><th className="num">Pass 장수<Q id="wph.period"/></th><th className="num">하루 평균 Pass</th><th className="num">Batch Report</th></tr></thead>
        <tbody>{[...list].reverse().map(x=><tr key={x.k} className={(onOpen&&x.a.n?'clickable':'')+(pick===x.k?' sel':'')} onClick={()=>open(x.k)}>
          <td>{periodName(x.k,unit)}{unit==='d'?'':<small> · {x.days.length}일</small>}</td><td className="num">{f1(x.wn)}</td><td className="num"><b>{f1(x.wa)}</b></td><td className="num v4">{pc(drop(x.wn,x.wa))}</td>
          <td className="num"><b>{x.cap==null?'—':num(x.cap)}</b>{x.machines>1&&<small> · {x.machines}대</small>}</td><td className="num">{num(x.a.ps)}</td><td className="num">{x.a.n?num(per(x)):'—'}</td><td className="num">{num(x.a.n)}</td></tr>)}</tbody></table></div>
      <p className="hint">{recipe?'기간을 누르면 그 기간의 레시피 상세 창이 열립니다.':'레시피를 고르면 기간을 눌러 그 기간의 레시피 상세 창을 볼 수 있습니다.'} 하루 생산능력 = 호기마다 24 × 그 기간 실제 WPH 의 합{recipe?'':'(레시피 통합)'}, 하루 평균 Pass = Pass 장수 ÷ 기간 일수(조사 범위 안).</p></>
      :<p className="hint">조사 범위에 WPH 자료가 없습니다.</p>}</div>;
}

/** 호기 × 레시피 표 — 상위 레시피 머리 줄 › 하위 레시피 합계 줄 › 호기별 줄(들여 쓰기, 이슈 #10). */
function Table({cells,recipes,col,onOpen}:{cells:Cell[];recipes:string[];col:Record<string,string>;onOpen:(r:string,m:string)=>void}){
  const row=(r:string,m:string,a:Agg,sum:number|null,key:string,total?:boolean)=>{const n=wphNormal(a),w=wphActual(a);
    return <tr key={key} className={'clickable'+(total?' total':'')} onClick={()=>onOpen(r,total?'':m)}>
      <td className={total?'subr':'mrow'}>{total?<><span className="lv dn">하위</span><b>{stepOf(r)}</b></>:''}</td><td>{total?<b>합계 ({m})</b>:<><i className="msw" style={{background:col[m]}}/>{m}</>}</td><td className="num">{unitSec(a)==null?'—':num(unitSec(a),0)+'초'}</td><td className="num">{avgScan(a)==null?'—':num(avgScan(a),0)+'초'}</td>
      <td className="num">{f1(n)}</td><td className="num"><b>{f1(w)}</b></td><td className="num v4">{pc(drop(n,w))}</td><td className="num"><b>{sum==null?'—':num(sum)}</b></td><td className="num">{num(a.n)}</td></tr>;};
  return <div className="chartcard"><div className="table-scroll" style={{maxHeight:560}}><table className="t-compact">
    <thead><tr><th>레시피 (상위 › 하위)</th><th>호기</th><th className="num">1장 처리 시간<Q id="wph.unit"/></th><th className="num">Avg. Scan Time<Q id="wph.avgscan"/></th><th className="num">정상 WPH<Q id="wph.normal"/></th>
      <th className="num">실제 WPH<Q id="wph.actual"/></th><th className="num">처리량 감소<Q id="wph.drop"/></th><th className="num">하루 생산능력<Q id="wph.capacity"/></th><th className="num">Batch Report</th></tr></thead>
    <tbody>{recipes.flatMap((r,i)=>{const cs=cells.filter(c=>c.r===r);if(!cs.length)return [];const newJob=!i||jobOf(recipes[i-1])!==jobOf(r);const all=cs.reduce((acc,c)=>addAgg(acc,c.a),sumU([]));
      const sum=cs.reduce((s,c)=>s+(cap(c.a)||0),0);
      const jc=newJob?cells.filter(c=>jobOf(c.r)===jobOf(r)):[];
      return [...(newJob?[<tr key={r+'h'} className="grouphead job"><td colSpan={9}><span className="lv up">상위 레시피</span><b>{jobOf(r)}</b>
        <small>하위 레시피 {recipes.filter(x=>jobOf(x)===jobOf(r)&&cells.some(c=>c.r===x)).length}개 · 호기 {new Set(jc.map(c=>c.m)).size}대 · Batch Report {num(jc.reduce((s,c)=>s+c.a.n,0))}개</small></td></tr>]:[]),
        row(r,`${cs.length}대`,all,sum,r+'t',true),...cs.map(c=>row(r,c.m,c.a,cap(c.a),r+c.m))];})}
      {!recipes.length&&<tr><td colSpan={9}>조사 범위에 WPH 자료가 없습니다.</td></tr>}</tbody></table></div></div>;
}
function addAgg(a:Agg,b:Agg):Agg{const o={...a,err:{...a.err}};(['p','du','ck','e','sd','so','ps','dn','n','ne','nsd','nso','w25','s25','aw','asum'] as const).forEach(k=>{o[k]=a[k]+b[k];});return o;}

/** 레시피 상세 창 — WPH 분해 · 1장 처리 시간 · Lot별 실제 WPH. m = '' 이면 그 레시피를 돌린 호기 전체. */
function RecipeWindow({v,r,m,ids,range,openLot,showRaw,onClose}:{v:View;r:string;m:string;ids:string[];range:{from:string;to:string};
  openLot:(li:number)=>void;showRaw:(g:number)=>void;onClose:()=>void}){
  const ref=useRef<HTMLDialogElement>(null);
  const [tab,setTab]=useState<'split'|'unit'|'lots'>('split'),[bin,setBin]=useState<string|null>(null);
  useEffect(()=>{const d=ref.current;if(d&&!d.open)d.showModal();},[]);
  const inR=(d:string)=>d>=range.from&&d<=range.to,okM=(x:string)=>m?x===m:ids.includes(x);
  const us=v.U.filter(u=>u.r===r&&okM(u.m)&&inR(u.d)),A=sumU(us);
  const wn=wphNormal(A),wa=wphActual(A),D=A.p+lossOf(A),wp=A.p?A.ps*3600/A.p:null;
  const machines=[...new Set(us.filter(u=>u.n).map(u=>u.m))].sort();
  // 분해: 정상 → (기타 차이) → 처리 WPH → Error · 중단 손실 → 실제
  const steps:[string,number,string,string?][]=[];
  if(wn!=null&&wp!=null)steps.push(['기타 차이 (25매가 아닌 Lot · 느렸던 스캔 · 다시 스캔)',wn-wp,C_IDLE]);
  if(wp!=null&&D>0){steps.push(['Error',wp*A.e/D,C_ERR]);steps.push([STOPK.d,wp*A.sd/D,C_DEFECT,'stop.defect']);steps.push([STOPK.o,wp*A.so/D,C_STOP]);}
  const top=Math.max(wn||0,wp||0,1);
  const errs=Object.entries(A.err).sort((a,b)=>b[1][0]-a[1][0]),emx=errs.length?errs[0][1][0]:1;
  // 1장 처리 시간 — 호기별
  const perM=machines.map(x=>({m:x,a:sumU(us.filter(u=>u.m===x))}));
  const umx=Math.max(1,...perM.map(x=>unitSec(x.a)||0));
  // 정상 25매 Batch Report WPH 분포
  const cl=v.N.filter(x=>x.r===r&&okM(x.m)&&inR(x.d)).map(x=>({x,w:25*3600/x.s,bin:''}));
  let bins:{id:string;lo:number;hi:number;n:number}[]=[];
  if(cl.length){const vs=cl.map(c=>c.w),lo=Math.min(...vs),hi=Math.max(...vs),span=Math.max(hi-lo,1),st=[0.5,1,2,2.5,5,10,20].find(s=>span/s<=14)||20,s0=Math.floor(lo/st)*st,nb=Math.floor((hi-s0)/st)+1;
    bins=Array.from({length:nb},(_,i)=>({id:String(i),lo:s0+i*st,hi:s0+(i+1)*st,n:0}));cl.forEach(c=>{const i=Math.min(nb-1,Math.floor((c.w-s0)/st));bins[i].n++;c.bin=String(i);});}
  const cur=bin!=null&&bins[+bin]?bin:null,list=cl.filter(c=>cur==null||c.bin===cur).sort((a,b)=>v.R[a.x.g].s<v.R[b.x.g].s?1:-1);
  const L=v.L.filter(x=>x.r===r&&okM(x.m)&&inR(x.d));
  const worst=L.filter(x=>x.n>1).map(x=>[x,x.ps*3600/x.s] as const).sort((a,b)=>a[1]-b[1]).slice(0,40);
  const rate=(x:number,n:number)=>n?num(x/n*100,1)+'% ('+num(x)+' / '+num(n)+')':'—';
  return <dialog className="lotwin" ref={ref} aria-labelledby="rwTitle" onClose={onClose}>
    <div className="lw-head"><div><span className="step">레시피 상세 창</span><h2 id="rwTitle">{stepOf(r)} · {m||`호기 ${machines.length}대`}</h2></div>
      <div className="lw-actions"><button type="button" className="primary" onClick={()=>ref.current?.close()}>닫기</button></div>
      <div className="lw-meta"><span className="job">{jobOf(r)}</span><span>정상 WPH <b>{f1(wn)}</b></span><span>실제 WPH <b>{f1(wa)}</b></span><span>처리량 감소 {pc(drop(wn,wa))}</span>
        <span>하루 생산능력 <b>{m?num(cap(A)):num(perM.reduce((s,x)=>s+(cap(x.a)||0),0))}</b>장{m?'':` (${machines.length}대 합계)`}</span><span>{range.from} ~ {range.to}</span></div></div>
    <div className="pilltabs lw-tabs" role="tablist">{([['split','WPH 분해'],['unit','1장 처리 시간'],['lots','Lot별 실제 WPH']] as const).map(([t,l])=>
      <button key={t} role="tab" type="button" className={tab===t?'active':''} aria-selected={tab===t} onClick={()=>setTab(t)}>{l}</button>)}</div>
    <div className="lw-body">
      {tab==='split'&&<><h3>정상 WPH에서 실제 WPH까지 <Q id="wph.split" calc={wp==null?[]:[`처리 WPH = ${num(A.ps)}장 × 3,600 ÷ ${hrs(A.p)}시간 = ${f1(wp)}`,...steps.map(s=>`${s[0]}: ${num(s[1],2)} WPH`),`실제 WPH = ${f1(wa)}`]}/></h3>
        <div className="wfall">{wn!=null&&<div className="wf"><span className="lab">정상 WPH<Q id="wph.normal"/></span><span className="track"><span style={{left:0,width:(wn/top*100)+'%',background:'#31517c'}}/></span><b>{f1(wn)}</b></div>}
          {(()=>{let at=wn??wp??0;return steps.map(([l,d,c,h])=>{const a=at,b=at-d;at=b;const lo=Math.min(a,b),w=Math.abs(d);
            return <div key={l} className="wf" data-tip={`${l}\n${d>=0?'−':'+'}${num(Math.abs(d),2)} WPH`}><span className="lab">{l}{h&&<Q id={h}/>}</span><span className="track"><span style={{left:(lo/top*100)+'%',width:Math.max(.4,w/top*100)+'%',background:c}}/></span><b>{d>=0?'−':'+'}{Math.abs(d).toFixed(1)}</b></div>;});})()}
          <div className="wf"><span className="lab">실제 WPH<Q id="wph.actual"/></span><span className="track"><span style={{left:0,width:((wa||0)/top*100)+'%',background:C_OK}}/></span><b>{f1(wa)}</b></div></div>
        <div className="two"><div><h3>시간 <small>유휴는 빼고 셉니다</small></h3><table className="t-compact"><tbody>
            <tr><td>웨이퍼 처리<Q id="util.proc"/></td><td className="num">{hrs(A.p)}h</td><td className="num">{pc(pctOf(A.p,D))}</td></tr>
            <tr><td>Error<Q id="util.loss"/></td><td className="num">{hrs(A.e)}h</td><td className="num">{pc(pctOf(A.e,D))}</td></tr>
            <tr><td>{STOPK.d}<Q id="stop.defect"/></td><td className="num">{hrs(A.sd)}h</td><td className="num">{pc(pctOf(A.sd,D))}</td></tr>
            <tr><td>{STOPK.o}</td><td className="num">{hrs(A.so)}h</td><td className="num">{pc(pctOf(A.so,D))}</td></tr></tbody></table></div>
          <div><h3>얼마나 자주</h3><table className="t-compact"><tbody>
            <tr><td>Error 발생률<Q id="wph.errrate" calc={[`${num(A.ne)} ÷ ${num(A.n)} Batch Report`]}/></td><td className="num">{rate(A.ne,A.n)}</td></tr>
            <tr><td>중단 발생률 · Defect 과다<Q id="wph.stoprate"/></td><td className="num">{rate(A.nsd,A.n)}</td></tr>
            <tr><td>중단 발생률 · 그 외</td><td className="num">{rate(A.nso,A.n)}</td></tr>
            <tr><td>재스캔 참고 비율<Q id="wph.rescan" calc={[`${num(A.dn)}장 ÷ Pass ${num(A.ps)}장`]}/></td><td className="num">{rate(A.dn,A.ps)}</td></tr></tbody></table></div></div>
        <h3>Error 원문별 잃은 시간 <small>Batch Report 남은 시간 + 다시 스캔하기까지 조치</small></h3>
        {errs.length?errs.map(([e,t])=><div key={e} className="hbar"><span className="lab">{e}</span><span className="track"><span style={{width:(t[0]/emx*100)+'%',background:C_ERR}}/></span><span className="val">{hrs(t[0])}h · wafer {num(t[1])}</span></div>)
          :<p className="hint">Error로 잃은 시간이 없습니다.</p>}</>}
      {tab==='unit'&&<><h3>1장 처리 시간 = Avg. Scan Time + 로봇 이동 · 로딩 · 얼라인 <Q id="wph.unit"/><Q id="wph.avgscan"/></h3>
        {perM.length?<div className="caprows">{perM.map(x=>{const u=unitSec(x.a),s=avgScan(x.a);return <div key={x.m} className="caprow" data-tip={`${x.m}\n1장 처리 시간 ${u==null?'—':num(u,1)+'초'}\nAvg. Scan Time ${s==null?'—':num(s,1)+'초'}\n로봇 이동 등 ${u!=null&&s!=null?num(u-s,1)+'초':'—'}\n정상 25매 Batch Report ${num(x.a.w25/25)}장`}>
          <span className="cl">{x.m}</span><span className="capbar">{u!=null&&s!=null?<><span style={{width:(s/umx*100)+'%',background:'#31517c'}}>Avg. Scan {num(s)}초</span><span style={{width:((u-s)/umx*100)+'%',background:'#9db7d9'}}/></>
            :u!=null?<span style={{width:(u/umx*100)+'%',background:'#9db7d9'}}/>:null}</span><span className="capv"><b>{u==null?'—':num(u)}</b>초</span></div>;})}</div>
          :<p className="hint">자료가 없습니다.</p>}
        <div className="keys"><span><i style={{background:'#31517c'}}>　</i> Avg. Scan Time(순수 스캔, 원문)</span><span><i style={{background:'#9db7d9'}}>　</i> 로봇 이동 · 로딩 · 얼라인</span><span>정상 25매 Batch Report 기준</span></div>
        <h3>정상 25매 Batch Report의 WPH 분포 <small>막대를 누르면 그 구간만 목록에 · 행을 누르면 원문</small></h3>
        {cl.length?<><ColChart items={bins.map(b=>({id:b.id,short:num(b.lo,1),v:{n:b.n},tip:`WPH ${num(b.lo,1)} ~ ${num(b.hi,1)}\n정상 25매 Batch Report ${b.n}개\n누르면 이 구간만 목록에`}))}
            keys={[{k:'n',label:'Batch Report',c:'#31517c'}]} h={190} minw={18} maxw={70} sel={cur} label="정상 WPH 분포" onClick={id=>setBin(b=>b===id?null:id)}/>
          <div className="table-scroll" style={{maxHeight:300}}><table className="t-compact"><thead><tr><th>시작</th><th>호기</th><th>Lot</th><th className="num">Batch Time</th><th className="num">Avg. Scan Time</th><th className="num">WPH</th></tr></thead>
            <tbody>{list.map(c=>{const rr=v.R[c.x.g];return <tr key={c.x.g} className="clickable" onClick={()=>showRaw(c.x.g)}><td>{rr.s}</td><td>{rr.m}</td>
              <td><button type="button" className="linklike" onClick={e=>{e.stopPropagation();openLot(c.x.lot);}}>{v.lots[c.x.lot].label}</button></td><td className="num">{dur(c.x.s/60)}</td>
              <td className="num">{c.x.a==null?'—':num(c.x.a)+'초'}</td><td className="num"><b>{num(c.w,1)}</b></td></tr>;})}</tbody></table></div></>
          :<p className="hint">정상 25매 Batch Report가 없습니다.</p>}</>}
      {tab==='lots'&&<><h3>Lot별 실제 WPH <small>점 하나 = Lot 한 번의 스캔(공정 단계) · 누르면 Lot History</small><Q id="wph.actual"/></h3>
        <div className="keys"><span><i style={{background:C_OK}}>　</i> 한 번에 스캔</span><span><i style={{background:C_WAIT}}>　</i> 재스캔 포함</span><span>점선 = 정상 WPH</span></div>
        <Scatter base={wn} onClick={openLot} pts={L.map(x=>{const y=x.ps*3600/x.s;return {t:new Date(x.d+'T12:00:00').getTime(),y,id:x.lot,c:x.n>1?C_WAIT:C_OK,
          tip:`Lot ${v.lots[x.lot].label} · ${x.m}\n${x.d}\nBatch Report ${x.n}개 · Pass ${x.ps}장${x.dn?' (다시 스캔해 또 Pass '+x.dn+')':''}\n쓴 시간 ${hrs(x.s)}h (조치 대기 포함)\n실제 WPH ${num(y,1)}\n누르면 Lot History`};})}/>
        <h3>처리량이 많이 줄어든 Lot <small>재스캔이 있었던 Lot 중 실제 WPH가 낮은 순</small></h3>
        <div className="table-scroll" style={{maxHeight:330}}><table className="t-compact"><thead><tr><th>Lot</th><th>시작</th><th>호기</th><th className="num">Batch Report</th><th className="num">쓴 시간(h)</th><th className="num">실제 WPH</th><th className="num">처리량 감소</th></tr></thead>
          <tbody>{worst.map(([x,y])=><tr key={x.lot+'|'+x.b} className="clickable" onClick={()=>openLot(x.lot)}><td><b>{v.lots[x.lot].label}</b></td><td>{x.d}</td><td>{x.m}</td>
            <td className="num">{x.n}</td><td className="num">{hrs(x.s)}</td><td className="num">{num(y,1)}</td><td className="num v4">{pc(drop(wn,y))}</td></tr>)}
            {!worst.length&&<tr><td colSpan={7}>재스캔한 Lot이 없습니다.</td></tr>}</tbody></table></div></>}
    </div></dialog>;
}
