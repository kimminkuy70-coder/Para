import {useEffect,useMemo,useRef,useState,type CSSProperties} from 'react';
import {desktop,errorText,pickFolder} from './desktop';
import {notify} from './ui';
import {openPath} from './OpenPath';

/* TB500 Review 조회 (v14.4.2, 소유자 2026-11-23) — 맨 위 탭(KLA 와 설정 사이, AOI Manager Mini 에도).
   리뷰 전용 HTML(TB500_Review.html, 브랜치 version_TB500_review — 앱이 없는 PC 용으로 유지)의 조회를 앱 안으로 옮겼다.
   엔진 = param_manager/desktop_tb500.py: Conder Scan 폴더는 이름만 읽고(쓰기 없음), Camtek · KLA 는 이 PC 의 로컬 캐시.
   HTML 의 브라우저 허용 창 · 폴더 연결(IndexedDB) · 내 PC 캐시 폴더가 없다 — 파일은 엔진이 직접 읽는다.
   [OneDrive 에서 최신 캐시 받기] = 기존 Batch Report · KLA [OneDrive 에서 불러오기]를 한 번에(tb500_cache_update). */

type Stage={key:string;aoi:string;aoi_name:string;rev:string;rev_name:string};
type Scan={total:number;n:{P:number;E:number;A:number;S:number};outcome:string};
type Hit={vendor:'Camtek'|'KLA';machine:string;at:string;layer:string;id?:number;sm?:string;file?:string;scan?:Scan;lot?:string;slots?:number;path?:string;review?:boolean};
type VerdictSum={name:string;state:string;wafers:number;counts:Record<string,number>};
type Sub={name:string;kind:string;star:boolean;path:string;stage:Stage|null;status:string;txt:{count:number;partial:boolean}|null;
  equipment:string;hits:Hit[];total:number;machines:number;verdicts:VerdictSum[]};
type LotResult={lot:string;folder:string;sm:string;code:string;missing:boolean;subs:Sub[];layers:{key:string;status:string}[];error:string};
type Lookup={conder:string;lots:number;done:number;stopped:boolean;results:LotResult[];elapsed:number;
  summary:{lots:number;missing:number;layers:number;done:number;need:number;skip:number};
  cache:{camtek_reports:number;camtek_machines:number;camtek_bad:number;kla_lots:number;kla_machines:number;kla_at:string;kla_error:string}};
type State={conder:string;default_conder:string;is_default:boolean;imported:{camtek:string;kla:string;at:string};
  camtek:{files:number;size:number;reports?:number;machines?:string[];error?:boolean};kla:{present:boolean;size:number;error?:boolean}};
type Update={camtek:{status:string;name?:string;exported_at?:string;message?:string};kla:{status:string;name?:string;exported_at?:string;message?:string};state:State};
type HRow={vendor:'Camtek'|'KLA';id?:number;machine:string;at:string;layer:string;what:string;sm?:string;scan?:Scan;src:string};
type Wafer={key:string;slot:number|null;wid:string;items:{pos:number;k:string;t:string}[];verdict:string};
type Group={name:string;layer:string;scans:number[];wafers:Wafer[];counts:Record<string,number>;state:string};
type History={lot:string;folder:string;sm:string;code:string;rows:HRow[];groups:Group[];layers:string[]};
type Report={id:number;machine:string;at:string;file:string;scan:Scan;meta:string[][];cols:string[];vals:string[][];cells:[number|null,string][]};

const TAB='TB500 Review 조회';
const STALE_HOURS=24;
const LAYERS=['RDL4','PIDS3','RDL3','PIDS5','RDL2','PIDS7','RDL1','FS UBM'];
const STATUS:Record<string,[string,string]>={rereview:['재리뷰 결과','done'],done:['재리뷰 완료','done'],need:['재리뷰 필요','need'],skip:['Skip','skip']};
const KIND:Record<string,string>={rescan:'재스캔',rereview:'재리뷰',skip:'Skip'};
const VERDICTS=['한 번에 Pass','재스캔 Pass','중복 Pass','Pass 없음'];
const STATE_CLS:Record<string,string>={'한 번에 완료':'all','재스캔으로 완료':'part','Pass하지 못한 wafer 존재':'none'};
const VC:Record<string,string>={'한 번에 Pass':'vok','재스캔 Pass':'vre','중복 Pass':'vdup','Pass 없음':'vno'};
const MPAL=['#2563eb','#d97706','#059669','#db2777','#7c3aed','#0891b2','#65a30d','#dc2626','#475569','#c026d3'];
const LPAL=['#6d28d9','#be185d','#0369a1','#b45309','#15803d','#9333ea','#0f766e','#a16207'];
const layerColor=(k:string)=>{const i=LAYERS.indexOf(k);return i<0?'#64748b':LPAL[i%LPAL.length];};
function machColors(list:string[]){const m=new Map<string,string>();[...new Set(list)].sort((a,b)=>a.localeCompare(b,'ko',{numeric:true})).forEach((x,i)=>m.set(x,MPAL[i%MPAL.length]));return m;}
const parseLots=(text:string)=>{const seen=new Set<string>(),out:string[]=[];for(const x of text.split(/[\n\r\t,;]+/).map(s=>s.trim()).filter(Boolean)){if(!seen.has(x.toLowerCase())){seen.add(x.toLowerCase());out.push(x);}}return out;};
const short=(s:string)=>String(s||'').slice(5,16);
const toDate=(s:string)=>{const m=String(s||'').match(/^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?)?/);return m?new Date(+m[1],+m[2]-1,+m[3],+(m[4]||0),+(m[5]||0),+(m[6]||0)):null;};
function dur(a:string,b:string){const A=toDate(a),B=toDate(b);if(!A||!B)return '';let m=Math.max(0,Math.round((B.getTime()-A.getTime())/60000));if(m<60)return m+'분';
  const h=Math.floor(m/60);m%=60;if(h<24)return h+'시간'+(m?' '+m+'분':'');const d=Math.floor(h/24);return d+'일'+(h%24?' '+(h%24)+'시간':'');}
const scanKind=(c:Scan)=>c.outcome==='정상'?'all':c.outcome==='작업자 중단'?'stop':c.n.P?'part':'none';
const scanCount=(c:Scan)=>'Pass '+c.n.P+(c.n.E?' · Error '+c.n.E:'')+(c.n.A?' · 중단 '+c.n.A:'')+(c.n.S?' · 스캔 안 한 슬롯 '+c.n.S:'');
const svCount=(c:Scan)=>c.n.P+'P'+(c.n.E?' '+c.n.E+'E':'')+(c.n.A?' '+c.n.A+'중단':'');
const mb=(n:number)=>(n/1048576).toFixed(1)+'MB';
const hoursSince=(s:string)=>{const d=toDate(s);return d?(Date.now()-d.getTime())/3600000:Infinity;};

function ScanBadge({scan}:{scan?:Scan}){
  if(!scan)return null;
  return <><span className={'tb5-scan '+scanKind(scan)}>{scan.outcome}</span> <span className="tb5-small">{scanCount(scan)}</span></>;
}
function Equip({e}:{e:string}){
  if(!e)return null;
  return e==='Unknown'?<span className="tb5-equip unknown">모름</span>:<span className={'tb5-equip '+(e==='KLA'?'kla':'camtek')}>{e}</span>;
}
function VerdictLine({v}:{v:{state:string;counts:Record<string,number>;wafers:number}}){
  return <span className="tb5-vsum"><span className={'tb5-scan '+STATE_CLS[v.state]}>{v.state}</span> wafer {v.wafers} · {VERDICTS.filter(x=>v.counts[x]).map(x=>x+' '+v.counts[x]).join(' · ')}</span>;
}

export function Tb500(){
  const [state,setState]=useState<State>();
  const [stateError,setStateError]=useState('');
  const [busy,setBusy]=useState('');           // 'lookup' | 'cache' | 'conder'
  const [progress,setProgress]=useState('');
  const [text,setText]=useState('');
  const [result,setResult]=useState<Lookup>();
  const [hist,setHist]=useState<{data:History;layer:string}>();
  const [report,setReport]=useState<Report>();
  const [conderInput,setConderInput]=useState('');
  const histRef=useRef<HTMLDialogElement>(null);
  const repRef=useRef<HTMLDialogElement>(null);

  async function call<T>(method:string,params:Record<string,unknown>,label?:string):Promise<T|undefined>{
    if(label){setBusy(label);setProgress('');}
    try{return (await desktop.request(method,params,v=>{if(v.message)setProgress(v.message);}).promise).tb500 as T;}
    catch(e){notify(errorText(e),'error');return undefined;}
    finally{if(label){setBusy('');setProgress('');}}
  }
  async function loadState(){
    try{const s=(await desktop.request('tb500_state',{}).promise).tb500 as State;setState(s);setConderInput(s.conder);setStateError('');}
    catch(e){setStateError(errorText(e));}
  }
  useEffect(()=>{void loadState();
    // 다른 탭(Batch Report · KLA)에서 캐시를 불러왔을 수 있어 이 탭을 다시 열 때 상태를 새로 읽는다.
    const on=(e:Event)=>{if((e as CustomEvent<string>).detail===TAB)void loadState();};
    window.addEventListener('para:tab',on);return()=>window.removeEventListener('para:tab',on);},[]);
  useEffect(()=>{const d=histRef.current;if(hist&&d&&!d.open)d.showModal();if(!hist&&d?.open)d.close();},[hist]);
  useEffect(()=>{const d=repRef.current;if(report&&d&&!d.open)d.showModal();if(!report&&d?.open)d.close();},[report]);

  async function updateCache(){
    const r=await call<Update>('tb500_cache_update',{},'cache');if(!r)return;
    setState(r.state);
    const line=(label:string,x:Update['camtek'])=>label+': '+(x.status==='imported'?`${x.name} 받음`:x.status==='latest'?`이미 최신(${x.name})`:x.message||x.status);
    const bad=[r.camtek,r.kla].some(x=>x.status==='error'||x.status==='wait');
    notify(line('Camtek',r.camtek)+' / '+line('KLA',r.kla),bad?'error':'ok');
  }
  async function setConder(path:string){
    const r=await call<State>('tb500_set_conder',{path},'conder');
    if(r){setState(r);setConderInput(r.conder);setResult(undefined);notify(r.is_default?'Conder Scan 폴더를 기본 경로로 되돌렸습니다':'Conder Scan 폴더를 바꿨습니다','ok');}
  }
  async function pickConder(){const p=await pickFolder();if(p)await setConder(p);}
  const lots=useMemo(()=>parseLots(text),[text]);
  async function run(){
    if(!lots.length){notify('조회할 Lot 을 입력하세요','error');return;}
    setHist(undefined);setReport(undefined);
    const r=await call<Lookup>('tb500_lookup',{lots},'lookup');if(!r)return;
    setResult(r);
    notify(r.stopped?`조회를 중단했습니다: Lot ${r.lots}개 중 ${r.done}개까지 조회 · 끝난 Lot 만 표에 보입니다`
      :`조회 완료: Lot ${r.lots}개 · 재리뷰 필요 Layer ${r.summary.need}개`,r.stopped?'info':'ok');
  }
  async function stop(){await call('tb500_stop',{});setProgress('중단하는 중… (지금 읽는 폴더가 끝나면 멈춥니다)');}
  async function openHistory(i:number,layer=''){const h=await call<History>('tb500_history',{lot:i});if(h)setHist({data:h,layer});}
  async function openReport(id:number){const r=await call<Report>('tb500_report',{id});if(r)setReport(r);}
  async function copy(t:string){try{await navigator.clipboard.writeText(t);notify('경로를 복사했습니다','ok');}catch{notify('복사하지 못했습니다: '+t,'error');}}

  const age=state?.imported.at?hoursSince(state.imported.at):Infinity;
  const camtekText=!state?'…':state.camtek.error?'읽지 못함':state.camtek.files?`캐시 파일 ${state.camtek.files}개 · ${mb(state.camtek.size)}`
    +(state.camtek.reports!==undefined?` · Batch Report ${state.camtek.reports.toLocaleString()}개 · 호기 ${state.camtek.machines?.length||0}대`:''):'없음';
  const klaText=!state?'…':state.kla.error?'읽지 못함':state.kla.present?`색인 ${mb(state.kla.size)}`:'없음';

  return <section className="panel tb5">
    <div className="section-heading"><div><span className="step">TB500</span><h2>TB500 Review 조회</h2></div></div>
    <p className="hint">Conder Scan 폴더는 <b>이름만 읽고</b> 아무것도 쓰지 않습니다. 호기 · 스캔 시각은 이 PC 의 Camtek(Batch Report) · KLA 캐시에서 찾습니다.
      브라우저 허용 창 없이 프로그램이 직접 읽습니다.</p>
    {stateError&&<p className="warn">{stateError} <button className="linklike" onClick={()=>void loadState()}>다시 시도</button></p>}

    <div className="tb5-setup" data-tour="tb500:setup">
      <div className="tb5-box">
        <h4>Conder Scan 폴더 <span className="tb5-small">Lot 폴더들이 바로 아래에 있는 폴더 · 읽기만</span></h4>
        <div className="tb5-row"><input aria-label="Conder Scan 폴더" value={conderInput} onChange={e=>setConderInput(e.target.value)} spellCheck={false}
          onKeyDown={e=>{if(e.key==='Enter'&&conderInput.trim()!==state?.conder)void setConder(conderInput);}}/>
          <button type="button" disabled={!!busy} onClick={()=>void pickConder()}>폴더 고르기</button>
          {conderInput.trim()!==(state?.conder||'')&&<button type="button" className="primary" disabled={!!busy} onClick={()=>void setConder(conderInput)}>저장</button>}
          {state&&!state.is_default&&<button type="button" disabled={!!busy} onClick={()=>void setConder('')} title={state.default_conder}>기본 경로로</button>}</div>
        <p className="tb5-small">{state?.is_default?'기본 경로입니다. ':''}파일 탐색기에서 이 폴더가 열리면 조회할 수 있습니다(네트워크 드라이브 연결 불필요).</p>
      </div>
      <div className="tb5-box">
        <h4>캐시 <span className="tb5-small">개발자가 OneDrive 캐시공유 폴더에 올린 것</span></h4>
        <p className="tb5-line"><b>Camtek</b> {camtekText}{state?.imported.camtek&&<span className="tb5-small"> · 받은 zip {state.imported.camtek}</span>}</p>
        <p className="tb5-line"><b>KLA</b> {klaText}{state?.imported.kla&&<span className="tb5-small"> · 받은 zip {state.imported.kla}</span>}</p>
        <div className="tb5-row"><button type="button" className="primary" data-tour="tb500:cache" disabled={!!busy} onClick={()=>void updateCache()}>
          {busy==='cache'?'받는 중…':'OneDrive 에서 최신 캐시 받기'}</button>
          <span className="tb5-small">Camtek · KLA 각각 가장 최근 zip · 크기와 SHA-256 이 맞을 때만 · 받은 것과 같으면 건너뜀</span></div>
        {state&&(state.imported.at?age>=STALE_HOURS&&<p className="tb5-banner">캐시를 받은 지 {Math.floor(age/24)}일 {Math.floor(age%24)}시간 지났습니다({state.imported.at}). [OneDrive 에서 최신 캐시 받기]를 누르세요.</p>
          :<p className="tb5-banner">OneDrive 에서 캐시를 아직 받지 않았습니다 — [OneDrive 에서 최신 캐시 받기]를 누르세요(개발자 PC 처럼 직접 만든 캐시가 있으면 그대로 써도 됩니다).</p>)}
      </div>
    </div>

    <div className="tb5-input">
      <label className="field">Lot 목록 <span className="tb5-small">Excel 셀을 그대로 붙여 넣기 · 줄바꿈 · 탭 · 쉼표로 나눔 · 같은 Lot 은 한 번만 · Ctrl+Enter = 조회</span>
        <textarea aria-label="Lot 목록" value={text} placeholder={'TB500.INT1041\nTB500.INT948'} onChange={e=>setText(e.target.value)}
          onKeyDown={e=>{if(e.key==='Enter'&&(e.ctrlKey||e.metaKey)&&!busy)void run();}}/></label>
      <div className="tb5-row"><button type="button" className="primary" data-tour="tb500:run" disabled={!!busy||!lots.length} onClick={()=>void run()}>{busy==='lookup'?'조회 중…':`조회${lots.length?` (${lots.length})`:''}`}</button>
        <button type="button" disabled={busy!=='lookup'} onClick={()=>void stop()}>중단</button>
        <button type="button" disabled={!!busy} onClick={()=>{setText('');setResult(undefined);}}>초기화</button>
        {busy&&<span className="tb5-small"><span className="spinner" aria-hidden="true"/> {progress||'처리 중…'}</span>}</div>
    </div>

    {result&&<Results r={result} onHistory={(i,l)=>void openHistory(i,l)} onCopy={p=>void copy(p)}/>}

    <dialog className="tb5-win" ref={histRef} onClose={()=>setHist(undefined)} aria-label="Lot History">
      {hist&&<HistoryView h={hist.data} layer={hist.layer} setLayer={l=>setHist({...hist,layer:l})} onReport={id=>void openReport(id)} onClose={()=>setHist(undefined)}/>}
    </dialog>
    <dialog className="tb5-win" ref={repRef} onClose={()=>setReport(undefined)} aria-label="Batch Report">
      {report&&<ReportView r={report} onClose={()=>setReport(undefined)}/>}
    </dialog>
  </section>;
}

function Results({r,onHistory,onCopy}:{r:Lookup;onHistory:(i:number,layer?:string)=>void;onCopy:(p:string)=>void}){
  const s=r.summary;
  return <div className="tb5-result">
    <p className="tb5-sum">Lot {s.lots}개 · 못 찾은 Lot {s.missing}개 · Layer {s.layers}개(재리뷰 완료 {s.done} · <b className="tb5-need">재리뷰 필요 {s.need}</b> · Skip {s.skip})
      {r.stopped&&<b className="warn"> · 중단함({r.done}/{r.lots})</b>}
      <span className="tb5-small"> · 캐시: Camtek Batch Report {r.cache.camtek_reports.toLocaleString()}개(호기 {r.cache.camtek_machines}대) · KLA Lot 폴더 {r.cache.kla_lots.toLocaleString()}개 · {r.elapsed}초</span></p>
    {r.cache.kla_error&&<p className="warn">KLA 캐시를 읽지 못해 KLA 없이 조회했습니다: {r.cache.kla_error}</p>}
    {r.cache.camtek_bad>0&&<p className="warn">Camtek 캐시 파일 {r.cache.camtek_bad}개를 읽지 못해 빼고 조회했습니다.</p>}
    <div className="table-scroll tb5-scroll"><table className="tb5-table"><thead><tr><th>입력 Lot</th><th>Conder Scan Lot 폴더 · S/M</th><th>하위 폴더 (실제 이름)</th><th>Layer</th>
      <th>공정번호 (AOI · Review)</th><th>재리뷰</th><th>장비</th><th>호기 · 스캔 시각</th><th>경로</th></tr></thead>
      <tbody>{r.results.map((lot,ri)=>{
        if(lot.missing)return <tr key={ri} className="tb5-lotstart"><td>{lot.lot}</td><td colSpan={8} className="tb5-missing">Conder Scan 에서 Lot 폴더를 찾지 못했습니다</td></tr>;
        const head=<><b>{lot.folder}</b><span className="tb5-small tb5-sub">S/M {lot.sm||'없음'}</span>
          <button type="button" className="tb5-mini" onClick={()=>onHistory(ri)}>Lot History</button></>;
        if(!lot.subs.length)return <tr key={ri} className="tb5-lotstart"><td>{lot.lot}</td><td>{head}</td><td colSpan={7} className="tb5-small">{lot.error||'하위 폴더 없음'}</td></tr>;
        return lot.subs.map((S,si)=><tr key={ri+':'+si} className={(si===0?'tb5-lotstart ':'')+(S.status==='need'?'tb5-rowneed':'')}>
          {si===0&&<><td rowSpan={lot.subs.length} className="tb5-lot">{lot.lot}</td><td rowSpan={lot.subs.length} className="tb5-head">{head}</td></>}
          <td className="tb5-sname">{S.name}{KIND[S.kind]&&S.stage&&<> <span className={'tb5-kind k-'+S.kind}>{KIND[S.kind]}</span></>}</td>
          <td className="tb5-layer">{S.stage?.key||''}</td>
          <td>{S.stage&&<><span className="tb5-proc aoi">{S.stage.aoi} {S.stage.aoi_name}</span> <span className="tb5-proc review">{S.stage.rev} {S.stage.rev_name}</span></>}</td>
          <td>{S.status&&<span className={'tb5-st '+STATUS[S.status][1]}>{STATUS[S.status][0]}</span>}
            {S.status==='rereview'&&S.txt&&<span className="tb5-small tb5-sub">맵(.txt) {S.txt.partial?'많음 — 세지 않음':S.txt.count+'개'}</span>}</td>
          <td>{(S.status==='need'||S.status==='done')&&<Equip e={S.equipment}/>}</td>
          <td className="tb5-hits">{(S.status==='need'||S.status==='done')&&(S.total?<>
            {S.machines>1&&<span className="tb5-st skip tb5-mini-st">여러 호기 {S.machines}대</span>}
            {S.verdicts.map(v=><VerdictLine key={v.name} v={v}/>)}
            {S.hits.map((h,i)=><span key={i} className="tb5-hit"><b>{h.machine}</b> · {h.at||'시각 모름'} {h.vendor==='Camtek'?<ScanBadge scan={h.scan}/>:<span className="tb5-small">KLA {h.review?'Review':'AOI'} · 슬롯 {h.slots}개</span>}</span>)}
            <button type="button" className="tb5-mini" onClick={()=>onHistory(ri,S.stage?.key)}>{S.total>S.hits.length?`외 ${S.total-S.hits.length}건 · `:''}Lot History</button></>
            :<span className="tb5-small">캐시에 없음</span>)}</td>
          <td className="tb5-acts">{!S.star&&<><button type="button" className="tb5-mini" title={S.path} onClick={()=>onCopy(S.path)}>경로 복사</button>{' '}
            <button type="button" className="tb5-mini" title={S.path} onClick={()=>void openPath(S.path)}>폴더 열기</button></>}</td>
        </tr>);})}</tbody></table></div>
  </div>;
}

function HistoryView({h,layer,setLayer,onReport,onClose}:{h:History;layer:string;setLayer:(l:string)=>void;onReport:(id:number)=>void;onClose:()=>void}){
  const rows=layer?h.rows.filter(x=>x.layer===layer):h.rows;
  const mc=machColors(h.rows.map(x=>x.machine));
  const ms=[...new Set(rows.map(x=>x.machine))];
  let moves=0;rows.forEach((x,i)=>{if(i&&rows[i-1].machine!==x.machine)moves++;});
  const num=new Map<number,number>();rows.forEach((x,i)=>{if(x.id!==undefined)num.set(x.id,i+1);});
  const groups=h.groups.filter(g=>!layer||g.layer===layer);
  const shortAt=(id:number)=>{const x=h.rows.find(y=>y.id===id);return x?short(x.at):'';};
  const machineOf=(id:number)=>h.rows.find(y=>y.id===id)?.machine||'';
  return <>
    <div className="tb5-whead"><h3>{h.lot} · Lot History</h3><span className="tb5-small">{h.folder} · S/M {h.sm||'없음'}</span><span className="tb5-grow"/><button type="button" onClick={onClose}>닫기</button></div>
    <div className="tb5-wbody">
      <div className="tb5-chips" role="group" aria-label="Layer 고르기">
        <button type="button" className={'tb5-chip'+(layer?'':' on')} onClick={()=>setLayer('')}>전체 {h.rows.length}</button>
        {h.layers.map(k=><button type="button" key={k} className={'tb5-chip'+(layer===k?' on':'')} style={{'--c':layerColor(k)} as CSSProperties} onClick={()=>setLayer(k)}>{k} {h.rows.filter(x=>x.layer===k).length}</button>)}</div>
      <div className="tb5-kpi"><div><b>{rows.length}</b><span>스캔</span></div><div><b>{ms.length}</b><span>호기 · {ms.join(', ')||'—'}</span></div>
        <div><b>{moves}</b><span>호기 이동</span></div><div><b className="sm">{rows.length?short(rows[0].at)+' ~ '+short(rows[rows.length-1].at):'—'}</b><span>기간</span></div></div>
      {!rows.length?<div className="empty-state"><p>캐시에서 이 Lot 의 스캔을 찾지 못했습니다.</p></div>:<>
        <h4 className="tb5-hsec">① 시간순 요약 <small>스캔마다 한 칸 — 위 = Layer, 가운데 = 호기 · 장비, 아래 = 스캔 시각. 칸 사이 = 간격 · 호기 이동.</small></h4>
        <TimeSvg rows={rows} mc={mc}/>
        <h4 className="tb5-hsec">② 시간순 기록</h4>
        <ol className="tb5-hlist">{rows.map((x,i)=>{const p=i?rows[i-1]:null,mv=!!p&&p.machine!==x.machine;return [
          p&&<li key={'g'+i} className={'tb5-gap'+(mv?' moved':'')}>↓ {dur(p.at,x.at)} 뒤{p.layer!==x.layer?` · Layer 바뀜(${p.layer} → ${x.layer})`:' · 다시 스캔'}{mv&&<b> · 호기 이동 {p.machine} → {x.machine}</b>}</li>,
          <li key={'r'+i} className="tb5-hrow"><span className="tb5-hn">{i+1}</span><span className="tb5-ht">{x.at||'시각 모름'}</span>
            <span className="tb5-mchip" style={{'--c':mc.get(x.machine)} as CSSProperties}>{x.machine}</span>
            <span className="tb5-lchip" style={{'--c':layerColor(x.layer)} as CSSProperties}>{x.layer}</span><Equip e={x.vendor}/>
            <div className="tb5-hw">{x.what} <ScanBadge scan={x.scan}/>{x.id!==undefined?<button type="button" className="tb5-mini tb5-mono" title="Batch Report 보기" onClick={()=>onReport(x.id!)}>{x.src}</button>
              :<span className="tb5-mono">{x.src}</span>}</div></li>];})}</ol>
        {groups.length>0&&<><h4 className="tb5-hsec">③ wafer 판정 (Camtek) <small>같은 Layer 의 Batch Report 를 wafer(슬롯)마다 모아 판정(AOI Manager 와 같은 규칙). 칸 번호 = ② 의 번호. 스캔 안 한 슬롯(Skipped)은 세지 않음.</small></h4>
          {groups.map(g=><details key={g.name} className="tb5-vgrp"><summary><b>{g.name}</b> <VerdictLine v={{state:g.state,counts:g.counts,wafers:g.wafers.length}}/> <span className="tb5-small">슬롯별 표</span></summary>
            <div className="table-scroll"><table className="tb5-vtab"><thead><tr><th>슬롯</th><th>Wafer ID</th>{g.scans.map(id=><th key={id}>{num.get(id)||''}. {machineOf(id)}<br/>{shortAt(id)}</th>)}<th>판정</th></tr></thead>
              <tbody>{g.wafers.map(w=><tr key={w.key}><td>{w.slot??'?'}</td><td className="tb5-mono">{w.wid}</td>
                {g.scans.map((id,pos)=>{const it=w.items.filter(x=>x.pos===pos);if(!it.length)return <td key={id} className="vs"/>;const x=it[it.length-1];
                  return x.k==='P'?<td key={id} className="vp">Pass</td>:<td key={id} className={x.k==='A'?'va':'ve'} title={x.t}>{x.t}</td>;})}
                <td className={VC[w.verdict]}>{w.verdict}</td></tr>)}</tbody></table></div></details>)}</>}
      </>}
      <p className="tb5-small">Camtek = 캐시의 Batch Report 중 S/M 코드 {h.code||'?'} 인 것 · KLA = {h.lot}@공정번호 폴더. 같은 S/M 코드를 다른 Lot 이 다시 쓰면 섞일 수 있습니다.</p>
    </div></>;
}

function TimeSvg({rows,mc}:{rows:HRow[];mc:Map<string,string>}){
  const step=128,L=24,W=Math.max(640,L*2+rows.length*step),H=164;
  return <div className="tb5-svscroll"><svg width={W} height={H} role="img" aria-label="시간순 요약">{rows.map((x,i)=>{const cx=L+i*step+step/2,lc=layerColor(x.layer),c=mc.get(x.machine)||'#64748b',p=i?rows[i-1]:null;
    return <g key={i}>
      {p&&<text x={cx-step/2} y={14} textAnchor="middle" className="sv-gap">{dur(p.at,x.at)}</text>}
      {p&&p.machine!==x.machine&&<><text x={cx-step/2} y={72} textAnchor="middle" className="sv-mv">⇄</text><text x={cx-step/2} y={86} textAnchor="middle" className="sv-mv sm">호기 이동</text></>}
      <title>{`${i+1}. ${x.at} · ${x.machine} · ${x.layer} · ${x.vendor}\n${x.what}`}</title>
      <rect x={cx-30} y={24} width={60} height={22} rx={6} fill={lc}/><text x={cx} y={39} textAnchor="middle" className="sv-lay">{x.layer}</text>
      <rect x={cx-34} y={50} width={68} height={58} rx={6} fill={c} opacity={.16} stroke={c}/>
      <text x={cx} y={68} textAnchor="middle" className="sv-m" fill={c}>{x.machine}</text><text x={cx} y={84} textAnchor="middle" className="sv-v">{x.vendor}</text>
      {x.scan&&<text x={cx} y={100} textAnchor="middle" className={'sv-pass '+scanKind(x.scan)}>{svCount(x.scan)}</text>}
      <text x={cx} y={124} textAnchor="middle" className="sv-t">{short(x.at).slice(0,5)}</text><text x={cx} y={138} textAnchor="middle" className="sv-t">{short(x.at).slice(6)}</text>
      <text x={cx} y={156} textAnchor="middle" className="sv-n">{i+1}</text></g>;})}</svg></div>;
}

function ReportView({r,onClose}:{r:Report;onClose:()=>void}){
  const KC:Record<string,string>={P:'vp',E:'ve',A:'va',S:'vs'};
  const pf=r.cols.findIndex(k=>/^(pass\/fail|status|state)$/i.test(k));
  return <>
    <div className="tb5-whead"><h3 className="tb5-mono">{r.file}</h3><span className="tb5-grow"/><button type="button" onClick={onClose}>닫기</button></div>
    <div className="tb5-wbody">
      <p><b>{r.machine}</b> · {r.at||'시각 모름'} <ScanBadge scan={r.scan}/></p>
      <table className="tb5-vtab tb5-meta"><tbody>{r.meta.map((p,i)=><tr key={i}><th>{p[0]}</th><td>{p[1]}</td></tr>)}</tbody></table>
      <h4 className="tb5-hsec">Wafer 표 <small>{r.vals.length}행 · 표 위가 먼저 스캔한 wafer · 슬롯 = 25행 표면 행 위치(1행 = 25번), 아니면 Wafer ID</small></h4>
      <div className="table-scroll"><table className="tb5-vtab tb5-wafers"><thead><tr><th>슬롯</th>{r.cols.map(k=><th key={k}>{k}</th>)}</tr></thead>
        <tbody>{r.vals.map((v,i)=><tr key={i}><td>{r.cells[i]?.[0]??'?'}</td>{v.map((x,j)=><td key={j} className={j===pf?KC[r.cells[i]?.[1]||'']:undefined} title={j===pf?x:undefined}>{x}</td>)}</tr>)}</tbody></table></div>
      <p className="tb5-small">원본 Batch Report 파일이 아니라 캐시에서 다시 그린 표입니다. 값은 원문 그대로입니다.</p>
    </div></>;
}
