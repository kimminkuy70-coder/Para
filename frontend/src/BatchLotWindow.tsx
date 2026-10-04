import {Fragment,useEffect,useRef,useState,type ReactNode} from 'react';
import {StPill} from './BatchLot';
import {OpenPath} from './OpenPath';
import {V,VC,DONE,RE,C_OK,C_ERR,C_CHAIN,dur,mins,hrs,num,phList,isRealId,spanLabel,grpLabel,flat,
  type View,type LotDetail,type Wafer,type Cell} from './batchData';

/* Lot 창(큰 창) — 탭 ① Lot 이력 상세(시간순 요약 그래프 · 문장 요약 · Batch Report 이력 · Lot × wafer 오류 지도)
   ② Lot · wafer 취합(공정 단계별 Dice 합계 · wafer 취합, 개발자 기능이면 중복 Pass 를 고른다). */
export type Drafts=Record<string,number>;
type Props={v:View;view:string;li:number;detail?:LotDetail;dev:boolean;drafts:Drafts;setDraft:(k:string,p:number|null)=>void;
  onClose:()=>void;showRaw:(g:number)=>void;toFind:(code:string)=>void;onCrit:()=>void;onSave:()=>void;onExport:(drafts:Record<string,number>)=>void;busy:boolean;xlsx?:string};

const btn={minHeight:30,padding:'4px 10px',fontSize:12} as const;
function slotKey(w:Wafer){return w.slot==null?'ID '+w.id:String(w.slot);}
function slotRows(detail:LotDetail){
  const slots:Record<string,Record<number,Wafer>>={},keys:string[]=[];
  detail.bunches.forEach((b,bi)=>b.wafers.forEach(w=>{const k=slotKey(w);if(!slots[k]){slots[k]={};keys.push(k);}slots[k][bi]=w;}));
  keys.sort((a,b)=>(Number.isNaN(+b)?-1:+b)-(Number.isNaN(+a)?-1:+a));
  return {slots,keys};
}
const idOf=(row:Record<number,Wafer>)=>Object.values(row).map(w=>w.id).find(isRealId)||Object.values(row)[0].id;

export function LotWindow(p:Props){
  const ref=useRef<HTMLDialogElement>(null);
  const [tab,setTab]=useState<'hist'|'agg'>('hist');
  useEffect(()=>{const d=ref.current;if(d&&!d.open)d.showModal();setTab('hist');},[p.li,p.view]);
  const l=p.v.lots[p.li];
  const key=(bi:number,w:Wafer)=>`${p.view}|${p.li}|${bi}|${w.k}`;
  const pickOf=(bi:number,w:Wafer,preview:boolean)=>{const d=p.drafts[key(bi,w)];return preview&&p.dev&&d!=null?d:w.pick;};
  const nDraft=Object.keys(p.drafts).filter(k=>k.startsWith(`${p.view}|${p.li}|`)).length;
  const nSaved=p.detail?p.detail.bunches.reduce((a,b)=>a+b.wafers.filter(w=>w.ov).length,0):l.saved;
  return <dialog className="lotwin" ref={ref} aria-labelledby="lotTitle" onClose={p.onClose}>
    <div className="lw-head"><span className="step">LOT</span><h2 id="lotTitle">Lot {l.label}</h2>
      <span><StPill s={l.state}/>{l.moved&&<> <span className="st mv">호기 이동</span></>}{l.dup>0&&<> <span className="st dup">중복 Scan wafer {l.dup}</span></>}{nSaved>0&&<> <span className="st mv">사람 선택 {nSaved}건 적용</span></>}</span>
      <div className="lw-actions"><button type="button" onClick={p.onCrit}>? 판정 기준</button><button type="button" onClick={()=>p.toFind(l.code)}>찾기 · 취합에서 열기</button>
        <button type="button" className="primary" style={{minWidth:0,padding:'6px 18px'}} onClick={()=>ref.current?.close()}>닫기</button></div>
      <div className="lw-meta"><span className="job">{l.jobs.join(' / ')}</span><span>S/M {l.sms.join(', ')}</span>{l.lot_id&&<span>Lot ID {l.lot_id}</span>}
        <span>호기 {l.machines.join(' → ')}</span><span>Batch Report {l.n}장</span><span>{l.s} ~ {l.e}</span></div></div>
    <div className="subtabs lw-tabs" role="tablist">{([['hist','Lot 이력 상세'],['agg','Lot · wafer 취합']] as const).map(([k,t])=>
      <button key={k} role="tab" type="button" aria-selected={tab===k} className={tab===k?'active':''} onClick={()=>setTab(k)}>{t}</button>)}</div>
    <div className="lw-body">{!p.detail?<p className="hint">Lot 상세를 불러오는 중…</p>:tab==='hist'?<History {...p} pickOf={pickOf}/>
      :<Aggregate {...p} pickOf={pickOf} keyOf={key} nDraft={nDraft} nSaved={nSaved}/>}</div>
  </dialog>;
}

function Timeline({v,li,detail}:{v:View;li:number;detail:LotDetail}){
  const l=v.lots[li],F=flat(l),R=v.R,SP=172,L=34,W=Math.max(L*2+F.length*SP,560),H=262,top=66,bh=118;
  const maxRows=Math.max(...F.map(x=>R[x.g].n),1),cx=(n:number)=>L+(n-0.5)*SP;
  const out:ReactNode[]=[];
  l.bunches.forEach((b,bi)=>{const xs=F.filter(x=>x.bi===bi),x0=L+(xs[0].n-1)*SP+5,x1=L+xs[xs.length-1].n*SP-5;
    out.push(<g key={'b'+bi}><rect x={x0} y={4} width={x1-x0} height={H-8} rx={12} fill={bi%2?'#f3f6fa':'#f4fbf7'} stroke="#e1e7ee"/>
      <text x={x0+12} y={24} fontWeight={700} fill="#31517c" style={{fontSize:12.5}}>{b.step||'—'}</text><text x={x0+12} y={41}>{spanLabel(b)}</text></g>);});
  F.forEach((x,i)=>{if(!i)return;const pr=F[i-1],xa=cx(pr.n)+28,xb=cx(x.n)-28,y=top+bh/2,mv=R[pr.g].m!==R[x.g].m,nb=pr.bi!==x.bi,mid=(xa+xb)/2;
    out.push(<g key={'a'+i}><line x1={xa} x2={xb} y1={y} y2={y} stroke={mv?'#31517c':'#8193a8'} strokeWidth={2} strokeDasharray={nb?'5 4':undefined} markerEnd="url(#arr)"/>
      <text x={mid} y={y-9} textAnchor="middle" fontWeight={700}>{dur(mins(R[pr.g].e,R[x.g].s))} 뒤</text>
      {mv?<text x={mid} y={y+18} textAnchor="middle" fill="#31517c" fontWeight={700}>호기 이동</text>
        :nb?<text x={mid} y={y+18} textAnchor="middle" fill="#8a5a00">{l.bunches[pr.bi].step!==l.bunches[x.bi].step?'공정 바뀜':'다시 검사'}</text>:null}</g>);});
  F.forEach(x=>{const r=R[x.g],st=detail.stats[x.g]||{ph:[],cph:[]},c=cx(x.n),bw=44,h=bh*Math.max(r.n,1)/maxRows;let y=top+bh;
    const tip=`#${x.n}  ${r.f}\n${r.s} ~ ${r.e.slice(11)} · ${r.m}\nS/M ${r.sm} · ${r.step}\nPass ${r.ok} · Error ${r.err}${r.chain?' · 연쇄 '+r.chain:''}  (${r.n}행)`+
      (r.err?'\nError: '+phList(st.ph):'')+(r.chain?'\n연쇄: '+phList(st.cph):'')+'\n누르면 원문';
    const parts:[number,string][]=[[r.ok,C_OK],[r.chain,C_CHAIN],[r.err,C_ERR]];
    out.push(<g key={'n'+x.n} className="node" data-raw={x.g} data-tip={tip}><rect x={c-SP/2+12} y={top-20} width={SP-24} height={bh+76} fill="transparent"/>
      <text x={c} y={top-6} textAnchor="middle" fontWeight={800} fill="#1f2937" style={{fontSize:12}}>#{x.n} · {r.s.slice(5)}</text>
      <rect className="nb" x={c-bw/2} y={y-h} width={bw} height={h} rx={4} fill="#eef1f5"/>
      {parts.map(([n,col],k)=>{if(!n)return null;const hh=h*n/Math.max(r.n,1);y-=hh;return <rect key={k} x={c-bw/2} y={y.toFixed(1)} width={bw} height={hh.toFixed(1)} fill={col}/>;})}
      <text x={c} y={top+bh+18} textAnchor="middle" fontWeight={700}>{r.m}</text>
      <text x={c} y={top+bh+35} textAnchor="middle" fill={r.err+r.chain?'#a33820':'#0b5e46'}>Pass {r.ok} / {r.n}</text></g>);});
  return <div className="chartscroll"><svg width={W} height={H} role="img" aria-label="시간순 Batch Report 요약">
    <defs><marker id="arr" viewBox="0 0 10 10" refX={9} refY={5} markerWidth={7} markerHeight={7} orient="auto"><path d="M0 0L10 5L0 10z" fill="#8193a8"/></marker></defs>{out}</svg></div>;
}

function History(p:Props&{pickOf:(bi:number,w:Wafer,preview:boolean)=>number|null}){
  const {v,li}=p,detail=p.detail!,l=v.lots[li],R=v.R,F=flat(l),no:Record<string,number>={};
  F.forEach(x=>{no[x.bi+'|'+x.ai]=x.n;});
  const openW:string[]=[];detail.bunches.forEach(b=>b.wafers.forEach(w=>{if(w.v==='Pass 없음')openW.push(w.slot==null?w.id:'S'+w.slot);}));
  let end=l.state===DONE?'결과: 한 번에 완료 — 모든 wafer가 첫 스캔에서 Pass':l.state===RE?`결과: 재스캔으로 완료 — Error 난 wafer ${l.re}장 모두 재스캔하여 Pass`
    :`결과: Pass하지 못한 wafer ${openW.length}장(${openW.slice(0,10).join(', ')}${openW.length>10?' …':''}) — 다른 호기에서 Scan되었는지 확인 필요`;
  if(l.dup)end+=` · 같은 wafer를 Pass 후 다시 스캔한 ${l.dup}장은 가장 나중 Pass를 씀`;
  const {slots,keys}=slotRows(detail);
  const click=(e:React.MouseEvent)=>{const t=(e.target as Element).closest('[data-raw]');if(t)p.showRaw(+t.getAttribute('data-raw')!);};
  return <div onClick={click}>
    <h3>시간순 요약<small>Batch Report마다 막대 하나 — 초록 Pass · 주황 연쇄(앞 Error 뒤 Aborted/Skipped) · 빨강 Error. 마우스를 올리면 자세히, 누르면 원문.</small></h3>
    <div className="chart"><Timeline v={v} li={li} detail={detail}/></div>
    <ol className="story">{F.map((x,i)=>{const r=R[x.g],st=detail.stats[x.g]||{ph:[],cph:[]},bad=r.err+r.chain;let hd:string;
      if(!i)hd='처음 스캔';else{const pr=F[i-1],gap=dur(mins(R[pr.g].e,r.s))+' 뒤 ';
        hd=pr.bi!==x.bi?(l.bunches[pr.bi].step!==l.bunches[x.bi].step?`${gap}공정 단계 바뀜(${l.bunches[pr.bi].step} → ${l.bunches[x.bi].step})`:gap+'다시 검사'):gap+'다시 스캔';
        if(R[pr.g].m!==r.m)hd+=` · 호기 이동 ${R[pr.g].m} → ${r.m}`;}
      return <li key={x.n} className={bad?'err':'ok'}><span className="when">{r.s.slice(5)}</span><span className="hd">#{x.n} {hd}</span>
        {r.m} · {r.step} · {r.n}장 스캔 → {bad?<>Pass {r.ok} · Error {bad} <span className="v4">({phList(st.ph)}{r.chain?(r.err?' · ':'')+'연쇄 '+phList(st.cph):''})</span></>:<span className="v1">모두 Pass</span>}</li>;})}
      <li className="end">{end}</li></ol>
    <h3>Batch Report 이력<small>공정 단계별로 시간순. 원문 보기 = Batch Report 표 그대로</small></h3>
    {l.bunches.map((b,bi)=><div key={bi} className="bgroup"><div className="bh"><b>{b.step||'—'}</b><span>{b.s} ~ {b.e}</span><span>{b.machines.join(' → ')}</span>
        <span>Batch Report {b.att.length}장 · 스캔 {hrs(b.sec)}h</span>{b.moved&&<span className="st mv">호기 이동</span>}</div>
      {b.att.map((g,ai)=>{const r=R[g],prev=ai>0?R[b.att[ai-1]]:null;return <Fragment key={g}>
        {prev&&<div className="gapline">↓ {dur(mins(prev.e,r.s))} 뒤 다시 스캔{prev.m!==r.m&&<b> · 호기 이동 {prev.m} → {r.m}</b>}{prev.fe&&' — 앞 Batch Report 첫 Error: '+prev.fe}</div>}
        <div className="att"><span className="n">#{no[bi+'|'+ai]}</span><span>{r.s} ~ {r.e.slice(11)}</span><span className="mch">{r.m}</span>
          <span style={{minWidth:0}}><span className="fn" title={r.f}>{r.f}</span><span className="meta">S/M {r.sm} · Pass {r.ok} / {r.n}행{r.err+r.chain?' · Error '+(r.err+r.chain):''}</span></span>
          <span><button type="button" data-raw={g}>원문 보기</button></span></div></Fragment>;})}</div>)}
    <h3>Lot × wafer 오류 지도<small>칸 = 그 Batch Report의 Pass/Fail 원문 그대로</small></h3>
    <div className="keys"><span><i className="c-p">Pass</i></span><span><i className="c-e">Error 원문</i> 직접 Error</span><span><i className="c-c">Aborted.</i> 앞 Error 뒤 연쇄</span>
      <span><i className="c-p c-pick">Pass</i> 같은 wafer Pass 여럿 중 쓰는 것</span><span><i className="c-p c-drop">Pass</i> 쓰지 않는 Pass</span></div>
    <div className="mapscroll"><table className="map"><thead><tr><th rowSpan={2}>슬롯</th><th rowSpan={2}>Wafer ID</th>
      {l.bunches.map((b,bi)=><th key={bi} colSpan={b.att.length+1} className="gsep">{b.step||'—'}<small>{b.s.slice(5)} · {b.machines.join('→')}</small></th>)}</tr>
      <tr>{l.bunches.map((b,bi)=><Fragment key={bi}>{b.att.map((g,ai)=><th key={g} className={ai?'':'gsep'}>#{no[bi+'|'+ai]}<small>{R[g].m} {R[g].s.slice(11)}</small></th>)}<th>결과</th></Fragment>)}</tr></thead>
      <tbody>{keys.map(k=>{const row=slots[k];return <tr key={k}><th>{k}</th><td>{idOf(row)}</td>{l.bunches.map((b,bi)=>{const w=row[bi];
        if(!w)return <td key={bi} className="c-n gsep" colSpan={b.att.length+1}>·</td>;
        const pk=p.pickOf(bi,w,true),passes=w.cells.filter(c=>c[2]).length,cells:ReactNode[]=b.att.map((_,ai)=><td key={ai} className={'c-n'+(ai?'':' gsep')}>·</td>);
        w.cells.forEach((c:Cell)=>{const cls=c[2]?'c-p'+(passes>1?(c[0]===pk?' c-pick':' c-drop'):''):c[3]?'c-c':'c-e',r=R[b.att[c[0]]];
          cells[c[0]]=<td key={c[0]} className={cls+(c[0]?'':' gsep')} data-tip={`#${no[bi+'|'+c[0]]} ${r.s} · ${r.m}\n${c[1]}\nScanned ${num(c[4])} · Bad ${num(c[5])} · Good ${num(c[6])}`}>{c[1]}</td>;});
        return <Fragment key={bi}>{cells}<td className={VC[w.v]}>{w.v}</td></Fragment>;})}</tr>;})}</tbody></table></div>
  </div>;
}

function Aggregate(p:Props&{pickOf:(bi:number,w:Wafer,preview:boolean)=>number|null;keyOf:(bi:number,w:Wafer)=>string;nDraft:number;nSaved:number}){
  const {v,li,dev}=p,detail=p.detail!,l=v.lots[li],R=v.R,F=flat(l),no:Record<string,number>={};
  F.forEach(x=>{no[x.bi+'|'+x.ai]=x.n;});
  const {slots,keys}=slotRows(detail);
  const totals=(bi:number)=>{const t={sc:0,bad:0,good:0,c:{} as Record<string,number>};detail.bunches[bi].wafers.forEach(w=>{const pk=p.pickOf(bi,w,true);t.c[w.v]=(t.c[w.v]||0)+1;
    const cell=pk==null?undefined:w.cells.find(c=>c[0]===pk);if(cell&&cell[2]&&cell[4]!=null){t.sc+=cell[4];t.bad+=cell[5]||0;t.good+=cell[6]||0;}});return {...t,y:t.sc?t.good/t.sc*100:null};};
  const reset=()=>{detail.bunches.forEach((b,bi)=>b.wafers.forEach(w=>{if(w.ov)p.setDraft(p.keyOf(bi,w),w.rec);}));};
  const exportDrafts=()=>{const out:Record<string,number>={};if(dev)Object.entries(p.drafts).forEach(([k,val])=>{const s=k.split('|');if(s[0]===p.view&&+s[1]===li)out[s[2]+'|'+s.slice(3).join('|')]=val;});return out;};
  return <>
    <div className="stamp"><span>선택 기준: <b>추천(가장 나중 Pass)</b>{p.nSaved>0&&<> + <b>저장된 사람 선택 {p.nSaved}건</b></>}</span>
      {dev&&p.nDraft>0&&<span className="v2">· 저장 전 미리 보기 {p.nDraft}건 — 아래 숫자에 포함, 다른 화면에는 아직 반영 안 됨</span>}</div>
    {dev&&<div className="devnote">개발자 기능 켜짐 — 같은 wafer Pass가 여럿이면 아래 wafer 취합에서 쓸 Batch Report를 직접 고르고 저장할 수 있습니다. 저장해야 결과(가동률 · WPH · 찾기 · 취합)에 반영됩니다.</div>}
    <h3>Lot 취합<small>공정 단계마다 한 줄 — 2D_WBG · 2D처럼 다른 공정 스캔을 더하면 같은 wafer가 두 번 들어가므로 따로 셉니다.</small></h3>
    <div className="table-scroll" style={{maxHeight:'none'}}><table className="t-compact"><thead><tr><th>공정 단계(Recipe(s))</th><th>기간</th><th>호기</th><th className="num">Batch Report</th><th className="num">wafer</th>
      {V.map(x=><th key={x} className="num">{x}</th>)}<th className="num">Scanned</th><th className="num">Bad</th><th className="num">Good</th><th className="num">Yield</th></tr></thead>
      <tbody>{l.bunches.map((b,bi)=>{const t=totals(bi);return <tr key={bi}><td><b>{b.step||'—'}</b></td><td>{b.s} ~ {b.e.slice(5)}</td><td>{b.machines.join(' → ')}{b.moved&&<> <span className="st mv">호기 이동</span></>}</td>
        <td className="num">{b.att.length}</td><td className="num">{detail.bunches[bi].wafers.length}</td>{V.map(x=><td key={x} className={'num '+VC[x]}>{t.c[x]||''}</td>)}
        <td className="num">{num(t.sc)}</td><td className="num">{num(t.bad)}</td><td className="num">{num(t.good)}</td><td className="num">{t.y==null?'—':num(t.y,2)+'%'}</td></tr>;})}</tbody></table></div>
    <h3>wafer 취합<small>슬롯마다 공정 단계별로 쓰는 Batch Report의 결과 원문과 Dice. 같은 wafer Pass가 여럿이면 가장 나중 Pass(추천)를 씁니다.</small></h3>
    <div className="mapscroll"><table className="map"><thead><tr><th rowSpan={2}>슬롯</th><th rowSpan={2}>Wafer ID</th>
      {l.bunches.map((b,bi)=><th key={bi} colSpan={5} className="gsep">{grpLabel(b)}<small>{b.machines.join('→')}</small></th>)}</tr>
      <tr>{l.bunches.map((_,bi)=><Fragment key={bi}><th className="gsep">결과(쓰는 Batch Report 원문)</th><th>쓰는 Batch Report</th><th>Scanned</th><th>Bad</th><th>Good</th></Fragment>)}</tr></thead>
      <tbody>{keys.map(k=>{const row=slots[k];return <tr key={k}><th>{k}</th><td>{idOf(row)}</td>{l.bunches.map((b,bi)=>{const w=row[bi];
        if(!w)return <td key={bi} className="c-n gsep" colSpan={5}>·</td>;
        const wk=p.keyOf(bi,w),pk=p.pickOf(bi,w,true),cell=pk==null?undefined:w.cells.find(c=>c[0]===pk),last=w.cells[w.cells.length-1],r=cell||last;
        const passes=w.cells.filter(c=>c[2]),draft=dev&&p.drafts[wk]!=null;
        const tag=draft?<span className="tag-draft" data-tip={'개발자 기능에서 고쳤지만 아직 저장 안 함\n저장해야 결과에 반영됩니다'}>저장 전</span>
          :w.ov?<span className="tag-man" data-tip={`개발자 기능에서 저장한 사람 선택\n(추천은 #${w.rec==null?'—':no[bi+'|'+w.rec]})`}>사람 선택</span>:null;
        const label=(c:number)=>'#'+no[bi+'|'+c]+' '+R[b.att[c]].s.slice(5);
        const pick=passes.length>1?(dev?<span className="pickrow"><select aria-label={`슬롯 ${k} 쓸 Batch Report`} value={pk??''} onChange={e=>{const val=+e.target.value;p.setDraft(wk,val===w.pick?null:val);}}>
            {passes.map(c=><option key={c[0]} value={c[0]}>{label(c[0])}{c[0]===w.rec?' (추천)':''}</option>)}</select>{tag}</span>
          :<>{label(pk!)}{tag||<span className="rectag" data-tip={`같은 wafer Pass ${passes.length}번 — 가장 나중 Pass를 씁니다(추천)\n직접 바꾸기는 개발자 기능`}>추천</span>}</>)
          :pk==null?'—':label(pk);
        return <Fragment key={bi}><td className={'gsep '+VC[w.v]}>{r[1]}{w.v!=='한 번에 Pass'&&<small> ({w.v})</small>}</td><td>{pick}</td>
          <td className="n">{pk==null?'—':num(r[4])}</td><td className="n">{pk==null?'—':num(r[5])}</td><td className="n">{pk==null?'—':num(r[6])}</td></Fragment>;})}</tr>;})}</tbody></table></div>
    <div className="savebar"><button type="button" disabled={p.busy} onClick={()=>p.onExport(exportDrafts())}>Excel로 저장</button>
      {dev&&<><button type="button" className="primary" disabled={!p.nDraft||p.busy} onClick={p.onSave}>선택 저장</button>
        <button type="button" disabled={!p.nSaved||p.busy} onClick={reset}>이 Lot 추천으로 되돌리기</button>
        <span className="hint" style={{margin:0}}>저장하면 이 PC의 로컬 Cache(batch_lot_choices.json)에 남고, 개발자 기능을 꺼도 찾기 · 가동률 · WPH가 같은 선택을 씁니다.</span></>}</div>
    {p.xlsx&&<div className="outputs"><OpenPath label="저장된 Excel" path={p.xlsx}/></div>}
  </>;
}
