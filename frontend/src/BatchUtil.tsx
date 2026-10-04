import {useMemo,useState,type ReactNode} from 'react';
import {Legend,Seg,useWidth,type Key} from './BatchCharts';
import {addDays,bucket,bucketDays,dur,hrs,mins,num,pad,ts,weekday,C_OK,C_ERR,C_WAIT,type View,type Unit} from './batchData';

/* 가동률 · 원인 탭 — 달력 시간 = 유효 스캔 + Error·중복 스캔 + 재스캔 전 대기 + 점검 스캔 + 기타.
   호기 탭(전체 호기 · 호기마다), 기간 행을 누르면 오른쪽 상세, 24시간 시간표. */
const UK:(Key&{d:string})[]=[{k:'valid',label:'유효 스캔',c:C_OK,d:'최종 결과로 쓰는 wafer를 스캔한 시간'},
  {k:'dropped',label:'Error·중복 스캔',c:C_ERR,d:'스캔은 했지만 Error가 났거나, 이미 Pass한 wafer를 다시 스캔해 최종 결과에 쓰이지 않은 시간'},
  {k:'wait',label:'재스캔 전 대기',c:C_WAIT,d:'Error 뒤 같은 Lot을 다시 스캔하기까지 장비가 아무것도 스캔하지 않은 시간'},
  {k:'check',label:'점검 스캔',c:'#94a3b8',d:'Lot이 아닌 점검 스캔(S/M 0 · FOCUS 등)'},
  {k:'other',label:'기타(구분 불가)',c:'#dfe5ec',d:'Batch Report가 없는 시간 — 대기 · PM · 셋업 · 전원 OFF'}];
type Agg={valid:number;dropped:number;wait:number;check:number;rec:Record<string,number>;err:Record<string,[number,number,Record<number,1>,number]>};
type Comp={valid:number;dropped:number;wait:number;check:number;other:number};
const small={minHeight:26,padding:'2px 9px',fontSize:12} as const;

export function UtilTab({v,ids,range,openLot,showRaw}:{v:View;ids:string[];range:{from:string;to:string};openLot:(li:number)=>void;showRaw:(g:number)=>void}){
  const [unit,setUnit]=useState<Unit>('w'),[sel,setSel]=useState<string|null>(null),[hid,setHid]=useState<Record<string,boolean>>({});
  const [mach,setMach]=useState('all'),[tDay,setTDay]=useState<string|null>(null),[errSel,setErrSel]=useState<string|null>(null);
  const m=mach!=='all'&&!ids.includes(mach)?'all':mach;
  const days=useMemo(()=>{const s:Record<string,1>={};v.R.forEach(r=>{if(r.s)s[r.m+'|'+r.s.slice(0,10)]=1;});return s;},[v]);
  function agg(use:string[],whole:boolean){const by:Record<string,Agg>={},order:string[]=[];
    v.B.forEach(x=>{if(!use.includes(x.m)||x.d<range.from||x.d>range.to)return;const k=whole?'all':bucket(x.d,unit);
      if(!by[k]){by[k]={valid:0,dropped:0,wait:0,check:0,rec:{},err:{}};order.push(k);}const b=by[k];
      b.valid+=x.valid;b.dropped+=x.dropped;b.wait+=x.wait;b.check+=x.check;
      Object.entries(x.rec).forEach(([r,s])=>{b.rec[r]=(b.rec[r]||0)+s;});
      Object.entries(x.err).forEach(([e,s])=>{const t=b.err[e]||(b.err[e]=[0,0,{},0]);t[0]+=s[0];t[1]+=s[1];t[3]+=s[3]||0;s[2].forEach(li=>{t[2][li]=1;});});});
    order.sort();return {by,order};}
  const comp=(b:Agg|undefined,cal:number):Comp=>{const x=b||{valid:0,dropped:0,wait:0,check:0};return {valid:x.valid,dropped:x.dropped,wait:x.wait,check:x.check,other:Math.max(0,cal-x.valid-x.dropped-x.wait-x.check)};};
  const stack=(c:Comp,cal:number)=>UK.map(k=>{const x=c[k.k as keyof Comp]||0;return !hid[k.k]&&x>0?<span key={k.k} style={{width:(x/cal*100).toFixed(2)+'%',background:k.c}}/>:null;});
  const compTip=(title:string,c:Comp,cal:number)=>title+`  (달력 ${hrs(cal)}h)\n`+UK.map(k=>`${k.label} ${hrs(c[k.k as keyof Comp])}h · ${num(c[k.k as keyof Comp]/cal*100,1)}%`).join('\n');
  function periodDays(k:string|null){if(!k)return [];if(unit==='d')return [k];const st=unit==='m'?k+'-01':k.slice(0,10),n=unit==='m'?bucketDays(k,'m'):7,out:string[]=[];
    for(let i=0;i<n;i++){const d=addDays(st,i);if(d>=range.from&&d<=range.to)out.push(d);}return out;}
  function dataDays(use:string[]){const out:string[]=[];if(!range.from||!range.to)return out;for(let d=range.from;d<=range.to;d=addDays(d,1)){if(use.some(x=>days[x+'|'+d]))out.push(d);}return out;}
  const use=m==='all'?ids:[m],nm=Math.max(1,use.length),{by,order}=agg(use,false);
  const cur=sel&&by[sel]?sel:order.length?order[order.length-1]:null;
  const U={d:'일',w:'주',m:'월'}[unit];
  const tot={cal:0,valid:0,dropped:0,wait:0,check:0};
  const rows=order.slice().reverse().map(k=>{const cal=bucketDays(k,unit)*86400*nm,c=comp(by[k],cal);tot.cal+=cal;tot.valid+=c.valid;tot.dropped+=c.dropped;tot.wait+=c.wait;tot.check+=c.check;
    return <div key={k} className={'prow'+(cur===k?' sel':'')} data-tip={compTip(k,c,cal)+'\n누르면 오른쪽에 이 기간 상세'} onClick={()=>{setSel(k);setErrSel(null);
      const dd=dataDays(use).filter(d=>periodDays(k).includes(d));if(dd.length)setTDay(dd[dd.length-1]);}}>
      <span className="pl">{k}</span><span className="stack">{stack(c,cal)}</span><span className="pv">{num(c.valid/cal*100,1)}%</span></div>;});
  const cal=tot.cal||1;
  const K:[string,string,string,string][]=[['달력 시간',hrs(tot.cal),'h',`${order.length}개 ${U}${nm>1?' × '+nm+'대':''}`],['유효 스캔',num(tot.valid/cal*100,1),'%',hrs(tot.valid)+'h · 최종 결과로 쓰는 wafer'],
    ['Error·중복 스캔',hrs(tot.dropped),'h','Error · 다시 스캔한 Pass wafer 몫'],['재스캔 전 대기',hrs(tot.wait),'h','Error 뒤 같은 Lot 다시 스캔까지'],
    ['기타(구분 불가)',num(Math.max(0,tot.cal-tot.valid-tot.dropped-tot.wait-tot.check)/cal*100,1),'%','대기 · PM · 셋업 · 전원 OFF']];
  const rangeDays=range.from&&range.to?Math.round((ts(range.to+' 00:00')-ts(range.from+' 00:00'))/864e5)+1:1;
  // 오른쪽 상세
  const b=cur?by[cur]:undefined,dcal=cur?bucketDays(cur,unit)*86400*nm:1,dc=comp(b,dcal);
  const rec=b?.rec||{},rt=Object.values(rec).reduce((a,x)=>a+x,0)||1,err=b?.err||{};
  const ek=Object.keys(err).sort((a,c)=>(err[c][0]+err[c][1])-(err[a][0]+err[a][1]));
  return <section className="panel tabpanel" aria-label="가동률 · 원인">
    <div className="section-heading"><div><span className="step">가동률 · 원인</span><h2>호기 가동률과 낮은 이유</h2></div>
      <Seg label="기간 단위" value={unit} items={[['d','일'],['w','주'],['m','월']]} onChange={u=>{setUnit(u);setSel(null);}}/></div>
    <div className="mtabs" role="tablist" aria-label="호기별 보기"><button type="button" role="tab" className={m==='all'?'on':''} aria-selected={m==='all'} onClick={()=>setMach('all')}>전체 호기 <small>{ids.length}대</small></button>
      {ids.map(id=><button key={id} type="button" role="tab" className={m===id?'on':''} aria-selected={m===id} onClick={()=>setMach(id)}>{id}</button>)}</div>
    <div className="terms">{UK.map(k=><div key={k.k}><b><i style={{background:k.c}}/>{k.label}</b><p>{k.d}</p></div>)}</div>
    <details className="logic"><summary>로직 · 가동률</summary><ol>
      <li>달력 시간(호기마다 하루 24시간) = <b>유효 스캔</b> + <b>Error·중복 스캔</b> + <b>재스캔 전 대기</b> + 점검 스캔 + <b>기타</b>.</li>
      <li>Batch Report 1장의 Batch Time을 Dice가 있는 wafer 행 수로 똑같이 나눠 <b>wafer 1장 몫</b>을 구합니다. 최종 결과로 쓰는 wafer 몫 = 유효 스캔, Error가 난 wafer 몫과 이미 Pass한 wafer를 다시 스캔한 몫 = Error·중복 스캔입니다. Dice 있는 행이 없으면(예: 전부 Nothing to Scan.) Batch Time 전부를 Error 행 비율로 나눕니다.</li>
      <li><b>Error 원문별 시간</b>: 한 Batch Report에 Error가 여러 종류 섞여 있어도 wafer마다 자기 Error 원문(첫 문구)으로 따로 셉니다. 앞 Error 뒤 따라온 Aborted · Skipped(연쇄)는 그 앞 Error 원문으로 셉니다.</li>
      <li><b>재스캔 전 대기</b> = Error 뒤 같은 호기에서 같은 Lot을 다시 스캔하기까지 걸린 시간 중 <b>장비가 아무것도 스캔하지 않은 시간</b>(그 사이 다른 Lot을 스캔했으면 뺌). 앞 Batch Report의 Error wafer 원문 비율로 나눠 셉니다.</li>
      <li>자정을 넘긴 스캔 · 대기 시간은 날마다 나눠 넣습니다. 기타 = 나머지(대기 · PM · 셋업 · 전원 OFF — Batch Report로 구분 불가).</li></ol></details>
    <section className="kpis k5">{K.map(([l,val,u,s])=><article key={l}><span>{l}</span><strong>{val}<small>{u}</small></strong><p>{s}</p></article>)}</section>
    {m==='all'&&<div className="chartcard"><div className="ch"><h3>호기별 가동률 비교</h3><span className="hint">조사 기간 전체 · 행을 누르면 그 호기 탭으로</span></div>
      <div className="prows"><div className="prow head"><span>호기</span><span>달력 시간 구성 ({range.from} ~ {range.to})</span><span>유효 스캔</span></div>
        {ids.map(id=>{const rc=rangeDays*86400,c=comp(agg([id],true).by.all,rc);return <div key={id} className="prow" data-tip={compTip(id,c,rc)+'\n누르면 이 호기 탭으로'} onClick={()=>setMach(id)}>
          <span className="pl">{id}</span><span className="stack">{stack(c,rc)}</span><span className="pv">{num(c.valid/rc*100,1)}%</span></div>;})}</div></div>}
    <div className="split">
      <div className="chartcard" style={{margin:0}}><div className="ch"><h3>기간별 달력 시간 구성 ({U} · {m==='all'?'전체 호기':m})</h3><span className="hint">행을 누르면 오른쪽에 그 기간 상세</span><span className="grow"/>
          <Legend keys={UK} hidden={hid} onToggle={k=>setHid(h=>({...h,[k]:!h[k]}))}/></div>
        <div className="prows" style={{maxHeight:620,overflow:'auto'}}><div className="prow head"><span>기간</span><span>달력 시간 구성 (100% = {nm>1?nm+'대 × ':''}24시간 × 일수)</span><span>유효 스캔</span></div>
          {rows.length?rows:<p className="hint">조사 범위에 Batch Report가 없습니다.</p>}</div></div>
      <aside className="chartcard detailpane" style={{margin:0}}>{!cur?<p className="hint">조사 범위에 자료가 없습니다.</p>:<>
        <div className="ch"><h3>{cur} 상세</h3><span className="count">{m==='all'?'전체 호기':m}</span></div>
        <div className="stack big">{stack(dc,dcal)}</div>
        <div className="comp">{UK.map(x=><div key={x.k} data-tip={x.label+'\n'+x.d}><i style={{background:x.c}}/><span>{x.label}</span><b>{hrs(dc[x.k as keyof Comp])}h</b><em>{num(dc[x.k as keyof Comp]/dcal*100,1)}%</em></div>)}</div>
        <h4>레시피(Job · Recipe(s))별 유효 스캔 점유</h4>
        {Object.keys(rec).length?Object.keys(rec).sort((a,c)=>rec[c]-rec[a]).map(r=><div key={r} className="hbar" data-tip={`${r}\n유효 스캔 ${hrs(rec[r])}h · ${num(rec[r]/rt*100,1)}%`}>
          <span className="lab">{r}</span><span className="track"><span style={{width:(rec[r]/rt*100).toFixed(1)+'%'}}/></span><span className="val">{num(rec[r]/rt*100,1)}% · {hrs(rec[r])}h</span></div>):<p className="hint">유효 스캔 없음</p>}
        <h4>Error 원문별 잃은 시간 <small>wafer마다 자기 Error 원문으로 · 연쇄는 앞 Error로</small></h4>
        <div className="table-scroll" style={{maxHeight:300}}><table className="t-compact"><thead><tr><th>Error 원문</th><th className="num">wafer</th><th className="num">Error·중복 스캔</th><th className="num">재스캔 전 대기</th><th className="num">합계</th><th className="num">Lot</th></tr></thead>
          <tbody>{ek.map(e=>{const t=err[e],nl=Object.keys(t[2]).length;return <tr key={e} className={'clickable'+(errSel===e?' sel':'')} onClick={()=>setErrSel(e)}
            data-tip={`${e}\nwafer ${t[3]}장의 몫(Batch Time ÷ Dice 있는 행 수) = ${hrs(t[0])}h\n재스캔 전 대기 ${hrs(t[1])}h (앞 Batch Report의 Error wafer 비율로 나눔)\nLot ${nl}개 — 누르면 Lot 목록`}>
            <td>{e}</td><td className="num">{t[3]}</td><td className="num">{hrs(t[0])}h</td><td className="num">{hrs(t[1])}h</td><td className="num"><b>{hrs(t[0]+t[1])}h</b></td><td className="num">{nl}</td></tr>;})}
            {!ek.length&&<tr><td colSpan={6}>잃은 시간 없음</td></tr>}</tbody></table></div>
        {errSel&&err[errSel]&&<><p className="hint">{errSel} — Lot {Object.keys(err[errSel][2]).length}개 (누르면 Lot 이력 상세)</p>
          <div style={{display:'flex',flexWrap:'wrap',gap:6,marginTop:6}}>{Object.keys(err[errSel][2]).slice(0,80).map(li=><button key={li} type="button" style={{minHeight:28,padding:'3px 10px',fontSize:12}} onClick={()=>openLot(+li)}>{v.lots[+li].label}</button>)}</div></>}
      </>}</aside>
    </div>
    <TimeTable v={v} ids={ids} m={m} dataDays={dataDays(ids)} periodDays={periodDays(cur)} cur={cur} tDay={tDay} setTDay={setTDay} openLot={openLot} showRaw={showRaw}/>
  </section>;
}

function TimeTable({v,ids,m,dataDays,periodDays,cur,tDay,setTDay,openLot,showRaw}:{v:View;ids:string[];m:string;dataDays:string[];periodDays:string[];cur:string|null;
  tDay:string|null;setTDay:(d:string)=>void;openLot:(li:number)=>void;showRaw:(g:number)=>void}){
  const [ref,width]=useWidth<HTMLDivElement>(1000);
  const all=m==='all',R=v.R;
  const byMachine=useMemo(()=>{const o:Record<string,number[]>={};R.forEach((r,g)=>{(o[r.m]||=[]).push(g);});return o;},[R]);
  const day=all?(tDay&&dataDays.includes(tDay)?tDay:dataDays[dataDays.length-1]||''):'';
  const rows=all?ids.map(id=>({label:id,day,m:id})):periodDays.map(d=>({label:d.slice(5)+' ('+weekday(d)+')',day:d,m}));
  const W=Math.max(640,width-4),L=100,RH=30,top=24,H=top+rows.length*RH+8,pw=W-L-12;
  const X=(ms:number)=>L+ms/864e5*pw;
  const kind=(g:number):[string,string,string]=>R[g].lot==null?['점검 스캔','#94a3b8','out']:R[g].fe?['Error 포함',C_ERR,'open']:['모두 Pass',C_OK,'done'];
  const svg:ReactNode[]=[];const ev:{t:string;g?:number;w?:number}[]=[];const seen:Record<string,1>={};
  for(let hh=0;hh<=24;hh+=2){const x=L+hh/24*pw;svg.push(<g key={'h'+hh}><line x1={x} x2={x} y1={top-4} y2={H-4} stroke={hh%6?'#eef1f5':'#d5dde6'}/><text x={x} y={top-9} textAnchor="middle">{pad(hh)}시</text></g>);}
  rows.forEach((rw,ri)=>{const y=top+ri*RH,d0=ts(rw.day+' 00:00'),d1=d0+864e5;
    svg.push(<g key={'r'+ri}><rect x={L} y={y+2} width={pw} height={RH-4} fill={ri%2?'#f8fafc':'#fff'} stroke="#e6ebf0"/><text x={L-8} y={y+RH/2+4} textAnchor="end" fontWeight={700}>{rw.label}</text></g>);
    (byMachine[rw.m]||[]).forEach(g=>{const r=R[g];if(!r.s||!r.e)return;const a=ts(r.s),b=ts(r.e);if(b<=d0||a>=d1)return;const k=kind(g),x0=X(Math.max(a,d0)-d0),x1=X(Math.min(b,d1)-d0);
      svg.push(<rect key={'b'+ri+'_'+g} className="ttb" x={x0.toFixed(1)} y={y+5} width={Math.max(2,x1-x0).toFixed(1)} height={RH-17} rx={2} fill={k[1]} data-raw={g}
        data-tip={`${r.s.slice(11)} ~ ${r.e.slice(11)} · ${r.m} · ${k[0]}\n${r.lot!=null?'Lot '+v.lots[r.lot].label+' · ':''}S/M ${r.sm} · ${r.step}\nPass ${r.ok} / ${r.n}행${r.fe?'\n첫 Error: '+r.fe:''}\n${r.f}\n누르면 원문`}/>);
      if(!seen['r'+g]){seen['r'+g]=1;ev.push({t:r.s,g});}});
    v.waits.forEach((w,wi)=>{if(w.m!==rw.m)return;const a=ts(w.s),b=ts(w.e);if(b<=d0||a>=d1)return;const x0=X(Math.max(a,d0)-d0),x1=X(Math.min(b,d1)-d0);
      svg.push(<rect key={'w'+ri+'_'+wi} className="ttw" x={x0.toFixed(1)} y={y+RH-11} width={Math.max(2,x1-x0).toFixed(1)} height={5} rx={1} fill={C_WAIT} data-li={w.li}
        data-tip={`재스캔 전 대기 · Lot ${v.lots[w.li].label}\n${w.s.slice(5)} → ${w.e.slice(5)} (${dur(mins(w.s,w.e))})\n앞 Batch Report 첫 Error: ${R[w.g].fe||'—'}\n그 사이 다른 스캔 시간은 가동률에서 뺍니다\n누르면 Lot 이력 상세`}/>);
      if(!seen['w'+wi]){seen['w'+wi]=1;ev.push({t:w.s,w:wi});}});});
  ev.sort((a,b)=>a.t<b.t?-1:a.t>b.t?1:0);
  const click=(e:React.MouseEvent)=>{const t=e.target as Element,l=t.closest('[data-li]');if(l){openLot(+l.getAttribute('data-li')!);return;}const r=t.closest('[data-raw]');if(r)showRaw(+r.getAttribute('data-raw')!);};
  const step=(k:number)=>{const i=dataDays.indexOf(day)+k;if(i>=0&&i<dataDays.length)setTDay(dataDays[i]);};
  return <div className="chartcard" style={{marginTop:18}}><div className="ch"><h3>{all?`24시간 시간표 — ${day} (${day?weekday(day):''}) · 호기별`:`24시간 시간표 — ${m} · ${cur||''}`}</h3>
      <span className="hint">{all?'날짜를 바꿔 보세요 · 막대에 마우스를 올리면 자세히, 누르면 원문':'위 기간 행을 고르면 그 기간의 날마다 한 줄 · 누르면 원문'}</span><span className="grow"/>
      {all&&<span className="ttnav"><button type="button" aria-label="전날" onClick={()=>step(-1)}>◀</button>
        <select aria-label="날짜" value={day} onChange={e=>setTDay(e.target.value)}>{dataDays.map(d=><option key={d}>{d}</option>)}</select>
        <button type="button" aria-label="다음날" onClick={()=>step(1)}>▶</button></span>}</div>
    <div className="keys" style={{marginTop:0}}><span><i style={{background:C_OK}}>　</i> Batch Report 모두 Pass</span><span><i style={{background:C_ERR}}>　</i> Error 포함</span><span><i style={{background:'#94a3b8'}}>　</i> 점검 스캔</span>
      <span><i style={{background:C_WAIT}}>　</i> 아래 노란 줄 = 재스캔 전 대기(Error 뒤 같은 Lot 다시 스캔까지)</span><span>빈칸 = 스캔 기록 없음</span></div>
    <div className="chart" ref={ref} onClick={click}><div className="chartscroll"><svg width={W} height={H} role="img" aria-label="24시간 시간표">{svg}</svg></div></div>
    <div className="table-scroll" style={{maxHeight:360,marginTop:12}} onClick={click}><table className="t-compact"><thead><tr><th>시작</th><th>끝</th><th>호기</th><th>한 일</th><th>Lot</th><th>S/M</th><th className="num">Pass / 행</th><th>첫 Error 원문</th><th className="num">시간</th><th/></tr></thead>
      <tbody>{ev.map(x=>{if(x.w!=null){const w=v.waits[x.w];return <tr key={'w'+x.w} className="clickable" data-li={w.li}><td>{w.s}</td><td>{w.e.slice(5)}</td><td>{w.m}</td><td><span className="st re">재스캔 전 대기</span></td>
          <td><b>{v.lots[w.li].label}</b></td><td/><td/><td>{R[w.g].fe}</td><td className="num">{dur(mins(w.s,w.e))}</td><td/></tr>;}
        const r=R[x.g!],k=kind(x.g!);return <tr key={'r'+x.g} className="clickable" data-raw={x.g}><td>{r.s}</td><td>{r.e.slice(5)}</td><td>{r.m}</td><td><span className={'st '+k[2]}>{k[0]}</span></td>
          <td>{r.lot!=null&&<button type="button" className="linklike" data-li={r.lot}>{v.lots[r.lot].label}</button>}</td><td>{r.sm}</td><td className="num">{r.ok} / {r.n}</td>
          <td className={r.fe?'v4':''}>{r.fe}</td><td className="num">{dur(r.sec/60)}</td><td><button type="button" style={small} data-raw={x.g}>원문 보기</button></td></tr>;})}
        {!ev.length&&<tr><td colSpan={10}>이 범위에 스캔 기록이 없습니다.</td></tr>}</tbody></table></div></div>;
}
