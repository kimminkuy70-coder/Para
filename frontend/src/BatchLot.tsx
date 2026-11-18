import {Fragment,useMemo,useRef,useState} from 'react';
import {ColChart,Legend,Seg,type Key,type ColItem} from './BatchCharts';
import {Q,openDefect} from './BatchHelp';
import {bucket,shortKey,weekRange,periodName,num,stepLabel,is3D,STATES,ST,DONE,RE,OPEN,C_OK,C_ERR,C_WAIT,C_STOP,C_DEFECT,STOPK,type View,type Unit,type Lot} from './batchData';

/* Lot 추적 탭 — 지표 5개(누르면 목록) · 기간별 Lot Scan 현황 · Lot 단위 Scan List · 멈춘 이유 요약(Error / 작업자 중단) · 점검 스캔.
   설명 글은 화면에 두지 않고 ? 버튼으로(사용자 지시 2026-10-05). */
export function StPill({s}:{s:string}){return <span className={'st '+(ST[s]||'dup')}>{s}</span>;}
type Mode='lots'|'reports'|'re'|'open'|'dup';
const SUB:Record<Mode,string>={lots:'조사 범위 내 Scan된 Lot 전체',reports:'',re:'Error · 작업자 중단 뒤 재스캔하여 모든 wafer가 Pass한 Lot',
  open:'끝까지 Pass하지 못한 wafer가 있는 Lot — 다른 호기에서 Scan되었는지 확인하세요',dup:'같은 wafer를 Pass한 뒤 다시 스캔한 Lot — 취합은 가장 나중 Pass를 씁니다'};
/* 목록 제목 — 지표를 누르면 아래 목록이 바뀐 것이 바로 보이게 목록 위에 크게 쓴다(사용자 요청 2026-10-05). */
const TITLE:Record<Mode,string>={lots:'Lot 단위 Scan List — 전체 Lot',reports:'Batch Report 목록 — 전체 Batch Report',
  re:'재스캔으로 완료된 Lot 목록',open:'Pass하지 못한 Lot 목록',dup:'중복 Scan한 wafer가 존재하는 Lot 목록'};
const LOTKEYS:Key[]=[{k:'done',label:DONE,c:C_OK},{k:'re',label:RE,c:C_WAIT},{k:'open',label:OPEN,c:C_ERR}];
const small={minHeight:28,padding:'3px 10px',fontSize:12} as const;
/* 멈춘 이유 요약 필터(이슈 #80) — Lot 의 (원문, 호기, 레시피)별 묶음. 예전 저장 결과(cx 없음)는 Lot 의 호기 · 레시피가 하나일 때만 그 값, 아니면 '(알 수 없음)'. */
const UNK='(알 수 없음)';
type CX=[string,string,string,number,boolean];
function lotCx(l:Lot,stop:boolean):CX[]{
  const x=stop?l.sx:l.cx;if(x)return x as CX[];
  const m=l.machines.length===1?l.machines[0]:UNK,rs=[...new Set(l.bunches.map(b=>b.r||''))],r=rs.length===1&&rs[0]?rs[0]:UNK;
  return (stop?l.sz:l.cz).map(([c,w,o])=>[c,m,r,w,o] as CX);}
type Agg={lots:number;w:number;ok:number;open:number};
/** 필터에 맞는 묶음만 모아 원문(또는 중단 종류)별 Lot 수 — Lot 하나는 원문마다 한 번 센다(Pass 못 한 wafer 가 하나라도 있으면 Pass하지 못한 Lot). */
function aggCx(lots:Lot[],stop:boolean,ok:(e:CX)=>boolean,col?:(e:CX)=>string){
  const m:Record<string,Agg>={},g:Record<string,Record<string,Agg>>={};
  lots.forEach(l=>{const per:Record<string,[number,boolean]>={},pc:Record<string,[number,boolean]>={};
    lotCx(l,stop).forEach(e=>{if(!ok(e))return;const p=per[e[0]]||(per[e[0]]=[0,false]);p[0]+=e[3];p[1]=p[1]||e[4];
      if(col){const k=e[0]+'\u0000'+col(e),q=pc[k]||(pc[k]=[0,false]);q[0]+=e[3];q[1]=q[1]||e[4];}});
    Object.entries(per).forEach(([c,[w,o]])=>{const t=m[c]||(m[c]={lots:0,w:0,ok:0,open:0});t.lots++;t.w+=w;if(o)t.open++;else t.ok++;});
    Object.entries(pc).forEach(([k,[w,o]])=>{const [c,cl]=k.split('\u0000');const r=g[c]||(g[c]={});const t=r[cl]||(r[cl]={lots:0,w:0,ok:0,open:0});t.lots++;t.w+=w;if(o)t.open++;else t.ok++;});});
  return {m,g};}

export function LotTab({v,openLot,showRaw}:{v:View;openLot:(li:number)=>void;showRaw:(g:number)=>void}){
  const [mode,setMode]=useState<Mode>('lots');
  const [state,setState]=useState(''),[period,setPeriod]=useState<string|null>(null),[cause,setCause]=useState<string|null>(null);
  const [q,setQ]=useState(''),[fRe,setFRe]=useState(false),[fMove,setFMove]=useState(false);
  const [repQ,setRepQ]=useState(''),[repRes,setRepRes]=useState(''),[repKind,setRepKind]=useState('');
  const [unit,setUnit]=useState<Unit>('w'),[hid,setHid]=useState<Record<string,boolean>>({}),[why,setWhy]=useState<'err'|'stop'>('err');
  // 멈춘 이유 요약 필터(이슈 #80): 레시피 · 호기 · Error 원문, 보기 = 목록 / 호기별 표
  const [fRcp,setFRcp]=useState(''),[fMac,setFMac]=useState(''),[fErr,setFErr]=useState(''),[rv,setRv]=useState<'list'|'grid'>('list');
  const [cxf,setCxf]=useState<{m:string;r:string}>({m:'',r:''});
  const listTop=useRef<HTMLHeadingElement>(null);
  const lots=v.lots,R=v.R;
  const kpi=useMemo(()=>({re:lots.filter(l=>l.state===RE).length,open:lots.filter(l=>l.state===OPEN).length,dup:lots.filter(l=>l.dup).length}),[lots]);
  const chk=v.excluded.length;
  const stCount=useMemo(()=>Object.fromEntries(STATES.map(x=>[x,lots.filter(l=>l.state===x).length])) as Record<string,number>,[lots]);
  const dupOnly=mode==='dup';
  const on:Mode=mode==='reports'?'reports':dupOnly?'dup':state===RE?'re':state===OPEN?'open':'lots';
  function pick(k:Mode){setMode(k);setState(k==='re'?RE:k==='open'?OPEN:'');setPeriod(null);setCause(null);setQ('');setRepQ('');setFRe(false);setFMove(false);
    listTop.current?.scrollIntoView({behavior:'smooth',block:'start'});}
  const items=useMemo(():ColItem[]=>{const by:Record<string,Record<string,number>>={};
    lots.forEach(l=>{if(!l.s)return;const k=bucket(l.s.slice(0,10),unit);(by[k]||=({done:0,re:0,open:0}))[ST[l.state]]++;});
    return Object.keys(by).sort().map(k=>{const x=by[k],t=x.done+x.re+x.open;
      const name=periodName(k,unit);
      return {id:k,short:shortKey(k,unit),short2:unit==='w'?weekRange(k):undefined,v:x,
        tip:`${name}\nLot ${t}개 (처음 스캔 기준)\n${DONE} ${x.done}\n${RE} ${x.re}\n${OPEN} ${x.open}\n누르면 이 기간 Lot만 목록에`,
        tipx:{t:name,rows:[[C_OK,DONE,num(x.done),'Lot'],[C_WAIT,RE,num(x.re),'Lot'],[C_ERR,OPEN,num(x.open),'Lot'],['transparent','합계',num(t),'Lot']],
          f:['처음 스캔한 날 기준 · 누르면 이 기간 Lot만 아래 목록에']}};});},[lots,unit]);
  const rows=useMemo(()=>{const t=q.trim().toUpperCase();
    return lots.map((l,i)=>[l,i] as const).filter(([l])=>{
      if(t&&!(l.label+' '+l.sms.join(' ')+' '+l.lot_id+' '+l.jobs.join(' ')).toUpperCase().includes(t))return false;
      if(state&&l.state!==state)return false;if(fRe&&!l.multi)return false;if(fMove&&!l.moved)return false;if(dupOnly&&!l.dup)return false;
      if(period&&(!l.s||bucket(l.s.slice(0,10),unit)!==period))return false;if(cause){const st=cause.startsWith('__stop_'),c=st?cause.slice(7):cause;
        if(!lotCx(l,st).some(e=>e[0]===c&&(!cxf.m||e[1]===cxf.m)&&(!cxf.r||e[2]===cxf.r)))return false;}return true;})
      .sort((a,b)=>a[0].s<b[0].s?1:-1);},[lots,q,state,fRe,fMove,dupOnly,period,cause,cxf,unit]);
  const reports=useMemo(()=>{const t=repQ.trim().toLowerCase();
    return R.map((r,i)=>[r,i] as const).filter(([r])=>{if(t&&!(r.f+' '+r.sm+' '+(r.lot!=null?lots[r.lot].label:'')).toLowerCase().includes(t))return false;
      if(repRes==='err'&&r.o!=='e')return false;if(repRes==='ok'&&r.o!=='c')return false;if(repRes==='stop'&&r.o!=='s')return false;if(repKind==='lot'&&r.lot==null)return false;if(repKind==='chk'&&r.lot!=null)return false;return true;})
      .sort((a,b)=>a[0].s<b[0].s?1:-1);},[R,lots,repQ,repRes,repKind]);
  // 필터 고르기 목록 — 조사 범위 전체의 Error · 작업자 중단 묶음에서(개수 = 그 값이 들어간 Lot 수)
  const opts=useMemo(()=>{const R:Record<string,Set<string>>={},M:Record<string,Set<string>>={},E:Record<string,Set<string>>={};
    lots.forEach(l=>{([false,true] as const).forEach(st=>lotCx(l,st).forEach(e=>{
      if(!fMac||e[1]===fMac)(R[e[2]]||(R[e[2]]=new Set())).add(l.key);
      if(!fRcp||e[2]===fRcp)(M[e[1]]||(M[e[1]]=new Set())).add(l.key);
      if(!st&&(!fRcp||e[2]===fRcp)&&(!fMac||e[1]===fMac))(E[e[0]]||(E[e[0]]=new Set())).add(l.key);}));});
    const srt=(o:Record<string,Set<string>>)=>Object.keys(o).sort((a,b)=>o[b].size-o[a].size||a.localeCompare(b)).map(k=>[k,o[k].size] as [string,number]);
    return {r:srt(R),m:srt(M),e:srt(E)};},[lots,fRcp,fMac]);
  const fOk=(e:CX)=>(!fRcp||e[2]===fRcp)&&(!fMac||e[1]===fMac);
  const causes=useMemo(()=>{const {m,g}=aggCx(lots,false,e=>fOk(e)&&(!fErr||e[0]===fErr),e=>e[1]);
    const keys=Object.keys(m).sort((a,b)=>m[b].lots-m[a].lots||m[b].w-m[a].w);
    const cm:Record<string,number>={};keys.forEach(k=>Object.entries(g[k]||{}).forEach(([mc,t])=>{cm[mc]=(cm[mc]||0)+t.lots;}));
    const cols=Object.keys(cm).sort((a,b)=>a.localeCompare(b,undefined,{numeric:true}));
    return {m,g,keys,cols,mx:keys.length?m[keys[0]].lots:1};},[lots,fRcp,fMac,fErr]);// eslint-disable-line react-hooks/exhaustive-deps
  const allErr=useMemo(()=>new Set(lots.flatMap(l=>l.cz.map(c=>c[0]))).size,[lots]);
  // 작업자 중단(Error 아님) — 종류별 Lot 수 · 그 뒤 Pass / Pass 못 함 (레시피 · 호기 필터 따름)
  const stops=useMemo(()=>{const {m:a}=aggCx(lots,true,fOk);const z={lots:0,w:0,ok:0,open:0};
    const m:Record<string,Agg&{n:number}>={d:{...z,...a.d,n:0},o:{...z,...a.o,n:0}};
    v.stops.forEach(x=>{if((!fRcp||x.r===fRcp)&&(!fMac||x.m===fMac))m[x.k].n++;});
    return {m,mx:Math.max(1,m.d.lots,m.o.lots)};},[lots,v.stops,fRcp,fMac]);// eslint-disable-line react-hooks/exhaustive-deps
  const fOn=!!(fRcp||fMac||fErr);
  function toList(c:string,m=fMac){setMode('lots');setState('');setPeriod(null);setCause(c);setCxf({m,r:fRcp});listTop.current?.scrollIntoView({behavior:'smooth',block:'start'});}
  const K:[Mode,string,string,number,string,string,string][]=[
    ['lots','','조사 범위 내 Lot Scan 완료',lots.length,'Lot','S/M 영문 3글자 + Lot ID 기준','Lot 단위 Scan List 보기 →'],
    ['reports','','조사 범위 내 Batch Report 존재',R.length,'개',`Lot ${R.length-chk} · 점검 스캔 ${chk}`,'Batch Report 목록 · 누르면 원문 →'],
    ['re','k-re','재스캔으로 완료된 Lot',kpi.re,'Lot','Error · 작업자 중단 뒤 재스캔하여 Pass','목록 보기 →'],
    ['open','k-open','Pass하지 못한 Lot',kpi.open,'Lot','다른 호기에서 Scan되었는지 확인 필요','목록 보기 →'],
    ['dup','k-dup','중복 Scan한 wafer가 존재하는 Lot',kpi.dup,'Lot','같은 wafer를 Pass 후 다시 스캔','목록 보기 →']];
  const chips:[string,string,()=>void][]=[];
  if(period)chips.push(['period','기간 '+period,()=>setPeriod(null)]);
  if(dupOnly)chips.push(['dup','중복 Scan한 wafer가 존재하는 Lot',()=>setMode('lots')]);
  if(cause)chips.push(['cause',(cause.startsWith('__stop_')?STOPK[cause.slice(7)]:'Error '+cause)+(cxf.r?' · '+cxf.r:'')+(cxf.m?' · '+cxf.m:''),()=>{setCause(null);setCxf({m:'',r:''});}]);
  const lotMode=mode!=='reports';
  return <section className="panel tabpanel" aria-label="Lot 추적">
    <div className="section-heading"><div><span className="step">Lot 추적</span><h2>Lot은 어떻게 스캔됐고, 모든 wafer가 Pass했나 <Q id="lot.about"/></h2></div></div>
    <section className="kpib" aria-label="Lot 지표 — 누르면 목록">{K.map(([k,cls,lab,val,u,s2,go])=>
      <button key={k} type="button" className={cls+(on===k?' on':'')} aria-pressed={on===k} onClick={()=>pick(k)}>
        <span className="lab">{lab}</span><strong>{num(val)}<small>{u}</small></strong><span className="s2">{s2}</span><span className="go2">{go}</span></button>)}</section>
    <div className="chartcard"><div className="ch"><h3>기간별 Lot Scan 현황</h3><span className="hint">막대에 마우스를 올리면 자세히, 누르면 그 기간 Lot만 아래 목록에 보입니다.</span><span className="grow"/>
        <Legend keys={LOTKEYS} hidden={hid} onToggle={k=>setHid(h=>({...h,[k]:!h[k]}))}/>
        <Seg label="기간 단위" value={unit} items={[['d','일'],['w','주'],['m','월']]} onChange={u=>{setUnit(u);setPeriod(null);}}/></div>
      <ColChart items={items} keys={LOTKEYS} maxw={unit==='w'?100:60} hidden={hid} sel={period} label="기간별 Lot Scan 현황" onClick={id=>{setPeriod(p=>p===id?null:id);if(!lotMode)setMode('lots');}}/></div>
    {/* 지금 보는 목록 — 프로그램 테마(네이비 · 라임 카드)에 맞춘 카드(이슈 #8): 머리(제목 · 개수) → 도구 줄(검색 · 상태 · 조건) → 표 */}
    <section className={'lotlist lt-'+on} aria-label="지금 보는 목록">
      <header className="ll-head">
        <div className="ll-title"><span className="ll-eyebrow">지금 보는 목록</span>
          <h2 ref={listTop} key={on} className="listtitle"><i className="ll-dot" aria-hidden="true"/>{TITLE[on]}</h2>
          <p className="sub">{lotMode?(SUB[on]||'조사 범위 내 Scan된 Lot 전체')+' · Lot을 누르면 새 창(Lot 창)에서 Lot History'
            :'행을 누르면 Batch Report 원문 창(그 1장의 표 그대로), Lot 이름을 누르면 Lot 창(그 Lot의 모든 Batch Report를 모은 Lot History)'}</p></div>
        <div className="ll-count" aria-live="polite"><strong>{num(lotMode?rows.length:reports.length)}</strong>
          <span>/ {lotMode?`${num(lots.length)} Lot`:`${num(R.length)}개`}</span></div>
      </header>
      {lotMode?<div className="ll-tools">
        <label className="ll-search"><span aria-hidden="true">⌕</span><input type="search" value={q} onChange={e=>setQ(e.target.value)} placeholder="Lot 코드 · S/M · Lot ID · Job 검색" aria-label="Lot 검색"/></label>
        <div className="ll-seg" role="group" aria-label="상태">{([['','전체',lots.length],...STATES.map(x=>[x,x,stCount[x]])] as [string,string,number][]).map(([k,t,n])=>
          <button key={k||'all'} type="button" className={'ll-opt '+(k?ST[k]:'all')+(state===k?' on':'')} aria-pressed={state===k} onClick={()=>setState(k)}>{t}<b>{num(n)}</b></button>)}</div>
        <div className="ll-toggles" role="group" aria-label="조건">
          <button type="button" className={'ll-tg'+(fRe?' on':'')} aria-pressed={fRe} title="같은 Lot을 2번 이상 이어서 스캔한 Lot (Error 재스캔 · 나눠 스캔)" onClick={()=>setFRe(x=>!x)}>재스캔</button>
          <button type="button" className={'ll-tg'+(fMove?' on':'')} aria-pressed={fMove} title="다른 호기로 옮겨 이어서 스캔한 Lot" onClick={()=>setFMove(x=>!x)}>호기 이동</button></div>
        {chips.length>0&&<span className="chips">{chips.map(([k,t,clear])=><button key={k} type="button" className="chip" onClick={clear}>{t} <i aria-hidden="true">✕</i></button>)}</span>}</div>
      :<div className="ll-tools">
        <label className="ll-search"><span aria-hidden="true">⌕</span><input type="search" value={repQ} onChange={e=>setRepQ(e.target.value)} placeholder="파일 이름 · S/M · Lot 검색" aria-label="Batch Report 검색"/></label>
        <select aria-label="결과" value={repRes} onChange={e=>setRepRes(e.target.value)}><option value="">전체 결과</option><option value="err">Error 있음</option><option value="stop">작업자 중단</option><option value="ok">모두 Pass</option></select>
        <select aria-label="종류" value={repKind} onChange={e=>setRepKind(e.target.value)}><option value="">Lot + 점검 스캔</option><option value="lot">Lot만</option><option value="chk">점검 스캔만</option></select></div>}
      <div className="table-scroll ll-table"><table className="t-compact">
        {lotMode?<><thead><tr><th>Lot · S/M</th><th>호기</th><th className="num">Batch Report</th><th>스캔 기간</th><th>상태</th><th className="num">Pass하지 못한 wafer</th><th className="num">재스캔 Pass wafer</th><th className="num">중복 Scan wafer</th><th>주요 Error 원문(wafer 수)</th><th aria-hidden="true"/></tr></thead>
          <tbody>{rows.slice(0,2000).map(([l,i])=><tr key={i} className="clickable" tabIndex={0} onClick={()=>openLot(i)} onKeyDown={e=>{if(e.key==='Enter'){e.preventDefault();openLot(i);}}}>
            <td><b className="ll-lot">{l.label}</b><small className="ll-sm">{l.sms.join(', ')}</small></td>
            <td><span className="ll-mach">{l.machines.map((m,j)=><Fragment key={j}>{j>0&&<i aria-hidden="true">→</i>}<span>{m}</span></Fragment>)}</span></td>
            <td className="num">{l.n}</td>
            <td className="ll-time"><span>{l.s}</span><small>~ {l.e}</small></td>
            <td><span className="ll-pills"><StPill s={l.state}/>{l.moved&&<span className="st mv">호기 이동</span>}{l.sz.length>0&&<span className={'st '+(l.sz.some(x=>x[0]==='d')?'sd':'so')} title="앞 Error 없이 Aborted.로 멈춘 스캔이 있습니다(Error 아님)">작업자 중단</span>}{l.scans.includes('3D')&&<span className="st s3d" title="S/M에 3D가 붙은 3D 스캔이 있습니다 — 2D와 따로 셉니다">3D 스캔 포함</span>}</span></td>
            <td className={'num'+(l.open?' v4':' ll-zero')}>{l.open||'—'}</td><td className={'num'+(l.re?' v2':' ll-zero')}>{l.re||'—'}</td><td className={'num'+(l.dup?' v3':' ll-zero')}>{l.dup||'—'}</td>
            <td>{l.causes.length?<span className="ll-errs">{l.causes.slice(0,2).map(c=><span key={c[0]} className="ll-err" title={c[0]}>{c[0]} <b>×{c[1]}</b></span>)}{l.causes.length>2&&<span className="ll-more" title={l.causes.slice(2).map(c=>c[0]+' ×'+c[1]).join('\n')}>+{l.causes.length-2}</span>}</span>:<span className="ll-zero">—</span>}</td>
            <td className="ll-go" aria-hidden="true">›</td></tr>)}
            {!rows.length&&<tr className="ll-empty"><td colSpan={10}><b>조건에 맞는 Lot이 없습니다.</b><span>검색어나 상태 · 조건을 바꿔 보세요.</span></td></tr>}</tbody></>
        :<><thead><tr><th>시작</th><th>끝</th><th>호기</th><th>S/M</th><th title="누르면 Lot 창">Lot</th><th>공정 단계(Recipe(s))</th><th className="num">Pass / 행</th><th>첫 Error 원문 · 중단</th><th>파일 이름</th><th/></tr></thead>
          <tbody>{reports.slice(0,2000).map(([r,i])=><tr key={i} className="clickable" onClick={()=>showRaw(i)}><td>{r.s}</td><td>{r.e.slice(11)}</td><td>{r.m}</td><td>{r.sm}</td>
            <td>{r.lot!=null?<button type="button" className="linklike" title="Lot 창 열기 — 이 Lot의 모든 Batch Report를 모은 Lot History" onClick={e=>{e.stopPropagation();openLot(r.lot!);}}>{lots[r.lot].label}</button>:<span className="st out">점검 스캔</span>}</td>
            <td>{stepLabel(r)}{is3D(r.k)&&<> <span className="st s3d">3D</span></>}</td><td className="num">{r.ok} / {r.n}{r.sp?<small className="muted"> (스캔 안 함 {r.sp})</small>:null}</td><td className={r.fe?'v4':''}>{r.fe||(r.o==='s'?<span className={'st '+(r.sk==='d'?'sd':'so')} title={`앞 Error 없이 Aborted. — 멈출 때 wafer Faults ${r.ff??'—'}`}>{STOPK[r.sk||'o']}</span>:'')}</td><td className="mono">{r.f}</td><td><button type="button" style={small} onClick={e=>{e.stopPropagation();showRaw(i);}}>원문 보기</button></td></tr>)}
            {!reports.length&&<tr className="ll-empty"><td colSpan={10}><b>조건에 맞는 Batch Report가 없습니다.</b><span>검색어나 결과 · 종류를 바꿔 보세요.</span></td></tr>}</tbody></>}
      </table></div>
      {(lotMode?rows.length:reports.length)>2000&&<p className="ll-foot">처음 2,000행만 보여 줍니다. 검색 · 필터로 좁혀 보세요.</p>}
    </section>
    <section className="card2"><div className="section-heading"><div><h2>멈춘 이유 요약 <Q id="lot.reasons"/></h2><p className="sub">개수는 모두 <b>Lot</b> 기준 · 행{why==='err'&&rv==='grid'?' · 칸':''}을 누르면 그 Lot만 위 목록에</p></div><span className="grow"/>
        <Seg label="멈춘 이유" value={why} items={[['err',`Error ${fOn?causes.keys.length+' / '+allErr:allErr}종`],['stop',`작업자 중단 ${stops.m.d.n+stops.m.o.n}건`]]} onChange={setWhy}/></div>
      {/* 필터(이슈 #80) — 예: 레시피 하나 + Error 하나 → 호기별 표에서 호기마다 몇 Lot 인지 한눈에 */}
      <div className="ll-tools rz-filter" role="group" aria-label="멈춘 이유 필터">
        <label>레시피 <select aria-label="레시피 필터" value={fRcp} onChange={e=>setFRcp(e.target.value)}><option value="">전체 레시피</option>
          {fRcp&&!opts.r.some(o=>o[0]===fRcp)&&<option value={fRcp}>{fRcp} (0)</option>}{opts.r.map(([k,n])=><option key={k} value={k}>{k} ({n})</option>)}</select></label>
        <label>호기 <select aria-label="호기 필터" value={fMac} onChange={e=>setFMac(e.target.value)}><option value="">전체 호기</option>
          {fMac&&!opts.m.some(o=>o[0]===fMac)&&<option value={fMac}>{fMac} (0)</option>}{opts.m.map(([k,n])=><option key={k} value={k}>{k} ({n})</option>)}</select></label>
        {why==='err'&&<label>Error <select aria-label="Error 필터" value={fErr} onChange={e=>setFErr(e.target.value)} style={{maxWidth:320}}><option value="">전체 Error</option>
          {fErr&&!opts.e.some(o=>o[0]===fErr)&&<option value={fErr}>{fErr} (0)</option>}{opts.e.map(([k,n])=><option key={k} value={k}>{k} ({n})</option>)}</select></label>}
        {why==='err'&&<Seg label="보기" value={rv} items={[['list','목록'],['grid','호기별 표']]} onChange={setRv}/>}
        {fOn&&<button type="button" className="chip" onClick={()=>{setFRcp('');setFMac('');setFErr('');}}>필터 지우기 <i aria-hidden="true">✕</i></button>}
        <span className="hint">( ) 안 = 그 값이 있는 Lot 수</span></div>
      {!(why==='err'&&rv==='grid')&&<div className="keys"><span><i style={{background:C_OK}}>　</i> 재스캔하여 Pass한 Lot</span><span><i style={{background:C_ERR}}>　</i> Pass하지 못한 Lot</span></div>}
      {why==='err'&&rv==='grid'?<div className="table-scroll" style={{maxHeight:420}}><table className="t-compact rz-grid"><thead><tr><th>Error 원문(첫 문구)</th>
          {causes.cols.map(c=><th key={c} className="num">{c}</th>)}<th className="num">합계 Lot</th></tr></thead>
        <tbody>{causes.keys.map(k=>{const t=causes.m[k],r=causes.g[k]||{};return <tr key={k}><td><button type="button" className="linklike" title="이 Error Lot만 위 목록에" onClick={()=>toList(k)}><b>{k}</b></button></td>
          {causes.cols.map(c=>{const x=r[c];return <td key={c} className={'num'+(x?' clickable':' ll-zero')} title={x?`${k}\n호기 ${c}${fRcp?'\n레시피 '+fRcp:''}\nLot ${x.lots}개 · wafer ${x.w}장\n재스캔하여 Pass한 Lot ${x.ok}\nPass하지 못한 Lot ${x.open}\n누르면 이 Lot들만 목록에`:undefined}
            onClick={x?()=>toList(k,c):undefined}>{x?<><b>{x.lots}</b>{x.open?<small className="v4"> ({x.open})</small>:null}</>:'—'}</td>;})}
          <td className="num"><b>{t.lots}</b></td></tr>;})}
          {!causes.keys.length&&<tr><td colSpan={causes.cols.length+2}>{fOn?'필터에 맞는 Error 없음':'Error 없음'}</td></tr>}</tbody></table>
        <p className="hint">칸 숫자 = 그 호기에서 이 Error가 난 Lot 수, ( ) = 그중 Pass하지 못한 Lot. Lot이 여러 호기에서 Error가 나면 호기마다 셉니다(합계 Lot은 한 번).</p></div>
      :why==='err'?<div className="table-scroll" style={{maxHeight:380}}><table className="t-compact"><thead><tr><th>Error 원문(첫 문구)</th><th className="num">Lot</th><th/><th className="num" title="이 Error가 난 wafer가 모두 재스캔으로 Pass한 Lot">재스캔하여 Pass한 Lot</th><th className="num" title="이 Error가 난 wafer 중 끝까지 Pass하지 못한 wafer가 있는 Lot">Pass하지 못한 Lot</th><th className="num">wafer</th></tr></thead>
        <tbody>{causes.keys.map(k=>{const t=causes.m[k];return <tr key={k} className="clickable" onClick={()=>toList(k)}>
          <td><b>{k}</b></td><td className="num"><b>{t.lots}</b></td><td><span className="ebar" data-tip={`${k}\nLot ${t.lots}개\n재스캔하여 Pass한 Lot ${t.ok}\nPass하지 못한 Lot ${t.open}\n누르면 이 Lot들만 목록에`}>
            <span style={{width:(t.ok/causes.mx*100).toFixed(1)+'%',background:C_OK}}/><span style={{width:(t.open/causes.mx*100).toFixed(1)+'%',background:C_ERR}}/></span></td>
          <td className="num v1">{t.ok}</td><td className="num v4">{t.open||''}</td><td className="num">{t.w}</td></tr>;})}
          {!causes.keys.length&&<tr><td colSpan={6}>{fOn?'필터에 맞는 Error 없음':'Error 없음'}</td></tr>}</tbody></table></div>
      :<div className="table-scroll" style={{maxHeight:380}}><table className="t-compact"><thead><tr><th>작업자 중단(앞 Error 없는 Aborted.)</th><th className="num">Batch Report</th><th className="num">Lot</th><th/><th className="num">재스캔하여 Pass한 Lot</th><th className="num">Pass하지 못한 Lot</th><th className="num">wafer</th></tr></thead>
        <tbody>{(['d','o'] as const).map(k=>{const t=stops.m[k];return <tr key={k} className="clickable" onClick={()=>toList('__stop_'+k)}>
          <td><i className="sw" style={{background:k==='d'?C_DEFECT:C_STOP}}/><b>{STOPK[k]}</b>{k==='d'&&<Q id="stop.defect"/>}</td><td className="num">{t.n}</td><td className="num"><b>{t.lots}</b></td>
          <td><span className="ebar"><span style={{width:(t.ok/stops.mx*100).toFixed(1)+'%',background:C_OK}}/><span style={{width:(t.open/stops.mx*100).toFixed(1)+'%',background:C_ERR}}/></span></td>
          <td className="num v1">{t.ok}</td><td className="num v4">{t.open||''}</td><td className="num">{t.w}</td></tr>;})}</tbody></table>
        <p className="hint">작업자가 멈춘 것은 Error로 세지 않습니다. 멈춘 시간은 가동률 · WPH에서 'Error · 중단 및 조치'로 셉니다. <button type="button" className="linklike" onClick={openDefect}>Defect 과다 판정 기준 · 목록 보기</button></p></div>}</section>
    <details className="more"><summary>점검 스캔 (Lot에서 제외) {chk}개</summary><div className="table-scroll" style={{maxHeight:260,marginTop:8}}><table className="t-compact">
      <thead><tr><th>호기</th><th>S/M</th><th>시작</th><th>파일 이름</th><th/></tr></thead>
      <tbody>{v.excluded.map(g=>{const r=R[g];return <tr key={g}><td>{r.m}</td><td>{r.sm}</td><td>{r.s}</td><td className="mono">{r.f}</td><td><button type="button" style={small} onClick={()=>showRaw(g)}>원문 보기</button></td></tr>;})}</tbody></table></div></details>
  </section>;
}
