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
const cacheText=(c?:KlaCache)=>!c||!c.lots?'없음':`${c.updated_at||'시각 모름'} · 장비 ${c.machines.length}대 · Lot 폴더 ${c.lots.toLocaleString()}개 · 날짜 ${c.first||'?'} ~ ${c.last||'?'}`;

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
  const [source,setSource]=useState<Source>();
  const src:Source=source??((!roots?.length&&cache?.lots)?'cache':'equipment');
  const [share,setShare]=useState<ShareList>();
  const [sharePick,setSharePick]=useState('');
  const [cacheBusy,setCacheBusy]=useState('');
  const [devTools,setDevTools]=useState(false);
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
    if(r){setKlaCache(r);setSource('cache');notify(`KLA 캐시를 불러왔습니다 — 장비 ${r.machines.length}대 · Lot 폴더 ${r.lots}개. 찾을 곳이 'KLA 캐시'로 바뀌었습니다.`,'ok');}
  }
  // 설정에서 장비를 더하거나 빼면 찾을 장비 고르기도 따라간다(새 장비는 골라 둔다).
  const known=useRef<string[]|undefined>(undefined);
  useEffect(()=>{
    if(!roots)return;
    const now=roots.map(r=>r.name),before=known.current;
    setPicked(p=>before===undefined?now:[...p.filter(n=>now.includes(n)),...now.filter(n=>!before.includes(n))]);
    known.current=now;
  },[roots]);
  async function search(){
    if(!query.trim()){notify('Lot 이름(또는 그 일부)을 입력하세요','error');return;}
    setBusy(true);setProgress('찾는 중…');setOpen({});setFilter('');
    try{
      const params:Record<string,unknown>=src==='cache'?{query:query.trim(),start,end,source:'cache'}:{query:query.trim(),machines:picked,start,end,source:'equipment'};
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
    <p className="hint">KLA 장비는 스캔 결과를 <code>{'{장비 폴더}\\{날짜}\\{Lot}\\{스캔 시각}_{슬롯}'}</code> 로 저장합니다
      (예 <code>J:\2.K2\2025-05-21\RINT63@6324\2025-05-21-09-08_16</code> = 장비 2.K2 · Lot RINT63@6324 · 슬롯 16).
      Lot 이름 키워드를 넣으면 <b>폴더 이름만</b> 빠르게 훑어 해당 경로를 알려 줍니다. 파일은 열지 않고, 장비 폴더는 읽기만 합니다.</p>

    <div className="kla-roots-line">
      <span><b>KLA 장비 폴더</b> · {roots===undefined?(loadError?'':'불러오는 중…'):roots.length?`${roots.length}개 · ${roots.map(r=>r.name).join(', ')}`:<b className="warn">⚠ 등록된 폴더 없음 — 설정에서 먼저 등록하세요</b>}</span>
      <button onClick={()=>goToSettings({sub:'kla'})}>⚙ 설정 › AOI 장비 호기 루트 › KLA</button>
    </div>
    {loadError&&<p className="warn">{loadError} <button className="linklike" onClick={()=>void load()}>다시 시도</button></p>}
    <KlaBackupBar note="장비 폴더 · 백업 폴더 등록은 설정 › AOI 장비 호기 루트 › KLA 에서 합니다." disabled={busy}/>

    <div className="cache-drop kla-cache" aria-label="KLA 캐시">
      <div className="cache-drop-head"><span className="cache-drop-ic" aria-hidden="true">⇩</span>
        <div className="grow"><b>KLA 캐시</b><small>장비에 연결하지 않아도 찾을 수 있게, 개발자가 OneDrive 에 올린 KLA 폴더 이름 캐시(날짜 · Lot · 슬롯)를 이 PC 로 불러옵니다.
          이 PC 캐시: <b>{cacheText(cache)}</b></small></div>
        <button type="button" className="primary" disabled={!!cacheBusy||busy} onClick={()=>void loadShare()}>{cacheBusy==='list'?'목록 읽는 중…':'OneDrive 에서 불러오기'}</button>
        <button type="button" className={devTools?'active':''} aria-expanded={devTools} onClick={()=>setDevTools(o=>!o)} title="KLA 캐시 갱신 · OneDrive 게시(개발자용)">🛠 개발자 기능</button></div>
      {share&&<div className="cache-share" aria-label="OneDrive KLA 캐시 목록">
        <p className="hint">OneDrive 캐시 공유 폴더: <code>{share.folder}</code>{share.exists?'':' (아직 없음 — 개발자가 처음 게시하면 생깁니다)'}</p>
        {share.items.length>0?<><div className="table-scroll" style={{maxHeight:220}}><table className="t-compact"><thead><tr><th/><th>게시 시각</th><th>캐시 갱신</th><th>장비</th><th>Lot 폴더</th><th>크기</th><th>프로그램</th><th>상태</th></tr></thead>
          <tbody>{share.items.map(i=>{const ok=i.present&&i.compatible;return <tr key={i.name} className={sharePick===i.name?'row-now':''}>
            <td><input type="radio" name="kla-share" aria-label={`${i.exported_at||i.name} KLA 캐시 고르기`} disabled={!ok} checked={sharePick===i.name} onChange={()=>setSharePick(i.name)}/></td>
            <td>{i.exported_at||i.name}</td><td>{i.updated_at||'—'}</td><td title={i.machines.join(', ')}>{i.machines.length}대</td><td>{i.lots.toLocaleString()}개</td><td>{mb(i.size)}</td><td>{i.app_version?`v${i.app_version}`:'—'}</td>
            <td>{!i.compatible?<b className="warn">형식이 다름</b>:i.present?'받을 수 있음':<b className="warn">동기화 대기</b>}</td></tr>;})}</tbody></table></div>
          <div className="toolbar"><button type="button" className="primary" disabled={!sharePick||!!cacheBusy||busy} onClick={()=>void importShare()}>{cacheBusy==='import'?'받는 중…':'고른 캐시 받아서 불러오기'}</button>
            <button type="button" disabled={!!cacheBusy} onClick={()=>void loadShare()}>목록 새로고침</button></div>
          <p className="hint">고른 zip 을 이 PC 로컬 임시 폴더로 복사하고, 게시할 때 적어 둔 크기 · SHA-256 이 같을 때만 불러옵니다(OneDrive 동기화가 덜 된 파일은 거부). OneDrive 에는 아무것도 쓰지 않습니다.</p></>
          :<p className="table-empty">게시된 KLA 캐시가 없습니다.</p>}</div>}
      {devTools&&<div className="cache-export" aria-label="KLA 캐시 갱신 · OneDrive 게시">
        <div className="toolbar"><button type="button" disabled={!!cacheBusy||busy||!roots?.length} onClick={()=>void buildCache()}>{cacheBusy==='build'?'갱신 중…':'캐시 갱신 (장비 폴더 이름 읽기)'}</button>
          <button type="button" className="primary" disabled={!!cacheBusy||busy||!cache?.lots} onClick={()=>void publishCache()}>{cacheBusy==='publish'?'올리는 중…':'OneDrive 에 게시'}</button>
          {published&&<button type="button" onClick={()=>void openPath(published.path,true)}>폴더 열기</button>}</div>
        <p className="hint">[캐시 갱신]은 등록한 KLA 장비 폴더(백업본 포함 설정을 따름)의 날짜 · Lot · 슬롯 폴더 <b>이름만</b> 읽어 이 PC 로컬 캐시에 모읍니다(파일은 열지 않음).
          두 번째부터는 최근 3일 날짜와 바뀐 날짜 폴더만 다시 읽습니다. [OneDrive 에 게시]는 캐시를 <code>KLA_캐시_YYYYMMDD_HHMMSS.zip</code> 하나로 만들어 저장 폴더 옆 <code>캐시공유</code>에 올립니다
          (Camtek Batch Report 캐시 <code>BatchReport_캐시_*.zip</code> 과 같은 폴더 · 다른 이름, 목록 파일도 <code>KLA캐시정보.json</code> 으로 따로 · 최근 3개만 보관).</p>
        {built&&<p className="hint" role="status">갱신함: 장비 {built.machines.length}대 · Lot 폴더 {built.lots}개 · 다시 읽은 날짜 {built.read_dates}개 · 그대로 쓴 날짜 {built.reused_dates}개
          {built.failed.map(f=><span key={f.machine+f.path} className="warn"> · {f.machine} 읽지 못함({f.reason}) — 예전 캐시 유지</span>)}</p>}
        {published&&<p className="hint" role="status">게시함: <code>{published.path}</code> — 장비 {published.machines.length}대 · Lot 폴더 {published.lots}개 · {mb(published.size)} (보관 {published.kept}개)</p>}</div>}
      {cacheBusy&&progress&&<p className="hint"><span className="spinner" aria-hidden="true"/> {progress}</p>}
    </div>

    <div className="kla-source" role="radiogroup" aria-label="찾을 곳">
      <span className="hint" style={{margin:0}}>찾을 곳</span>
      <label className="field checkbox"><input type="radio" name="kla-src" checked={src==='equipment'} onChange={()=>setSource('equipment')}/>장비 폴더 (지금 연결된 장비)</label>
      <label className="field checkbox"><input type="radio" name="kla-src" checked={src==='cache'} disabled={!cache?.lots} onChange={()=>setSource('cache')}/>KLA 캐시 ({cache?.lots?cache.updated_at||'시각 모름':'없음'})</label>
    </div>

    <div className="form-filter" style={{marginTop:16}}>
      <label className="field" style={{flex:1,minWidth:260}}>Lot 키워드 <span className="hint" style={{margin:0}}>(여러 단어 = 모두 포함 · 대소문자 무시)</span>
        <input value={query} placeholder="예: RINT63  또는  RINT63 6324" maxLength={200} onChange={e=>setQuery(e.target.value)}
          onKeyDown={e=>{if(e.key==='Enter'&&!busy)void search();}}/></label>
      <label className="field" style={{width:150}}>시작 날짜<input type="date" value={start} onChange={e=>setStart(e.target.value)}/></label>
      <label className="field" style={{width:150}}>끝 날짜<input type="date" value={end} onChange={e=>setEnd(e.target.value)}/></label>
      <button className="primary" disabled={busy||!!cacheBusy||!query.trim()||(src==='cache'?!cache?.lots:(!roots?.length||!picked.length))} onClick={()=>void search()}>{busy?'찾는 중…':src==='cache'?'캐시에서 찾기':'찾기'}</button>
    </div>
    {src==='equipment'&&roots&&roots.length>1&&<div className="kla-machines" role="group" aria-label="찾을 장비">
      <span className="hint" style={{margin:0}}>찾을 장비</span>
      {roots.map(r=><label key={r.name} className="field checkbox"><input type="checkbox" checked={picked.includes(r.name)}
        onChange={e=>setPicked(p=>e.target.checked?[...p,r.name]:p.filter(n=>n!==r.name))}/>{r.name}</label>)}
      <button className="linklike" onClick={()=>setPicked(roots.map(r=>r.name))}>모두</button>
      <button className="linklike" onClick={()=>setPicked([])}>해제</button>
    </div>}
    <p className="hint">기간을 비우면 모든 날짜를 봅니다. 날짜가 많으면 기간을 좁힐수록 빨라집니다.</p>
    {busy&&<p className="hint"><span className="spinner" aria-hidden="true"/> {progress}</p>}

    {result&&<div className="kla-result">
      <div className="form-filter" style={{alignItems:'end'}}>
        <p className="hint" style={{flex:1,margin:0}}><b>'{result.query}'</b> — Lot 폴더 {result.hits.length}개(Lot {new Set(result.hits.map(h=>h.lot)).size}개) ·
          장비 {result.machines.length}대 · 날짜 폴더 {result.dates}개 확인{result.start||result.end?` · 기간 ${result.start||'처음'} ~ ${result.end||'끝'}`:''}
          {' · '}{result.source==='cache'?<b>KLA 캐시에서 찾음(캐시 갱신 {result.cache_at||'시각 모름'} — 그 뒤 스캔한 자재는 없을 수 있음)</b>:result.backup?`백업 폴더 ${result.backup_folders||0}개 포함`:'원본만(백업본 제외)'}</p>
        {result.hits.length>0&&<label className="field" style={{width:260}}>결과 안에서 거르기<input value={filter} placeholder="장비 · 날짜 · Lot · 백업본" onChange={e=>setFilter(e.target.value)}/></label>}
      </div>
      {result.truncated&&<p className="warn">결과가 많아 앞의 {result.max_hits}개만 보여 줍니다. 키워드를 더 길게 하거나 기간을 좁혀 다시 찾으세요.</p>}
      {result.failed.map(f=><p key={f.machine+f.path} className="warn">{f.machine}{f.backup?' 백업 폴더':''}: 폴더를 읽지 못했습니다({f.reason}) — <code>{f.path}</code> 연결을 확인하세요.</p>)}
      {shown.length>0?<>
        <p className="hint" style={{marginTop:6}}>보이는 Lot 폴더 {shown.length}개 · Lot {lots}개 · 슬롯 폴더 {slotCount}개. 행을 누르면 슬롯 폴더가 펼쳐집니다.</p>
        <div className="table-scroll"><table className="kla-table"><thead><tr><th>장비</th><th>날짜</th><th>Lot</th><th>슬롯</th><th>경로</th><th/></tr></thead><tbody>
          {shown.map(h=>{const key=h.path;const isOpen=!!open[key];return [
            <tr key={key} className="kla-row" onClick={()=>setOpen(o=>({...o,[key]:!o[key]}))}>
              <td>{h.machine}</td><td>{h.date}</td><td><b>{h.lot}</b>{h.backup&&<span className="sbk-kind bk" title="Defect 이미지 백업 폴더에서 찾음">백업본</span>}</td>
              <td>{h.slots.length?`${isOpen?'▾':'▸'} ${h.slots.map(s=>s.slot||'?').join(', ')}${h.more?` 외 ${h.more}`:''}`:'—'}</td>
              <td><code>{h.path}</code></td>
              <td style={{whiteSpace:'nowrap'}} onClick={e=>e.stopPropagation()}>
                <button onClick={()=>void openPath(h.path)}>폴더 열기</button>{' '}
                <button className="linklike" onClick={()=>void copy(h.path)}>경로 복사</button></td></tr>,
            ...(isOpen?h.slots.map(s=><tr key={s.path} className="kla-slot">
              <td/><td>{s.time||''}</td><td>슬롯 {s.slot||'?'}</td><td>{s.name}</td><td><code>{s.path}</code></td>
              <td style={{whiteSpace:'nowrap'}}><button onClick={()=>void openPath(s.path)}>폴더 열기</button>{' '}
                <button className="linklike" onClick={()=>void copy(s.path)}>경로 복사</button></td></tr>):[])];})}
        </tbody></table></div></>
        :<div className="empty-state"><h3>{result.hits.length?'거르기에 맞는 결과가 없습니다':'맞는 Lot 폴더가 없습니다'}</h3>
          <p>{result.hits.length?'결과 안에서 거르기 칸을 비워 보세요.':'키워드 철자 · 기간 · 등록한 장비 폴더(설정)를 확인하세요.'}</p></div>}
    </div>}
  </section>;
}
