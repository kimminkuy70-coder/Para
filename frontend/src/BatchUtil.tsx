import {useEffect,useMemo,useRef,useState,type ReactNode} from 'react';
import {Legend,Seg,useWidth,type Key,type TipX} from './BatchCharts';
import {Q,openDefect} from './BatchHelp';
import {addDays,bucket,dur,hrs,mins,num,pad,ts,weekday,periodName,shortKey,sumU,lossOf,pctOf,emptyAgg,addU,
  C_PROC,C_LOSS,C_IDLE,C_ERR,C_OK,C_WAIT,C_STOP,C_DEFECT,C_CHECK,STOPK,type View,type Unit,type Agg,type U} from './batchData';

/* 가동률 탭 — 호기마다 하루 24시간 = 웨이퍼 처리 + Error · 중단 및 조치 + 유휴(사용자 확정 2026-10-05).
   화면은 숫자 4개 + 그래프 1개. 자세한 것은 기간 상세 창(새 창), 계산식은 ? 버튼. */
const KEYS:Key[]=[{k:'proc',label:'웨이퍼 처리',c:C_PROC},{k:'loss',label:'Error · 중단 및 조치',c:C_LOSS},{k:'idle',label:'유휴',c:C_IDLE}];
type Comp={proc:number;loss:number;idle:number;cal:number;a:Agg};
const comp=(a:Agg,cal:number):Comp=>{const proc=a.p+a.ck,loss=lossOf(a);return {proc,loss,idle:Math.max(0,cal-proc-loss),cal,a};};
const pc=(x:number,t:number)=>num(pctOf(x,t),1)+'%';
function tipOf(title:string,c:Comp,foot?:string):TipX{
  return {t:title,rows:[[C_PROC,'웨이퍼 처리',hrs(c.proc),'h · '+pc(c.proc,c.cal)],[C_LOSS,'Error · 중단 및 조치',hrs(c.loss),'h · '+pc(c.loss,c.cal)],
    [C_IDLE,'유휴',hrs(c.idle),'h · '+pc(c.idle,c.cal)],['transparent','달력 시간',hrs(c.cal),'h']],f:foot?[foot]:undefined};}
const tipText=(x:TipX)=>[x.t,...x.rows.map(r=>`${r[1]} ${r[2]}${r[3]||''}`),...(x.f||[])].join('\n');
function Stack({c,hid,big}:{c:Comp;hid:Record<string,boolean>;big?:boolean}){
  return <span className={'stack'+(big?' big':'')}>{KEYS.map(k=>{const x=c[k.k as 'proc'|'loss'|'idle'];return !hid[k.k]&&x>0?<span key={k.k} style={{width:(x/c.cal*100).toFixed(2)+'%',background:k.c}}/>:null;})}</span>;
}
/** 범위 안 날짜 목록 */
function rangeDays(from:string,to:string){const out:string[]=[];if(!from||!to)return out;for(let d=from;d<=to;d=addDays(d,1))out.push(d);return out;}

export function UtilTab({v,ids,range,openLot,showRaw}:{v:View;ids:string[];range:{from:string;to:string};openLot:(li:number)=>void;showRaw:(g:number)=>void}){
  const [unit,setUnit]=useState<Unit>('w'),[hid,setHid]=useState<Record<string,boolean>>({}),[mach,setMach]=useState('all');
  const [view,setView]=useState<'comp'|'time'>('comp'),[by,setBy]=useState<'m'|'p'>('m'),[win,setWin]=useState<{key:string;use:string[]}|null>(null);
  const [tDay,setTDay]=useState<string|null>(null);
  const m=mach!=='all'&&!ids.includes(mach)?'all':mach;
  const use=m==='all'?ids:[m],nm=Math.max(1,use.length);
  const days=useMemo(()=>rangeDays(range.from,range.to),[range.from,range.to]);
  const rows=useMemo(()=>v.U.filter(u=>u.d>=range.from&&u.d<=range.to),[v,range.from,range.to]);
  const mine=rows.filter(u=>use.includes(u.m));
  const all=comp(sumU(mine),days.length*86400*nm);
  // 기간별(단위) — 범위 밖 날짜는 달력 시간에서 뺀다
  const periods=useMemo(()=>{const o:Record<string,{days:number;a:Agg}>={};days.forEach(d=>{const k=bucket(d,unit);(o[k]||(o[k]={days:0,a:emptyAgg()})).days++;});
    mine.forEach(u=>{const k=bucket(u.d,unit);if(o[k])addU(o[k].a,u);});return Object.entries(o).sort((a,b)=>a[0]<b[0]?1:-1);},[mine,days,unit]);
  const machines=useMemo(()=>ids.map(id=>[id,comp(sumU(rows.filter(u=>u.m===id)),days.length*86400)] as const),[ids,rows,days]);
  const U_={d:'일',w:'주',m:'월'}[unit];
  const K:[string,string,string,string,string[]][]=[
    ['util.rate','가동률',num(pctOf(all.proc,all.cal),1),'%',[`웨이퍼 처리 ${hrs(all.proc)}시간 ÷ 달력 시간 ${hrs(all.cal)}시간 = ${pc(all.proc,all.cal)}`]],
    ['util.loss','Error · 중단 및 조치',num(pctOf(all.loss,all.cal),1),'%',[`Error ${hrs(all.a.e)}시간 + 작업자 중단 ${hrs(all.a.sd+all.a.so)}시간(Defect 과다 ${hrs(all.a.sd)} · 그 외 ${hrs(all.a.so)}) = ${hrs(all.loss)}시간`,`${hrs(all.loss)} ÷ ${hrs(all.cal)} = ${pc(all.loss,all.cal)}`]],
    ['util.idle','유휴',num(pctOf(all.idle,all.cal),1),'%',[`${hrs(all.cal)} − ${hrs(all.proc)} − ${hrs(all.loss)} = ${hrs(all.idle)}시간 (${pc(all.idle,all.cal)})`]],
    ['util.cal','달력 시간',hrs(all.cal),'h',[`24시간 × ${days.length}일 × ${nm}대 = ${hrs(all.cal)}시간`]]];
  const dataDays=useMemo(()=>{const s:Record<string,1>={};v.R.forEach(r=>{if(r.s&&use.includes(r.m))s[r.s.slice(0,10)]=1;});return days.filter(d=>s[d]);},[v,use.join('|'),days]); // eslint-disable-line react-hooks/exhaustive-deps
  const day=tDay&&dataDays.includes(tDay)?tDay:dataDays[dataDays.length-1]||'';
  // 호기 탭의 시간표 = 고른 날이 든 주(월 ~ 일)
  const week=useMemo(()=>{if(!day)return [];const dt=new Date(day+'T00:00:00'),w=(dt.getDay()+6)%7,st=addDays(day,-w);return Array.from({length:7},(_,i)=>addDays(st,i)).filter(d=>d>=range.from&&d<=range.to);},[day,range.from,range.to]);
  const step=(k:number)=>{if(m==='all'){const i=dataDays.indexOf(day)+k;if(i>=0&&i<dataDays.length)setTDay(dataDays[i]);}
    else{const target=addDays(day,7*k);const cand=k>0?dataDays.find(d=>d>=target):[...dataDays].reverse().find(d=>d<=target);if(cand)setTDay(cand);}};
  return <section className="panel tabpanel" aria-label="가동률">
    <div className="section-heading"><div><span className="step">가동률</span><h2>호기는 얼마나 바빴고, 무엇으로 시간을 잃었나</h2></div>
      <Seg label="기간 단위" value={unit} items={[['d','일'],['w','주'],['m','월']]} onChange={setUnit}/></div>
    <div className="mtabs" role="tablist" aria-label="호기별 보기"><button type="button" role="tab" className={m==='all'?'on':''} aria-selected={m==='all'} onClick={()=>setMach('all')}>전체 호기 <small>{ids.length}대</small></button>
      {ids.map(id=><button key={id} type="button" role="tab" className={m===id?'on':''} aria-selected={m===id} onClick={()=>setMach(id)}>{id}</button>)}</div>
    <section className="kpis k4">{K.map(([id,l,val,u,calc],i)=><article key={id} className={'kq k'+i}><span>{i<3&&<i className="sw" style={{background:KEYS[i].c}}/>}{l}<Q id={id} calc={calc}/></span><strong>{val}<small>{u}</small></strong>
      <p>{i===3?`${days.length}일 × ${nm}대 · 하루 24시간`:hrs([all.proc,all.loss,all.idle][i])+'시간'}</p></article>)}</section>
    <div className="viewbar"><Seg label="보기" value={view} items={[['comp','시간 구성'],['time','24시간 시간표']]} onChange={setView}/>
      {view==='comp'&&m==='all'&&<Seg label="나눠 보기" value={by} items={[['m','호기별'],['p','기간별']]} onChange={setBy}/>}<span className="grow"/>
      {view==='comp'&&<Legend keys={KEYS} hidden={hid} onToggle={k=>setHid(h=>({...h,[k]:!h[k]}))}/>}</div>
    {view==='comp'?<div className="chartcard">
      {m==='all'&&by==='m'?<><div className="ch"><h3>호기별 시간 구성 <small>{range.from} ~ {range.to}</small></h3><span className="hint">마우스 = 값 · 누르면 그 호기</span></div>
        <div className="prows"><div className="prow head"><span>호기</span><span>100% = 24시간 × {days.length}일</span><span>가동률</span></div>
          {machines.map(([id,c])=>{const x=tipOf(id,c,'누르면 이 호기 탭으로');return <div key={id} className="prow" data-tip={tipText(x)} data-tipx={JSON.stringify(x)} onClick={()=>setMach(id)}>
            <span className="pl">{id}</span><Stack c={c} hid={hid}/><span className="pv">{pc(c.proc,c.cal)}</span></div>;})}</div></>
      :<><div className="ch"><h3>기간별 시간 구성 <small>{U_} · {m==='all'?'전체 호기':m}</small></h3><span className="hint">마우스 = 값 · 누르면 그 기간 상세 창</span></div>
        <div className="prows" style={{maxHeight:560,overflow:'auto'}}><div className="prow head"><span>기간</span><span>100% = {nm>1?nm+'대 × ':''}24시간 × 일수</span><span>가동률</span></div>
          {periods.map(([k,o])=>{const c=comp(o.a,o.days*86400*nm),x=tipOf(periodName(k,unit),c,'누르면 이 기간 상세 창');
            return <div key={k} className="prow" data-tip={tipText(x)} data-tipx={JSON.stringify(x)} onClick={()=>setWin({key:k,use})}>
              <span className="pl">{unit==='w'?shortKey(k,unit)+' '+k.slice(5,10):k}</span><Stack c={c} hid={hid}/><span className="pv">{pc(c.proc,c.cal)}</span></div>;})}
          {!periods.length&&<p className="hint">조사 범위에 자료가 없습니다.</p>}</div></>}
    </div>
    :<div className="chartcard"><div className="ch"><h3>24시간 시간표 — {m==='all'?`${day} (${day?weekday(day):''}) · 호기별`:`${m} · ${week[0]?.slice(5)||''} ~ ${week[week.length-1]?.slice(5)||''}`}</h3>
        <Q id="util.timetable"/><span className="grow"/>
        <span className="ttnav"><button type="button" aria-label={m==='all'?'전날':'전주'} onClick={()=>step(-1)}>◀</button>
          <select aria-label="날짜" value={day} onChange={e=>setTDay(e.target.value)}>{dataDays.map(d=><option key={d}>{d}</option>)}</select>
          <button type="button" aria-label={m==='all'?'다음날':'다음주'} onClick={()=>step(1)}>▶</button></span></div>
      <TimeTable v={v} rows={m==='all'?ids.map(id=>({label:id,day,m:id})):week.map(d=>({label:d.slice(5)+' ('+weekday(d)+')',day:d,m}))} openLot={openLot} showRaw={showRaw}/></div>}
    {win&&<PeriodWindow v={v} k={win.key} unit={unit} use={win.use} range={range} openLot={openLot} showRaw={showRaw} onClose={()=>setWin(null)}/>}
  </section>;
}

/** 기간 상세 창 — 시간 구성 · 손실 이유 · 24시간 시간표. */
function PeriodWindow({v,k,unit,use,range,openLot,showRaw,onClose}:{v:View;k:string;unit:Unit;use:string[];range:{from:string;to:string};
  openLot:(li:number)=>void;showRaw:(g:number)=>void;onClose:()=>void}){
  const ref=useRef<HTMLDialogElement>(null);
  const [tab,setTab]=useState<'comp'|'loss'|'time'>('comp'),[sel,setSel]=useState<string|null>(null),[tDay,setTDay]=useState<string|null>(null);
  useEffect(()=>{const d=ref.current;if(d&&!d.open)d.showModal();},[]);
  const days=rangeDays(range.from,range.to).filter(d=>bucket(d,unit)===k),nm=use.length;
  const a=sumU(v.U.filter((u:U)=>use.includes(u.m)&&bucket(u.d,unit)===k&&u.d>=range.from&&u.d<=range.to));
  const c=comp(a,days.length*86400*nm);
  const recs=Object.entries(a.rec).sort((x,y)=>y[1]-x[1]),rt=recs.reduce((s,x)=>s+x[1],0)||1;
  const reasons:[string,string,number,number[],string][]=[...Object.entries(a.err).map(([e,t])=>[e,e,t[0],Object.keys(t[2]).map(Number),C_ERR] as [string,string,number,number[],string]),
    ['__d',STOPK.d,a.sd,Object.keys(a.sdl).map(Number),C_DEFECT],['__o',STOPK.o,a.so,Object.keys(a.sol).map(Number),C_STOP]];
  const rs=reasons.filter(x=>x[2]>0).sort((x,y)=>y[2]-x[2]),rmx=rs.length?rs[0][2]:1;
  const cur=rs.find(x=>x[0]===sel);
  const dataDays=days.filter(d=>v.R.some(r=>use.includes(r.m)&&r.s.slice(0,10)===d));
  const day=tDay&&dataDays.includes(tDay)?tDay:dataDays[dataDays.length-1]||'';
  const one=use.length===1;
  const line=(color:string,label:string,x:number,help?:string,sub?:boolean)=><div key={label} className={sub?'sub':''}><i style={{background:color}}/><span>{label}{help&&<Q id={help}/>}</span><b>{hrs(x)}h</b><em>{pc(x,c.cal)}</em></div>;
  return <dialog className="lotwin" ref={ref} aria-labelledby="pwTitle" onClose={onClose}>
    <div className="lw-head"><div><span className="step">기간 상세 창</span><h2 id="pwTitle">{periodName(k,unit)} · {one?use[0]:`전체 호기 ${nm}대`}</h2></div>
      <div className="lw-actions"><button type="button" className="primary" onClick={()=>ref.current?.close()}>닫기</button></div>
      <div className="lw-meta"><span>달력 시간 {hrs(c.cal)}h ({days.length}일 × {nm}대)</span><span>가동률 <b>{pc(c.proc,c.cal)}</b></span><span>Error · 중단 및 조치 {pc(c.loss,c.cal)}</span><span>유휴 {pc(c.idle,c.cal)}</span></div></div>
    <div className="pilltabs lw-tabs" role="tablist">{([['comp','시간 구성'],['loss','손실 이유'],['time','24시간 시간표']] as const).map(([t,l])=>
      <button key={t} role="tab" type="button" className={tab===t?'active':''} aria-selected={tab===t} onClick={()=>setTab(t)}>{l}</button>)}</div>
    <div className="lw-body">
      {tab==='comp'&&<><Stack c={c} hid={{}} big/>
        <div className="comp">{line(C_PROC,'웨이퍼 처리',c.proc,'util.proc')}{line(C_OK,'그중 같은 wafer 다시 스캔',a.du,undefined,true)}{line(C_CHECK,'그중 점검 스캔',a.ck,undefined,true)}
          {line(C_LOSS,'Error · 중단 및 조치',c.loss,'util.loss')}{line(C_ERR,'Error',a.e,undefined,true)}{line(C_DEFECT,STOPK.d,a.sd,'stop.defect',true)}{line(C_STOP,STOPK.o,a.so,undefined,true)}
          {line(C_IDLE,'유휴',c.idle,'util.idle')}</div>
        <h3>레시피(Job · Recipe(s))별 웨이퍼 처리 시간</h3>
        {recs.length?recs.map(([r,s])=><div key={r} className="hbar" data-tip={`${r}\n웨이퍼 처리 ${hrs(s)}h · ${pc(s,rt)}`}><span className="lab">{r}</span>
          <span className="track"><span style={{width:(s/rt*100).toFixed(1)+'%'}}/></span><span className="val">{pc(s,rt)} · {hrs(s)}h</span></div>):<p className="hint">웨이퍼 처리 없음</p>}</>}
      {tab==='loss'&&<><h3>무엇으로 시간을 잃었나 <small>Batch Report의 남은 시간 + 다시 스캔하기까지 조치 · 막대를 누르면 그 Lot</small><Q id="util.loss"/></h3>
        {rs.length?rs.map(([id,label,s,lots,color])=><div key={id} className={'hbar clickable'+(sel===id?' sel':'')} onClick={()=>setSel(id)}
          data-tip={`${label}\n${hrs(s)}시간 · Lot ${lots.length}개\n누르면 Lot 목록`}><span className="lab">{label}{id==='__d'&&<Q id="stop.defect"/>}</span>
          <span className="track"><span style={{width:(s/rmx*100).toFixed(1)+'%',background:color}}/></span><span className="val">{hrs(s)}h · Lot {lots.length}</span></div>)
          :<p className="hint">잃은 시간이 없습니다.</p>}
        {cur&&<><p className="hint">{cur[1]} — Lot {cur[3].length}개 (누르면 Lot History)</p><div className="chips">{cur[3].slice(0,120).map(li=>
          <button key={li} type="button" className="chip" onClick={()=>openLot(li)}>{v.lots[li].label}</button>)}</div></>}
        <p className="hint" style={{marginTop:14}}>작업자 중단(앞 Error 없는 Aborted.)은 Error가 아니지만 결과를 내지 못한 시간이라 여기에 넣습니다. <button type="button" className="linklike" onClick={openDefect}>Defect 과다 판정 기준 보기</button></p></>}
      {tab==='time'&&<><div className="ch"><h3 style={{margin:0}}>24시간 시간표 — {one?`${use[0]} · 날마다 한 줄`:`${day} (${day?weekday(day):''}) · 호기별`}</h3><Q id="util.timetable"/><span className="grow"/>
          {!one&&<span className="ttnav"><select aria-label="날짜" value={day} onChange={e=>setTDay(e.target.value)}>{dataDays.map(d=><option key={d}>{d}</option>)}</select></span>}</div>
        <TimeTable v={v} rows={one?days.map(d=>({label:d.slice(5)+' ('+weekday(d)+')',day:d,m:use[0]})):use.map(id=>({label:id,day,m:id}))} openLot={openLot} showRaw={showRaw}/></>}
    </div></dialog>;
}

/** 24시간 시간표 — 줄마다 (호기, 날짜) 하나. 막대 = Batch Report(누르면 원문), 아래 줄 = Error · 중단 뒤 조치 대기(누르면 Lot). */
function TimeTable({v,rows,openLot,showRaw}:{v:View;rows:{label:string;day:string;m:string}[];openLot:(li:number)=>void;showRaw:(g:number)=>void}){
  const [ref,width]=useWidth<HTMLDivElement>(1000);
  const R=v.R;
  const byMachine=useMemo(()=>{const o:Record<string,number[]>={};R.forEach((r,g)=>{(o[r.m]||=[]).push(g);});return o;},[R]);
  const W=Math.max(640,width-4),L=100,RH=30,top=24,H=top+rows.length*RH+8,pw=W-L-12;
  const X=(ms:number)=>L+ms/864e5*pw;
  const kind=(g:number):[string,string,string]=>{const r=R[g];return r.lot==null?['점검 스캔',C_CHECK,'out']:r.o==='e'?['Error 포함',C_ERR,'open']
    :r.o==='s'?(r.sk==='d'?[STOPK.d,C_DEFECT,'sd']:[STOPK.o,C_STOP,'so']):['모두 Pass',C_OK,'done'];};
  const svg:ReactNode[]=[];const ev:{t:string;g?:number;w?:number}[]=[];const seen:Record<string,1>={};
  for(let hh=0;hh<=24;hh+=2){const x=L+hh/24*pw;svg.push(<g key={'h'+hh}><line x1={x} x2={x} y1={top-4} y2={H-4} stroke={hh%6?'#eef1f5':'#d5dde6'}/><text x={x} y={top-9} textAnchor="middle">{pad(hh)}시</text></g>);}
  rows.forEach((rw,ri)=>{const y=top+ri*RH,d0=ts(rw.day+' 00:00'),d1=d0+864e5;
    svg.push(<g key={'r'+ri}><rect x={L} y={y+2} width={pw} height={RH-4} fill={ri%2?'#f8fafc':'#fff'} stroke="#e6ebf0"/><text x={L-8} y={y+RH/2+4} textAnchor="end" fontWeight={700}>{rw.label}</text></g>);
    if(!rw.day)return;
    (byMachine[rw.m]||[]).forEach(g=>{const r=R[g];if(!r.s||!r.e)return;const a=ts(r.s),b=ts(r.e);if(b<=d0||a>=d1)return;const k=kind(g),x0=X(Math.max(a,d0)-d0),x1=X(Math.min(b,d1)-d0);
      svg.push(<rect key={'b'+ri+'_'+g} className="ttb" x={x0.toFixed(1)} y={y+5} width={Math.max(2,x1-x0).toFixed(1)} height={RH-17} rx={2} fill={k[1]} data-raw={g}
        data-tip={`${r.s.slice(11)} ~ ${r.e.slice(11)} · ${r.m} · ${k[0]}\n${r.lot!=null?'Lot '+v.lots[r.lot].label+' · ':''}S/M ${r.sm} · ${r.step}\nPass ${r.ok} / ${r.n}행${r.fe?'\n첫 Error: '+r.fe:''}${r.o==='s'?`\n작업자 중단 · 멈출 때 Faults ${r.ff??'—'}`:''}\n${r.f}\n누르면 원문`}/>);
      if(!seen['r'+g]){seen['r'+g]=1;ev.push({t:r.s,g});}});
    v.waits.forEach((w,wi)=>{if(w.m!==rw.m)return;const a=ts(w.s),b=ts(w.e);if(b<=d0||a>=d1)return;const x0=X(Math.max(a,d0)-d0),x1=X(Math.min(b,d1)-d0);
      svg.push(<rect key={'w'+ri+'_'+wi} className="ttw" x={x0.toFixed(1)} y={y+RH-11} width={Math.max(2,x1-x0).toFixed(1)} height={5} rx={1} fill={w.t==='s'?C_STOP:C_WAIT} data-li={w.li}
        data-tip={`${w.t==='s'?'작업자 중단':'Error'} 뒤 조치 대기 · Lot ${v.lots[w.li].label}\n${w.s.slice(5)} → ${w.e.slice(5)} (${dur(mins(w.s,w.e))})\n${w.t==='s'?'중단: '+(R[w.g].sk==='d'?'Defect 과다':'그 외'):'앞 Batch Report 첫 Error: '+(R[w.g].fe||'—')}\n그 사이 다른 스캔 시간은 빼고 셉니다\n누르면 Lot History`}/>);
      if(!seen['w'+wi]){seen['w'+wi]=1;ev.push({t:w.s,w:wi});}});});
  ev.sort((a,b)=>a.t<b.t?-1:a.t>b.t?1:0);
  const click=(e:React.MouseEvent)=>{const t=e.target as Element,l=t.closest('[data-li]');if(l){openLot(+l.getAttribute('data-li')!);return;}const r=t.closest('[data-raw]');if(r)showRaw(+r.getAttribute('data-raw')!);};
  return <>
    <div className="keys" style={{marginTop:0}}><span><i style={{background:C_OK}}>　</i> 모두 Pass</span><span><i style={{background:C_ERR}}>　</i> Error 포함</span>
      <span><i style={{background:C_DEFECT}}>　</i> {STOPK.d}</span><span><i style={{background:C_STOP}}>　</i> {STOPK.o}</span><span><i style={{background:C_CHECK}}>　</i> 점검 스캔</span>
      <span><i style={{background:C_WAIT}}>　</i> 아래 줄 = 조치 대기(Error 뒤)</span><span><i style={{background:C_STOP}}>　</i> 아래 줄 = 조치 대기(중단 뒤)</span><span>빈칸 = 유휴</span></div>
    <div className="chart" ref={ref} onClick={click}><div className="chartscroll"><svg width={W} height={H} role="img" aria-label="24시간 시간표">{svg}</svg></div></div>
    <details className="more" onClick={click}><summary>이 시간표의 Batch Report · 조치 대기 목록 ({ev.length}건)</summary>
      <div className="table-scroll" style={{maxHeight:360,marginTop:8}}><table className="t-compact"><thead><tr><th>시작</th><th>끝</th><th>호기</th><th>한 일</th><th>Lot</th><th>S/M</th><th className="num">Pass / 행</th><th>첫 Error 원문 · 중단</th><th className="num">시간</th></tr></thead>
        <tbody>{ev.map(x=>{if(x.w!=null){const w=v.waits[x.w];return <tr key={'w'+x.w} className="clickable" data-li={w.li}><td>{w.s}</td><td>{w.e.slice(5)}</td><td>{w.m}</td><td><span className="st re">조치 대기</span></td>
            <td><b>{v.lots[w.li].label}</b></td><td/><td/><td>{w.t==='s'?'작업자 중단 뒤':R[w.g].fe}</td><td className="num">{dur(mins(w.s,w.e))}</td></tr>;}
          const r=R[x.g!],k=kind(x.g!);return <tr key={'r'+x.g} className="clickable" data-raw={x.g}><td>{r.s}</td><td>{r.e.slice(5)}</td><td>{r.m}</td><td><span className={'st '+k[2]}>{k[0]}</span></td>
            <td>{r.lot!=null&&<button type="button" className="linklike" data-li={r.lot}>{v.lots[r.lot].label}</button>}</td><td>{r.sm}</td><td className="num">{r.ok} / {r.n}</td>
            <td className={r.fe?'v4':''}>{r.fe||(r.o==='s'?`Aborted. · Faults ${r.ff??'—'}`:'')}</td><td className="num">{dur(r.sec/60)}</td></tr>;})}
          {!ev.length&&<tr><td colSpan={9}>이 범위에 스캔 기록이 없습니다.</td></tr>}</tbody></table></div></details></>;
}
