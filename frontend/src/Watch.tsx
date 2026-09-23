import {useEffect,useState} from 'react';
import {desktop,type WatchNotice} from './desktop';
import {notify,fail} from './ui';
import {OpenPath} from './OpenPath';

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
type Row={id:number;use:boolean;variant:string;zone:string;alg:string;orig:string;name:string;transform:string;raw:string;display:string};
type Page={rows:Row[];total:number;used:number;offset:number};
const HOURS=Array.from({length:24},(_,i)=>i);
const TRANSFORMS=['RAW','LINEAR','AREA'];

async function ask<T>(method:string,params:object,key:'pwatch'|'cmwatch'|'watch'):Promise<T|undefined>{
  try{return (await desktop.request(method,params).promise)[key] as T;}catch(e){fail(e);return undefined;}
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

/* ------------------------------------------------------------------ */
/* 파라미터 자동 감시 (감시설정.json, 저장폴더 공유 — 한 PC만 실행)      */
/* ------------------------------------------------------------------ */
function ParamWatch({onChanged}:{onChanged:()=>void}){
  const [st,setSt]=useState<PState>(),[busy,setBusy]=useState(false);
  const [add,setAdd]=useState({machine:'',recipe:''}),[browse,setBrowse]=useState<Browse>();
  const [copyFrom,setCopyFrom]=useState(''),[copyTo,setCopyTo]=useState<string[]>([]);
  const load=()=>ask<PState>('pwatch_state',{},'pwatch').then(s=>s&&setSt(s));
  useEffect(()=>{void load();},[]);
  async function run<T>(method:string,params:object){
    setBusy(true);const r=await ask<T>(method,params,'pwatch');setBusy(false);return r;
  }
  async function save(enabled:boolean,patch:Partial<PState>={}){
    if(!st)return;const n={...st,...patch};
    const r=await run<PState>('pwatch_save',{enabled,interval_hours:n.interval_hours,window_start:n.window_start,window_end:n.window_end,notify_on_change_only:n.notify_on_change_only});
    if(r){setSt(r);onChanged();notify(enabled?'파라미터 자동 감시를 켰습니다.':'파라미터 자동 감시 설정을 저장했습니다.','ok');}
  }
  async function open(machine:string,recipe:string,sub:string){
    const r=await run<{dirs:string[];is_recipe:boolean;sub:string}>('pwatch_jobs',{machine,sub});
    if(r)setBrowse({machine,recipe,sub:r.sub,dirs:r.dirs,is_recipe:r.is_recipe});
  }
  async function assign(machine:string,recipe:string,rel:string){
    const r=await run<PState>('pwatch_set_path',{machine,recipe,rel});
    if(r){setSt(r);setBrowse(undefined);notify(rel?`${machine} · ${recipe} 감시 폴더를 지정했습니다.`:`${machine} · ${recipe} 감시를 뺐습니다.`,'ok');}
  }
  async function now(){
    setBusy(true);notify('파라미터 자동 감시를 한 번 실행합니다. 장비 수에 따라 몇 분 걸릴 수 있습니다.');
    try{
      const r=(await desktop.request('pwatch_run',{}).promise).pwatch as {summary:string;has_change:boolean;report:string;skipped:string[]};
      notify(`즉시 확인 완료 — ${r.summary}${r.skipped.length?` · 건너뜀 ${r.skipped.join(', ')}`:''}`,r.has_change?'info':'ok');
    }catch(e){fail(e);}
    setBusy(false);void load();
  }
  if(!st)return <section className="panel"><h2>파라미터 자동 감시</h2><p className="hint">설정을 불러오는 중…</p></section>;
  const byMachine=st.machines.map(m=>({m,rows:st.targets.filter(t=>t.machine===m)})).filter(x=>x.rows.length);
  const parts=browse?.sub?browse.sub.split('\\'):[];
  return <section className="panel">
    <div className="section-heading"><div><span className="step">WATCH</span><h2>파라미터 자동 감시</h2></div>
      <button className={st.enabled?'primary':''} disabled={busy} aria-pressed={st.enabled} onClick={()=>save(!st.enabled)}>{st.enabled?'● 켜짐':'○ 꺼짐'}</button></div>
    <p className="hint">장비의 지정 Job 폴더를 주기적으로 읽어 최신 취합과 비교합니다. <b>변경이 있을 때만</b> 저장폴더에 취합·변경보고서를 만들고 알립니다.
      장비는 탐색기(Win+R → \\장비IP\c$)로 미리 연결해 두세요. 한 번에 한 PC만 실행합니다.</p>
    {st.holder&&<p role="status">🔒 {st.holder} 님 PC가 감시를 실행 중입니다. 결과 알림은 이 PC에도 표시됩니다.</p>}
    <p className="hint">마지막 실행 {st.last_run||'—'} · {st.last_result||'—'}{st.fail_count?` · 연속 실패 ${st.fail_count}회(재시도 간격 늘림)`:''}{st.next_run?` · 다음 ${st.next_run}`:''}</p>
    <Schedule interval={st.interval_hours} intervals={st.intervals} start={st.window_start} end={st.window_end} disabled={busy}
      onChange={(k,v)=>setSt(s=>s&&{...s,[k]:v})}/>
    <div className="toolbar"><button disabled={busy} onClick={()=>save(st.enabled)}>주기·시간대 저장</button>
      <button disabled={busy||!st.targets.length} onClick={now}>▶ 즉시 확인</button>
      {st.log&&<OpenPath label="감시 로그" path={st.log}/>}</div>

    <h3>장비별 감시 대상 (호기 · 레시피 · Job 폴더)</h3>
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

    {st.reports.length>0&&<><h3>최근 변경보고서</h3>{st.reports.map(r=><OpenPath key={r.path} label={r.name} path={r.path}/>)}</>}

    {browse&&<div className="edit-dialog inline" role="dialog" aria-label="Job 폴더 선택">
      <h3>{browse.machine} · {browse.recipe} — Job 폴더 선택</h3>
      <p className="hint">\Job\{browse.sub||''} {browse.is_recipe&&'(레시피 설정 파일이 있는 폴더)'}</p>
      <p className="hint">Job 폴더(또는 그 아래 Setup/Recipes)까지만 골라도 됩니다. 그 아래 레시피는 자동으로 모두 읽습니다.</p>
      <div className="toolbar">{parts.length>0&&<button onClick={()=>open(browse.machine,browse.recipe,parts.slice(0,-1).join('\\'))}>⬆ 위로</button>}
        <button className="primary" disabled={!browse.sub} onClick={()=>assign(browse.machine,browse.recipe,browse.sub)}>이 폴더로 지정</button>
        <button onClick={()=>setBrowse(undefined)}>닫기</button></div>
      <div className="pick-list">{browse.dirs.map(d=><button key={d} className="pick-item" onClick={()=>open(browse.machine,browse.recipe,browse.sub?`${browse.sub}\\${d}`:d)}>📁 {d}</button>)}
        {!browse.dirs.length&&<p className="table-empty">하위 폴더가 없습니다.</p>}</div></div>}
  </section>;
}

/* ------------------------------------------------------------------ */
/* Commonality 자동 감시 (로컬 설정·결과, 새 S/M 감지 → 계획 → 조사)     */
/* ------------------------------------------------------------------ */
function CmWatch({onChanged}:{onChanged:()=>void}){
  const [st,setSt]=useState<CState>(),[busy,setBusy]=useState(false),[plan,setPlan]=useState<CPlan[]>([]);
  const [target,setTarget]=useState<CTarget>(),[cands,setCands]=useState<Cand[]>([]),[sm,setSm]=useState(''),[title,setTitle]=useState('');
  const [editing,setEditing]=useState<{version:string;recipe:string;index:number;total:number;used:number}>();
  const [page,setPage]=useState<Page>(),[offset,setOffset]=useState(0);
  const load=()=>ask<CState>('cmwatch_state',{},'cmwatch').then(s=>{if(s){setSt(s);setPlan(s.plan.length?s.plan:[{device:'',lot:'',machines:'',note:''}]);}});
  useEffect(()=>{void load();},[]);
  async function run<T>(method:string,params:object){setBusy(true);const r=await ask<T>(method,params,'cmwatch');setBusy(false);return r;}
  async function save(enabled:boolean){
    if(!st)return;
    const r=await run<CState>('cmwatch_save',{enabled,interval_hours:st.interval_hours,window_start:st.window_start,window_end:st.window_end,
      settle_minutes:st.settle_minutes,machines:st.machines,plan:plan.filter(p=>p.device.trim()||p.lot.trim())});
    if(r){setSt(r);setPlan(r.plan.length?r.plan:[{device:'',lot:'',machines:'',note:''}]);onChanged();notify(enabled?'Commonality 자동 감시를 켰습니다.':'Commonality 감시 설정을 저장했습니다.','ok');}
  }
  async function pickTarget(t:CTarget){
    setTarget(t);setSm('');setTitle(`${t.device}_${t.lot}`);
    const r=await run<{candidates:Cand[]}>('cmwatch_candidates',{machine:t.machine,device:t.device,lot:t.lot});
    setCands(r?.candidates||[]);if(r?.candidates.length)setSm(r.candidates[0].sm);
  }
  function opened(r:{stage:string;form?:{version:string;used:number};recipe?:string;index?:number;total?:number;forms?:string[]}|undefined){
    if(!r)return;
    if(r.stage==='edit'&&r.form){setEditing({version:r.form.version,recipe:r.recipe||'',index:r.index||0,total:r.total||1,used:r.form.used});setOffset(0);}
    else if(r.stage==='done'){setEditing(undefined);setTarget(undefined);notify(`감시 양식 ${r.forms?.length||0}개를 지정했습니다: ${(r.forms||[]).join(', ')}`,'ok');void load();}
  }
  useEffect(()=>{
    if(!editing)return;let active=true;
    desktop.request('cmwatch_page',{snapshot:editing.version,variant:'',query:'',used_only:false,offset,limit:100}).promise
      .then(r=>{if(active)setPage(r.cmwatch as Page);}).catch(e=>{if(active)fail(e);});
    return()=>{active=false;};
  },[editing,offset]);
  async function edit(row:Row,kind:'use'|'name'|'transform',value:boolean|string){
    if(!editing)return;
    try{await desktop.request('cmwatch_edit',{snapshot:editing.version,row:row.id,kind,value}).promise;
      const r=(await desktop.request('cmwatch_page',{snapshot:editing.version,variant:'',query:'',used_only:false,offset,limit:100}).promise).cmwatch as Page;
      setPage(r);setEditing(o=>o&&{...o,used:r.used});}catch(e){fail(e);}
  }
  async function now(){
    setBusy(true);
    try{const r=(await desktop.request('cmwatch_run',{}).promise).cmwatch as {summary:string;found:unknown[];notes:string[]};
      notify(`즉시 확인 완료 — ${r.summary||'새 S/M 없음'}${r.notes.length?` · ${r.notes.slice(0,3).join(' / ')}`:''}`,'ok');}
    catch(e){fail(e);}
    setBusy(false);void load();
  }
  if(!st)return <section className="panel"><h2>Commonality 자동 감시</h2><p className="hint">설정을 불러오는 중…</p></section>;
  return <section className="panel">
    <div className="section-heading"><div><span className="step">WATCH</span><h2>Commonality 자동 감시 (여러 호기 무인)</h2></div>
      <button className={st.enabled?'primary':''} disabled={busy} aria-pressed={st.enabled} onClick={()=>save(!st.enabled)}>{st.enabled?'● 켜짐':'○ 꺼짐'}</button></div>
    <p className="hint">감시 대상 (디바이스, 공정번호) 아래에 <b>새로 생긴 S/M 폴더</b>를 찾아 조사 계획에 추가하고, 감시 양식이 있으면 값 조사까지 합니다.
      첫 회차는 기준선만 잡고 알리지 않습니다. 설정·계획·결과는 모두 <b>로컬</b>에 저장됩니다(OneDrive 아님).</p>
    <p className="hint">마지막 실행 {st.last_run||'—'} · {st.last_result||'—'}{st.fail_count?` · 연속 실패 ${st.fail_count}회`:''}{st.next_run?` · 다음 ${st.next_run}`:''}</p>
    <Schedule interval={st.interval_hours} intervals={st.intervals} start={st.window_start} end={st.window_end} disabled={busy}
      onChange={(k,v)=>setSt(s=>s&&{...s,[k]:v})}/>
    <div className="form-filter"><label className="field">안정화 대기(분)<input type="number" min={0} max={1440} value={st.settle_minutes} onChange={e=>setSt(s=>s&&{...s,settle_minutes:Number(e.target.value)})}/></label>
      <span>감시 호기:</span>{st.available.length?st.available.map(m=><label key={m} className="field checkbox"><input type="checkbox" checked={st.machines.includes(m)}
        onChange={e=>setSt(s=>s&&{...s,machines:e.target.checked?[...s.machines,m]:s.machines.filter(x=>x!==m)})}/>{m}</label>)
        :<span className="hint">[설정]에서 호기별 Scanresult 루트를 먼저 등록하세요.</span>}</div>
    <h3>감시 대상 계획 (S/M 칸 없음 — 그 공정 아래 전부가 대상)</h3>
    <div className="table-scroll"><table><thead><tr><th>디바이스명</th><th>공정번호</th><th>AOI호기(비우면 전체)</th><th>비고</th><th></th></tr></thead>
      <tbody>{plan.map((p,i)=><tr key={i}>{(['device','lot','machines','note'] as const).map(k=><td key={k}><input value={p[k]} maxLength={256} aria-label={`${i+1}행 ${k}`}
        onChange={e=>setPlan(o=>o.map((x,j)=>j===i?{...x,[k]:e.target.value}:x))}/></td>)}
        <td><button onClick={()=>setPlan(o=>o.length>1?o.filter((_,j)=>j!==i):[{device:'',lot:'',machines:'',note:''}])}>삭제</button></td></tr>)}</tbody></table></div>
    <div className="toolbar"><button onClick={()=>setPlan(o=>[...o,{device:'',lot:'',machines:'',note:''}])}>+ 행 추가</button>
      <button disabled={busy} onClick={()=>save(st.enabled)}>설정·계획 저장</button>
      <button disabled={busy||!st.machines.length} onClick={now}>▶ 즉시 확인</button>
      {st.results&&<OpenPath label="자동감시 폴더" path={st.results} folder/>}{st.log&&<OpenPath label="감시 로그" path={st.log}/>}</div>

    <h3>대상별 감시 양식</h3>
    {st.targets.length?<div className="table-scroll"><table><thead><tr><th>호기</th><th>디바이스</th><th>공정</th><th>양식</th><th></th></tr></thead>
      <tbody>{st.targets.map(t=><tr key={t.machine+t.device+t.lot}><td>{t.machine}</td><td>{t.device}</td><td>{t.lot}</td>
        <td>{t.forms.length?t.forms.map(f=><span key={f.recipe} className={f.ok?'':'muted'}>{f.recipe} (대표 {f.sm}){f.ok?'':' — 파일 없음'} </span>):<span className="muted">양식 없음 — 계획 추가만 합니다</span>}</td>
        <td><button disabled={busy} onClick={()=>pickTarget(t)}>📋 양식 지정…</button></td></tr>)}</tbody></table></div>
      :<p className="table-empty">저장된 계획에서 감시 호기에 해당하는 대상이 없습니다.</p>}

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
      <div className="table-scroll"><table><thead><tr><th>사용</th><th>변형</th><th>Zone</th><th>Alg</th><th>원본 항목</th><th>표시 이름</th><th>변환</th><th>값</th></tr></thead>
        <tbody>{(page?.rows||[]).map(row=><tr key={row.id} className={row.use?'':'muted'}>
          <td><input type="checkbox" checked={row.use} aria-label={`${row.orig} 사용`} onChange={e=>edit(row,'use',e.target.checked)}/></td>
          <td>{row.variant||'(기본)'}</td><td>{row.zone}</td><td>{row.alg}</td><td>{row.orig}</td>
          <td><input value={row.name} maxLength={200} aria-label={`${row.orig} 표시 이름`} onChange={e=>setPage(p=>p&&{...p,rows:p.rows.map(r=>r.id===row.id?{...r,name:e.target.value}:r)})} onBlur={e=>void edit(row,'name',e.target.value)}/></td>
          <td><select value={row.transform} aria-label={`${row.orig} 변환`} onChange={e=>edit(row,'transform',e.target.value)}>{TRANSFORMS.map(t=><option key={t}>{t}</option>)}</select></td>
          <td>{row.display||row.raw}</td></tr>)}</tbody></table></div>
      <div className="pagination"><span>{page?.total?`${offset+1}–${Math.min(offset+100,page.total)} / ${page.total}개`:'0개'}</span>
        <div><button disabled={offset===0} onClick={()=>setOffset(n=>Math.max(0,n-100))}>이전</button><button disabled={offset+100>=(page?.total||0)} onClick={()=>setOffset(n=>n+100)}>다음</button></div></div>
      <div className="toolbar"><button onClick={async()=>{await run('cmwatch_cancel',{});setEditing(undefined);setTarget(undefined);}}>취소</button>
        <button className="primary" disabled={busy||!editing.used} onClick={async()=>opened(await run('cmwatch_confirm',{snapshot:editing.version}))}>양식 확정{editing.index+1<editing.total?' · 다음 레시피 ▶':''}</button></div></div>}
  </section>;
}

/** 자동 감시 탭: 두 감시 설정 + 최근 알림. */
export function Watch({notices,onChanged}:{notices:WatchNotice[];onChanged:()=>void}){
  return <>
    <section className="panel"><div className="section-heading"><div><span className="step">NOTICE</span><h2>최근 알림</h2></div></div>
      <p className="hint">감시가 켜져 있으면 창을 닫아도 알림 영역(트레이)에 남아 계속 감시합니다. 트레이 아이콘을 누르면 다시 열립니다.</p>
      {notices.length?<ul className="notice-list">{[...notices].reverse().map((n,i)=><li key={i}><b>{n.title}</b> <small>{n.at}</small><p>{n.summary}</p>
        {n.report&&<OpenPath label="변경보고서" path={n.report}/>}</li>)}</ul>:<p className="table-empty">아직 알림이 없습니다.</p>}</section>
    <ParamWatch onChanged={onChanged}/>
    <CmWatch onChanged={onChanged}/>
  </>;
}
