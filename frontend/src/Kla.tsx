import {useEffect,useMemo,useRef,useState} from 'react';
import {desktop,errorText} from './desktop';
import {notify} from './ui';
import {openPath} from './OpenPath';
import {goToSettings} from './nav';
import {useKlaState,KlaBackupBar,setKlaCache,type KlaCache} from './KlaSettings';

/* KLA 자재 찾기 (이슈 #30) — KLA 장비 스캔 결과 폴더
   `{장비 폴더}\{날짜}\{Lot}\{스캔 시각}_{슬롯}\` 에서 Lot 이름 키워드로 자재를 찾는다.
   엔진(param_manager/desktop_kla.py)은 폴더 이름만 보고(파일은 열지 않음) 경로 목록을 돌려준다.
   [폴더 열기] = 등록한 KLA 장비 · 백업 폴더 안의 폴더만(desktop_open).
   장비 폴더 등록 · Defect 이미지 백업본은 설정 › AOI 장비 호기 루트 › KLA 에서 한다(#32, KlaSettings.tsx).
   KLA 캐시(Para #40, Camtek Batch Report 캐시 #39 와 같은 방식): 개발자 = [🛠 개발자 기능] › [캐시 갱신](장비 폴더 이름만 읽어 로컬 색인)
   · [OneDrive 에 게시](캐시공유/ 에 KLA_캐시_*.zip + KLA캐시정보.json), 사용자 = [OneDrive 에서 불러오기] → 찾을 곳 'KLA 캐시'로 장비 없이 찾기. */

type Slot={name:string;slot:string;time:string;path:string};
type Hit={machine:string;date:string;lot:string;path:string;slots:Slot[];more:number;backup?:boolean};
type Result={query:string;start:string;end:string;hits:Hit[];truncated:boolean;max_hits:number;machines:string[];dates:number;
  failed:{machine:string;path:string;reason:string;backup?:boolean}[];backup?:boolean;backup_folders?:number;source?:'equipment'|'cache';cache_at?:string};
type Source='equipment'|'cache';
type ShareItem={name:string;exported_at:string;updated_at:string;app_version:string;size:number;machines:string[];lots:number;compatible:boolean;present:boolean};
type ShareList={folder:string;exists:boolean;items:ShareItem[]};
type Built=KlaCache&{read_dates:number;reused_dates:number;failed:{machine:string;path:string;reason:string}[];path:string};
type Published={name:string;path:string;folder:string;size:number;machines:string[];lots:number;kept:number};
const mb=(n:number)=>(n/1048576).toFixed(1)+'MB';
const cacheText=(c?:KlaCache)=>!c||!c.lots?'없음':`${c.updated_at||'시각 모름'} 갱신 · 장비 ${c.machines.length}대 · Lot 폴더 ${c.lots.toLocaleString()}개 · ${c.first||'?'} ~ ${c.last||'?'}`;

export function Kla(){
  const [kla,loadError,load]=useKlaState();
  const roots=kla?.roots;
  const [query,setQuery]=useState('');
  const [picked,setPicked]=useState<string[]>([]);
  const [start,setStart]=useState('');
  const [end,setEnd]=useState('');
  const [busy,setBusy]=useState(false);
  const [progress,setProgress]=useState('');
  const [result,setResult]=useState<Result>();
  const [filter,setFilter]=useState('');
  const [open,setOpen]=useState<Record<string,boolean>>({});
  const cache=kla?.cache;
  // [KLA 캐시에서만 찾기](Para #43, Batch Report 찾기 · 취합의 [캐시에서만 찾기]와 같은 모양). 정하지 않았으면 장비 미등록 PC 에서 캐시가 있을 때 켬.
  const [cacheOnly,setCacheOnly]=useState<boolean>();
  const src:Source=(cacheOnly??(!roots?.length&&!!cache?.lots))&&!!cache?.lots?'cache':'equipment';
  const [cachePicked,setCachePicked]=useState<string[]>();
  const [share,setShare]=useState<ShareList>();
  const [sharePick,setSharePick]=useState('');
  const [cacheBusy,setCacheBusy]=useState('');
  const [devTools,setDevTools]=useState(false);
  const [cacheOpen,setCacheOpen]=useState(()=>{try{return localStorage.getItem('para.kla.cacheOpen')==='1';}catch{return false;}});
  useEffect(()=>{try{localStorage.setItem('para.kla.cacheOpen',cacheOpen?'1':'0');}catch{/* 저장 못 해도 동작 */}},[cacheOpen]);
  const [built,setBuilt]=useState<Built>();
  const [published,setPublished]=useState<Published>();
  async function klaCall<T>(method:string,params:Record<string,unknown>,label:string):Promise<T|undefined>{
    setCacheBusy(label);setProgress('');
    try{return (await desktop.request(method,params,v=>{if(v.message)setProgress(v.message);}).promise).kla as T;}
    catch(e){notify(errorText(e),'error');return undefined;}
    finally{setCacheBusy('');setProgress('');}
  }
  async function buildCache(){
    const r=await klaCall<Built>('kla_cache_build',{},'build');
    if(r){setBuilt(r);setKlaCache(r);notify(`KLA 캐시를 갱신했습니다 — 장비 ${r.machines.length}대 · Lot 폴더 ${r.lots}개 (다시 읽은 날짜 ${r.read_dates}개)`,'ok');}
  }
  async function publishCache(){
    const r=await klaCall<Published>('kla_cache_publish',{},'publish');
    if(r){setPublished(r);setShare(undefined);notify(`KLA 캐시를 OneDrive 에 올렸습니다 — 장비 ${r.machines.length}대 · Lot 폴더 ${r.lots}개 · ${mb(r.size)}`,'ok');}
  }
  async function loadShare(){
    const r=await klaCall<ShareList>('kla_cache_share_list',{},'list');
    if(r){setShare(r);const first=r.items.find(i=>i.present&&i.compatible);setSharePick(first?first.name:'');
      if(!r.items.length)notify('OneDrive 에 게시된 KLA 캐시가 아직 없습니다.','info');}
  }
  async function importShare(){
    const r=await klaCall<KlaCache&{source:string}>('kla_cache_share_import',{name:sharePick},'import');
    if(r){setKlaCache(r);setCacheOnly(true);setCachePicked(undefined);notify(`KLA 캐시를 불러왔습니다 — 장비 ${r.machines.length}대 · Lot 폴더 ${r.lots}개. [KLA 캐시에서만 찾기]를 켰습니다.`,'ok');}
  }
  // 설정에서 장비를 더하거나 빼면 찾을 장비 고르기도 따라간다(새 장비는 골라 둔다).
  const known=useRef<string[]|undefined>(undefined);
  useEffect(()=>{
    if(!roots)return;
    const now=roots.map(r=>r.name),before=known.current;
    setPicked(p=>before===undefined?now:[...p.filter(n=>now.includes(n)),...now.filter(n=>!before.includes(n))]);
    known.current=now;
  },[roots]);
  // 찾을 장비 격자: 장비 폴더 = 등록한 장비, KLA 캐시 = 캐시에 든 장비(이 PC 에 등록 안 된 장비도).
  const list=src==='cache'?(cache?.machines||[]):(roots||[]).map(r=>r.name);
  const chosen=src==='cache'?(cachePicked??list).filter(n=>list.includes(n)):picked;
  const setChosen=(next:string[])=>src==='cache'?setCachePicked(next):setPicked(next);
  const folderOf=(name:string)=>roots?.find(r=>r.name===name||name.startsWith(r.name+' › '))?.path||'';
  async function search(){
    if(!query.trim()){notify('Lot 이름(또는 그 일부)을 입력하세요','error');return;}
    setBusy(true);setProgress('찾는 중…');setOpen({});setFilter('');
    try{
      const params:Record<string,unknown>=src==='cache'?{query:query.trim(),machines:chosen,start,end,source:'cache'}:{query:query.trim(),machines:picked,start,end,source:'equipment'};
      const r=(await desktop.request('kla_search',params,v=>{if(v.message)setProgress(v.message);}).promise).kla as Result;
      setResult(r);
      notify(r.hits.length?`Lot 폴더 ${r.hits.length}개를 찾았습니다`:'맞는 Lot 폴더가 없습니다',r.hits.length?'ok':'info');
    }catch(e){notify(errorText(e),'error');}
    finally{setBusy(false);setProgress('');}
  }
  const shown=useMemo(()=>{
    if(!result)return [];
    const words=filter.toLowerCase().split(/\s+/).filter(Boolean);
    return words.length?result.hits.filter(h=>{const t=`${h.machine} ${h.date} ${h.lot} ${h.path}${h.backup?' 백업본':''}`.toLowerCase();return words.every(w=>t.includes(w));}):result.hits;
  },[result,filter]);
  const lots=useMemo(()=>new Set(shown.map(h=>h.lot)).size,[shown]);
  const slotCount=shown.reduce((n,h)=>n+h.slots.length,0);
  async function copy(text:string){try{await navigator.clipboard.writeText(text);notify('경로를 복사했습니다','ok');}catch{notify('복사하지 못했습니다. 경로를 직접 선택해 복사하세요','error');}}

  return <section className="panel kla">
    <div className="section-heading"><div><span className="step">KLA</span><h2>KLA 자재 찾기</h2></div></div>
    <p className="hint kla-intro">Lot 키워드로 KLA 장비의 Lot · 슬롯 폴더 경로를 찾습니다. 폴더 이름만 읽습니다.
      <span className="kla-path">구조 <code>{'{장비}\\{날짜}\\{Lot}\\{스캔 시각}_{슬롯}'}</code></span></p>

    {loadError&&<p className="warn">{loadError} <button className="linklike" onClick={()=>void load()}>다시 시도</button></p>}

    <details className="kla-cache" open={cacheOpen} onToggle={e=>setCacheOpen((e.currentTarget as HTMLDetailsElement).open)}>
      <summary aria-label="KLA 캐시 접기/펼치기"><span className="kc-chev" aria-hidden="true">▸</span><b>KLA 캐시</b>
        <span className="kc-state">{cache?.lots?cacheText(cache):'이 PC 에 없음'}</span>{cacheBusy&&<span className="spinner" aria-hidden="true"/>}</summary>
      <div className="kc-body">
        <div className="kc-actions">
          <button type="button" className="primary" disabled={!!cacheBusy||busy} onClick={()=>void loadShare()}>{cacheBusy==='list'?'목록 읽는 중…':'OneDrive 에서 불러오기'}</button>
          <button type="button" className={devTools?'active':''} aria-expanded={devTools} onClick={()=>setDevTools(o=>!o)} title="KLA 캐시 갱신 · OneDrive 게시(개발자용)">🛠 개발자 기능</button>
        </div>
        {share&&<div className="kc-part" aria-label="OneDrive KLA 캐시 목록">
          <p className="kc-line">공유 폴더 <code>{share.folder}</code>{share.exists?'':' — 아직 없음'}</p>
          {share.items.length>0?<><div className="table-scroll" style={{maxHeight:220}}><table className="t-compact"><thead><tr><th/><th>게시 시각</th><th>캐시 갱신</th><th>장비</th><th>Lot 폴더</th><th>크기</th><th>프로그램</th><th>상태</th></tr></thead>
            <tbody>{share.items.map(i=>{const ok=i.present&&i.compatible;return <tr key={i.name} className={sharePick===i.name?'row-now':''}>
              <td><input type="radio" name="kla-share" aria-label={`${i.exported_at||i.name} KLA 캐시 고르기`} disabled={!ok} checked={sharePick===i.name} onChange={()=>setSharePick(i.name)}/></td>
              <td>{i.exported_at||i.name}</td><td>{i.updated_at||'—'}</td><td title={i.machines.join(', ')}>{i.machines.length}대</td><td>{i.lots.toLocaleString()}개</td><td>{mb(i.size)}</td><td>{i.app_version?`v${i.app_version}`:'—'}</td>
              <td>{!i.compatible?<b className="warn">형식이 다름</b>:i.present?'받을 수 있음':<b className="warn">동기화 대기</b>}</td></tr>;})}</tbody></table></div>
            <div className="kc-actions"><button type="button" className="primary" disabled={!sharePick||!!cacheBusy||busy} onClick={()=>void importShare()}>{cacheBusy==='import'?'받는 중…':'고른 캐시 받아서 불러오기'}</button>
              <button type="button" disabled={!!cacheBusy} onClick={()=>void loadShare()}>목록 새로고침</button>
              <span className="kc-note">크기 · SHA-256 이 맞을 때만 불러옵니다.</span></div></>
            :<p className="kc-line">게시된 KLA 캐시가 없습니다.</p>}</div>}
        {devTools&&<div className="kc-part" aria-label="KLA 캐시 갱신 · OneDrive 게시">
          <div className="kc-actions"><button type="button" disabled={!!cacheBusy||busy||!roots?.length} onClick={()=>void buildCache()}>{cacheBusy==='build'?'갱신 중…':'캐시 갱신 (장비 폴더 이름 읽기)'}</button>
            <button type="button" className="primary" disabled={!!cacheBusy||busy||!cache?.lots} onClick={()=>void publishCache()}>{cacheBusy==='publish'?'올리는 중…':'OneDrive 에 게시'}</button>
            {published&&<button type="button" onClick={()=>void openPath(published.path,true)}>폴더 열기</button>}</div>
          <ul className="kc-list">
            <li>갱신: 폴더 이름만 읽음 · 최근 3일과 바뀐 날짜만 다시 읽음</li>
            <li>게시: <code>캐시공유\KLA_캐시_날짜.zip</code> · 최근 3개 보관</li>
          </ul>
          {built&&<p className="kc-line" role="status">갱신함: 장비 {built.machines.length}대 · Lot 폴더 {built.lots}개 · 다시 읽은 날짜 {built.read_dates}개 · 그대로 쓴 날짜 {built.reused_dates}개
            {built.failed.map(f=><span key={f.machine+f.path} className="warn"> · {f.machine} 읽지 못함({f.reason}) — 예전 캐시 유지</span>)}</p>}
          {published&&<p className="kc-line" role="status">게시함: <code>{published.path}</code> · {mb(published.size)}</p>}</div>}
        {cacheBusy&&progress&&<p className="kc-line"><span className="spinner" aria-hidden="true"/> {progress}</p>}
      </div>
    </details>

    <div className="bv kla-find">
      <div className="mhead"><span className="lbl">{src==='cache'?'KLA 캐시 장비':'장비 범위'}</span><span className="count">선택 {chosen.length} / {list.length}</span><span className="grow"/>
        <label className="tgl2"><input type="checkbox" aria-label="찾기 모든 장비" disabled={!list.length} checked={!!list.length&&chosen.length===list.length}
          onChange={e=>setChosen(e.target.checked?list:[])}/> 모든 장비</label>
        <button type="button" className="gear" onClick={()=>goToSettings({sub:'kla'})}>⚙ 설정 › AOI 장비 호기 루트 › KLA</button></div>
      {list.length?<div className="mgrid compact" role="group" aria-label="찾을 장비">{list.map(n=>{const on=chosen.includes(n),folder=folderOf(n);
        return <label key={n} className={'mbox'+(on?' on':'')} data-tip={folder?n+'\n'+folder:n}><input type="checkbox" checked={on} aria-label={n+' 찾기'}
          onChange={e=>setChosen(e.target.checked?[...chosen,n]:chosen.filter(x=>x!==n))}/><span className="mn">{n}</span><span className="ms">{folder||'KLA 캐시'}</span></label>;})}</div>
        :roots===undefined?(loadError?null:<p className="hint">불러오는 중…</p>)
        :<p className="warn">{src==='cache'?'KLA 캐시에 장비가 없습니다.':'⚠ 등록된 KLA 장비 폴더가 없습니다 — 설정에서 등록하거나, 아래 [KLA 캐시]에서 OneDrive 캐시를 불러오세요.'}</p>}
      <div className="scope-row"><label className="field" style={{flex:1,minWidth:320}}>Lot 키워드<input value={query} maxLength={200} placeholder="예: RINT63 6324 — 여러 단어는 모두 포함"
          onChange={e=>setQuery(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!busy)void search();}}/></label>
        <div className="dates"><label className="field" title="비우면 처음부터">시작일<input type="date" aria-label="KLA 찾기 시작일" value={start} onChange={e=>setStart(e.target.value)}/></label>
          <label className="field" title="비우면 끝까지">종료일<input type="date" aria-label="KLA 찾기 종료일" value={end} onChange={e=>setEnd(e.target.value)}/></label></div>
        <label className="tgl2" title={cache?.lots?`로컬 KLA 캐시(${cache.updated_at||'시각 모름'} 갱신)에서만 찾습니다(장비에 접속하지 않음)`:'이 PC 에 KLA 캐시가 없습니다 — 아래 [KLA 캐시]에서 불러오세요'}>
          <input type="checkbox" aria-label="KLA 캐시에서만 찾기" disabled={!cache?.lots} checked={src==='cache'} onChange={e=>setCacheOnly(e.target.checked)}/> KLA 캐시에서만 찾기</label>
        <div className="go"><button className="primary" disabled={busy||!!cacheBusy||!query.trim()||!chosen.length} onClick={()=>void search()}>{busy?'찾는 중…':'검색 →'}</button></div></div>
      <p className="hint">{src==='cache'?`KLA 캐시(${cache?.updated_at||'시각 모름'} 기준)에서만 찾습니다 — 장비에 접속하지 않습니다.`:'장비 폴더 이름만 읽습니다(파일은 열지 않음).'} 기간을 비우면 모든 날짜를 찾습니다.</p>
      {src==='equipment'&&<KlaBackupBar disabled={busy}/>}
    </div>
    {busy&&<p className="kc-note"><span className="spinner" aria-hidden="true"/> {progress}</p>}

    {result&&<div className="kla-result">
      <div className="kla-sum">
        <p className="kla-sumtext"><b>'{result.query}'</b> · Lot 폴더 {result.hits.length}개(Lot {new Set(result.hits.map(h=>h.lot)).size}개) · 장비 {result.machines.length}대
          {result.start||result.end?` · ${result.start||'처음'} ~ ${result.end||'끝'}`:''}
          {' · '}{result.source==='cache'?<b>KLA 캐시에서 찾음 ({result.cache_at||'시각 모름'} 기준)</b>:result.backup?`백업 폴더 ${result.backup_folders||0}개 포함`:'원본만'}</p>
        {result.hits.length>0&&<label className="field kla-filter">결과 안에서 거르기<input value={filter} placeholder="장비 · 날짜 · Lot · 백업본" onChange={e=>setFilter(e.target.value)}/></label>}
      </div>
      {result.truncated&&<p className="warn">결과가 많아 앞의 {result.max_hits}개만 보여 줍니다. 키워드를 더 길게 하거나 기간을 좁혀 다시 찾으세요.</p>}
      {result.failed.map(f=><p key={f.machine+f.path} className="warn">{f.machine}{f.backup?' 백업 폴더':''}: 폴더를 읽지 못했습니다({f.reason}) — <code>{f.path}</code> 연결을 확인하세요.</p>)}
      {shown.length>0?<>
        <p className="kc-note">보이는 Lot 폴더 {shown.length}개 · Lot {lots}개 · 슬롯 {slotCount}개 · 행을 누르면 슬롯이 펼쳐집니다.</p>
        <div className="table-scroll"><table className="kla-table"><thead><tr><th>장비</th><th>날짜</th><th>Lot</th><th>슬롯</th><th>경로</th><th/></tr></thead><tbody>
          {shown.map(h=>{const key=h.path;const isOpen=!!open[key];return [
            <tr key={key} className="kla-row" onClick={()=>setOpen(o=>({...o,[key]:!o[key]}))}>
              <td>{h.machine}</td><td>{h.date}</td><td><b>{h.lot}</b>{h.backup&&<span className="sbk-kind bk" title="Defect 이미지 백업 폴더에서 찾음">백업본</span>}</td>
              <td>{h.slots.length?`${isOpen?'▾':'▸'} ${h.slots.map(s=>s.slot||'?').join(', ')}${h.more?` 외 ${h.more}`:''}`:'—'}</td>
              <td><code>{h.path}</code></td>
              <td className="kla-acts" onClick={e=>e.stopPropagation()}>
                <button onClick={()=>void openPath(h.path)}>폴더 열기</button><button onClick={()=>void copy(h.path)}>경로 복사</button></td></tr>,
            ...(isOpen?h.slots.map(s=><tr key={s.path} className="kla-slot">
              <td/><td>{s.time||''}</td><td>슬롯 {s.slot||'?'}</td><td>{s.name}</td><td><code>{s.path}</code></td>
              <td className="kla-acts"><button onClick={()=>void openPath(s.path)}>폴더 열기</button><button onClick={()=>void copy(s.path)}>경로 복사</button></td></tr>):[])];})}
        </tbody></table></div></>
        :<div className="empty-state"><h3>{result.hits.length?'거르기에 맞는 결과가 없습니다':'맞는 Lot 폴더가 없습니다'}</h3>
          <p>{result.hits.length?'결과 안에서 거르기 칸을 비워 보세요.':'키워드 철자 · 기간 · 등록한 장비 폴더(설정)를 확인하세요.'}</p></div>}
    </div>}
  </section>;
}
