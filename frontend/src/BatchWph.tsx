import {useMemo,useState} from 'react';
import {ColChart,Scatter} from './BatchCharts';
import {dur,hrs,num,C_OK,C_WAIT,type View} from './batchData';

/* WPH 탭 — 정상 스캔 WPH(Lot 을 한 번에 25매 모두 Pass 한 Batch Report) · 실제 WPH(재스캔 포함) · 처리량 감소. */
type T={m:string;r:string;bw:number;bs:number;bn:number;ew:number;es:number;en:number};
const wph=(w:number,s:number)=>s>0?w*3600/s:null;
const loss=(b:number|null,e:number|null)=>b&&e!=null?(1-e/b)*100:null;
const pct=(x:number|null)=>x==null?'—':num(x,1)+'%';
const small={minHeight:26,padding:'2px 9px',fontSize:12} as const;
function tipOf(t:T,title:string){const b=wph(t.bw,t.bs),e=wph(t.ew,t.es);
  return `${title}\n정상 스캔 WPH ${num(b,1)} — 25매 한 번에 모두 Pass한 Batch Report ${t.bn}장 · Batch Time ${hrs(t.bs)}h\n실제 WPH ${num(e,1)} — Lot ${t.en}개 · 최종 Pass wafer ${num(t.ew)}장 · 쓴 시간 ${hrs(t.es)}h\n처리량 감소 ${pct(loss(b,e))}`;}
function Bars({t,mx}:{t:T;mx:number}){const b=wph(t.bw,t.bs)||0,e=wph(t.ew,t.es)||0;
  return <div className="wb2" data-tip={tipOf(t,t.r?t.r+' · '+t.m:t.m)}><span style={{width:(b/mx*100).toFixed(1)+'%',background:'#31517c'}}/><span style={{width:(e/mx*100).toFixed(1)+'%',background:'#10b981'}}/></div>;}

export function WphTab({v,ids,openLot,showRaw}:{v:View;ids:string[];openLot:(li:number)=>void;showRaw:(g:number)=>void}){
  const [recipe,setRecipe]=useState(''),[bin,setBin]=useState<string|null>(null);
  const {base,eff}=v.C;
  const recipes=useMemo(()=>[...new Set([...base,...eff].map(x=>x.r))].sort(),[base,eff]);
  const mk=(o:Record<string,T>,k:string,m:string,r:string)=>o[k]||(o[k]={m,r,bw:0,bs:0,bn:0,ew:0,es:0,en:0});
  const mm:Record<string,T>={};ids.forEach(id=>mk(mm,id,id,''));
  base.forEach(x=>{const t=mk(mm,x.m,x.m,'');t.bw+=x.w;t.bs+=x.s;t.bn++;});eff.forEach(x=>{const t=mk(mm,x.m,x.m,'');t.ew+=x.w;t.es+=x.s;t.en++;});
  const mrows=ids.map(id=>mm[id]);let mx=1;mrows.forEach(t=>{mx=Math.max(mx,wph(t.bw,t.bs)||0,wph(t.ew,t.es)||0);});
  const g:Record<string,T>={};
  base.forEach(x=>{const t=mk(g,x.r+'||'+x.m,x.m,x.r);t.bw+=x.w;t.bs+=x.s;t.bn++;});eff.forEach(x=>{const t=mk(g,x.r+'||'+x.m,x.m,x.r);t.ew+=x.w;t.es+=x.s;t.en++;});
  const rows=Object.values(g).filter(t=>!recipe||t.r===recipe).sort((a,b)=>b.en-a.en);let rmx=1;rows.forEach(t=>{rmx=Math.max(rmx,wph(t.bw,t.bs)||0,wph(t.ew,t.es)||0);});
  const cl=base.filter(x=>!recipe||x.r===recipe).map(x=>({x,v:x.w*3600/x.s,bin:''}));
  let clean=null;
  if(cl.length){const vs=cl.map(c=>c.v).sort((a,b)=>a-b);let sw=0,ss=0;cl.forEach(c=>{sw+=c.x.w;ss+=c.x.s;});
    const med=vs.length%2?vs[(vs.length-1)/2]:(vs[vs.length/2-1]+vs[vs.length/2])/2;
    const lo=vs[0],hi=vs[vs.length-1],span=Math.max(hi-lo,1),step=[0.5,1,2,2.5,5,10,20].find(x=>span/x<=14)||20,st0=Math.floor(lo/step)*step,nb=Math.floor((hi-st0)/step)+1;
    const bins=Array.from({length:nb},(_,i)=>({id:String(i),lo:st0+i*step,hi:st0+(i+1)*step,n:0}));
    cl.forEach(c=>{const i=Math.min(nb-1,Math.floor((c.v-st0)/step));bins[i].n++;c.bin=String(i);});
    clean={vs,sw,ss,med,bins};}
  const curBin=clean&&bin!=null&&clean.bins[+bin]?bin:null;
  const list=cl.filter(c=>curBin==null||c.bin===curBin).sort((a,b)=>v.R[a.x.g].s<v.R[b.x.g].s?1:-1);
  const effs=eff.filter(x=>!recipe||x.r===recipe);
  let line:number|null=null;if(recipe){let bw=0,bs=0;rows.forEach(t=>{bw+=t.bw;bs+=t.bs;});line=wph(bw,bs);}
  const bases:Record<string,number|null>={};Object.entries(g).forEach(([k,t])=>{bases[k]=wph(t.bw,t.bs);});
  const lossRows=effs.filter(x=>x.n>1).map(x=>[x,x.w*3600/x.s] as const).sort((a,b)=>a[1]-b[1]).slice(0,40);
  const title=recipe||'전체 레시피';
  return <section className="panel tabpanel" aria-label="WPH">
    <div className="section-heading"><div><span className="step">WPH</span><h2>호기 · 레시피별 처리량 (Wafers Per Hour)</h2></div>
      <label className="field" style={{minWidth:380}}>레시피(Job · Recipe(s))<select value={recipe} onChange={e=>{setRecipe(e.target.value);setBin(null);}}><option value="">전체 레시피</option>{recipes.map(r=><option key={r}>{r}</option>)}</select></label></div>
    <div className="terms">
      <div><b><i style={{background:'#31517c'}}/>정상 스캔 WPH</b><p>Lot을 <b>한 번에 25매 모두 Pass</b>한 Batch Report만으로 잰 속도. 장비가 막힘없이 돌 때 1시간에 몇 매를 스캔하는지.</p><code>Σ25매 × 3600 ÷ ΣBatch Time</code></div>
      <div><b><i style={{background:'#10b981'}}/>실제 WPH (재스캔 포함)</b><p>Lot마다 최종 Pass한 wafer 수를 그 Lot에 쓴 <b>모든</b> Batch Time(Error · 재스캔 · 나눠 스캔 포함)으로 나눈 속도.</p><code>ΣPass wafer × 3600 ÷ Σ(Lot에 쓴 모든 Batch Time)</code></div>
      <div><b><i style={{background:'#c2410c'}}/>처리량 감소</b><p>Error · 재스캔 때문에 정상 스캔보다 처리량이 몇 % 줄었는지. 0%에 가까울수록 재스캔 없이 잘 돈 것.</p><code>1 − 실제 WPH ÷ 정상 스캔 WPH</code></div></div>
    <div className="chartcard"><div className="ch"><h3>호기별 전체 WPH <small style={{fontWeight:400,color:'var(--muted)'}}>— 레시피 통합, 호기 1대 기준</small></h3><span className="hint">행에 마우스를 올리면 자세히</span></div>
      <div className="table-scroll" style={{maxHeight:'none'}}><table className="t-compact"><thead><tr><th>호기</th><th className="num" title="25매 한 번에 모두 Pass한 Batch Report 기준">정상 스캔 WPH</th><th className="num">정상 스캔 Batch Report</th><th className="num" title="재스캔 · Error 시간 포함">실제 WPH</th><th className="num">Lot 수</th><th className="num">처리량 감소</th><th style={{width:320}}>비교</th></tr></thead>
        <tbody>{mrows.map(t=>{const b=wph(t.bw,t.bs),e=wph(t.ew,t.es),none=!t.bn&&!t.en;return <tr key={t.m} className={none?'outside':''} data-tip={none?t.m+'\n자료 없음':tipOf(t,t.m+' · 레시피 통합')}>
          <td><b>{t.m}</b></td><td className="num"><b>{num(b,1)}</b></td><td className="num">{t.bn||''}</td><td className="num"><b>{num(e,1)}</b></td><td className="num">{t.en||''}</td><td className="num v4">{pct(loss(b,e))}</td>
          <td>{none?<span style={{color:'var(--muted)'}}>자료 없음</span>:<Bars t={t} mx={mx}/>}</td></tr>;})}
          {!mrows.length&&<tr><td colSpan={7}>호기를 고르세요.</td></tr>}</tbody></table></div></div>
    <div className="chartcard"><div className="ch"><h3>레시피별 WPH — {title}</h3><span className="hint">행을 누르면 그 레시피만 아래에 보입니다</span></div>
      <div className="table-scroll" style={{maxHeight:360}}><table className="t-compact"><thead><tr><th>레시피(Job · Recipe(s))</th><th>호기</th><th className="num">정상 스캔 WPH</th><th className="num">정상 스캔 Batch Report</th><th className="num">실제 WPH</th><th className="num">Lot 수</th><th className="num">처리량 감소</th><th style={{width:240}}>비교</th></tr></thead>
        <tbody>{rows.map(t=>{const b=wph(t.bw,t.bs),e=wph(t.ew,t.es);return <tr key={t.r+'|'+t.m} className="clickable" data-tip={tipOf(t,t.r+' · '+t.m)} onClick={()=>{setRecipe(t.r);setBin(null);}}>
          <td>{t.r}</td><td>{t.m}</td><td className="num"><b>{num(b,1)}</b></td><td className="num">{t.bn||'—'}</td><td className="num"><b>{num(e,1)}</b></td><td className="num">{t.en}</td><td className="num v4">{pct(loss(b,e))}</td><td><Bars t={t} mx={rmx}/></td></tr>;})}
          {!rows.length&&<tr><td colSpan={8}>조사 범위에 WPH 자료가 없습니다.</td></tr>}</tbody></table></div></div>
    <div className="chartcard"><div className="ch"><h3>정상 스캔 Batch Report의 WPH — {title}</h3><span className="hint">Error 없이 25매를 한 번에 스캔한 Lot · 막대를 누르면 그 구간만 목록에</span></div>
      {clean?<><section className="kpis k5" style={{marginBottom:12}}>{([['정상 스캔 Batch Report',num(cl.length),'장','Error 없이 25매 한 번에'],['정상 스캔 WPH',num(clean.sw*3600/clean.ss,1),'','Σ25매 × 3600 ÷ ΣBatch Time'],
          ['중앙값',num(clean.med,1),'WPH','Batch Report마다 WPH'],['최소 ~ 최대',num(clean.vs[0],1)+' ~ '+num(clean.vs[clean.vs.length-1],1),'','느린 · 빠른 스캔'],['평균 Batch Time',num(clean.ss/cl.length/60,1),'분','25매 기준']] as const)
          .map(([l,val,u,s])=><article key={l}><span>{l}</span><strong>{val}<small>{u}</small></strong><p>{s}</p></article>)}</section>
        <ColChart items={clean.bins.map(b=>({id:b.id,short:num(b.lo,1),v:{n:b.n},tip:`WPH ${num(b.lo,1)} ~ ${num(b.hi,1)}\n정상 스캔 Batch Report ${b.n}장\n누르면 이 구간만 목록에`}))}
          keys={[{k:'n',label:'Batch Report',c:'#31517c'}]} h={200} minw={18} maxw={70} sel={curBin} label="정상 스캔 WPH 분포" onClick={id=>setBin(b=>b===id?null:id)}/>
        <div className="chips" style={{margin:'10px 0 6px'}}>{curBin!=null&&<button type="button" className="chip" onClick={()=>setBin(null)}>WPH {num(clean.bins[+curBin].lo,1)} ~ {num(clean.bins[+curBin].hi,1)} <i aria-hidden="true">✕</i></button>}</div>
        <div className="table-scroll" style={{maxHeight:320}}><table className="t-compact"><thead><tr><th>시작</th><th>호기</th><th>Lot</th><th>레시피(Job · Recipe(s))</th><th className="num">Batch Time</th><th className="num">WPH</th><th/></tr></thead>
          <tbody>{list.map(c=>{const r=v.R[c.x.g];return <tr key={c.x.g} className="clickable" onClick={()=>showRaw(c.x.g)}><td>{r.s}</td><td>{r.m}</td>
            <td><button type="button" className="linklike" onClick={e=>{e.stopPropagation();openLot(c.x.lot);}}>{v.lots[c.x.lot].label}</button></td><td>{c.x.r}</td><td className="num">{dur(c.x.s/60)}</td>
            <td className="num"><b>{num(c.v,1)}</b></td><td><button type="button" style={small} onClick={e=>{e.stopPropagation();showRaw(c.x.g);}}>원문 보기</button></td></tr>;})}</tbody></table></div></>
        :<p className="hint">정상 스캔 Batch Report가 없습니다.</p>}</div>
    <div className="chartcard"><div className="ch"><h3>Lot별 실제 WPH 추이 — {title}</h3><span className="hint">점 하나 = Lot 한 번의 스캔(공정 단계). 마우스를 올리면 자세히, 누르면 Lot 이력 상세.</span><span className="grow"/>
        <span style={{fontSize:12,color:'var(--muted)'}}><i className="lgdot" style={{background:C_OK}}/>한 번에 스캔 <i className="lgdot" style={{background:C_WAIT,marginLeft:12}}/>재스캔 포함 <i className="dash"/>정상 스캔 WPH</span></div>
      <Scatter base={line} onClick={openLot} pts={effs.map(x=>{const l=v.lots[x.lot],b=l.bunches[x.b],y=x.w*3600/x.s;
        return {t:new Date(x.d+'T12:00:00').getTime(),y,id:x.lot,c:x.n>1?C_WAIT:C_OK,
          tip:`Lot ${l.label} · ${b.step||'—'}\n${b.s} · ${x.m}\n${x.r}\nBatch Report ${x.n}장 · 최종 Pass wafer ${x.w}장 · 쓴 시간 ${hrs(x.s)}h\n실제 WPH ${num(y,1)}\n누르면 Lot 이력 상세`};})}/></div>
    <div className="chartcard"><div className="ch"><h3>처리량이 많이 줄어든 Lot</h3><span className="hint">재스캔이 있었던 Lot 중 실제 WPH가 낮은 순 · 누르면 Lot 이력 상세</span></div>
      <div className="table-scroll" style={{maxHeight:330}}><table className="t-compact"><thead><tr><th>Lot</th><th>공정 단계</th><th>시작</th><th>호기</th><th className="num">Batch Report</th><th className="num">스캔에 쓴 시간(h)</th><th className="num">실제 WPH</th><th className="num">처리량 감소</th></tr></thead>
        <tbody>{lossRows.map(([x,y])=>{const b=v.lots[x.lot].bunches[x.b];return <tr key={x.lot+'|'+x.b} className="clickable" onClick={()=>openLot(x.lot)}><td><b>{v.lots[x.lot].label}</b></td><td>{b.step}</td><td>{b.s}</td><td>{x.m}</td>
          <td className="num">{x.n}</td><td className="num">{hrs(x.s)}</td><td className="num">{num(y,1)}</td><td className="num v4">{pct(loss(bases[x.r+'||'+x.m]??null,y))}</td></tr>;})}
          {!lossRows.length&&<tr><td colSpan={8}>재스캔한 Lot이 없습니다.</td></tr>}</tbody></table></div></div>
  </section>;
}
