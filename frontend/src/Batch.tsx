import {useEffect,useMemo,useRef,useState} from 'react';
import {desktop,errorText,defaults,type Configuration,type Options,type Reply} from './desktop';
import {notify,fail} from './ui';
import {OpenPath,openPath} from './OpenPath';
import {goToSettings} from './nav';
import {TipLayer,Seg} from './BatchCharts';
import {LotTab} from './BatchLot';
import {LotWindow,type Drafts} from './BatchLotWindow';
import {UtilTab} from './BatchUtil';
import {WphTab} from './BatchWph';
import {CompareTab} from './BatchCompare';
import {FindTab,type FindCond} from './BatchFind';
import {DevHelp} from './DevHelp';
import {Q,DefectWindow} from './BatchHelp';
import {useDev,setDevLocked,setDevDrafts,registerDraftHandlers} from './devmode';
import {loadView,batchCall,addDays,ymd,type View,type ViewMeta,type ViewName,type LotDetail,type Raw,type AggGroup} from './batchData';

/* Batch Report 분석 — 큰 탭 2개: [가동률 조사 및 분석](조사 범위 공통 · Lot 추적 · 가동률 · WPH) /
   [Batch Report 찾기 · 취합]. 사용자 검토를 마친 프로토타입(tools/batch_prototype)과 같은 화면이다.
   계산은 엔진(batchview), 화면은 받은 요약으로 그린다. Lot 상세 · 원문은 누를 때 받는다. */
type Target={machine:string;query:string;start:string;end:string;names?:string[]};
const today=()=>ymd(new Date());

export function Batch({active}:{active:boolean}){
  const dev=useDev();
  const [config,setConfig]=useState<Configuration>();
  const [main,setMain]=useState<'analysis'|'find'>('analysis');
  const [sub,setSub]=useState<'lot'|'util'|'wph'|'cmp'>('lot');
  const [machines,setMachines]=useState<string[]>([]);
  const [allDates,setAllDates]=useState(true),[from,setFrom]=useState(''),[to,setTo]=useState(''),[preset,setPreset]=useState<'30'|'90'|null>(null);
  const [reuse,setReuse]=useState(true);
  const [views,setViews]=useState<{scope?:View;find?:View}>({});
  const [running,setRunning]=useState(false),[autoRun,setAutoRun]=useState(false),[cancelSent,setCancelSent]=useState(false);
  const [progress,setProgress]=useState<{message:string;current?:number;total?:number}>();
  const [busy,setBusy]=useState(false),[restoring,setRestoring]=useState(false);
  const [lot,setLot]=useState<{view:ViewName;li:number}>(),[detail,setDetail]=useState<LotDetail>(),[lotXlsx,setLotXlsx]=useState('');
  const [raw,setRaw]=useState<Raw>();
  const [drafts,setDrafts]=useState<Drafts>({});
  const [help,setHelp]=useState(false),[defect,setDefect]=useState(false);
  const [cond,setCond]=useState<FindCond>({machines:[],query:'',start:'',end:''});
  const [fstep,setFstep]=useState(0),[finding,setFinding]=useState(false),[fprog,setFprog]=useState('');
  const job=useRef<number|undefined>(undefined),runningRef=useRef(false),restoringRef=useRef(false),autoBlocked=useRef(false),first=useRef(true);
  const critRef=useRef<HTMLDialogElement>(null),rawRef=useRef<HTMLDialogElement>(null);

  useEffect(()=>{const on=()=>setDefect(true);window.addEventListener('bv:defect',on);return()=>window.removeEventListener('bv:defect',on);},[]);
  async function loadConfig(){
    try{
      await desktop.connect();
      const data=(await desktop.request('configuration').promise) as Configuration;
      if(!Array.isArray(data.machines))throw new Error('configuration_failed');
      setConfig(data);
      const ids=new Set(data.machines.map(m=>m.id));
      if(first.current){
        first.current=false;
        const last=(data.last?.targets||[]) as Target[];
        setMachines([...new Set(last.map(t=>t.machine))].filter(id=>ids.has(id)));
        const t0=last[0];
        if(t0&&(t0.start||t0.end)){setAllDates(false);setFrom(t0.start||'');setTo(t0.end||'');}
        setCond(c=>({...c,machines:data.machines.map(m=>m.id)}));
        if(!views.scope)void restore();
      }else{
        setMachines(old=>old.filter(id=>ids.has(id)));
        setCond(c=>({...c,machines:c.machines.filter(id=>ids.has(id))}));
      }
    }catch(e){fail(e);}
  }
  async function restore(){
    restoringRef.current=true;setRestoring(true);
    try{const r=await batchCall<{meta:ViewMeta;restored:boolean}>('batch_restore',{});
      if(r.restored){const v=await loadView(r.meta);if(v)setViews(o=>o.scope?o:{...o,scope:v});}}
    catch{/* 지난 결과가 없거나 캐시를 못 읽음: 조사 시작으로 새로 만든다 */}
    finally{restoringRef.current=false;setRestoring(false);}
  }
  useEffect(()=>{void loadConfig();},[]);
  useEffect(()=>{if(active&&!first.current&&!runningRef.current)void loadConfig();},[active]);

  // 개발자 기능: 조사 중 잠금 · 저장 안 한 선택 수 · 설정 화면의 끄기 확인창이 쓰는 저장/버리기.
  useEffect(()=>{setDevLocked(running);},[running]);
  const nDrafts=Object.keys(drafts).length;
  useEffect(()=>{setDevDrafts(nDrafts);},[nDrafts]);
  const draftsRef=useRef(drafts);draftsRef.current=drafts;
  const lotRef=useRef(lot);lotRef.current=lot;
  useEffect(()=>registerDraftHandlers({save:()=>saveDrafts(),drop:()=>{setDrafts({});}}),[]);
  useEffect(()=>{if(!dev.on&&nDrafts)setDrafts({});},[dev.on]);

  async function reloadViews(metas:Record<string,ViewMeta>){
    const next:{scope?:View;find?:View}={};
    for(const [name,meta] of Object.entries(metas)){const v=await loadView(meta);if(v)next[name as ViewName]=v;}
    setViews(o=>({...o,...next}));
  }
  async function saveDrafts():Promise<boolean>{
    const all=draftsRef.current;const by:Record<string,[number,number,string,number][]>={};
    Object.entries(all).forEach(([k,p])=>{const s=k.split('|');(by[s[0]]||=[]).push([+s[1],+s[2],s.slice(3).join('|'),p]);});
    if(!Object.keys(by).length)return true;
    setBusy(true);
    try{let metas:Record<string,ViewMeta>={},saved=0;
      for(const [view,changes] of Object.entries(by)){const r=await batchCall<{saved:number;views:Record<string,ViewMeta>}>('batch_choices',{view,changes});metas=r.views;saved=r.saved;}
      await reloadViews(metas);setDrafts({});
      const open=lotRef.current;if(open)setDetail(await batchCall<LotDetail>('batch_lot',{view:open.view,lot:open.li}));
      notify(`선택을 저장했습니다 — 개발자 기능을 꺼도 이 선택이 적용됩니다(저장된 사람 선택 ${saved}건). 가동률 · WPH도 다시 계산했습니다.`,'ok');return true;}
    catch(e){fail(e);return false;}finally{setBusy(false);}
  }
  const setDraft=(k:string,p:number|null)=>setDrafts(o=>{const n={...o};if(p==null)delete n[k];else n[k]=p;return n;});

  // ---- 조사 ---------------------------------------------------------------------
  const allIds=config?.machines.map(m=>m.id)||[];
  function targetsNow():Target[]{return machines.map(machine=>({machine,query:'',start:allDates?'':from,end:allDates?'':to}));}
  function optionsNow(saved?:Partial<Options>):Options&{reuse:boolean}{
    const metrics=(config?.metrics?.map(m=>m.id)||defaults.metrics) as Options['metrics'];
    return {...defaults,...saved,metrics,reuse:true};
  }
  async function start(){
    if(runningRef.current||!config||restoring)return;
    if(!machines.length){notify('조사할 호기를 하나 이상 고르세요.','error');return;}
    if(!allDates&&from&&to&&from>to){notify('시작일은 종료일보다 늦을 수 없습니다.','error');return;}
    autoBlocked.current=false;
    await launch(targetsNow(),{...optionsNow(config.last?.options),reuse},false);
  }
  async function launch(payload:Target[],opts:Options&{reuse:boolean},automatic:boolean){
    runningRef.current=true;setRunning(true);setAutoRun(automatic);setCancelSent(false);setProgress(undefined);
    try{
      if(job.current!==undefined){await desktop.request('release',{job:job.current}).promise.catch(()=>undefined);job.current=undefined;}
      const task=desktop.request('investigate',{targets:payload,options:opts},(ev:Reply)=>{if(ev.event==='accepted')job.current=ev.job;
        if(ev.message)setProgress({message:ev.message,current:ev.current??undefined,total:ev.total??undefined});});
      const reply=await task.promise;
      if(reply.event==='cancelled'){notify('조사가 취소되었습니다. 이전 결과는 그대로입니다.','info');return;}
      const meta=(reply as Reply&{view?:ViewMeta}).view;
      if(job.current!==undefined){await desktop.request('release',{job:job.current}).promise.catch(()=>undefined);job.current=undefined;}
      if(meta){setProgress({message:'결과를 화면으로 받는 중…'});const v=await loadView(meta);if(v)setViews(o=>({...o,scope:v}));}
      setDrafts(d=>Object.fromEntries(Object.entries(d).filter(([k])=>!k.startsWith('scope|'))));
      notify((automatic?'Batch Report 자동 갱신: ':'')+(reply.collection?.errors?'일부 원본을 읽지 못했습니다. 읽기 오류를 확인하세요.':'조사를 완료했습니다.'),reply.collection?.errors?'info':'ok');
    }catch(e){
      if(automatic){autoBlocked.current=true;notify('Batch Report 자동 갱신 실패: '+errorText(e),'error');}else fail(e);
    }finally{runningRef.current=false;setRunning(false);setAutoRun(false);setProgress(undefined);}
  }
  // 하루 1회 자동 분석(설정 › Batch Report 분석 주기 설정): 지난 조사 조건으로, 캐시는 늘 재사용.
  useEffect(()=>{
    const timer=window.setInterval(async()=>{
      if(runningRef.current||restoringRef.current||autoBlocked.current)return;
      try{
        const data=(await desktop.request('configuration').promise) as Configuration;
        if(!data.auto?.enabled||!data.auto.due||runningRef.current)return;
        const ids=new Set(data.machines.map(m=>m.id)),seen=new Set<string>();
        const payload=((data.last?.targets||[]) as Target[]).filter(t=>ids.has(t.machine)&&!seen.has(t.machine)&&seen.add(t.machine))
          .map(({machine,query,start,end,names})=>names&&names.length?{machine,query:query||'',start:start||'',end:end||'',names}:{machine,query:query||'',start:start||'',end:end||''});
        if(!payload.length)return;
        const metrics=(data.metrics?.map(m=>m.id)||defaults.metrics) as Options['metrics'];
        await launch(payload,{...defaults,...data.last?.options,metrics,reuse:true},true);
      }catch{/* engine busy with another screen: try again next minute */}
    },60000);
    return()=>window.clearInterval(timer);
  },[]);
  async function cancel(){if(job.current===undefined)return;setCancelSent(true);try{await desktop.request('cancel',{job:job.current}).promise;}catch(e){fail(e);setCancelSent(false);}}

  // ---- Lot 창 · 원문 ---------------------------------------------------------------
  async function openLot(view:ViewName,li:number){
    setLot({view,li});setDetail(undefined);setLotXlsx('');
    try{setDetail(await batchCall<LotDetail>('batch_lot',{view,lot:li}));}catch(e){fail(e);}
  }
  async function showRaw(view:ViewName,g:number){
    try{setRaw(await batchCall<Raw>('batch_raw',{view,report:g}));}catch(e){fail(e);}
  }
  useEffect(()=>{const d=rawRef.current;if(raw&&d&&!d.open)d.showModal();},[raw]);
  async function openFile(view:ViewName,g:number){try{const r=await batchCall<Raw>('batch_raw',{view,report:g});if(r.path)await openPath(r.path);}catch(e){fail(e);}}
  async function exportLot(d:Record<string,number>){
    if(!lot)return;const l=views[lot.view]?.lots[lot.li];if(!l)return;
    const nd=Object.keys(d).length,ns=detail?detail.bunches.reduce((a,b)=>a+b.wafers.filter(w=>w.ov).length,0):l.saved;
    const stamp='추천(가장 나중 Pass)'+(ns?` + 저장된 사람 선택 ${ns}건`:'')+(nd?` + 저장 전 미리 보기 ${nd}건`:'');
    setBusy(true);
    try{const r=await batchCall<{path:string}>('batch_export',{view:lot.view,kind:'lot',lot:lot.li,drafts:d,stamp});setLotXlsx(r.path);notify('Excel로 저장했습니다.','ok');}
    catch(e){fail(e);}finally{setBusy(false);}
  }

  // ---- 찾기 · 취합 -------------------------------------------------------------------
  async function runFind(c=cond){
    if(!c.query.trim()){notify('Batch Report 키워드를 입력하세요.','error');return;}
    if(!c.machines.length){notify('찾을 호기를 하나 이상 고르세요.','error');return;}
    setFinding(true);setFprog('');
    try{const meta=(await desktop.request('batch_find',{machines:c.machines,query:c.query.trim(),start:c.start,end:c.end},ev=>{if(ev.message)setFprog(ev.message);}).promise).batch as ViewMeta;
      const v=await loadView(meta);
      setViews(o=>({...o,find:v||{R:[],lots:[],excluded:[],U:[],waits:[],stops:[],N:[],L:[],X:{unit:{},faults:{},min_base:100,full:25},hits:[],range:['',''],saved:0,criteria:[]}}));
      setDrafts(d=>Object.fromEntries(Object.entries(d).filter(([k])=>!k.startsWith('find|'))));
      setFstep(1);}
    catch(e){fail(e);}finally{setFinding(false);setFprog('');}
  }
  async function aggregate(reports:number[]):Promise<AggGroup[]|undefined>{
    try{return (await batchCall<{groups:AggGroup[]}>('batch_aggregate',{view:'find',reports})).groups;}catch(e){fail(e);return undefined;}
  }
  async function exportAgg(reports:number[],choices:Record<string,number>,stamp:string){
    setBusy(true);
    try{const r=await batchCall<{path:string}>('batch_export',{view:'find',kind:'agg',reports,choices,stamp});notify('Excel로 저장했습니다.','ok');return r.path;}
    catch(e){fail(e);return undefined;}finally{setBusy(false);}
  }
  function toFind(code:string){
    const next={...cond,query:code,machines:cond.machines.length?cond.machines:allIds};
    setLot(undefined);setCond(next);setMain('find');setFstep(0);void runFind(next);
  }

  // ---- 화면 ------------------------------------------------------------------------
  const v=views.scope;
  const applied=v?.scope;
  const ids=useMemo(()=>applied?.machines?.length?applied.machines:v?[...new Set(v.R.map(r=>r.m))]:[],[v,applied]);
  const range=useMemo(()=>({from:applied?.start||v?.range[0]||'',to:applied?.end||v?.range[1]||''}),[v,applied]);
  const sameMachines=!!applied&&[...applied.machines].sort().join('|')===[...machines].sort().join('|');
  const sameDates=!!applied&&(allDates?!applied.start&&!applied.end:applied.start===from&&applied.end===to);
  const changed=!!applied&&!(sameMachines&&sameDates);
  const mstat=(id:string)=>{const s=v?.mstat?.[id];if(!s)return applied?.machines.includes(id)?'—':'조사 전';
    return s.offline?`연결 안 됨 · 캐시 ${s.records}`:s.cached?`캐시 ${s.records}개`:`새로 ${s.parsed} · 캐시 ${s.reused}`;};
  const pct=progress?.total?Math.round((progress.current||0)/progress.total*100):undefined;
  const status=restoring&&!running?'지난 조사 결과를 로컬 캐시에서 불러오는 중… (장비 접근 없음)':running?(cancelSent?'안전한 중단 지점을 기다리는 중…':progress?.message||(autoRun?'자동 분석 진행 중…':'장비 기록을 순차적으로 확인합니다.'))
    :v?`${v.restored?'지난 조사 결과(로컬 캐시 · 장비 접근 없음)':'조사 완료'} · ${range.from||'처음'} ~ ${range.to||'끝'} · 호기 ${ids.length}대 · Batch Report ${v.R.length}개`+
      (!v.restored&&v.collection?` (새로 읽음 ${v.collection.parsed} · 캐시 사용 ${v.collection.reused} · 읽기 오류 ${v.collection.errors})`:'')+(applied?.at?` · ${applied.at}`:'')
    :'조사할 호기와 기간을 고르고 [조사 시작]을 누르세요.';
  const lotView=lot?views[lot.view]:undefined;
  return <div className={'bv'+(dev.on?' dev':'')}>
    <TipLayer/>
    {(dev.on||(v?.saved||0)>0)&&<div className={'devbar '+(dev.on?'on':'info')} role="status">{dev.on?<>
        <b>개발자 기능 켜짐</b><button type="button" className="help-btn" aria-label="개발자 기능 설명" onClick={()=>setHelp(true)}>?</button>
        <span>중복 Pass를 Lot 창 [Lot · wafer 취합]에서 직접 고칠 수 있습니다 · 저장된 사람 선택 {v?.saved||0}건 적용 중{nDrafts>0&&<> · <b>저장 안 한 선택 {nDrafts}건</b>(저장 전에는 결과에 반영 안 됨)</>} · 끄기는 설정 › 정보</span><span className="grow"/>
        {nDrafts>0&&<><button type="button" className="primary" style={{minWidth:0}} disabled={busy} onClick={()=>void saveDrafts()}>저장</button><button type="button" onClick={()=>{setDrafts({});notify('저장 안 한 선택을 버렸습니다.','info');}}>버리기</button></>}</>
      :<><span>ⓘ 저장된 사람 선택 <b>{v?.saved}건</b>이 결과에 적용 중입니다(개발자 기능에서 저장). 나머지 wafer는 추천(가장 나중 Pass).</span>
        <button type="button" className="help-btn" aria-label="개발자 기능 설명" onClick={()=>setHelp(true)}>?</button></>}</div>}
    <div className="maintabs" role="tablist" aria-label="Batch Report 기능">
      <button role="tab" type="button" className={main==='analysis'?'active':''} aria-selected={main==='analysis'} onClick={()=>setMain('analysis')}>가동률 조사 및 분석<small>Lot 추적 · 가동률 · WPH — 조사 범위 공통</small></button>
      <button role="tab" type="button" className={main==='find'?'active':''} aria-selected={main==='find'} onClick={()=>setMain('find')}>Batch Report 찾기 · 취합<small>파일 이름으로 찾아 Lot별 Dice 취합</small></button></div>
    <div hidden={main!=='analysis'}>
      <section className="panel" aria-label="조사 범위">
        <div className="section-heading"><div><span className="step">조사 범위 · Lot 추적 · 가동률 · WPH 공통</span><h2>어느 호기의 어느 기간을 조사할까요?</h2></div>
          <span className="count">{machines.length}개 호기 · {allDates?'모든 기간':`${from||'처음'} ~ ${to||'끝'}`}</span></div>
        <div className="mhead"><span className="lbl">호기</span><span className="count">선택 {machines.length} / {allIds.length}</span><span className="grow"/>
          <label className="tgl2"><input type="checkbox" aria-label="모든 호기" disabled={running} checked={!!allIds.length&&machines.length===allIds.length}
            ref={el=>{if(el)el.indeterminate=machines.length>0&&machines.length<allIds.length;}} onChange={e=>setMachines(e.target.checked?allIds:[])}/> 모든 호기</label>
          <button type="button" className="gear" onClick={()=>goToSettings({sub:'aoi'})}>⚙ AOI 장비 호기 루트 설정</button></div>
        {config?.machines.length?<div className="mgrid" role="group" aria-label="조사할 호기">{config.machines.map(m=>{const on=machines.includes(m.id);
          return <label key={m.id} className={'mbox'+(on?' on':'')} data-tip={[m.id,m.folder,...(m.extra||[]).map(x=>'+ '+x),mstat(m.id)].join('\n')}>
            <input type="checkbox" aria-label={m.id+' 선택'} disabled={running} checked={on} onChange={e=>setMachines(o=>e.target.checked?[...o,m.id]:o.filter(x=>x!==m.id))}/>
            <span className="mn">{m.id}</span><span className="ms">{mstat(m.id)}</span></label>;})}</div>
          :<div className="empty-state"><h3>등록된 호기가 없습니다.</h3><p>[설정 › AOI 장비 호기 루트]에서 호기 폴더를 등록하세요. 그 아래 Reports 폴더를 읽습니다.</p></div>}
        <div className="scope-row">
          <div className="dates"><label className="field">시작일<input type="date" aria-label="조사 시작일" value={allDates?'':from} disabled={allDates||running} onChange={e=>{setFrom(e.target.value);setPreset(null);}}/></label>
            <label className="field">종료일<input type="date" aria-label="조사 종료일" value={allDates?'':to} disabled={allDates||running} onChange={e=>{setTo(e.target.value);setPreset(null);}}/></label>
            <label className="tgl2"><input type="checkbox" checked={allDates} disabled={running} onChange={e=>{setAllDates(e.target.checked);setPreset(null);}}/> 모든 기간</label>
            <Seg label="기간 빠른 선택" value={preset} items={[['30','최근 30일'],['90','최근 90일']]} onChange={k=>{const end=today();setAllDates(false);setPreset(k);setTo(end);setFrom(addDays(end,-(+k)+1));}}/></div>
          <label className="switch" title="끄면 고른 범위의 Batch Report를 전부 다시 엽니다"><input type="checkbox" checked={reuse} disabled={running} onChange={e=>setReuse(e.target.checked)}/>
            <span><b>이미 읽은 Batch Report는 다시 읽지 않기</b><small>파일 이름 · 수정시각 · 크기가 같으면 로컬 캐시 사용 (기본 켜짐)</small></span></label>
          <div className="go">{running?<button type="button" onClick={cancel} disabled={cancelSent||job.current===undefined}>{cancelSent?'취소 요청됨':'조사 취소'}</button>
            :<button className="primary" data-tour="batch:start" disabled={!config||!machines.length||restoring} onClick={start}>조사 시작 →</button>}
            <button type="button" className="help-btn lg" aria-label="Lot 판정 기준" title="어떤 기준으로 Lot을 조사하는지 보기" onClick={()=>critRef.current?.showModal()}>?</button></div></div>
        <p className="scope-status" role="status" aria-live="polite">{status}</p>
        {changed&&!running&&<p className="hint" style={{color:'#8a5a00'}}>조사 범위를 바꿨습니다 — [조사 시작]을 눌러야 아래 결과에 반영됩니다. 지금 결과는 {applied?.machines.length}대 · {applied?.start||'처음'} ~ {applied?.end||'끝'} 기준입니다.</p>}
        {running&&<div className="progress3" role="progressbar" aria-label="조사 중" aria-valuenow={pct}><span style={{width:(pct??35)+'%'}}/></div>}
        <p className="hint">조사 범위는 어떻게 읽나요? <Q id="scope.logic"/> · 자동 분석: <b>{config?.auto?.enabled?'켜짐':'꺼짐'}</b>{config?.auto?.last_run?` · 마지막 실행 ${config.auto.last_run} (${config.auto.last_result||'—'})`:''} — [설정 › Batch Report 분석 주기 설정]에서 바꿀 수 있습니다.</p>

        {v?.errors&&v.errors.length>0&&<details className="more"><summary>읽기 오류 {v.errors.length}건</summary><div className="table-scroll" style={{maxHeight:240,marginTop:8}}><table className="t-compact">
          <thead><tr><th>호기</th><th>Report</th><th>오류</th></tr></thead><tbody>{v.errors.map((e,i)=><tr key={i}><td>{e[0]}</td><td>{e[1]}</td><td>{e[2]}</td></tr>)}</tbody></table></div></details>}
        {v?.artifacts&&Object.values(v.artifacts).some(Boolean)&&<details className="more"><summary>저장된 결과 파일 (Lot 추적 HTML · Excel · HTML · 가동률 대시보드)</summary><div className="outputs">
          {v.artifacts.lots&&<OpenPath label="Lot 추적 HTML" path={v.artifacts.lots}/>}{v.artifacts.xlsx&&<OpenPath label="Excel" path={v.artifacts.xlsx}/>}
          {v.artifacts.html&&<OpenPath label="HTML" path={v.artifacts.html}/>}{v.artifacts.dashboard&&<OpenPath label="가동률 대시보드" path={v.artifacts.dashboard}/>}
          {v.artifacts.outdir&&<OpenPath label="결과 폴더" path={v.artifacts.outdir} folder/>}</div></details>}
      </section>
      <div className="pilltabs" role="tablist" aria-label="분석 화면" data-tour="batch:tabs">{([['lot','Lot 추적'],['util','가동률'],['wph','WPH · 생산능력'],['cmp','레시피 비교']] as const).map(([k,t])=>
        <button key={k} role="tab" type="button" className={sub===k?'active':''} aria-selected={sub===k} onClick={()=>setSub(k)}>{t}</button>)}</div>
      {sub==='cmp'?<CompareTab v={v} showRaw={g=>void showRaw('scope',g)}/>
        :!v?<section className="panel"><div className="empty-state"><span className="empty-symbol" aria-hidden="true">▤</span><h3>{running?'결과를 준비하고 있습니다.':'아직 조사 결과가 없습니다.'}</h3>
          <p>위에서 호기와 기간을 고르고 [조사 시작]을 누르면 Lot 추적 · 가동률 · WPH를 볼 수 있습니다.</p></div></section>
        :sub==='lot'?<LotTab v={v} openLot={li=>void openLot('scope',li)} showRaw={g=>void showRaw('scope',g)}/>
        :sub==='util'?<UtilTab v={v} ids={ids} range={range} openLot={li=>void openLot('scope',li)} showRaw={g=>void showRaw('scope',g)}/>
        :<WphTab v={v} ids={ids} range={range} openLot={li=>void openLot('scope',li)} showRaw={g=>void showRaw('scope',g)}/>}
    </div>
    <div hidden={main!=='find'}>
      <FindTab machines={config?.machines||[]} view={views.find} busy={finding||busy||restoring} dev={dev.on} progress={fprog} cond={cond} setCond={setCond} onFind={()=>void runFind()}
        aggregate={aggregate} exportAgg={exportAgg} openLot={li=>void openLot('find',li)} showRaw={g=>void showRaw('find',g)} openFile={g=>void openFile('find',g)}
        onCrit={()=>critRef.current?.showModal()} goSettings={()=>goToSettings({sub:'aoi'})} step={fstep} setStep={setFstep}/>
    </div>
    {lot&&lotView&&<LotWindow v={lotView} view={lot.view} li={lot.li} detail={detail} dev={dev.on} drafts={drafts} setDraft={setDraft} busy={busy} xlsx={lotXlsx}
      onClose={()=>setLot(undefined)} showRaw={g=>void showRaw(lot.view,g)} toFind={toFind} onCrit={()=>critRef.current?.showModal()} onSave={()=>void saveDrafts()} onExport={exportLot}/>}
    <dialog className="edit-dialog mid" ref={critRef} aria-labelledby="critTitle"><h3 id="critTitle">Lot 판정 기준</h3>
      <p className="sub">한 Lot은 Batch Report 여러 장으로 나뉘고 다른 호기로 옮겨 다시 스캔되기도 합니다. 아래 기준으로 Batch Report를 Lot으로 모읍니다.</p>
      <dl className="criteria">{(config?.lot_criteria||[]).map(c=><div key={c.title}><dt>{c.title}</dt><dd>{c.text}{c.example&&<small>{c.example}</small>}</dd></div>)}</dl>
      {!config?.lot_criteria?.length&&<p className="table-empty">엔진에서 기준을 받지 못했습니다. 엔진 연결을 확인하세요.</p>}
      <div className="dialog-actions"><button type="button" className="primary" onClick={()=>critRef.current?.close()}>닫기</button></div></dialog>
    <dialog className="edit-dialog wide" ref={rawRef} aria-labelledby="rawTitle" onClose={()=>setRaw(undefined)}>{raw&&<>
      <span className="step">Batch Report 원문 창</span><h3 id="rawTitle">Batch Report 원문 — 스캔 1번(Batch Report 1장)의 표 그대로</h3>
      <p className="rawfile mono">{raw.f}</p>
      <p className="sub">{raw.m} · Reports 폴더 원문 그대로(앱 캐시에 읽어 둔 표). 장비 원본은 수정하지 않습니다. 이 Lot의 다른 Batch Report까지 모아 보려면 Lot 이름을 눌러 Lot 창을 여세요.</p>
      <div className="two" style={{gridTemplateColumns:'minmax(0,330px) minmax(0,1fr)',marginTop:0}}>
        <div className="table-scroll" style={{maxHeight:'60vh'}}><table className="t-compact"><tbody>{raw.meta.map((kv,i)=><tr key={i}><th style={{position:'static'}}>{kv[0]}</th><td>{kv[1]}</td></tr>)}</tbody></table></div>
        <div className="mapscroll" style={{maxHeight:'60vh'}}><table className="map"><thead><tr><th>#</th>{raw.h.map(x=><th key={x}>{x}</th>)}</tr></thead>
          <tbody>{raw.rows.map((w,k)=>{const si=raw.h.findIndex(x=>x.toLowerCase().replace(/[^a-z0-9]/g,'')==='passfail'),ok=/^pass[.!]?$/i.test(String(w[si]||'').trim());
            return <tr key={k}><th>{k+1}</th>{w.map((x,j)=><td key={j} className={j===si?(ok?'c-p':'c-e'):undefined}>{x}</td>)}</tr>;})}</tbody></table></div></div>
      <div className="dialog-actions"><button type="button" disabled={!raw.path} onClick={()=>void openPath(raw.path)}>원본 열기</button><button type="button" className="primary" onClick={()=>rawRef.current?.close()}>닫기</button></div></>}</dialog>
    <DevHelp open={help} onClose={()=>setHelp(false)}/>
    <DefectWindow v={v} open={defect} onClose={()=>setDefect(false)} showRaw={g=>void showRaw('scope',g)} openLot={li=>void openLot('scope',li)}/>
  </div>;
}
