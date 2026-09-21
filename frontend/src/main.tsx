import {useEffect, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {desktop, defaults, errorText, type Configuration, type Metric, type Options, type Reply, type Table, type Target} from './desktop';
import './styles.css';
import {Recipe} from './Recipe';
import {Form} from './Form';
import {History} from './History';
import {Documents} from './Documents';
import {Commonality} from './Commonality';

const metrics: [Metric,string,string][] = [
  ['M01','처리량 · WPH','유효 매수 기준 처리 속도'], ['M02','스캔 가동률','일·주·월, 관측 범위 기준'],
  ['M03','오류 유형별 빈도','Wafer 발생 · Report · Lot 수'], ['M04','오류 성격','예방·조치·결과성 분류'],
  ['M05','Aborted 분석','직접·연쇄 중단 추정'], ['M06','재시작 간격','같은 lot 재스캔 간격'],
  ['M08','Recipe 품질 분포','Lot별 정상 Bad Dice'],
  ['M09','품질 이상 후보','과거 정상 표본과 비교'], ['M10','Lot 스캔 이슈율','이슈·재스캔 Lot 비중'],
  ['M11','미분류 상태','알 수 없는 원문도 보존']
];
const navigation = ['Recipe 관리','양식 만들기','이력 확인','Commonality 조사','배치 리포트 분석','특이사항','참고자료','장비 IP'];
const text = (value: unknown) => value == null ? '—' : typeof value === 'number' ? value.toLocaleString('ko-KR',{maximumFractionDigits:2}) : String(value);

function Trend({rows}: {rows:(string|number|null)[][]}) {
  const data=rows.filter(r=>r[0]!=null&&r[3]!=null).map(r=>({time:Date.parse(String(r[0])),value:Number(r[3])})).filter(p=>Number.isFinite(p.time)&&Number.isFinite(p.value)).sort((a,b)=>a.time-b.time);
  if(!data.length)return null;
  const start=data[0].time,end=data[data.length-1].time,maximum=Math.max(1,...data.map(p=>p.value));
  const x=(t:number)=>76+(t-start)/Math.max(1,end-start)*900, y=(v:number)=>220-v/maximum*172;
  const date=(t:number)=>new Date(t).toLocaleString('ko-KR',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false});
  const ticks=start===end?[start]:Array.from({length:5},(_,i)=>start+(end-start)*i/4);
  return <figure className="trend"><figcaption>시간순 Actual WPH <span>현재 조회 페이지 · {data.length} Report · 단위: wafer/h</span></figcaption>
    <svg viewBox="0 0 1040 292" role="img" aria-label="Batch End 시간순 WPH 추이">
      {[0,.25,.5,.75,1].map(f=><g key={f}><line x1="76" x2="976" y1={y(f*maximum)} y2={y(f*maximum)} stroke="#dce3ed"/><text x="62" y={y(f*maximum)+5} textAnchor="end">{text(f*maximum)}</text></g>)}
      <polyline points={data.map(p=>`${x(p.time)},${y(p.value)}`).join(' ')} fill="none" stroke="#24476f" strokeWidth="2.5"/>
      {data.length===1&&<circle cx={x(start)} cy={y(data[0].value)} r="4" fill="#24476f"/>}
      {ticks.map((t,i)=><text key={i} x={x(t)} y="248" textAnchor={i===0?'start':i===ticks.length-1?'end':'middle'}>{date(t)}</text>)}
      <text x="526" y="280" textAnchor="middle">Batch End · 배치 종료 시각</text>
    </svg></figure>;
}

function App(){
  const [tab,setTab]=useState('배치 리포트 분석');
  const [config,setConfig]=useState<Configuration>();
  const [targets,setTargets]=useState<Record<string,Target>>({});
  const [selected,setSelected]=useState<string[]>([]);
  const [options,setOptions]=useState<Options>(defaults);
  const [connection,setConnection]=useState('기존 설정 연결 중');
  const [error,setError]=useState('');
  const [busy,setBusy]=useState(false);
  const [progress,setProgress]=useState<Reply>();
  const [result,setResult]=useState<Reply>();
  const [table,setTable]=useState<Table>();
  const [rows,setRows]=useState<(string|number|null)[][]>([]);
  const [offset,setOffset]=useState(0);
  const [loading,setLoading]=useState(false);
  const [cancelSent,setCancelSent]=useState(false);
  const [note,setNote]=useState('조사를 시작하면 결과가 여기에 표시됩니다.');
  const job=useRef<number|undefined>(undefined), pageSequence=useRef(0);
  const PAGE=200;

  useEffect(()=>{
    let active=true;
    desktop.connect().then(()=>desktop.request('configuration').promise).then(reply=>{
      if(!active)return;
      const data=reply as Configuration;
      if(!Array.isArray(data.machines))throw new Error('configuration_failed');
      setConfig(data);setConnection('로컬 엔진 연결됨');
      const saved=data.last?.targets||[];
      setTargets(Object.fromEntries(data.machines.map(m=>[m.id,{machine:m.id,query:'',start:'',end:'',...saved.find(t=>t.machine===m.id)}])));
      setSelected([...new Set(saved.map(t=>t.machine))].filter(id=>data.machines.some(m=>m.id===id)));
      if(data.last?.options)setOptions({...defaults,...data.last.options});
    }).catch(e=>{if(active){setConnection('연결 확인 필요');setError(errorText(e));}});
    return()=>{active=false;};
  },[]);
  useEffect(()=>{
    if(!table||job.current===undefined)return;
    const sequence=++pageSequence.current;
    setLoading(true);setRows([]);
    desktop.request('table_page',{job:job.current,table:table.index,offset,limit:PAGE}).promise.then(reply=>{
      if(sequence===pageSequence.current)setRows(reply.rows||[]);
    }).catch(e=>{if(sequence===pageSequence.current)setError(errorText(e));})
      .finally(()=>{if(sequence===pageSequence.current)setLoading(false);});
    return()=>{pageSequence.current++;};
  },[table,offset]);
  const updateTarget=(id:string,key:'query'|'start'|'end',value:string)=>setTargets(old=>({...old,[id]:{...old[id],[key]:value}}));
  const toggleMetric=(id:Metric)=>setOptions(old=>({...old,metrics:old.metrics.includes(id)?old.metrics.filter(k=>k!==id):[...old.metrics,id]}));
  async function start(){
    if(busy||!config)return;
    if(!selected.length||!options.metrics.length){setError('호기와 분석 지표를 하나 이상 선택하세요.');return;}
    if(!Number.isInteger(options.valid_wafers)||options.valid_wafers<1||!Number.isInteger(options.min_baseline)||options.min_baseline<2||!Number.isFinite(options.yield_drop)||options.yield_drop<0||options.yield_drop>100){setError('매수·표본 수·Yield 기준을 확인하세요.');return;}
    if(selected.some(id=>targets[id].start&&targets[id].end&&targets[id].start>targets[id].end)){setError('시작일은 종료일보다 늦을 수 없습니다.');return;}
    setBusy(true);setCancelSent(false);setError('');setProgress(undefined);
    try{
      if(job.current!==undefined)await desktop.request('release',{job:job.current}).promise;
      job.current=undefined;setTable(undefined);setRows([]);setResult(undefined);setOffset(0);
      const task=desktop.request('investigate',{targets:selected.map(id=>{
        const {machine,query,start,end}=targets[id];return {machine,query,start,end};
      }),options},event=>{if(event.event==='accepted')job.current=event.job;setProgress(event);});
      const reply=await task.promise;
      if(reply.event==='cancelled'){setNote('조사가 취소되었습니다. 이전에 저장된 결과는 유지됩니다.');return;}
      setResult(reply);setTable(reply.tables?.[0]);
      setNote(reply.collection?.errors?'일부 원본을 읽지 못했습니다. 읽기 오류 표를 확인하세요.':'조사를 완료했습니다.');
    }catch(e){setError(errorText(e));setNote('조사 완료 여부를 확인하세요. 오류 안내를 참고해 주세요.');}
    finally{setBusy(false);}
  }
  async function cancel(){
    if(job.current===undefined)return;
    setCancelSent(true);
    try{await desktop.request('cancel',{job:job.current}).promise;}
    catch(e){setError(errorText(e));setCancelSent(false);}
  }
  const changeTable=(index:number)=>{setOffset(0);setTable(result?.tables?.find(t=>t.index===index));};
  const summary=result?.summary;
  return <div className="app">
    <header className="topbar"><a className="brand" href="#main"><span className="brand-icon" aria-hidden="true">C</span><span>Camtek <b>AOI Manager</b><small>장비 데이터 작업공간</small></span></a><span className="environment"><span aria-hidden="true">●</span> 오프라인 · 원본 읽기 전용</span></header>
    <nav className="navigation" aria-label="주요 기능">{navigation.map(name=><button key={name} className={tab===name?'active':''} aria-current={tab===name?'page':undefined} onClick={()=>setTab(name)}>{name}</button>)}</nav>
    <main id="main"><div className="page-heading"><div><p className="eyebrow">PROCESS INTELLIGENCE</p><h1>{tab}</h1><p>장비의 기록을 모아, 처리량과 오류 흐름을 한눈에 확인하세요.</p></div><span className={'connection '+(config?'connected':'')}>{connection}</span></div>
      {tab==='Commonality 조사'?<Commonality/>:tab==='Recipe 관리'?<Recipe/>:tab==='양식 만들기'?<Form/>:tab==='이력 확인'?<History/>:['특이사항','참고자료','장비 IP'].includes(tab)?<Documents key={tab} kind={tab==='특이사항'?'special':tab==='참고자료'?'reference':'ip'}/>:<>
      {error&&<div className="alert" role="alert"><strong>확인이 필요합니다</strong><span>{error}</span><button aria-label="오류 안내 닫기" onClick={()=>setError('')}>×</button></div>}
      <section className="kpis" aria-label="조사 요약">{[['전체 Report',summary?.['Batch(리포트) 수'],'건'],['분석 Lot',summary?.['Lot 수'],'개'],['이슈 Lot',summary?.['이슈 발생 Lot 수'],'개'],['읽기 오류',result?.collection?.errors,'건']].map(([label,value,unit])=><article key={String(label)}><span>{label}</span><strong>{text(value)}<small>{unit}</small></strong><p>{result?'마지막 완료 조사 기준':'조사 후 집계'}</p></article>)}</section>
      <div className="setup-grid"><section className="panel targets-panel"><div className="section-heading"><div><span className="step">01 · 조사 대상</span><h2>호기와 검색 범위</h2></div><span className="count">{selected.length}개 선택</span></div><p className="hint">검색어와 기간은 함께 적용됩니다. 비워 두면 해당 조건을 제한하지 않습니다.</p>
        <div className="toolbar"><button disabled={busy||!config?.machines.length} onClick={()=>setSelected(config?.machines.map(m=>m.id)||[])}>전체 선택</button><button disabled={busy||!selected.length} onClick={()=>setSelected([])}>선택 해제</button></div>
        <div className="targets" aria-label="호기별 검색 조건">{config?.machines.length?config.machines.map(m=><fieldset key={m.id} disabled={busy} className={selected.includes(m.id)?'machine selected':'machine'}><legend><label><input type="checkbox" checked={selected.includes(m.id)} onChange={e=>setSelected(old=>e.target.checked?[...old,m.id]:old.filter(id=>id!==m.id))}/>{m.id}</label></legend>
          <p className="folder" title={m.folder}>{m.folder}</p><label className="field">Recipe 검색어<input aria-label={`${m.id} 검색어`} value={targets[m.id]?.query||''} maxLength={256} onChange={e=>updateTarget(m.id,'query',e.target.value)} placeholder="예: 2D CAMTEK"/></label>
          <div className="date-fields"><label className="field">시작일<input type="date" aria-label={`${m.id} 시작일`} value={targets[m.id]?.start||''} onChange={e=>updateTarget(m.id,'start',e.target.value)}/></label><label className="field">종료일<input type="date" aria-label={`${m.id} 종료일`} value={targets[m.id]?.end||''} onChange={e=>updateTarget(m.id,'end',e.target.value)}/></label></div>
        </fieldset>):<div className="empty-state"><h3>등록된 호기가 없습니다.</h3><p>기존 프로그램에서 지정한 Report 폴더를 연결 후 불러옵니다. 새 화면의 폴더 등록 기능은 준비 중입니다.</p></div>}</div><p className="hint">마지막으로 시작한 조사 조건만 복원합니다. 원본 폴더는 수정하지 않습니다.</p>
      </section><section className="panel metrics-panel"><div className="section-heading"><div><span className="step">02 · 분석 설정</span><h2>필요한 지표 선택</h2></div><button disabled={busy} onClick={()=>setOptions(old=>({...old,metrics:old.metrics.length===11?[]:metrics.map(m=>m[0])}))}>{options.metrics.length===11?'전체 해제':'전체 선택'}</button></div>
        <fieldset disabled={busy} className="metric-list"><legend className="sr-only">분석 지표</legend>{metrics.map(([id,title,description])=><label key={id} className={options.metrics.includes(id)?'metric checked':'metric'}><input type="checkbox" checked={options.metrics.includes(id)} onChange={()=>toggleMetric(id)}/><span><b>{title}</b><small>{description}</small></span><code>{id}</code></label>)}</fieldset>
        <fieldset className="thresholds" disabled={busy}><legend>계산 기준</legend>{[['valid_wafers','WPH 유효 매수',1,100000],['min_baseline','최소 정상 표본',2,100000],['yield_drop','Yield 하락 (pp)',0,100]].map(([key,label,min,max])=><label className="field" key={key}>{label}<input type="number" min={min} max={max} step={key==='yield_drop'?'0.1':'1'} value={Number.isNaN(options[key as keyof Options])?'':Number(options[key as keyof Options])} onChange={e=>setOptions(old=>({...old,[key]:e.target.value===''?NaN:Number(e.target.value)}))}/></label>)}</fieldset>
        <p className="hint">중단·복구·품질 결과는 검토용 추정입니다. 장비 설정이나 자동 Hold를 변경하지 않습니다.</p>
      </section></div>
      <section className="runbar" aria-label="조사 실행"><div><strong>{busy?(cancelSent?'안전한 중단 지점을 기다리는 중…':'조사 진행 중…'):`${selected.length}개 호기 · ${options.metrics.length}개 지표`}</strong><p role="status" aria-live="polite">{busy?(progress?.message||'장비 기록을 순차적으로 확인합니다.'):note}</p></div><div className="actions">{busy?<button onClick={cancel} disabled={cancelSent}>{cancelSent?'취소 요청됨':'조사 취소'}</button>:<button className="primary" disabled={!config||!selected.length||!options.metrics.length} onClick={start}>조사 시작 <span aria-hidden="true">→</span></button>}</div></section>
      {busy&&<div className="progress-line" role="progressbar" aria-label="조사 중" aria-valuetext={progress?.message||'조사 중'}><span/></div>}
      <section className="panel results"><div className="section-heading"><div><span className="step">03 · 분석 결과</span><h2>결과 살펴보기</h2></div>{result&&<span className="count">{result.tables?.length}개 표</span>}</div>
        {!result?<div className="empty-state"><span className="empty-symbol" aria-hidden="true">▤</span><h3>{busy?'결과를 준비하고 있습니다.':'아직 조사 결과가 없습니다.'}</h3><p>조사가 끝나면 요약, 상세 표, 저장된 Excel·HTML 위치를 확인할 수 있습니다.</p></div>:<>
          <div className="result-toolbar"><label className="field">분석 표<select aria-label="분석 표" value={table?.index??''} onChange={e=>changeTable(Number(e.target.value))}>{result.tables?.map(t=><option key={t.index} value={t.index}>{t.title} · {t.total.toLocaleString()}행</option>)}</select></label><p>표는 한 번에 최대 {PAGE}행씩 표시합니다. 전체 결과는 Excel·HTML에 저장됩니다.</p></div>
          {table?.title==='시간순 Actual WPH'&&!loading&&<Trend rows={rows}/>}
          <div className="table-scroll" tabIndex={0} aria-label={table?.title} aria-busy={loading}><table><thead><tr>{table?.headers.map((h,i)=><th key={i} scope="col">{h}</th>)}</tr></thead><tbody>{rows.map((row,i)=><tr key={`${offset}-${i}`}>{row.map((cell,j)=><td key={j}>{text(cell)}</td>)}</tr>)}</tbody></table>{(loading||!rows.length)&&<p className="table-empty">{loading?'표를 불러오는 중…':'이 지표에 해당하는 결과가 없습니다.'}</p>}</div>
          <div className="pagination"><span>{table?.total?`${offset+1}–${Math.min(offset+PAGE,table.total)} / ${table.total.toLocaleString()}행`:'0행'}</span><div><button disabled={loading||offset===0} onClick={()=>setOffset(n=>Math.max(0,n-PAGE))}>이전</button><button disabled={loading||offset+PAGE>=(table?.total||0)} onClick={()=>setOffset(n=>n+PAGE)}>다음</button></div></div>
          {result.artifacts&&<div className="outputs"><h3>저장된 결과</h3><p>아래 위치의 파일을 탐색기에서 열 수 있습니다.</p>{(['xlsx','html','outdir'] as const).map(key=><label className="field" key={key}>{key==='xlsx'?'Excel':key==='html'?'HTML':'결과 폴더'}<input readOnly value={result.artifacts?.[key]||''} onFocus={e=>e.target.select()}/></label>)}{result.artifacts.dashboard_error&&<p role="alert">가동률 대시보드 저장 실패: {result.artifacts.dashboard_error}</p>}</div>}
        </>}
      </section></>}
    </main><footer><span>Camtek AOI Manager · 개편 시험 화면</span><span>{config?.local_root?`로컬 결과: ${config.local_root}`:'데이터는 장비 원본과 분리하여 로컬에 저장합니다.'}</span></footer>
  </div>;
}
createRoot(document.getElementById('root')!).render(<App/>);
