import {useEffect,useState} from 'react';
import {desktop,errorText} from './desktop';
import {notify,fail,LoadFailed} from './ui';
import {requestBatchRunNow} from './batchAuto';

// Batch Report 자동 분석 설정(#39: 설정 탭에서 CAMTEK › 자동 분석 및 취합 탭으로 옮김). 엔진 요청은 그대로 config_state · config_set_batch_auto.
type Auto={enabled:boolean;interval_hours:number;time?:string;publish?:boolean;kla?:boolean;kla_publish?:boolean;last_run:string;last_result:string;next_run:string};
type State={save_dir:string;batch_auto:boolean;batch?:Auto;batch_intervals?:number[];cache_share_dir?:string};
type Tab='camtek'|'kla';
export const periodLabel=(h:number)=>h%24===0?(h===24?'하루 1회 (24시간)':h===168?'일주일 1회':`${h/24}일마다`):`${h}시간마다`;
// 하루 단위 주기의 실행 시각(#33): 시 00~23, 분 5분 단위.
const HOURS=Array.from({length:24},(_,i)=>String(i).padStart(2,'0'));
const MINUTES=Array.from({length:12},(_,i)=>String(i*5).padStart(2,'0'));

export function BatchAutoPanel(){
  const [st,setSt]=useState<State>(),[busy,setBusy]=useState(false),[loadError,setLoadError]=useState('');
  // 자동 분석에 들어가는 회사별 작업(Para #43): CAMTEK = Batch Report 분석 · 캐시 게시, KLA = KLA 캐시 갱신 · 게시. 주기 · 시각은 같이 쓴다.
  const [tab,setTab]=useState<Tab>(()=>{try{return localStorage.getItem('para.batchAuto.tab')==='kla'?'kla':'camtek';}catch{return 'camtek';}});
  useEffect(()=>{try{localStorage.setItem('para.batchAuto.tab',tab);}catch{/* 저장 못 해도 동작 */}},[tab]);
  async function load(){
    setLoadError('');
    try{await desktop.connect();setSt((await desktop.request('config_state').promise).config as State);}
    catch(e){setLoadError(errorText(e));}
  }
  useEffect(()=>{void load();},[]);
  async function save(params:object,ok:string){
    setBusy(true);
    try{setSt((await desktop.request('config_set_batch_auto',{enabled:!!st?.batch_auto,...params}).promise).config as State);notify(ok,'ok');
      window.dispatchEvent(new Event('para:batch-auto-changed'));}
    catch(e){fail(e);}finally{setBusy(false);}
  }
  // Batch Report 자동 분석 실행 시각(#33) — "HH:MM" 5분 단위, 빈 문자열 = 지정 안 함.
  const autoTime=st?.batch?.time||'';
  const saveTime=(time:string)=>save({time},time?`실행 시각을 ${time} 으로 저장했습니다`:'실행 시각 지정을 껐습니다');
  const hours=st?.batch?.interval_hours??24;
  return <section className="panel">
    <div className="section-heading"><div><span className="step">BATCH REPORT</span><h2>Batch Report 자동 분석</h2></div>
      <button disabled={busy} onClick={()=>void load()}>새로고침</button></div>
    {loadError&&!st&&<LoadFailed message={loadError} onRetry={()=>void load()}/>}
    <p className="hint">앱이 켜져 있는 동안 주기마다 Batch Report 분석(CAMTEK)과, 켜 두었으면 KLA 캐시 갱신(KLA)을 다시 실행합니다.
      실행 기록은 기존 프로그램과 공유하므로 두 프로그램이 같은 주기 안에 중복 실행하지 않습니다(기존 프로그램은 항상 하루 1회).</p>
    <label className="field checkbox" style={{marginTop:10}}><input type="checkbox" disabled={busy||!st} checked={!!st?.batch_auto}
      onChange={e=>save({enabled:e.target.checked},e.target.checked?'자동 분석을 켰습니다':'자동 분석을 껐습니다')}/>자동 분석 사용 (기본 꺼짐)</label>
    <div className="form-filter" style={{marginTop:12}}>
      <label className="field" style={{width:220}}>분석 주기<select disabled={busy||!st} value={hours}
        onChange={e=>save({interval_hours:Number(e.target.value)},'분석 주기를 저장했습니다')}>
        {(st?.batch_intervals||[24]).map(h=><option key={h} value={h}>{periodLabel(h)}</option>)}</select></label>
      {hours%24===0&&<>
        <label className="field" style={{width:150}}>실행 시각 (시)<select disabled={busy||!st} value={autoTime?autoTime.slice(0,2):''}
          onChange={e=>saveTime(e.target.value?`${e.target.value}:${autoTime?autoTime.slice(3):'00'}`:'')}>
          <option value="">지정 안 함</option>{HOURS.map(h=><option key={h} value={h}>{h}시</option>)}</select></label>
        <label className="field" style={{width:130}}>분 (5분 단위)<select disabled={busy||!st||!autoTime} value={autoTime?autoTime.slice(3):'00'}
          onChange={e=>saveTime(`${autoTime.slice(0,2)}:${e.target.value}`)}>
          {MINUTES.map(m=><option key={m} value={m}>{m}분</option>)}</select></label></>}
      <button type="button" disabled={busy||!st} style={{alignSelf:'flex-end'}} title="자동 분석이 꺼져 있어도 지난 조사 조건으로 바로 한 번 실행합니다"
        onClick={requestBatchRunNow}>▶ 즉시 실행</button></div>
    {hours%24===0&&<p className="hint">{autoTime
      ?`${periodLabel(hours)} · ${autoTime} 에 실행합니다(그 시각에 앱이 꺼져 있었으면 앱을 켠 뒤 곧 실행).`
      :'실행 시각을 지정하지 않으면 마지막 실행(또는 마지막 조사) 시각부터 주기가 지나면 실행합니다.'} 켜거나 주기 · 시각을 바꾸면 그때부터 다시 셉니다.</p>}
    <p className="hint">[▶ 즉시 실행]은 자동 분석을 꺼 둔 채로도 지난 조사 조건으로 지금 한 번 분석합니다(Batch Report 분석 화면으로 이동).</p>
    <div className="subtabs auto-tabs" role="tablist" aria-label="자동 분석에 넣을 회사" style={{marginTop:14}}>
      <button role="tab" aria-selected={tab==='camtek'} className={tab==='camtek'?'active':''} onClick={()=>setTab('camtek')}>CAMTEK · Batch Report</button>
      <button role="tab" aria-selected={tab==='kla'} className={tab==='kla'?'active':''} onClick={()=>setTab('kla')}>KLA · KLA 캐시{st?.batch?.kla?' ✓':''}</button></div>
    {tab==='camtek'&&<div role="tabpanel" aria-label="CAMTEK 자동 분석">
      <p className="hint">마지막 조사 조건(호기 · 검색어 · 기간 · 지표)으로 Batch Report 를 다시 분석합니다.</p>
      <label className="field checkbox" style={{marginTop:10}}><input type="checkbox" disabled={busy||!st||!st.save_dir} checked={!!st?.batch?.publish}
        onChange={e=>save({publish:e.target.checked},e.target.checked?'자동 분석이 끝나면 캐시 zip 을 OneDrive 에 게시합니다':'OneDrive 게시를 껐습니다')}/>
        자동 분석이 끝나면 Batch Report 캐시 zip 을 OneDrive 에 올리기 (개발자 PC 용 · 기본 꺼짐)</label>
      <p className="hint">켜면 자동 분석(▶ 즉시 실행 포함)이 끝날 때마다 이 PC 의 캐시를 zip 1개로 만들어 {st?.cache_share_dir?<code>{st.cache_share_dir}</code>:'저장 폴더 옆 캐시공유 폴더'}에 올립니다(최근 3개만 보관).
        다른 사용자는 [Batch Report 분석 › OneDrive 에서 불러오기]로 받아 씁니다.
        {!st?.save_dir&&<b className="warn"> 저장 폴더(OneDrive)를 먼저 지정하세요.</b>}</p></div>}
    {tab==='kla'&&<div role="tabpanel" aria-label="KLA 자동 분석">
      <p className="hint">같은 주기 · 시각에 KLA 캐시도 갱신합니다(KLA 자재 찾기 › 🛠 개발자 기능 › [캐시 갱신]과 같음 — 장비 폴더 이름만 읽음). Batch Report 분석이 끝난 뒤 이어서 돌고, Camtek 지난 조사 조건이 없으면 KLA 만 돕니다.</p>
      <label className="field checkbox" style={{marginTop:10}}><input type="checkbox" aria-label="자동 분석에 KLA 캐시 갱신 넣기" disabled={busy||!st} checked={!!st?.batch?.kla}
        onChange={e=>save({kla:e.target.checked},e.target.checked?'자동 분석에 KLA 캐시 갱신을 넣었습니다':'자동 분석에서 KLA 캐시 갱신을 뺐습니다')}/>
        자동 분석에 KLA 캐시 갱신 넣기 (KLA 장비 폴더를 등록한 PC 용 · 기본 꺼짐)</label>
      <label className="field checkbox" style={{marginTop:6}}><input type="checkbox" aria-label="KLA 캐시 OneDrive 게시" disabled={busy||!st||!st.save_dir||!st.batch?.kla} checked={!!st?.batch?.kla&&!!st?.batch?.kla_publish}
        onChange={e=>save({kla_publish:e.target.checked},e.target.checked?'KLA 캐시 갱신이 끝나면 OneDrive 에 게시합니다':'KLA 캐시 OneDrive 게시를 껐습니다')}/>
        갱신이 끝나면 KLA 캐시 zip 을 OneDrive 에 올리기 (개발자 PC 용 · 기본 꺼짐)</label>
      <p className="hint">게시 위치는 Camtek 과 같은 {st?.cache_share_dir?<code>{st.cache_share_dir}</code>:'저장 폴더 옆 캐시공유 폴더'}이고 이름(<code>KLA_캐시_*.zip</code>)으로 구분합니다(최근 3개 보관).
        장비 폴더 등록은 <b>설정 › AOI 장비 호기 루트 › KLA</b>.
        {!st?.save_dir&&<b className="warn"> 저장 폴더(OneDrive)를 먼저 지정하세요.</b>}</p></div>}
    <table className="tbl" style={{marginTop:12}}><tbody>
      <tr><td style={{width:140,fontWeight:700}}>마지막 실행</td><td>{st?.batch?.last_run||'—'}{st?.batch?.last_result?` · ${st.batch.last_result}`:''}</td></tr>
      <tr><td style={{fontWeight:700}}>다음 실행</td><td>{st?.batch_auto?(st?.batch?.next_run||'앱을 켜 두면 곧 실행'):'꺼짐'}</td></tr></tbody></table>
    <p className="hint">분석 조건은 [Batch Report 분석] 탭에서 마지막으로 조사한 조건을 그대로 씁니다. 자동 분석은 [Batch Report 분석] 화면을 한 번 연 뒤부터 돕니다.</p>
  </section>;
}
