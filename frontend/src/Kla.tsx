import {useEffect,useMemo,useRef,useState} from 'react';
import {desktop,errorText} from './desktop';
import {notify} from './ui';
import {openPath} from './OpenPath';
import {goToSettings} from './nav';
import {useKlaState,KlaBackupBar} from './KlaSettings';

/* KLA 자재 찾기 (이슈 #30) — KLA 장비 스캔 결과 폴더
   `{장비 폴더}\{날짜}\{Lot}\{스캔 시각}_{슬롯}\` 에서 Lot 이름 키워드로 자재를 찾는다.
   엔진(param_manager/desktop_kla.py)은 폴더 이름만 보고(파일은 열지 않음) 경로 목록을 돌려준다.
   [폴더 열기] = 등록한 KLA 장비 · 백업 폴더 안의 폴더만(desktop_open).
   장비 폴더 등록 · Defect 이미지 백업본은 설정 › AOI 장비 호기 루트 › KLA 에서 한다(#32, KlaSettings.tsx). */

type Slot={name:string;slot:string;time:string;path:string};
type Hit={machine:string;date:string;lot:string;path:string;slots:Slot[];more:number;backup?:boolean};
type Result={query:string;start:string;end:string;hits:Hit[];truncated:boolean;max_hits:number;machines:string[];dates:number;
  failed:{machine:string;path:string;reason:string;backup?:boolean}[];backup?:boolean;backup_folders?:number};

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
      const r=(await desktop.request('kla_search',{query:query.trim(),machines:picked,start,end},v=>{if(v.message)setProgress(v.message);}).promise).kla as Result;
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

    <div className="form-filter" style={{marginTop:16}}>
      <label className="field" style={{flex:1,minWidth:260}}>Lot 키워드 <span className="hint" style={{margin:0}}>(여러 단어 = 모두 포함 · 대소문자 무시)</span>
        <input value={query} placeholder="예: RINT63  또는  RINT63 6324" maxLength={200} onChange={e=>setQuery(e.target.value)}
          onKeyDown={e=>{if(e.key==='Enter'&&!busy)void search();}}/></label>
      <label className="field" style={{width:150}}>시작 날짜<input type="date" value={start} onChange={e=>setStart(e.target.value)}/></label>
      <label className="field" style={{width:150}}>끝 날짜<input type="date" value={end} onChange={e=>setEnd(e.target.value)}/></label>
      <button className="primary" disabled={busy||!query.trim()||!roots?.length||!picked.length} onClick={()=>void search()}>{busy?'찾는 중…':'찾기'}</button>
    </div>
    {roots&&roots.length>1&&<div className="kla-machines" role="group" aria-label="찾을 장비">
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
          {' · '}{result.backup?`백업 폴더 ${result.backup_folders||0}개 포함`:'원본만(백업본 제외)'}</p>
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
