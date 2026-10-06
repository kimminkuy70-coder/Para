import {useEffect,useMemo,useState,type DragEvent} from 'react';
import {notify,fail} from './ui';
import {OpenPath} from './OpenPath';
import {batchCall,type View} from './batchData';

/* 레시피 비교 모드(이슈 #14) — 두 그룹(A=기존, B=신규)에 이름을 붙이고 레시피를 끌어 넣어 같은 기준으로 비교한다.
   계산은 엔진(recipecompare)이 지금 조사 결과 위에서 한다(장비 접근 없음). 기준: ① 정상 WPH(주 지표) ② 실제 WPH(오류 포함)
   ③ 같은 wafer Bad Dice(통과 조건) ④ 기준을 바꿔도 결론이 같은가(12 조합). */
type Rec={key:string;job:string;rec:string;reports:number;wafers:number;machines:string[];first:string;last:string};
type Grp={name:string;keys:string[];since:string;until:string};
type Opts={same_machine:boolean;exclude_test:boolean;pair_hours:number};
type M={reports:number;clean:number;clean25:number;wafers:number;passed:number;scan:number|null;per_wafer:number|null;wph25:number|null;wph_clean:number|null;wph_all:number|null;
  err_rate:number|null;recipe_err:number|null;op_err:number|null;faults:number|null;machines:string[]};
type Det={n:number;up:number;dn:number;eq:number;p:number|null;sa:number;sb:number;verdict:string};
type Result={groups:{a:Grp;b:Grp};options:Opts;speed:{name:string;A:M;B:M}[];err:{A:{wafers:number;items:[string,number,number][]};B:{wafers:number;items:[string,number,number][]}};
  layers:(Det&{key:string})[];detection:Det;pairs:{bg:number;ag:number;layer:string;n:number;sa:number;sb:number;gap:number}[];
  robust:{basis:string;test:string;machine:string;A:number|null;B:number|null;ratio:number|null;main:boolean}[];
  summary:{ratio:number|null;direction:string;detection:string;a_reports:number;b_reports:number;a_clean25:number;b_clean25:number};
  reports:Record<string,{g:number;m:string;s:string;f:string;key:string;grp:'A'|'B';lots:string[];ok:number;n:number;ast:number|null;fe:string;test:boolean}>};
const KEY='bv.compare.v1';
const empty=():{a:Grp;b:Grp;opts:Opts}=>({a:{name:'기존',keys:[],since:'',until:''},b:{name:'신규',keys:[],since:'',until:''},opts:{same_machine:true,exclude_test:true,pair_hours:72}});
function load(){try{const x=JSON.parse(localStorage.getItem(KEY)||'');if(x&&x.a&&x.b&&x.opts)return x as ReturnType<typeof empty>;}catch{/* 처음 · 저장소 없음 */}return empty();}
const f1=(x:number|null|undefined,d=1)=>x==null||isNaN(x)?'—':x.toLocaleString('ko-KR',{minimumFractionDigits:d,maximumFractionDigits:d});
const pct=(x:number|null|undefined)=>x==null?'—':(100*x).toFixed(1)+'%';
const pt=(p:number|null)=>p==null?'—':p>=0.001?String(Number(p.toPrecision(2))):p.toExponential(1);
const vcls=(v:string)=>v==='차이 없음'?'done':v==='B가 덜 잡음'?'open':v==='표본 없음'?'out':'re';

export function CompareTab({v,showRaw}:{v:View|undefined;showRaw:(g:number)=>void}){
  const init=useMemo(load,[]);
  const [recipes,setRecipes]=useState<Rec[]>([]),[loading,setLoading]=useState(false),[q,setQ]=useState('');
  const [a,setA]=useState<Grp>(init.a),[b,setB]=useState<Grp>(init.b),[opts,setOpts]=useState<Opts>(init.opts);
  const [res,setRes]=useState<Result>(),[busy,setBusy]=useState(false),[saved,setSaved]=useState(''),[over,setOver]=useState<'a'|'b'|null>(null);
  useEffect(()=>{try{localStorage.setItem(KEY,JSON.stringify({a,b,opts}));}catch{/* 저장소 없음: 이번 화면만 */}},[a,b,opts]);
  useEffect(()=>{if(!v){setRecipes([]);return;}let live=true;setLoading(true);
    batchCall<{recipes:Rec[]}>('batch_compare_recipes',{view:'scope'}).then(r=>{if(live)setRecipes(r.recipes);}).catch(e=>{if(live)fail(e);}).finally(()=>{if(live)setLoading(false);});
    return()=>{live=false;};},[v]);
  const known=useMemo(()=>new Map(recipes.map(r=>[r.key,r])),[recipes]);
  const list=useMemo(()=>{const t=q.trim().toLowerCase();return recipes.filter(r=>!t||r.key.toLowerCase().includes(t)||r.machines.join(' ').toLowerCase().includes(t));},[recipes,q]);
  function put(g:'a'|'b',key:string){
    const add=(x:Grp)=>x.keys.includes(key)?x:{...x,keys:[...x.keys,key]},drop=(x:Grp)=>({...x,keys:x.keys.filter(k=>k!==key)});
    if(g==='a'){setA(add);setB(drop);}else{setB(add);setA(drop);}
  }
  const remove=(g:'a'|'b',key:string)=>(g==='a'?setA:setB)(x=>({...x,keys:x.keys.filter(k=>k!==key)}));
  function onDrop(g:'a'|'b',e:DragEvent){e.preventDefault();setOver(null);const k=e.dataTransfer.getData('text/plain');if(k)put(g,k);}
  const spec=()=>({a:{name:a.name,keys:a.keys,since:a.since,until:a.until},b:{name:b.name,keys:b.keys,since:b.since,until:b.until},options:opts});
  async function run(){
    if(!a.keys.length||!b.keys.length){notify('A와 B 그룹에 레시피를 하나 이상 넣으세요.','error');return;}
    setBusy(true);setSaved('');
    try{setRes(await batchCall<Result>('batch_compare',{view:'scope',spec:spec()}));}catch(e){fail(e);}finally{setBusy(false);}
  }
  async function save(){
    setBusy(true);
    try{const r=await batchCall<{path:string}>('batch_compare_export',{view:'scope',spec:spec()});setSaved(r.path);notify('비교 결과를 HTML로 저장했습니다 — 원문 포함, 다른 PC에서도 열립니다.','ok');}
    catch(e){fail(e);}finally{setBusy(false);}
  }
  if(!v)return <section className="panel"><div className="empty-state"><span className="empty-symbol" aria-hidden="true">⇄</span><h3>먼저 조사를 하세요.</h3><p>레시피 비교는 지금 조사 결과(호기 · 기간) 안의 Batch Report로 계산합니다.</p></div></section>;
  const box=(g:'a'|'b',x:Grp,set:(f:(o:Grp)=>Grp)=>void)=><div className={'cmp-box '+g+(over===g?' over':'')} onDragOver={e=>{e.preventDefault();setOver(g);}} onDragLeave={()=>setOver(o=>o===g?null:o)} onDrop={e=>onDrop(g,e)}
      aria-label={(g==='a'?'A':'B')+' 그룹'}>
    <div className="cmp-boxhead"><span className={'abchip '+g}><i/>{g==='a'?'A · 기존':'B · 신규'}</span>
      <input aria-label={(g==='a'?'A':'B')+' 그룹 이름'} value={x.name} maxLength={40} onChange={e=>set(o=>({...o,name:e.target.value}))} placeholder="그룹 이름"/></div>
    <div className="cmp-keys">{x.keys.length?x.keys.map(k=>{const r=known.get(k);return <span key={k} className="chip" title={r?`Report ${r.reports} · ${r.machines.join(', ')} · ${r.first} ~ ${r.last}`:'지금 조사 결과에 없는 레시피'}>
        {k}{r?<small> · {r.reports}</small>:<small> · 없음</small>}<button type="button" aria-label={k+' 빼기'} onClick={()=>remove(g,k)}>×</button></span>;})
      :<p className="hint">왼쪽 목록에서 레시피를 끌어 놓거나 [{g==='a'?'A':'B'}] 를 누르세요.</p>}</div>
    <div className="cmp-dates"><label className="field">이 날짜부터<input type="date" value={x.since} onChange={e=>set(o=>({...o,since:e.target.value}))}/></label>
      <label className="field">이 날짜까지<input type="date" value={x.until} onChange={e=>set(o=>({...o,until:e.target.value}))}/></label></div>
  </div>;
  const S=res?.speed[0];
  return <div className="cmp">
    <section className="panel">
      <div className="section-heading"><div><span className="step">레시피 비교 · 지금 조사 결과 안에서</span><h2>두 레시피 그룹을 같은 기준으로 비교</h2></div>
        <span className="count">레시피 {recipes.length}개{loading?' · 불러오는 중…':''}</span></div>
      <p className="sub">그룹 이름을 정하고, 각 그룹에 볼 레시피(Job · Recipe(s))를 끌어 넣은 뒤 [비교]를 누르세요. 예: A = RDL Multi · x20, B = RDL Multi · x5.</p>
      <div className="cmp-grid">
        <div className="cmp-list"><input type="search" placeholder="레시피 · 호기 검색" aria-label="레시피 검색" value={q} onChange={e=>setQ(e.target.value)}/>
          <div className="cmp-items" role="list">{list.slice(0,400).map(r=>{const inA=a.keys.includes(r.key),inB=b.keys.includes(r.key);
            return <div key={r.key} role="listitem" className={'cmp-item'+(inA?' in-a':inB?' in-b':'')} draggable onDragStart={e=>{e.dataTransfer.setData('text/plain',r.key);e.dataTransfer.effectAllowed='copy';}}
              data-tip={`${r.key}\nReport ${r.reports} · Pass wafer ${r.wafers}\n${r.machines.join(', ')}\n${r.first} ~ ${r.last}`}>
              <span className="grip" aria-hidden="true">⋮⋮</span><span className="nm">{r.job}<small>{r.rec} · {r.reports}장 · {r.machines.length}대</small></span>
              <button type="button" className={inA?'on a':''} aria-label={r.key+' A에 넣기'} onClick={()=>put('a',r.key)}>A</button>
              <button type="button" className={inB?'on b':''} aria-label={r.key+' B에 넣기'} onClick={()=>put('b',r.key)}>B</button></div>;})}
            {!list.length&&<p className="table-empty">{loading?'레시피 목록을 만드는 중…':'맞는 레시피가 없습니다.'}</p>}</div></div>
        <div className="cmp-groups">{box('a',a,setA)}{box('b',b,setB)}</div>
      </div>
      <div className="cmp-opts">
        <label className="switch"><input type="checkbox" checked={opts.same_machine} onChange={e=>setOpts(o=>({...o,same_machine:e.target.checked}))}/><span><b>같은 호기끼리만</b><small>A · B를 모두 돌린 호기만 (호기 차이 제거)</small></span></label>
        <label className="switch"><input type="checkbox" checked={opts.exclude_test} onChange={e=>setOpts(o=>({...o,exclude_test:e.target.checked}))}/><span><b>테스트 Lot 빼기</b><small>Lot 이름 TEST · engineer · scan time 등</small></span></label>
        <label className="field">같은 wafer 짝 찾는 시간<select value={opts.pair_hours} onChange={e=>setOpts(o=>({...o,pair_hours:+e.target.value}))}>{[24,72,168,336].map(h=><option key={h} value={h}>{h}시간 이내</option>)}</select></label>
        <span className="grow"/>
        <button type="button" onClick={()=>{const e=empty();setA(e.a);setB(e.b);setOpts(e.opts);setRes(undefined);}}>비우기</button>
        <button type="button" className="primary" disabled={busy||!a.keys.length||!b.keys.length} onClick={()=>void run()}>{busy?'계산 중…':'비교 →'}</button></div>
    </section>
    {res&&S&&<>
      <div className="kpib" style={{marginTop:18}}>
        <button type="button" className={res.summary.ratio==null?'':res.summary.ratio>=1?'k-good':'k-open'}><span className="lab">정상 WPH B ÷ A</span><strong>{f1(res.summary.ratio,2)}<small>배</small></strong>
          <span className="s2">A {f1(S.A.wph25??S.A.wph_clean)} → B {f1(S.B.wph25??S.B.wph_clean)} WPH</span></button>
        <button type="button" className={res.summary.direction==='기준에 따라 달라짐'?'k-re':''}><span className="lab">기준을 바꿔도?</span><strong style={{fontSize:22}}>{res.summary.direction}</strong><span className="s2">12 조합의 B ÷ A 방향</span></button>
        <button type="button" className={res.detection.verdict==='차이 없음'?'k-good':res.detection.verdict==='B가 덜 잡음'?'k-open':'k-re'}><span className="lab">같은 wafer Bad Dice B ÷ A</span>
          <strong>{res.detection.sa?f1(res.detection.sb/res.detection.sa,2):'—'}<small>배</small></strong><span className="s2">{res.detection.n}장 · {res.detection.verdict}{res.detection.p!=null?` · p=${pt(res.detection.p)}`:''}</span></button>
        <button type="button"><span className="lab">표본 · 정상 25매 Report</span><strong>{S.A.clean25} / {S.B.clean25}</strong><span className="s2">A / B · Report {S.A.reports} / {S.B.reports}</span></button></div>
      <section className="panel">
        <div className="section-heading"><div><span className="step">① · ④ 속도와 기준</span><h2>기준을 바꿔도 결론이 같은가</h2></div>
          <div className="go"><button type="button" disabled={busy} onClick={()=>void save()}>HTML로 저장 (원문 포함)</button></div></div>
        <p className="sub">굵은 줄 = 주 기준(정상 WPH · 25매). 모든 조합에서 B ÷ A 가 1보다 크면(또는 모두 작으면) 어떤 기준으로 봐도 같은 결론입니다.</p>
        {saved&&<div className="outputs" style={{marginTop:10}}><OpenPath label="비교 결과 HTML" path={saved}/></div>}
        <div className="table-scroll" style={{maxHeight:'none',marginTop:10}}><table className="t-compact"><thead><tr><th>WPH 기준</th><th>테스트 Lot</th><th>호기 범위</th><th className="num">A</th><th className="num">B</th><th className="num">B ÷ A</th></tr></thead>
          <tbody>{res.robust.map((r,i)=><tr key={i} style={r.main?{fontWeight:800}:undefined}><td>{r.basis}</td><td>{r.test}</td><td>{r.machine}</td><td className="num">{f1(r.A)}</td><td className="num">{f1(r.B)}</td>
            <td className={'num '+(r.ratio==null?'':r.ratio>=1?'v1':'v4')}>{r.ratio==null?'—':f1(r.ratio,2)+'배'}</td></tr>)}</tbody></table></div>
        <h3 style={{marginTop:20}}>속도 · WPH <small className="muted">순수 스캔 = Avg. Scan Time · 1장 처리 = Batch Time ÷ 장수 · 실제 WPH = 오류 · 중단 Report 시간 포함</small></h3>
        <div className="table-scroll" style={{maxHeight:420}}><table className="t-compact"><thead><tr><th>범위</th><th>그룹</th><th className="num">Report</th><th className="num">정상 25매</th><th className="num">순수 스캔/장</th><th className="num">1장 처리</th><th className="num">정상 WPH</th><th className="num">실제 WPH</th><th className="num">레시피 탓 오류</th><th className="num">작업자 중단</th></tr></thead>
          <tbody>{res.speed.flatMap((s,i)=>(['A','B'] as const).map(g=>{const o=s[g];return <tr key={i+g}><td>{s.name}</td><td><span className={'abchip '+g.toLowerCase()}><i/>{g} · {g==='A'?res.groups.a.name:res.groups.b.name}</span></td>
            <td className="num">{o.reports}</td><td className="num">{o.clean25}</td><td className="num">{f1(o.scan,0)}초</td><td className="num">{f1(o.per_wafer,0)}초</td><td className="num"><b>{f1(o.wph25)}</b></td><td className="num">{f1(o.wph_all)}</td>
            <td className="num">{pct(o.recipe_err)}</td><td className="num">{pct(o.op_err)}</td></tr>;}))}</tbody></table></div>
      </section>
      <section className="panel" style={{marginTop:18}}>
        <div className="section-heading"><div><span className="step">③ 검출력 · 같은 wafer</span><h2>같은 wafer 에서 누가 Bad Dice 를 더 많이 잡았나</h2></div></div>
        <p className="sub">똑같은 wafer 한 장을 A로도 B로도 스캔한 경우({res.options.pair_hours}시간 안 · Scanned Dice 같음 · 둘 다 Pass)만 씁니다. 같은 wafer 라 결함은 같으므로 Bad Dice 판정 차이가 곧 검출 차이입니다.
          <b> B가 더 많이 잡음</b> = 더 잘 찾았거나 가성 증가, <b>B가 덜 잡음</b> = 놓쳤거나 A의 가성이 많았음 — 어느 쪽인지는 리뷰로만 가릴 수 있습니다. p &lt; 0.05 이면 우연이 아닌 레시피 차이입니다.</p>
        {res.layers.length?<div className="cmp-det">{res.layers.map(l=><div key={l.key} className="cmp-detrow">
          <span className="lab" title={l.key}>{l.key}<small>{l.n}장</small></span>
          <span className="cmp-stack">{([[l.up,'up','B가 더 많이 잡은 wafer'],[l.eq,'eq','같은 개수'],[l.dn,'dn','B가 덜 잡은 wafer']] as const).map(([n,c,t])=>n>0&&
            <span key={c} className={c} style={{flexGrow:n}} data-tip={`${l.key}\n${t} ${n}장 / ${l.n}장`}>{n}</span>)}</span>
          <span className="val">Bad Dice A {f1(l.sa,0)} → B {f1(l.sb,0)}<br/><span className={'st '+vcls(l.verdict)}>{l.verdict}</span>{l.p!=null&&<small> p={pt(l.p)}</small>}</span></div>)}</div>
          :<p className="table-empty">A와 B로 함께 스캔한 같은 wafer 가 없습니다(시간 범위를 늘려 보세요).</p>}
        {res.pairs.length>0&&<details className="more"><summary>같은 wafer 비교 목록 {res.pairs.length}건</summary><div className="table-scroll" style={{maxHeight:420,marginTop:8}}><table className="t-compact">
          <thead><tr><th>B 레시피</th><th>B 스캔</th><th>A 스캔</th><th className="num">같은 wafer</th><th className="num">Bad Dice A</th><th className="num">Bad Dice B</th><th className="num">B − A</th></tr></thead>
          <tbody>{res.pairs.map((p,i)=>{const A=res.reports[p.ag],B=res.reports[p.bg],d=p.sb-p.sa;return <tr key={i}><td>{p.layer}</td>
            <td>{B.m} · {B.s} · {B.lots.join(', ')} <button type="button" className="linklike" onClick={()=>showRaw(p.bg)}>원문</button></td>
            <td>{A.m} · {A.s} · {A.lots.join(', ')} <button type="button" className="linklike" onClick={()=>showRaw(p.ag)}>원문</button></td>
            <td className="num">{p.n}</td><td className="num">{p.sa}</td><td className="num">{p.sb}</td><td className={'num '+(d>0?'v2':d<0?'v4':'')}>{d>0?'+':''}{d}</td></tr>;})}</tbody></table></div></details>}
      </section>
      <section className="panel" style={{marginTop:18}}>
        <div className="section-heading"><div><span className="step">② 오류 · Pass wafer 만 보면 사라지는 손실</span><h2>오류 원인별 wafer 비율</h2></div></div>
        <div className="table-scroll" style={{maxHeight:'none',marginTop:10}}><table className="t-compact"><thead><tr><th>원인(첫 문구)</th><th className="num">A ({f1(res.err.A.wafers,0)}장)</th><th className="num">B ({f1(res.err.B.wafers,0)}장)</th></tr></thead>
          <tbody>{[...new Set([...res.err.A.items,...res.err.B.items].map(x=>x[0]))].map(k=>{const a1=res.err.A.items.find(x=>x[0]===k),b1=res.err.B.items.find(x=>x[0]===k);
            return <tr key={k}><td>{k}</td><td className="num">{pct(a1?a1[2]:0)}</td><td className="num">{pct(b1?b1[2]:0)}</td></tr>;})}</tbody></table></div>
      </section>
    </>}
  </div>;
}
