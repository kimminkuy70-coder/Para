import {useMemo,useRef,useState} from 'react';
import {ColChart,Legend,Seg,type Key,type ColItem} from './BatchCharts';
import {Q,openDefect} from './BatchHelp';
import {bucket,shortKey,weekRange,periodName,num,stepLabel,is3D,STATES,ST,DONE,RE,OPEN,C_OK,C_ERR,C_WAIT,C_STOP,C_DEFECT,STOPK,type View,type Unit} from './batchData';

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

export function LotTab({v,openLot,showRaw}:{v:View;openLot:(li:number)=>void;showRaw:(g:number)=>void}){
  const [mode,setMode]=useState<Mode>('lots');
  const [state,setState]=useState(''),[period,setPeriod]=useState<string|null>(null),[cause,setCause]=useState<string|null>(null);
  const [q,setQ]=useState(''),[fRe,setFRe]=useState(false),[fMove,setFMove]=useState(false);
  const [repQ,setRepQ]=useState(''),[repRes,setRepRes]=useState(''),[repKind,setRepKind]=useState('');
  const [unit,setUnit]=useState<Unit>('w'),[hid,setHid]=useState<Record<string,boolean>>({}),[why,setWhy]=useState<'err'|'stop'>('err');
  const listTop=useRef<HTMLHeadingElement>(null);
  const lots=v.lots,R=v.R;
  const kpi=useMemo(()=>({re:lots.filter(l=>l.state===RE).length,open:lots.filter(l=>l.state===OPEN).length,dup:lots.filter(l=>l.dup).length}),[lots]);
  const chk=v.excluded.length;
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
      if(period&&(!l.s||bucket(l.s.slice(0,10),unit)!==period))return false;if(cause&&(cause.startsWith('__stop_')?!l.sz.some(c=>c[0]===cause.slice(7)):!l.cz.some(c=>c[0]===cause)))return false;return true;})
      .sort((a,b)=>a[0].s<b[0].s?1:-1);},[lots,q,state,fRe,fMove,dupOnly,period,cause,unit]);
  const reports=useMemo(()=>{const t=repQ.trim().toLowerCase();
    return R.map((r,i)=>[r,i] as const).filter(([r])=>{if(t&&!(r.f+' '+r.sm+' '+(r.lot!=null?lots[r.lot].label:'')).toLowerCase().includes(t))return false;
      if(repRes==='err'&&r.o!=='e')return false;if(repRes==='ok'&&r.o!=='c')return false;if(repRes==='stop'&&r.o!=='s')return false;if(repKind==='lot'&&r.lot==null)return false;if(repKind==='chk'&&r.lot!=null)return false;return true;})
      .sort((a,b)=>a[0].s<b[0].s?1:-1);},[R,lots,repQ,repRes,repKind]);
  const causes=useMemo(()=>{const m:Record<string,{lots:number;w:number;ok:number;open:number}>={};
    lots.forEach(l=>l.cz.forEach(([c,w,o])=>{const t=m[c]||(m[c]={lots:0,w:0,ok:0,open:0});t.lots++;t.w+=w;if(o)t.open++;else t.ok++;}));
    const keys=Object.keys(m).sort((a,b)=>m[b].lots-m[a].lots||m[b].w-m[a].w);return {m,keys,mx:keys.length?m[keys[0]].lots:1};},[lots]);
  // 작업자 중단(Error 아님) — 종류별 Lot 수 · 그 뒤 Pass / Pass 못 함
  const stops=useMemo(()=>{const m:Record<string,{lots:number;w:number;ok:number;open:number;n:number}>={d:{lots:0,w:0,ok:0,open:0,n:0},o:{lots:0,w:0,ok:0,open:0,n:0}};
    lots.forEach(l=>l.sz.forEach(([k,w,o])=>{const t=m[k];t.lots++;t.w+=w;if(o)t.open++;else t.ok++;}));v.stops.forEach(x=>{m[x.k].n++;});
    return {m,mx:Math.max(1,m.d.lots,m.o.lots)};},[lots,v.stops]);
  const K:[Mode,string,string,number,string,string,string][]=[
    ['lots','','조사 범위 내 Lot Scan 완료',lots.length,'Lot','S/M 영문 3글자 + Lot ID 기준','Lot 단위 Scan List 보기 →'],
    ['reports','','조사 범위 내 Batch Report 존재',R.length,'개',`Lot ${R.length-chk} · 점검 스캔 ${chk}`,'Batch Report 목록 · 누르면 원문 →'],
    ['re','k-re','재스캔으로 완료된 Lot',kpi.re,'Lot','Error · 작업자 중단 뒤 재스캔하여 Pass','목록 보기 →'],
    ['open','k-open','Pass하지 못한 Lot',kpi.open,'Lot','다른 호기에서 Scan되었는지 확인 필요','목록 보기 →'],
    ['dup','k-dup','중복 Scan한 wafer가 존재하는 Lot',kpi.dup,'Lot','같은 wafer를 Pass 후 다시 스캔','목록 보기 →']];
  const chips:[string,string,()=>void][]=[];
  if(period)chips.push(['period','기간 '+period,()=>setPeriod(null)]);
  if(dupOnly)chips.push(['dup','중복 Scan한 wafer가 존재하는 Lot',()=>setMode('lots')]);
  if(cause)chips.push(['cause',cause.startsWith('__stop_')?STOPK[cause.slice(7)]:'Error '+cause,()=>setCause(null)]);
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
    <div className={'section-heading listhead lt-'+on}><div><span className="step">지금 보는 목록</span><h2 ref={listTop} key={on} className="listtitle">{TITLE[on]}</h2>
      <p className="sub">{lotMode?(SUB[on]||'조사 범위 내 Scan된 Lot 전체')+' · Lot을 누르면 새 창(Lot 창)에서 Lot History'
        :'조사 범위 내 Batch Report 전체 · 행을 누르면 Batch Report 원문 창(그 1장의 표 그대로), Lot 이름을 누르면 Lot 창(그 Lot의 모든 Batch Report를 모은 Lot History)'}</p></div>
      <span className="count">{lotMode?`${rows.length} / ${lots.length} Lot`:`${reports.length} / ${R.length}개`}</span></div>
    {lotMode?<div className="filters"><input type="search" value={q} onChange={e=>setQ(e.target.value)} placeholder="Lot 코드 · S/M · Lot ID · Job 검색" aria-label="Lot 검색"/>
      <select aria-label="상태" value={state} onChange={e=>setState(e.target.value)}><option value="">전체 상태</option>{STATES.map(s=><option key={s}>{s}</option>)}</select>
      <label title="같은 Lot을 2번 이상 이어서 스캔한 Lot (Error 재스캔 · 나눠 스캔)"><input type="checkbox" checked={fRe} onChange={e=>setFRe(e.target.checked)}/> 재스캔</label>
      <label title="다른 호기로 옮겨 이어서 스캔한 Lot"><input type="checkbox" checked={fMove} onChange={e=>setFMove(e.target.checked)}/> 호기 이동</label>
      <span className="chips">{chips.map(([k,t,clear])=><button key={k} type="button" className="chip" onClick={clear}>{t} <i aria-hidden="true">✕</i></button>)}</span></div>
    :<div className="filters"><input type="search" value={repQ} onChange={e=>setRepQ(e.target.value)} placeholder="파일 이름 · S/M · Lot 검색" aria-label="Batch Report 검색"/>
      <select aria-label="결과" value={repRes} onChange={e=>setRepRes(e.target.value)}><option value="">전체 결과</option><option value="err">Error 있음</option><option value="stop">작업자 중단</option><option value="ok">모두 Pass</option></select>
      <select aria-label="종류" value={repKind} onChange={e=>setRepKind(e.target.value)}><option value="">Lot + 점검 스캔</option><option value="lot">Lot만</option><option value="chk">점검 스캔만</option></select></div>}
    <div className="table-scroll" style={{maxHeight:470}}><table className="t-compact">
      {lotMode?<><thead><tr><th>Lot</th><th>S/M</th><th>호기</th><th className="num">Batch Report</th><th>처음 스캔</th><th>마지막 스캔</th><th>상태</th><th className="num">Pass하지 못한 wafer</th><th className="num">재스캔 Pass wafer</th><th className="num">중복 Scan wafer</th><th>주요 Error 원문(wafer 수)</th></tr></thead>
        <tbody>{rows.slice(0,2000).map(([l,i])=><tr key={i} className="clickable" onClick={()=>openLot(i)}><td><b>{l.label}</b></td><td>{l.sms.join(', ')}</td><td>{l.machines.join(' → ')}</td><td className="num">{l.n}</td><td>{l.s}</td><td>{l.e}</td>
          <td><StPill s={l.state}/>{l.moved&&<> <span className="st mv">호기 이동</span></>}{l.sz.length>0&&<> <span className={'st '+(l.sz.some(x=>x[0]==='d')?'sd':'so')} title="앞 Error 없이 Aborted.로 멈춘 스캔이 있습니다(Error 아님)">작업자 중단</span></>}{l.scans.includes('3D')&&<> <span className="st s3d" title="S/M에 3D가 붙은 3D 스캔이 있습니다 — 2D와 따로 셉니다">3D 스캔 포함</span></>}</td><td className="num v4">{l.open||''}</td><td className="num v2">{l.re||''}</td><td className="num v3">{l.dup||''}</td><td>{l.causes.map(c=>c[0]+' ×'+c[1]).join(' · ')}</td></tr>)}
          {!rows.length&&<tr><td colSpan={11}>조건에 맞는 Lot이 없습니다.</td></tr>}</tbody></>
      :<><thead><tr><th>시작</th><th>끝</th><th>호기</th><th>S/M</th><th title="누르면 Lot 창">Lot</th><th>공정 단계(Recipe(s))</th><th className="num">Pass / 행</th><th>첫 Error 원문 · 중단</th><th>파일 이름</th><th/></tr></thead>
        <tbody>{reports.slice(0,2000).map(([r,i])=><tr key={i} className="clickable" onClick={()=>showRaw(i)}><td>{r.s}</td><td>{r.e.slice(11)}</td><td>{r.m}</td><td>{r.sm}</td>
          <td>{r.lot!=null?<button type="button" className="linklike" title="Lot 창 열기 — 이 Lot의 모든 Batch Report를 모은 Lot History" onClick={e=>{e.stopPropagation();openLot(r.lot!);}}>{lots[r.lot].label}</button>:<span className="st out">점검 스캔</span>}</td>
          <td>{stepLabel(r)}{is3D(r.k)&&<> <span className="st s3d">3D</span></>}</td><td className="num">{r.ok} / {r.n}{r.sp?<small className="muted"> (스캔 안 함 {r.sp})</small>:null}</td><td className={r.fe?'v4':''}>{r.fe||(r.o==='s'?<span className={'st '+(r.sk==='d'?'sd':'so')} title={`앞 Error 없이 Aborted. — 멈출 때 wafer Faults ${r.ff??'—'}`}>{STOPK[r.sk||'o']}</span>:'')}</td><td className="mono">{r.f}</td><td><button type="button" style={small} onClick={e=>{e.stopPropagation();showRaw(i);}}>원문 보기</button></td></tr>)}
          {!reports.length&&<tr><td colSpan={10}>조건에 맞는 Batch Report가 없습니다.</td></tr>}</tbody></>}
    </table></div>
    {(lotMode?rows.length:reports.length)>2000&&<p className="hint">처음 2,000행만 보여 줍니다. 검색 · 필터로 좁혀 보세요.</p>}
    <section className="card2"><div className="section-heading"><div><h2>멈춘 이유 요약 <Q id="lot.reasons"/></h2><p className="sub">개수는 모두 <b>Lot</b> 기준 · 행을 누르면 그 Lot만 위 목록에</p></div><span className="grow"/>
        <Seg label="멈춘 이유" value={why} items={[['err',`Error ${causes.keys.length}종`],['stop',`작업자 중단 ${stops.m.d.n+stops.m.o.n}건`]]} onChange={setWhy}/></div>
      <div className="keys"><span><i style={{background:C_OK}}>　</i> 재스캔하여 Pass한 Lot</span><span><i style={{background:C_ERR}}>　</i> Pass하지 못한 Lot</span></div>
      {why==='err'?<div className="table-scroll" style={{maxHeight:380}}><table className="t-compact"><thead><tr><th>Error 원문(첫 문구)</th><th className="num">Lot</th><th/><th className="num" title="이 Error가 난 wafer가 모두 재스캔으로 Pass한 Lot">재스캔하여 Pass한 Lot</th><th className="num" title="이 Error가 난 wafer 중 끝까지 Pass하지 못한 wafer가 있는 Lot">Pass하지 못한 Lot</th><th className="num">wafer</th></tr></thead>
        <tbody>{causes.keys.map(k=>{const t=causes.m[k];return <tr key={k} className="clickable" onClick={()=>{setMode('lots');setState('');setPeriod(null);setCause(k);listTop.current?.scrollIntoView({behavior:'smooth',block:'start'});}}>
          <td><b>{k}</b></td><td className="num"><b>{t.lots}</b></td><td><span className="ebar" data-tip={`${k}\nLot ${t.lots}개\n재스캔하여 Pass한 Lot ${t.ok}\nPass하지 못한 Lot ${t.open}\n누르면 이 Lot들만 목록에`}>
            <span style={{width:(t.ok/causes.mx*100).toFixed(1)+'%',background:C_OK}}/><span style={{width:(t.open/causes.mx*100).toFixed(1)+'%',background:C_ERR}}/></span></td>
          <td className="num v1">{t.ok}</td><td className="num v4">{t.open||''}</td><td className="num">{t.w}</td></tr>;})}
          {!causes.keys.length&&<tr><td colSpan={6}>Error 없음</td></tr>}</tbody></table></div>
      :<div className="table-scroll" style={{maxHeight:380}}><table className="t-compact"><thead><tr><th>작업자 중단(앞 Error 없는 Aborted.)</th><th className="num">Batch Report</th><th className="num">Lot</th><th/><th className="num">재스캔하여 Pass한 Lot</th><th className="num">Pass하지 못한 Lot</th><th className="num">wafer</th></tr></thead>
        <tbody>{(['d','o'] as const).map(k=>{const t=stops.m[k];return <tr key={k} className="clickable" onClick={()=>{setMode('lots');setState('');setPeriod(null);setCause('__stop_'+k);listTop.current?.scrollIntoView({behavior:'smooth',block:'start'});}}>
          <td><i className="sw" style={{background:k==='d'?C_DEFECT:C_STOP}}/><b>{STOPK[k]}</b>{k==='d'&&<Q id="stop.defect"/>}</td><td className="num">{t.n}</td><td className="num"><b>{t.lots}</b></td>
          <td><span className="ebar"><span style={{width:(t.ok/stops.mx*100).toFixed(1)+'%',background:C_OK}}/><span style={{width:(t.open/stops.mx*100).toFixed(1)+'%',background:C_ERR}}/></span></td>
          <td className="num v1">{t.ok}</td><td className="num v4">{t.open||''}</td><td className="num">{t.w}</td></tr>;})}</tbody></table>
        <p className="hint">작업자가 멈춘 것은 Error로 세지 않습니다. 멈춘 시간은 가동률 · WPH에서 'Error · 중단 및 조치'로 셉니다. <button type="button" className="linklike" onClick={openDefect}>Defect 과다 판정 기준 · 목록 보기</button></p></div>}</section>
    <details className="more"><summary>점검 스캔 (Lot에서 제외) {chk}개</summary><div className="table-scroll" style={{maxHeight:260,marginTop:8}}><table className="t-compact">
      <thead><tr><th>호기</th><th>S/M</th><th>시작</th><th>파일 이름</th><th/></tr></thead>
      <tbody>{v.excluded.map(g=>{const r=R[g];return <tr key={g}><td>{r.m}</td><td>{r.sm}</td><td>{r.s}</td><td className="mono">{r.f}</td><td><button type="button" style={small} onClick={()=>showRaw(g)}>원문 보기</button></td></tr>;})}</tbody></table></div></details>
  </section>;
}
