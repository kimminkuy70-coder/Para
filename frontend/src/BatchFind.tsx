import {Fragment,useEffect,useRef,useState} from 'react';
import {Stepper,notify} from './ui';
import {StPill} from './BatchLot';
import {OpenPath,openPath} from './OpenPath';
import {ScanBackupBar} from './ScanBackup';
import {grpLabel,num,isRealId,type View,type AggGroup} from './batchData';

/* Batch Report 찾기 · 취합 — ① 파일 이름으로 찾기(로컬 조사 캐시 먼저 → 장비 Reports 폴더 이름, 원문은 안 엶)
   ② 찾은 파일 고르기 ③ 고른 것 + 같은 호기 앞뒤 24시간만 읽어 Lot · 공정 단계별로 고르기(Scanresult 경로 · 원문)
   ④ 취합(같은 wafer 여러 장이면 최신 스캔 자동 = 가장 나중 Pass, 개발자 기능이면 Pass 2번 이상을 직접 고름). (이슈 #19) */
const small={minHeight:28,padding:'3px 10px',fontSize:12} as const;
export type FindCond={machines:string[];query:string;start:string;end:string;cacheOnly?:boolean};
export type FindHit={i:number;m:string;f:string;t:string;c:boolean};
export type FindList={stage:'cache'|'equipment';query:string;start:string;end:string;hits:FindHit[];total:number;cached:number;listed:number;offline:string[];neighbor_h:number};
const LIST_MAX=1000;
type Props={machines:{id:string;folder:string}[];view?:View;busy:boolean;dev:boolean;progress:string;
  cond:FindCond;setCond:(c:FindCond)=>void;onFind:()=>void;aggregate:(reports:number[])=>Promise<AggGroup[]|undefined>;
  exportAgg:(reports:number[],choices:Record<string,number>,stamp:string)=>Promise<string|undefined>;
  openLot:(li:number)=>void;showRaw:(g:number)=>void;openFile:(g:number)=>void;onCrit:()=>void;goSettings:()=>void;step:number;setStep:(n:number)=>void;
  list?:FindList;checking:boolean;onLoad:(hits:number[])=>void};
type Stamp={manual:number;saved:number;at:string};
const recIdx=(c:{ok:boolean}[])=>{for(let j=c.length-1;j>=0;j--)if(c[j].ok)return j;return c.length-1;};

export function FindTab(p:Props){
  const {view:v,cond}=p;
  const [sel,setSel]=useState<Record<number,1>>({});
  const [groups,setGroups]=useState<AggGroup[]>([]),[choice,setChoice]=useState<Record<string,number>>({});
  const [stamp,setStamp]=useState<Stamp>(),[note,setNote]=useState(''),[xlsx,setXlsx]=useState('');
  const [must,setMust]=useState<[number,string][]>([]),[auto,setAuto]=useState<[number,string][]>([]);
  const dupRef=useRef<HTMLDialogElement>(null);
  const [pick,setPick]=useState<Record<string,1>>({});
  const L=p.list,hk=(h:FindHit)=>h.m+'\t'+h.f,shown=L?L.hits.slice(0,LIST_MAX):[];
  const listKey=L?[L.query,L.start,L.end].join('\n'):'';
  useEffect(()=>{setPick({});},[listKey]);   // 새 검색이면 고른 것 비움(장비 단계가 목록을 늘릴 때는 유지)
  const picked=L?L.hits.filter(h=>pick[hk(h)]).map(h=>h.i):[];
  useEffect(()=>{setSel({});},[v]);
  useEffect(()=>{if(must.length)dupRef.current?.showModal();},[must]);
  const hits=new Set(v?.hits||[]);
  const order:string[]=[];const members:Record<string,number[]>={};
  (v?.hits||[]).forEach(g=>{const r=v!.R[g],k=r.lot==null?'x'+g:r.lot+'|'+r.b;if(!members[k]){order.push(k);members[k]=r.lot==null?[g]:v!.lots[r.lot].bunches[r.b!].att;}});
  const nSel=Object.keys(sel).length;
  const selGroups=new Set(Object.keys(sel).map(Number).filter(g=>v!.R[g].lot!=null).map(g=>v!.R[g].lot+'|'+v!.R[g].b)).size;
  async function start(){
    const reports=Object.keys(sel).map(Number);
    const gs=await p.aggregate(reports);if(!gs)return;
    const ch:Record<string,number>={},dups:[number,string][]=[];
    gs.forEach((g,gi)=>g.keys.forEach(k=>{ch[gi+'|'+k]=g.w[k].rec;if(g.w[k].cells.length>1)dups.push([gi,k]);}));
    const many=dups.filter(([gi,k])=>gs[gi].w[k].cells.filter(c=>c.ok).length>1);
    const saved=gs.reduce((a,g)=>a+g.keys.filter(k=>g.w[k].saved).length,0);
    setGroups(gs);setChoice(ch);setXlsx('');
    setNote(dups.length?`같은 wafer가 고른 Batch Report 2장 이상에 있는 ${dups.length}장은 최신 스캔으로 자동 취합했습니다(Pass가 있으면 가장 나중 Pass, 없으면 가장 나중 스캔). 그중 Pass 2번 이상 ${many.length}장.`+(p.dev?'':' 직접 고르기는 개발자 기능입니다.'):'');
    setStamp({manual:0,saved,at:new Date().toTimeString().slice(0,5)});
    if(many.length&&p.dev){setAuto(dups.filter(d=>!many.includes(d)));setMust(many);}
    else p.setStep(3);
  }
  function confirmDup(){dupRef.current?.close();let manual=0;groups.forEach((g,gi)=>g.keys.forEach(k=>{if(g.w[k].cells.length>1&&choice[gi+'|'+k]!==g.w[k].rec)manual++;}));
    setStamp(s=>s&&{...s,manual});setMust([]);p.setStep(3);}
  const stampText=stamp?`최신 스캔 자동(Pass가 있으면 가장 나중 Pass)${stamp.saved?` + 저장된 사람 선택 ${stamp.saved}건`:''}${stamp.manual?` + 개발자 직접 선택 ${stamp.manual}건`:''}`:'';
  const block=([gi,k]:[number,string])=>{const g=groups[gi],c=g.w[k].cells,rec=g.w[k].rec;
    return <div key={gi+'|'+k} className="dupwafer"><div className="w">Lot {v!.lots[g.li].label} · {grpLabel(v!.lots[g.li].bunches[g.bi])} · 슬롯 {k.replace(/^S0?/,'')} · {(c.find(x=>isRealId(x.id))||c[0]).id}</div>
      {c.map((x,j)=><label key={j}><input type="radio" name={`d${gi}_${k}`} checked={choice[gi+'|'+k]===j} onChange={()=>setChoice(o=>({...o,[gi+'|'+k]:j}))}/>
        <span>{v!.R[x.g].s}{j===rec&&<span className="rectag">추천</span>}</span><span className={x.ok?'v1':'v4'}>{x.status}</span><span>Scanned {num(x.sc)} · Bad {num(x.bad)}</span></label>)}</div>;};
  const scanKey=(g:number)=>{const r=v!.R[g];return [r.m,r.job,r.setup,r.sm].join('|');};
  return <section className="panel" aria-label="Batch Report 찾기 · 취합">
    <div className="section-heading"><div><span className="step">찾기 · 취합</span><h2>Batch Report 찾기 · Lot 취합</h2></div>{v?.find&&<span className="count">찾은 Batch Report {v.find.total}개</span>}</div>
    <Stepper labels={['검색','찾은 파일 고르기','Lot · Batch Report 고르기','취합 결과']} current={p.step} onJump={p.setStep}/>
    {p.step===0&&<>
      <div className="mhead"><span className="lbl">호기 범위</span><span className="count">선택 {cond.machines.length} / {p.machines.length}</span><span className="grow"/>
        <label className="tgl2"><input type="checkbox" aria-label="찾기 모든 호기" checked={!!p.machines.length&&cond.machines.length===p.machines.length}
          onChange={e=>p.setCond({...cond,machines:e.target.checked?p.machines.map(m=>m.id):[]})}/> 모든 호기</label>
        <button type="button" className="gear" onClick={p.goSettings}>⚙ AOI 장비 호기 루트 설정</button></div>
      <div className="mgrid compact" role="group" aria-label="찾을 호기">{p.machines.map(m=>{const on=cond.machines.includes(m.id);
        return <label key={m.id} className={'mbox'+(on?' on':'')} data-tip={m.id+'\n'+m.folder}><input type="checkbox" checked={on} aria-label={m.id+' 찾기'}
          onChange={e=>p.setCond({...cond,machines:e.target.checked?[...cond.machines,m.id]:cond.machines.filter(x=>x!==m.id)})}/><span className="mn">{m.id}</span><span className="ms">{m.folder}</span></label>;})}</div>
      <div className="scope-row"><label className="field" style={{flex:1,minWidth:360}}>Batch Report 키워드<input value={cond.query} maxLength={256} placeholder="예: BAW · NSW WBG · 0856268PD — 여러 단어는 모두 포함"
          onChange={e=>p.setCond({...cond,query:e.target.value})} onKeyDown={e=>{if(e.key==='Enter'&&!p.busy)p.onFind();}}/></label>
        <div className="dates"><label className="field">시작일<input type="date" aria-label="찾기 시작일" value={cond.start} onChange={e=>p.setCond({...cond,start:e.target.value})}/></label>
          <label className="field">종료일<input type="date" aria-label="찾기 종료일" value={cond.end} onChange={e=>p.setCond({...cond,end:e.target.value})}/></label></div>
        <label className="tgl2" title="[조사 시작]으로 이미 읽어 둔 로컬 캐시에서만 찾습니다(장비에 접속하지 않음)"><input type="checkbox" aria-label="캐시에서만 찾기" checked={!!cond.cacheOnly}
          onChange={e=>p.setCond({...cond,cacheOnly:e.target.checked})}/> 캐시에서만 찾기</label>
        <div className="go"><button className="primary" disabled={p.busy||!cond.query.trim()||!cond.machines.length} onClick={p.onFind}>{p.busy?'찾는 중…':'검색 →'}</button>
          <button type="button" className="help-btn lg" aria-label="Lot 판정 기준" title="어떤 기준으로 Lot을 묶는지 보기" onClick={p.onCrit}>?</button></div></div>
      <ScanBackupBar note="찾은 Lot 의 Scanresult 경로를 보여 줄 때 적용됩니다." disabled={p.busy}/>
      {p.busy&&<p className="scope-status" role="status">{p.progress||'Reports 폴더를 확인하는 중…'}</p>}
      <details className="logic"><summary>로직 · 검색</summary><ol>
        <li><b>파일 이름만</b> 봅니다(원본을 열지 않음). 키워드는 대소문자 무시, 여러 단어는 모두 포함, 기간은 파일 이름 안 날짜.</li>
        <li>먼저 <b>[조사 시작]으로 이미 읽어 둔 로컬 캐시</b>에서 찾아 바로 보여 주고(장비 접속 없음), 이어서 고른 호기 Reports 폴더 이름 목록에서 캐시에 없는 새 Batch Report를 더합니다. [캐시에서만 찾기]를 켜면 장비에 접속하지 않습니다.</li>
        <li>찾은 목록에서 고른 것만 읽습니다. 고른 Batch Report와, 같은 호기에서 그 <b>앞뒤 24시간</b> 안에 스캔한 Batch Report를 함께 읽어(캐시에 있으면 장비 접속 없음) <b>Lot · 공정 단계</b>로 모읍니다. 같은 Lot을 이어서 스캔했는데 키워드에 안 걸린 Batch Report(S/M 꼬리가 다른 것 등)도 회색으로 함께 보여 놓칠 일이 없게 합니다.</li>
        <li>호기 사이에는 2초 간격으로 순서대로 읽습니다(장비 접속 매너).</li></ol></details></>}
    {p.step===1&&<>
      {!L?<div className="empty-state"><h3>먼저 검색하세요.</h3></div>:<>
      <div className="mhead"><span className="lbl">찾은 Batch Report</span><span className="count">{L.total}개 · 캐시 {L.cached} · 장비 새 {L.total-L.cached}</span><span className="grow"/>
        <button type="button" style={small} disabled={!shown.length} onClick={()=>setPick(Object.fromEntries(shown.map(h=>[hk(h),1])))}>모두 고르기</button>
        <button type="button" style={small} disabled={!picked.length} onClick={()=>setPick({})}>모두 해제</button></div>
      {p.checking?<p className="scope-status" role="status">{p.progress||'장비 Reports 폴더에서 캐시에 없는 새 Batch Report를 확인하는 중…'} (캐시 결과는 아래에 먼저 보입니다)</p>
        :L.stage==='cache'?<p className="hint">로컬 조사 캐시에서만 찾았습니다(장비 접속 없음). 캐시 이후 Batch Report까지 찾으려면 [캐시에서만 찾기]를 끄고 다시 검색하세요.</p>
        :<p className="hint">캐시 + 장비 Reports 폴더 이름에서 찾았습니다{L.offline.length?` — 연결 안 된 호기(캐시만): ${L.offline.join(', ')}`:''}. 원문은 아직 열지 않았습니다.</p>}
      {L.total>LIST_MAX&&<p className="hint">앞(최근) {LIST_MAX}개만 보입니다. 키워드 · 기간을 좁히세요.</p>}
      {!L.total?<div className="empty-state"><h3>찾은 Batch Report가 없습니다.</h3><p>키워드 · 기간 · 호기 범위를 바꿔 보세요.</p></div>
        :<div className="table-scroll" style={{maxHeight:'52vh'}}><table className="t-compact" aria-label="찾은 Batch Report 목록"><thead><tr><th/><th>스캔 시각(파일 이름)</th><th>호기</th><th>파일 이름</th><th>어디서</th></tr></thead>
          <tbody>{shown.map(h=><tr key={hk(h)}><td><input type="checkbox" checked={!!pick[hk(h)]} aria-label={h.f+' 고르기'}
              onChange={e=>setPick(o=>{const n={...o};if(e.target.checked)n[hk(h)]=1;else delete n[hk(h)];return n;})}/></td>
            <td>{h.t||'—'}</td><td>{h.m}</td><td className="mono">{h.f}</td><td>{h.c?<span className="st">캐시</span>:<span className="st out">장비</span>}</td></tr>)}</tbody></table></div>}
      <div className="selbar"><span>고른 {picked.length}개{picked.length?` — 같은 호기 앞뒤 ${L.neighbor_h}시간 안의 Batch Report도 함께 읽습니다`:''}</span><div style={{display:'flex',gap:8}}>
        <button onClick={()=>p.setStep(0)}>◀ 검색으로</button><button className="primary" disabled={!picked.length||p.busy} onClick={()=>p.onLoad(picked)}>{p.busy&&!p.checking?'읽는 중…':'고른 Batch Report 읽기 →'}</button></div></div>
      {p.busy&&!p.checking&&p.progress&&<p className="scope-status" role="status">{p.progress}</p>}</>}</>}
    {p.step===2&&v&&<>
      <p className="hint">Scanresult 경로 검색 범위: <b>{v.scan_backup===false?'원본 Scanresult 만(백업본 제외)':'원본 + 백업본'}</b> — 바꾸려면 1단계의 [백업본 포함] 스위치를 바꾸고 다시 검색하세요.</p>
      <details className="logic"><summary>로직 · 고르기</summary><ol>
        <li><b>원문 보기</b> = 캐시에 읽어 둔 Batch Report의 표를 그대로 앱 안에서 보여 줍니다. <b>원본 열기</b> = 장비 Report 폴더의 .htm을 기본 브라우저로 엽니다(읽기 전용).</li>
        <li><b>Scanresult 경로</b> = 같은 호기 루트의 <code>Scanresult*</code> <code>\Job\Setup\S/M</code>. 폴더 이름만 확인해 있는 곳을 보여 줍니다. <b>폴더 열기</b> = 그 폴더를 탐색기로 바로 엽니다(장비 폴더는 읽기만). 이번 검색: <b>{v.scan_backup===false?'원본 Scanresult 만(백업본 제외)':'백업본 포함'}</b>.</li>
        <li>여러 Lot을 함께 골라도 됩니다. 취합은 Lot · 공정 단계마다 따로 합니다(WBG · CMP처럼 다른 공정 스캔을 더하지 않음).</li></ol></details>
      <div className="groups">{!order.length?<div className="empty-state"><h3>찾은 Batch Report가 없습니다.</h3><p>키워드 · 기간 · 호기 범위를 바꿔 보세요.</p></div>
        :order.map(k=>{const mem=members[k],first=v.R[mem[0]],l=first.lot!=null?v.lots[first.lot]:null,b=l?l.bunches[first.b!]:null;
          const paths=[...new Set(mem.map(scanKey))];const all=mem.every(g=>sel[g]);
          return <div key={k} className="group"><div className="gh"><label style={{display:'flex',gap:8,alignItems:'center'}}><input type="checkbox" checked={all} aria-label={(l?'Lot '+l.label:'점검 스캔')+' 전체 선택'}
              onChange={e=>setSel(o=>{const n={...o};mem.forEach(g=>{if(e.target.checked)n[g]=1;else delete n[g];});return n;})}/> <b>{l&&b?`Lot ${l.label} · ${grpLabel(b)}`:'점검 스캔(Lot 아님)'}</b></label>
            {l?<StPill s={l.state}/>:<span className="st out">Lot에서 제외</span>}<span className="meta">{b?`${b.s} ~ ${b.e.slice(5)} · ${b.machines.join(' → ')} · Batch Report ${mem.length}장`:''}</span>
            {l&&<button style={{...small,marginLeft:'auto'}} onClick={()=>p.openLot(first.lot!)}>Lot History 보기</button>}</div>
            {paths.map(pk=>{const s=v.scan?.[pk];const found=s?.paths||[];return <div key={pk} className="sr"><span>Scanresult 경로</span>
              {found.length?found.map(x=><Fragment key={x}><code>{x}</code><button style={small} onClick={()=>openPath(x)} title="탐색기에서 이 Scanresult 폴더 열기(읽기만)">폴더 열기</button><button style={small} onClick={()=>copy(x)}>복사</button></Fragment>)
                :<><code>{s?.pattern||pk}</code><button style={small} onClick={()=>copy(s?.pattern||pk)}>복사</button><span className="meta">{v.scan_backup===false?'원본 Scanresult 에서 폴더를 찾지 못했습니다(백업본은 제외하고 찾음)':'폴더를 찾지 못했습니다(Scanresult · 백업 폴더 확인)'}</span></>}</div>;})}
            <div className="table-scroll" style={{maxHeight:'none',border:0,borderRadius:0}}><table className="t-compact"><thead><tr><th/><th>#</th><th>시작 ~ 끝</th><th>호기</th><th>S/M</th><th className="num">Pass / 행</th><th>첫 Error 원문</th><th>파일 이름</th><th/></tr></thead>
              <tbody>{mem.map((g,ai)=>{const r=v.R[g],out=!hits.has(g);return <tr key={g} className={out?'outside':''}><td><input type="checkbox" checked={!!sel[g]} aria-label={r.f+' 선택'}
                  onChange={e=>setSel(o=>{const n={...o};if(e.target.checked)n[g]=1;else delete n[g];return n;})}/></td><td>{ai+1}</td><td>{r.s} ~ {r.e.slice(11)}</td><td>{r.m}</td>
                <td>{r.sm}{out&&<> <span className="st out">키워드 밖 · 같은 Lot 이어서 스캔</span></>}</td><td className="num">{r.ok} / {r.n}</td><td>{r.fe}</td><td className="mono">{r.f}</td>
                <td><button style={small} onClick={()=>p.showRaw(g)}>원문 보기</button> <button style={small} onClick={()=>p.openFile(g)}>원본 열기</button></td></tr>;})}</tbody></table></div></div>;})}</div>
      <div className="selbar"><span>선택 {nSel}개{nSel?` · 취합 대상 Lot · 공정 단계 ${selGroups}개`:''}</span><div style={{display:'flex',gap:8}}>
        <button onClick={()=>p.setStep(1)}>◀ 찾은 파일로</button><button className="primary" disabled={!nSel||p.busy} onClick={start}>선택한 Batch Report 취합 →</button></div></div></>}
    {p.step===3&&v&&stamp&&<>
      {stamp.manual>0&&!p.dev&&<div className="alert" style={{marginBottom:12}}><span>이 결과에는 개발자 기능에서 직접 고른 선택 {stamp.manual}건이 들어 있습니다(개발자 기능은 지금 꺼짐). 다른 화면과 기준을 맞추려면 다시 취합하세요.</span>
        <button type="button" style={{fontSize:12,minHeight:30,padding:'4px 12px'}} onClick={start}>추천으로 다시 취합</button></div>}
      <div className="stamp"><span>선택 기준: <b>최신 스캔 자동</b>(Pass가 있으면 가장 나중 Pass){stamp.saved>0&&<> + <b>저장된 사람 선택 {stamp.saved}건</b></>}{stamp.manual>0&&<> + <b>개발자 직접 선택 {stamp.manual}건</b></>}</span>
        <span style={{color:'var(--muted)'}}>취합 시각 {stamp.at} · Excel 첫 줄에도 같은 문구를 적습니다</span></div>
      {note&&<div className="alert" style={{marginBottom:12}}><span>{note}</span></div>}
      <h3 style={{marginTop:4}}>Lot 취합</h3>
      <div className="table-scroll" style={{maxHeight:'none'}}><table className="t-compact"><thead><tr><th>Lot</th><th>공정 단계</th><th>호기</th><th className="num">고른 Batch Report</th><th className="num">wafer</th><th className="num">Pass</th><th className="num">Pass 없음</th><th className="num">Scanned</th><th className="num">Bad</th><th className="num">Good</th><th className="num">Yield</th></tr></thead>
        <tbody>{groups.map((g,gi)=>{const t={sc:0,bad:0,good:0,p:0,np:0};g.keys.forEach(k=>{const x=g.w[k].cells[choice[gi+'|'+k]];if(x.ok){t.p++;if(x.sc!=null){t.sc+=x.sc;t.bad+=x.bad||0;t.good+=x.good||0;}}else t.np++;});
          const b=v.lots[g.li].bunches[g.bi];return <tr key={gi}><td><button type="button" className="linklike" onClick={()=>p.openLot(g.li)}>{v.lots[g.li].label}</button></td><td>{grpLabel(b)}</td>
            <td>{[...new Set(g.att.map(x=>v.R[x].m))].join(', ')}</td><td className="num">{g.att.length}</td><td className="num">{g.keys.length}</td><td className="num">{t.p}</td><td className="num">{t.np}</td>
            <td className="num">{num(t.sc)}</td><td className="num">{num(t.bad)}</td><td className="num">{num(t.good)}</td><td className="num">{t.sc?num(t.good/t.sc*100,2)+'%':'—'}</td></tr>;})}</tbody></table></div>
      {groups.map((g,gi)=>{const b=v.lots[g.li].bunches[g.bi];return <Fragment key={gi}><h3>wafer — Lot {v.lots[g.li].label} · {grpLabel(b)}</h3>
        <div className="usedr"><span>고른 Batch Report</span>{g.att.map((x,n)=>{const r=v.R[x];return <button key={x} type="button" onClick={()=>p.showRaw(x)}
          data-tip={`${r.f}\nPass ${r.ok} / ${r.n}행${r.fe?'\n첫 Error: '+r.fe:''}\n누르면 원문`}>#{n+1} {r.s.slice(5)} · {r.m} 원문 보기</button>;})}</div>
        <div className="mapscroll"><table className="map"><thead><tr><th>슬롯</th><th>Wafer ID</th><th>쓰는 Batch Report</th><th>결과 원문</th><th>Scanned</th><th>Bad</th><th>Good</th><th>Yield</th><th/></tr></thead>
          <tbody>{g.keys.map(k=>{const c=g.w[k].cells,x=c[choice[gi+'|'+k]],id=(c.find(y=>isRealId(y.id))||x).id,r=v.R[x.g];
            return <tr key={k}><th>{k.replace(/^S0?/,'').replace(/^ID:/,'')}</th><td>{id}</td><td className="mono">{r.s} · {r.f}{c.length>1&&<span className="rectag" data-tip={`${c.length}장 중 ${g.w[k].saved?'저장된 사람 선택':'추천(가장 나중 Pass)'}으로 선택`}>{c.length}장 중 {g.w[k].saved?'사람 선택':'추천'}</span>}</td>
              <td className={x.ok?'c-p':'c-e'}>{x.status}</td><td className="n">{num(x.sc)}</td><td className="n">{num(x.bad)}</td><td className="n">{num(x.good)}</td><td className="n">{x.sc?num((x.good||0)/x.sc*100,1)+'%':'—'}</td>
              <td><button type="button" style={{minHeight:22,padding:'1px 8px',fontSize:11}} onClick={()=>p.showRaw(x.g)}>원문</button></td></tr>;})}</tbody></table></div></Fragment>;})}
      {xlsx&&<div className="outputs" style={{marginTop:16}}><OpenPath label="저장된 Excel" path={xlsx}/></div>}
      <div className="stepnav" style={{marginTop:16}}><button className="btn" onClick={()=>p.setStep(2)}>◀ 다시 고르기</button><span className="stepcount">4 / 4</span>
        <button className="btn primary" disabled={p.busy} onClick={async()=>{const path=await p.exportAgg(Object.keys(sel).map(Number),choice,stampText);if(path)setXlsx(path);}}>Excel로 저장</button></div></>}
    <dialog className="edit-dialog mid" ref={dupRef} aria-labelledby="dupTitle" onClose={()=>setMust([])}>
      <h3 id="dupTitle">같은 wafer가 여러 Batch Report에 있습니다 <span className="st" style={{background:'#f3eefc',color:'#5b3f8f'}}>개발자 기능</span></h3>
      <p className="sub">개발자 기능 — 같은 wafer가 고른 Batch Report 2장 이상에 있습니다. 추천 = 가장 나중 Pass(없으면 가장 나중 스캔).</p>
      <div style={{maxHeight:'56vh',overflow:'auto'}}>{must.length>0&&<><p className="hint" style={{margin:'0 0 8px'}}><b>Pass가 2번 이상인 wafer {must.length}장</b>은 어느 스캔을 쓸지 고를 수 있습니다(기본 = 추천).{auto.length?` Error 뒤 Pass 1번인 ${auto.length}장은 그 Pass로 자동입니다.`:''}</p>
        {must.map(block)}{auto.length>0&&<details className="more"><summary>Error 뒤 Pass 1번 — 자동 {auto.length}장 보기</summary>{auto.map(block)}</details>}</>}</div>
      <div className="dialog-actions" style={{justifyContent:'space-between'}}><div style={{display:'flex',gap:8}}>
          <button type="button" onClick={()=>setChoice(o=>{const n={...o};must.forEach(([gi,k])=>{n[gi+'|'+k]=groups[gi].w[k].cells.length-1;});return n;})}>모두 가장 나중 스캔</button>
          <button type="button" onClick={()=>setChoice(o=>{const n={...o};must.forEach(([gi,k])=>{n[gi+'|'+k]=recIdx(groups[gi].w[k].cells);});return n;})}>모두 추천(가장 나중 Pass)</button></div>
        <div style={{display:'flex',gap:8}}><button type="button" onClick={()=>dupRef.current?.close()}>취소</button><button type="button" className="primary" onClick={confirmDup}>이대로 취합</button></div></div>
    </dialog>
  </section>;
}

function copy(text:string){
  (navigator.clipboard?navigator.clipboard.writeText(text):Promise.reject()).then(()=>notify('경로를 복사했습니다.','ok'),()=>notify(text,'info'));
}
