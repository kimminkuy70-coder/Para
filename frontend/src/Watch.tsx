import {useEffect,useState} from 'react';
import {desktop,errorText,type WatchNotice} from './desktop';
import {notify,fail,LoadFailed,Stepper,StepNav} from './ui';
import {RowPick} from './RowPick';
import {OpenPath} from './OpenPath';
import {FormEditor} from './FormEditor';

type Interval={hours:number;label:string};
type PTarget={machine:string;recipe:string;path:string};
type PState={enabled:boolean;interval_hours:number;intervals:Interval[];window_start:number;window_end:number;
  notify_on_change_only:boolean;targets:PTarget[];machines:string[];recipes:string[];last_run:string;last_result:string;
  fail_count:number;next_run:string;owned:boolean;holder:string;reports:{name:string;path:string}[];log:string};
type CForm={recipe:string;sm:string;ok:boolean};
type CTarget={machine:string;device:string;lot:string;forms:CForm[]};
type CPlan={device:string;lot:string;machines:string;note:string};
type CState={enabled:boolean;interval_hours:number;intervals:Interval[];window_start:number;window_end:number;settle_minutes:number;
  machines:string[];available:string[];plan:CPlan[];plan_file:string;targets:CTarget[];last_run:string;last_result:string;
  fail_count:number;baseline:boolean;next_run:string;results:string;log:string};
type Browse={machine:string;recipe:string;sub:string;dirs:string[];is_recipe:boolean};
type Cand={sm:string;created:string;scan:string;slots:number};
const HOURS=Array.from({length:24},(_,i)=>i);

async function ask<T>(method:string,params:object,key:'pwatch'|'cmwatch'|'watch',onError?:(m:string)=>void):Promise<T|undefined>{
  try{return (await desktop.request(method,params).promise)[key] as T;}
  catch(e){if(onError)onError(errorText(e));else fail(e);return undefined;}
}
function Schedule({interval,intervals,start,end,onChange,disabled}:{interval:number;intervals:Interval[];start:number;end:number;
  onChange:(k:'interval_hours'|'window_start'|'window_end',v:number)=>void;disabled?:boolean}){
  return <div className="form-filter">
    <label className="field">주기<select value={interval} disabled={disabled} onChange={e=>onChange('interval_hours',Number(e.target.value))}>
      {intervals.map(i=><option key={i.hours} value={i.hours}>{i.label}</option>)}</select></label>
    <label className="field">실행 시간대 시작<select value={start} disabled={disabled} onChange={e=>onChange('window_start',Number(e.target.value))}>{HOURS.map(h=><option key={h} value={h}>{h}시</option>)}</select></label>
    <label className="field">끝<select value={end} disabled={disabled} onChange={e=>onChange('window_end',Number(e.target.value))}>{HOURS.map(h=><option key={h} value={h}>{h}시</option>)}</select></label>
    <p className="hint">{start===end?(start===0?'시간 제한 없음':`매일 ${start}시에 시작해 주기마다 반복`):`${start}시~${end}시 사이에만 실행`}</p>
  </div>;
}

const scheduleText=(s:{interval_hours:number;intervals:Interval[];window_start:number;window_end:number})=>{
  const every=s.intervals.find(i=>i.hours===s.interval_hours)?.label||`${s.interval_hours}시간`;
  const when=s.window_start===s.window_end?(s.window_start===0?'시간 제한 없음':`매일 ${s.window_start}시 시작`):`${s.window_start}시~${s.window_end}시`;
  return [every,when] as const;
};

/** ON/OFF: 저장된 설정 그대로 켜고 끈다(마법사에서 고치는 중인 값과 무관). OFF 는 빨강. */
function OnOff({on,busy,onToggle,label}:{on:boolean;busy:boolean;onToggle:()=>void;label:string}){
  return <button type="button" className={'onoff '+(on?'on':'off')} disabled={busy} aria-pressed={on}
    aria-label={`${label} ${on?'ON — 누르면 끕니다':'OFF — 누르면 켭니다'}`} onClick={onToggle}>{on?'ON':'OFF'}</button>;
}

/* ------------------------------------------------------------------ */
/* 파라미터 자동 감시 (감시설정.json, 저장폴더 공유 — 한 PC만 실행)      */
/* ------------------------------------------------------------------ */
const P_STEPS=['주기·시간대','감시 대상','확인·저장'];
type PDraft={interval_hours:number;window_start:number;window_end:number};
function ParamWatch({onChanged}:{onChanged:()=>void}){
  const [st,setSt]=useState<PState>(),[busy,setBusy]=useState(false),[step,setStep]=useState(0);
  const [draft,setDraft]=useState<PDraft>();
  const [add,setAdd]=useState({machine:'',recipe:''}),[browse,setBrowse]=useState<Browse>();
  const [copyFrom,setCopyFrom]=useState(''),[copyTo,setCopyTo]=useState<string[]>([]);
  const [loadError,setLoadError]=useState('');
  const accept=(s:PState)=>{setSt(s);setDraft({interval_hours:s.interval_hours,window_start:s.window_start,window_end:s.window_end});};
  const load=()=>{setLoadError('');return ask<PState>('pwatch_state',{},'pwatch',st?undefined:setLoadError).then(s=>s&&accept(s));};
  useEffect(()=>{void load();},[]);
  async function run<T>(method:string,params:object){
    setBusy(true);const r=await ask<T>(method,params,'pwatch');setBusy(false);return r;
  }
  // ON/OFF uses the saved schedule, never the wizard's unsaved edits.
  async function toggle(){
    if(!st)return;
    const r=await run<PState>('pwatch_save',{enabled:!st.enabled,interval_hours:st.interval_hours,window_start:st.window_start,
      window_end:st.window_end,notify_on_change_only:st.notify_on_change_only});
    if(r){setSt(r);onChanged();notify(r.enabled?'파라미터 자동 감시 ON':'파라미터 자동 감시 OFF',r.enabled?'ok':'info');}
  }
  async function saveSchedule(){
    if(!st||!draft)return;
    const r=await run<PState>('pwatch_save',{enabled:st.enabled,...draft,notify_on_change_only:st.notify_on_change_only});
    if(r){accept(r);onChanged();notify('파라미터 자동 감시 설정을 저장했습니다.','ok');}
    return r;
  }
  async function open(machine:string,recipe:string,sub:string){
    const r=await run<{dirs:string[];is_recipe:boolean;sub:string}>('pwatch_jobs',{machine,sub});
    if(r)setBrowse({machine,recipe,sub:r.sub,dirs:r.dirs,is_recipe:r.is_recipe});
  }
  async function assign(machine:string,recipe:string,rel:string){
    const r=await run<PState>('pwatch_set_path',{machine,recipe,rel});
    if(r){setSt(r);setBrowse(undefined);
      notify(rel?`${machine} · ${recipe} 감시 폴더를 지정했습니다.`:`${machine} · ${recipe} 감시를 뺐습니다.`,'ok');}
  }
  async function now(){
    setBusy(true);notify('파라미터 자동 감시를 한 번 실행합니다. 진행 과정은 위 [최근 알림]에 나옵니다.');
    try{
      const r=(await desktop.request('pwatch_run',{}).promise).pwatch as {summary:string;has_change:boolean;report:string;skipped:string[]};
      notify(`즉시 확인 완료 — ${r.summary}${r.skipped.length?` · 건너뜀 ${r.skipped.join(', ')}`:''}`,r.has_change?'info':'ok');
    }catch(e){fail(e);}
    setBusy(false);void load();
  }
  if(!st||!draft)return <section className="panel">{loadError?<LoadFailed message={loadError} onRetry={()=>void load()}/>:<p className="hint">설정을 불러오는 중…</p>}</section>;
  const byMachine=st.machines.map(m=>({m,rows:st.targets.filter(t=>t.machine===m)})).filter(x=>x.rows.length);
  const missing=st.targets.filter(t=>!t.path).length;
  const parts=browse?.sub?browse.sub.split('\\'):[];
  const [every,when]=scheduleText(st);
  const dirty=draft.interval_hours!==st.interval_hours||draft.window_start!==st.window_start||draft.window_end!==st.window_end;
  return <section className="panel watch-panel">
    <div className="section-heading"><div><span className="step">WATCH</span><h2>파라미터 자동 감시</h2></div>
      <OnOff on={st.enabled} busy={busy} onToggle={toggle} label="파라미터 자동 감시"/></div>
    <p className="hint">장비의 지정 Job 폴더를 주기적으로 읽어 최신 취합과 비교합니다. <b>변경이 있을 때만</b> 저장폴더에 취합·변경보고서를 만들고 알립니다.
      장비는 탐색기(Win+R → \\장비IP\c$)로 미리 연결해 두세요. 한 번에 한 PC만 실행합니다.</p>
    <h3>현황</h3>
    <table className="tbl watch-status" aria-label="파라미터 자동 감시 현황"><tbody>
      <tr><th>상태</th><td><b className={st.enabled?'st-on':'st-off'}>{st.enabled?'ON':'OFF'}</b>{st.holder?` · 🔒 ${st.holder} 님 PC가 실행 중`:st.enabled&&st.owned?' · 이 PC가 실행':''}</td></tr>
      <tr><th>주기 · 시간대</th><td>{every} · {when}</td></tr>
      <tr><th>감시 대상</th><td>{byMachine.length?byMachine.map(x=>`${x.m}(${x.rows.map(r=>r.recipe).join(', ')})`).join(' · '):'없음'}
        {missing>0&&<b className="warn"> · 폴더 미지정 {missing}건</b>}</td></tr>
      <tr><th>마지막 실행</th><td>{st.last_run||'—'}{st.last_result?` · ${st.last_result}`:''}</td></tr>
      <tr><th>다음 실행</th><td>{st.enabled?(st.next_run||'곧 실행'):'OFF — 실행하지 않음'}{st.fail_count?<b className="warn"> · 연속 실패 {st.fail_count}회(재시도 간격 늘림)</b>:''}</td></tr>
      <tr><th>기록</th><td>{st.log?<OpenPath label="감시 로그" path={st.log}/>:'—'}{st.reports.slice(0,3).map(r=><OpenPath key={r.path} label={r.name} path={r.path}/>)}</td></tr>
    </tbody></table>

    <h3>설정 마법사</h3>
    <Stepper labels={P_STEPS} current={step} onJump={setStep}/>
    <div className="step-body">
    {step===0&&<>
      <p className="hint">몇 시간마다, 어느 시간대에 감시할지 정합니다. 저장은 마지막 단계에서 합니다.</p>
      <Schedule interval={draft.interval_hours} intervals={st.intervals} start={draft.window_start} end={draft.window_end} disabled={busy}
        onChange={(k,v)=>setDraft(d=>d&&{...d,[k]:v})}/>
    </>}
    {step===1&&<>
      <p className="hint">호기와 레시피를 고른 뒤 장비의 Job 폴더를 지정합니다. 지정·변경·빼기는 바로 저장됩니다.</p>
      <div className="form-filter">
        <label className="field">호기<select value={add.machine} onChange={e=>setAdd(a=>({...a,machine:e.target.value}))}><option value="">선택</option>{st.machines.map(m=><option key={m}>{m}</option>)}</select></label>
        <label className="field">레시피<select value={add.recipe} onChange={e=>setAdd(a=>({...a,recipe:e.target.value}))}><option value="">선택</option>{st.recipes.map(r=><option key={r}>{r}</option>)}</select></label>
        <button disabled={busy||!add.machine||!add.recipe} onClick={()=>open(add.machine,add.recipe,'')}>📁 장비에서 폴더 고르기…</button>
      </div>
      {byMachine.length?<div className="table-scroll"><table><thead><tr><th>호기</th><th>레시피</th><th>Job 폴더(\Job\ 아래)</th><th></th></tr></thead>
        <tbody>{byMachine.flatMap(({m,rows})=>rows.map((t,i)=><tr key={m+t.recipe}>
          <td>{i===0?m:''}</td><td>{t.recipe}</td><td>{t.path||<b role="alert">미지정</b>}</td>
          <td><button disabled={busy} onClick={()=>open(m,t.recipe,'')}>변경</button> <button disabled={busy} onClick={()=>assign(m,t.recipe,'')}>빼기</button></td></tr>))}</tbody></table></div>
        :<p className="table-empty">감시 대상이 없습니다. 호기와 레시피를 고른 뒤 장비의 Job 폴더를 지정하세요.</p>}
      {byMachine.length>0&&<div className="form-filter"><label className="field">이 호기 경로를<select value={copyFrom} onChange={e=>setCopyFrom(e.target.value)}><option value="">선택</option>{byMachine.map(x=><option key={x.m}>{x.m}</option>)}</select></label>
        <span>다른 호기에 복사:</span>{st.machines.filter(m=>m!==copyFrom).map(m=><label key={m} className="field checkbox"><input type="checkbox" checked={copyTo.includes(m)} onChange={e=>setCopyTo(o=>e.target.checked?[...o,m]:o.filter(x=>x!==m))}/>{m}</label>)}
        <button disabled={busy||!copyFrom||!copyTo.length} onClick={async()=>{const r=await run<PState>('pwatch_copy_paths',{source:copyFrom,targets:copyTo});if(r){setSt(r);setCopyTo([]);notify('경로를 복사했습니다.','ok');}}}>복사</button></div>}
      {browse&&<div className="edit-dialog inline" role="dialog" aria-label="Job 폴더 선택">
        <h3>{browse.machine} · {browse.recipe} — Job 폴더 선택</h3>
        <p className="hint">\Job\{browse.sub||''} {browse.is_recipe&&'(레시피 설정 파일이 있는 폴더)'}</p>
        <p className="hint">Job 폴더(또는 그 아래 Setup/Recipes)까지만 골라도 됩니다. 그 아래 레시피는 자동으로 모두 읽습니다.</p>
        <div className="toolbar">{parts.length>0&&<button onClick={()=>open(browse.machine,browse.recipe,parts.slice(0,-1).join('\\'))}>⬆ 위로</button>}
          <button className="primary" disabled={!browse.sub} onClick={()=>assign(browse.machine,browse.recipe,browse.sub)}>이 폴더로 지정</button>
          <button onClick={()=>setBrowse(undefined)}>닫기</button></div>
        <div className="pick-list">{browse.dirs.map(d=><button key={d} className="pick-item" onClick={()=>open(browse.machine,browse.recipe,browse.sub?`${browse.sub}\\${d}`:d)}>📁 {d}</button>)}
          {!browse.dirs.length&&<p className="table-empty">하위 폴더가 없습니다.</p>}</div></div>}
    </>}
    {step===2&&<>
      <table className="tbl" aria-label="저장할 파라미터 감시 설정"><tbody>
        <tr><th>주기 · 시간대</th><td>{scheduleText({...st,...draft}).join(' · ')}{dirty&&<b className="warn"> (저장 안 됨)</b>}</td></tr>
        <tr><th>감시 대상</th><td>{st.targets.length}건{missing>0&&<b className="warn"> · 폴더 미지정 {missing}건 — 이대로 켜면 실패합니다</b>}</td></tr>
      </tbody></table>
      <div className="toolbar"><button className="primary" disabled={busy||!dirty} onClick={()=>void saveSchedule()}>설정 저장</button>
        <button disabled={busy||!st.targets.length} onClick={now}>▶ 즉시 확인</button></div>
      <p className="hint">감시를 켜고 끄는 것은 위 <b>ON/OFF</b> 버튼입니다(마법사와 따로 동작).</p>
    </>}
    </div>
    {step<P_STEPS.length-1&&<StepNav step={step} total={P_STEPS.length} busy={busy} onBack={()=>setStep(s=>s-1)} onNext={()=>setStep(s=>s+1)}/>}
    {step===P_STEPS.length-1&&<div className="stepnav"><button className="btn" disabled={busy} onClick={()=>setStep(s=>s-1)}>◀ 이전</button>
      <span className="stepcount">{P_STEPS.length} / {P_STEPS.length}</span><button className="btn" onClick={()=>setStep(0)}>⟲ 처음으로</button></div>}
  </section>;
}

/* ------------------------------------------------------------------ */
/* Commonality 자동 감시 (로컬 설정·결과, 새 S/M 감지 → 계획 → 조사)     */
/* ------------------------------------------------------------------ */
const C_STEPS=['주기·시간대','감시 호기','감시 대상 계획','대상별 감시 양식','확인'];
type CDraft={interval_hours:number;window_start:number;window_end:number;settle_minutes:number;machines:string[];plan:CPlan[]};
const EMPTY_ROW:CPlan={device:'',lot:'',machines:'',note:''};
function CmWatch({onChanged}:{onChanged:()=>void}){
  const [st,setSt]=useState<CState>(),[busy,setBusy]=useState(false),[step,setStep]=useState(0);
  const [draft,setDraft]=useState<CDraft>();
  const [target,setTarget]=useState<CTarget>(),[cands,setCands]=useState<Cand[]>([]),[sm,setSm]=useState(''),[title,setTitle]=useState('');
  const [editing,setEditing]=useState<{version:string;recipe:string;index:number;total:number;used:number}>();
  const [loadError,setLoadError]=useState('');
  const accept=(s:CState)=>{setSt(s);setDraft({interval_hours:s.interval_hours,window_start:s.window_start,window_end:s.window_end,
    settle_minutes:s.settle_minutes,machines:[...s.machines],plan:s.plan.length?s.plan:[{...EMPTY_ROW}]});};
  const load=()=>{setLoadError('');return ask<CState>('cmwatch_state',{},'cmwatch',st?undefined:setLoadError).then(s=>s&&accept(s));};
  useEffect(()=>{void load();},[]);
  // 설정에서 호기 루트를 추가/삭제하면 이 탭으로 돌아올 때 호기 목록만 새로 받는다(편집 중인 값은 유지).
  useEffect(()=>{const again=(e:Event)=>{if((e as CustomEvent<string>).detail!=='자동 감시')return;
    void ask<CState>('cmwatch_state',{},'cmwatch').then(s=>s&&setSt(o=>o?{...o,available:s.available}:s));};
    window.addEventListener('para:tab',again);return()=>window.removeEventListener('para:tab',again);},[]);
  async function run<T>(method:string,params:object){setBusy(true);const r=await ask<T>(method,params,'cmwatch');setBusy(false);return r;}
  // ON/OFF: saved settings only (the wizard's unsaved edits are not sent).
  async function toggle(){
    if(!st)return;
    const r=await run<CState>('cmwatch_save',{enabled:!st.enabled});
    if(r){setSt(r);onChanged();notify(r.enabled?'Commonality 자동 감시 ON':'Commonality 자동 감시 OFF',r.enabled?'ok':'info');}
  }
  async function saveDraft(){
    if(!st||!draft)return;
    const r=await run<CState>('cmwatch_save',{enabled:st.enabled,interval_hours:draft.interval_hours,window_start:draft.window_start,
      window_end:draft.window_end,settle_minutes:draft.settle_minutes,machines:draft.machines,plan:draft.plan.filter(p=>p.device.trim()||p.lot.trim())});
    if(r){accept(r);onChanged();notify('Commonality 감시 설정을 저장했습니다.','ok');}
    return r;
  }
  async function pickTarget(t:CTarget){
    setTarget(t);setSm('');setTitle(`${t.device}_${t.lot}`);
    const r=await run<{candidates:Cand[]}>('cmwatch_candidates',{machine:t.machine,device:t.device,lot:t.lot});
    setCands(r?.candidates||[]);if(r?.candidates.length)setSm(r.candidates[0].sm);
  }
  function opened(r:{stage:string;form?:{version:string;used:number};recipe?:string;index?:number;total?:number;forms?:string[]}|undefined){
    if(!r)return;
    if(r.stage==='edit'&&r.form){setEditing({version:r.form.version,recipe:r.recipe||'',index:r.index||0,total:r.total||1,used:r.form.used});}
    else if(r.stage==='done'){setEditing(undefined);setTarget(undefined);notify(`감시 양식 ${r.forms?.length||0}개를 지정했습니다: ${(r.forms||[]).join(', ')}`,'ok');void load();}
  }
  async function now(){
    setBusy(true);notify('Commonality 자동 감시를 한 번 실행합니다. 진행 과정은 위 [최근 알림]에 나옵니다.');
    try{const r=(await desktop.request('cmwatch_run',{}).promise).cmwatch as {summary:string;found:unknown[];notes:string[]};
      notify(`즉시 확인 완료 — ${r.summary||'새 S/M 없음'}${r.notes.length?` · ${r.notes.slice(0,3).join(' / ')}`:''}`,'ok');}
    catch(e){fail(e);}
    setBusy(false);void load();
  }
  if(!st||!draft)return <section className="panel">{loadError?<LoadFailed message={loadError} onRetry={()=>void load()}/>:<p className="hint">설정을 불러오는 중…</p>}</section>;
  const [every,when]=scheduleText(st);
  const planRows=st.plan.length;
  const formsOk=st.targets.filter(t=>t.forms.some(f=>f.ok)).length;
  const planDirty=JSON.stringify(draft.plan.filter(p=>p.device.trim()||p.lot.trim()))!==JSON.stringify(st.plan);
  const dirty=planDirty||draft.interval_hours!==st.interval_hours||draft.window_start!==st.window_start||draft.window_end!==st.window_end
    ||draft.settle_minutes!==st.settle_minutes||draft.machines.join('|')!==st.machines.join('|');
  // 대상별 양식(4단계)은 저장된 호기·계획으로 계산되므로, 넘어가기 전에 저장한다.
  async function next(){if(step===2&&dirty){if(!await saveDraft())return;}setStep(s=>s+1);}
  return <section className="panel watch-panel">
    <div className="section-heading"><div><span className="step">WATCH</span><h2>Commonality 자동 감시 (여러 호기 무인)</h2></div>
      <OnOff on={st.enabled} busy={busy} onToggle={toggle} label="Commonality 자동 감시"/></div>
    <p className="hint">감시 대상 (디바이스, 공정번호) 아래에 <b>새로 생긴 S/M 폴더</b>를 찾아 조사 계획에 추가하고, 감시 양식이 있으면 값 조사까지 합니다.
      첫 회차는 기준선만 잡고 알리지 않습니다. 설정·계획·결과는 모두 <b>로컬</b>에 저장됩니다(OneDrive 아님).</p>
    <h3>현황</h3>
    <table className="tbl watch-status" aria-label="Commonality 자동 감시 현황"><tbody>
      <tr><th>상태</th><td><b className={st.enabled?'st-on':'st-off'}>{st.enabled?'ON':'OFF'}</b>{st.baseline?'':' · 첫 회차 전(기준선 미설정)'}</td></tr>
      <tr><th>주기 · 시간대</th><td>{every} · {when} · 안정화 대기 {st.settle_minutes}분</td></tr>
      <tr><th>감시 호기</th><td>{st.machines.length?st.machines.join(', '):<b className="warn">없음</b>}</td></tr>
      <tr><th>감시 대상 계획</th><td>{planRows?`${planRows}행 (${st.plan.slice(0,4).map(p=>`${p.device}/${p.lot}`).join(', ')}${planRows>4?' …':''})`:<b className="warn">없음</b>}</td></tr>
      <tr><th>대상별 감시 양식</th><td>{st.targets.length?`${formsOk} / ${st.targets.length} 대상 지정됨`:'대상 없음'}{st.targets.length>formsOk&&<span className="hint"> · 양식 없는 대상은 계획 추가만 합니다</span>}</td></tr>
      <tr><th>마지막 실행</th><td>{st.last_run||'—'}{st.last_result?` · ${st.last_result}`:''}</td></tr>
      <tr><th>다음 실행</th><td>{st.enabled?(st.next_run||'곧 실행'):'OFF — 실행하지 않음'}{st.fail_count?<b className="warn"> · 연속 실패 {st.fail_count}회</b>:''}</td></tr>
      <tr><th>기록</th><td>{st.results&&<OpenPath label="자동감시 폴더" path={st.results} folder/>}{st.log&&<OpenPath label="감시 로그" path={st.log}/>}</td></tr>
    </tbody></table>

    <h3>설정 마법사</h3>
    <Stepper labels={C_STEPS} current={step} onJump={setStep}/>
    <div className="step-body">
    {step===0&&<>
      <p className="hint">감시 주기·시간대와, 새 폴더가 다 채워질 때까지 기다릴 시간(안정화 대기)을 정합니다.</p>
      <Schedule interval={draft.interval_hours} intervals={st.intervals} start={draft.window_start} end={draft.window_end} disabled={busy}
        onChange={(k,v)=>setDraft(d=>d&&{...d,[k]:v})}/>
      <div className="form-filter"><label className="field">안정화 대기(분)<input type="number" min={0} max={1440} value={draft.settle_minutes}
        onChange={e=>setDraft(d=>d&&{...d,settle_minutes:Number(e.target.value)})}/></label></div>
    </>}
    {step===1&&<>
      <p className="hint">새 S/M 폴더를 찾을 호기를 고릅니다. 목록은 [설정 › AOI 장비 호기 루트]에 등록된 호기입니다.</p>
      <RowPick label="감시 호기" columns={['호기']} value={draft.machines} onChange={v=>setDraft(d=>d&&{...d,machines:v})}
        rows={st.available.map(m=>({id:m,cells:[<b key="m">{m}</b>]}))}
        empty={<p className="table-empty">[설정 › AOI 장비 호기 루트]에서 호기 폴더를 먼저 등록하세요.</p>}/>
    </>}
    {step===2&&<>
      <p className="hint">감시할 (디바이스, 공정번호)를 적습니다. S/M 칸은 없습니다 — 그 공정 아래 새로 생기는 S/M 전부가 대상입니다. [다음]을 누르면 저장합니다.</p>
      <div className="table-scroll"><table><thead><tr><th>디바이스명</th><th>공정번호</th><th>AOI호기(비우면 전체)</th><th>비고</th><th></th></tr></thead>
        <tbody>{draft.plan.map((p,i)=><tr key={i}>{(['device','lot','machines','note'] as const).map(k=><td key={k}><input value={p[k]} maxLength={256} aria-label={`${i+1}행 ${k}`}
          onChange={e=>setDraft(d=>d&&{...d,plan:d.plan.map((x,j)=>j===i?{...x,[k]:e.target.value}:x)})}/></td>)}
          <td><button onClick={()=>setDraft(d=>d&&{...d,plan:d.plan.length>1?d.plan.filter((_,j)=>j!==i):[{...EMPTY_ROW}]})}>삭제</button></td></tr>)}</tbody></table></div>
      <div className="toolbar"><button onClick={()=>setDraft(d=>d&&{...d,plan:[...d.plan,{...EMPTY_ROW}]})}>+ 행 추가</button></div>
    </>}
    {step===3&&<>
      <p className="hint">대상마다 대표 S/M 으로 감시 양식을 만들면, 새 S/M 이 생길 때 값 조사까지 자동으로 합니다. 양식이 없으면 조사 계획에 추가만 합니다.</p>
      {st.targets.length?<div className="table-scroll"><table><thead><tr><th>호기</th><th>디바이스</th><th>공정</th><th>양식</th><th></th></tr></thead>
        <tbody>{st.targets.map(t=><tr key={t.machine+t.device+t.lot}><td>{t.machine}</td><td>{t.device}</td><td>{t.lot}</td>
          <td>{t.forms.length?t.forms.map(f=><span key={f.recipe} className={f.ok?'':'muted'}>{f.recipe} (대표 {f.sm}){f.ok?'':' — 파일 없음'} </span>):<span className="muted">양식 없음 — 계획 추가만 합니다</span>}</td>
          <td><button disabled={busy} onClick={()=>pickTarget(t)}>📋 양식 지정…</button></td></tr>)}</tbody></table></div>
        :<p className="table-empty">저장된 계획에서 감시 호기에 해당하는 대상이 없습니다. 2·3단계를 확인하세요.</p>}
      {target&&!editing&&<div className="edit-dialog inline" role="dialog" aria-label="대표 S/M 선택">
        <h3>{target.machine} · {target.device} / {target.lot} — 대표 S/M</h3>
        <p className="hint">양식을 만들 기준 S/M 을 고릅니다(최근 생성순). 로컬로 안전복사한 뒤 읽으며, 레시피가 여럿이면 레시피마다 양식을 따로 만듭니다.</p>
        <div className="pick-list">{cands.map(c=><label key={c.sm} className="pick-item"><input type="radio" name="rep-sm" checked={sm===c.sm} onChange={()=>setSm(c.sm)}/> {c.sm}
          <small> · 생성 {c.created||'—'} · 스캔 {c.scan||'—'} · 슬롯 {c.slots}</small></label>)}
          {!cands.length&&<p className="table-empty">이 대상 아래 S/M 폴더가 없습니다.</p>}</div>
        <label className="field">양식 제목<input value={title} maxLength={60} onChange={e=>setTitle(e.target.value)}/></label>
        <div className="toolbar"><button onClick={()=>setTarget(undefined)}>취소</button>
          <button className="primary" disabled={busy||!sm||!title.trim()} onClick={async()=>opened(await run('cmwatch_begin',{sm,title:title.trim()}))}>복사 후 양식 편집 ▶</button></div></div>}
      {editing&&<div className="edit-dialog inline" role="dialog" aria-label="감시 양식 편집">
        <div className="section-heading"><div><h3>{editing.recipe} 감시 양식 ({editing.index+1}/{editing.total})</h3></div><span className="count">사용 {editing.used}</span></div>
        <FormEditor version={editing.version} pageMethod="cmwatch_page" editMethod="cmwatch_edit" replyKey="cmwatch"
          onUsed={n=>setEditing(o=>o&&o.used!==n?{...o,used:n}:o)}/>
        <div className="toolbar"><button onClick={async()=>{await run('cmwatch_cancel',{});setEditing(undefined);setTarget(undefined);}}>취소</button>
          <button className="primary" disabled={busy||!editing.used} onClick={async()=>opened(await run('cmwatch_confirm',{snapshot:editing.version}))}>양식 확정{editing.index+1<editing.total?' · 다음 레시피 ▶':''}</button></div></div>}
    </>}
    {step===4&&<>
      <table className="tbl" aria-label="저장할 Commonality 감시 설정"><tbody>
        <tr><th>주기 · 시간대</th><td>{scheduleText({...st,...draft}).join(' · ')} · 안정화 대기 {draft.settle_minutes}분</td></tr>
        <tr><th>감시 호기</th><td>{draft.machines.join(', ')||<b className="warn">없음</b>}</td></tr>
        <tr><th>감시 대상 계획</th><td>{draft.plan.filter(p=>p.device.trim()||p.lot.trim()).length}행</td></tr>
        <tr><th>저장 상태</th><td>{dirty?<b className="warn">저장 안 된 변경이 있습니다</b>:'모두 저장됨'}</td></tr>
      </tbody></table>
      <div className="toolbar"><button className="primary" disabled={busy||!dirty} onClick={()=>void saveDraft()}>설정 저장</button>
        <button disabled={busy||!st.machines.length} onClick={now}>▶ 즉시 확인</button></div>
      <p className="hint">감시를 켜고 끄는 것은 위 <b>ON/OFF</b> 버튼입니다(마법사와 따로 동작).</p>
    </>}
    </div>
    {step<C_STEPS.length-1&&<StepNav step={step} total={C_STEPS.length} busy={busy} onBack={()=>setStep(s=>s-1)} onNext={()=>void next()}
      nextLabel={step===2&&dirty?'저장하고 다음':'다음'}/>}
    {step===C_STEPS.length-1&&<div className="stepnav"><button className="btn" disabled={busy} onClick={()=>setStep(s=>s-1)}>◀ 이전</button>
      <span className="stepcount">{C_STEPS.length} / {C_STEPS.length}</span><button className="btn" onClick={()=>setStep(0)}>⟲ 처음으로</button></div>}
  </section>;
}

/** 자동 감시 탭: 최근 알림(맨 위 고정) + 두 감시를 탭으로. 두 탭 모두 계속 살아 있어 편집 중인 값이 유지된다. */
const WATCH_TABS:[string,string][]=[['param','파라미터 자동 감시'],['cm','Commonality 자동 감시 (여러 호기 무인)']];
export function Watch({notices,onChanged}:{notices:WatchNotice[];onChanged:()=>void}){
  const [tab,setTab]=useState('param');
  return <>
    <section className="panel notice-panel"><div className="section-heading"><div><span className="step">NOTICE</span><h2>최근 알림</h2></div></div>
      <p className="hint">감시가 켜져 있으면 창을 닫아도 알림 영역(트레이)에 남아 계속 감시합니다. 트레이 아이콘을 누르면 다시 열립니다.
        회차마다 시작 → 진행 중 → 결과(변경 없음 포함)가 여기에 남습니다. 변경·새 S/M·실패만 팝업으로도 알립니다.</p>
      {notices.length?<ul className="notice-list">{[...notices].reverse().map((n,i)=><li key={i} className={(n.live?'live ':'')+(n.quiet?'quiet ':'')+(n.kind.endsWith('_failed')?'failed':'')}>
        {n.live&&<span className="spinner" aria-hidden="true"/>}<b>{n.title}</b> <small>{n.at}</small><p>{n.summary}</p>
        {n.report&&<OpenPath label="변경보고서" path={n.report}/>}</li>)}</ul>:<p className="table-empty">아직 알림이 없습니다.</p>}</section>
    <div className="subtabs" role="tablist" aria-label="자동 감시 종류">{WATCH_TABS.map(([id,label])=>
      <button key={id} role="tab" aria-selected={tab===id} className={tab===id?'active':''} onClick={()=>setTab(id)}>{label}</button>)}</div>
    <div hidden={tab!=='param'} className="kept-screen"><ParamWatch onChanged={onChanged}/></div>
    <div hidden={tab!=='cm'} className="kept-screen"><CmWatch onChanged={onChanged}/></div>
  </>;
}
