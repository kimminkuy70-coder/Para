import {useEffect,useRef,useState} from 'react';
import {HELP} from './metricHelp';
import {num,STOPK,C_DEFECT,C_STOP,type View} from './batchData';

/* ? 버튼 — 지표 이름 옆에 두고, 누르면 뜻 · 식 · 지금 화면 숫자로 계산한 예 · 확인할 것 · 한계를 한 창에 보여 준다.
   화면에는 설명 글을 두지 않고 모두 이 창으로 보낸다(사용자 지시 2026-10-05: 화면은 심플하게). */
export const openDefect=()=>window.dispatchEvent(new CustomEvent('bv:defect'));

export function Q({id,calc,lg}:{id:string;calc?:string[];lg?:boolean}){
  const [open,setOpen]=useState(false);
  const h=HELP[id];
  if(!h)return null;
  return <><button type="button" className={'help-btn'+(lg?' lg':'')} aria-label={h.t+' 설명'} title={h.t+' — 어떻게 계산하나요?'}
    onClick={e=>{e.stopPropagation();setOpen(true);}}>?</button>{open&&<HelpDialog id={id} calc={calc} onClose={()=>setOpen(false)}/>}</>;
}

function HelpDialog({id,calc,onClose}:{id:string;calc?:string[];onClose:()=>void}){
  const ref=useRef<HTMLDialogElement>(null),h=HELP[id];
  useEffect(()=>{const d=ref.current;if(d&&!d.open)d.showModal();},[]);
  return <dialog className="edit-dialog mid qhelp" ref={ref} aria-labelledby={'q-'+id} onClose={onClose} onClick={e=>e.stopPropagation()}>
    <span className="step">지표 설명</span><h3 id={'q-'+id}>{h.t}</h3>
    <p className="lead">{h.what}</p>
    {h.f&&<><h4>계산식</h4><ul className="formula">{h.f.map(x=><li key={x}>{x}</li>)}</ul></>}
    {calc&&calc.length>0&&<><h4>지금 화면 숫자로 계산하면</h4><ul className="calc">{calc.map(x=><li key={x}>{x}</li>)}</ul></>}
    {h.check&&<><h4>이 값으로 확인할 것</h4><p>{h.check}</p></>}
    {h.limits&&<><h4>한계</h4><ul>{h.limits.map(x=><li key={x}>{x}</li>)}</ul></>}
    <div className="dialog-actions">{id==='stop.defect'&&<button type="button" onClick={()=>{ref.current?.close();openDefect();}}>기준값 · 판정 목록 보기</button>}
      <button type="button" className="primary" onClick={()=>ref.current?.close()}>닫기</button></div>
  </dialog>;
}

/** Defect 과다 중단 설명 창 — 판정 방법 · 레시피별 기준값 · 이번 조사 작업자 중단 목록(사용자 요청: 프로그램 안에 설명이 있어야 함). */
export function DefectWindow({v,open,onClose,showRaw,openLot}:{v?:View;open:boolean;onClose:()=>void;showRaw:(g:number)=>void;openLot:(li:number)=>void}){
  const ref=useRef<HTMLDialogElement>(null);
  const [kind,setKind]=useState<''|'d'|'o'>('');
  useEffect(()=>{const d=ref.current;if(!d)return;if(open&&!d.open)d.showModal();if(!open&&d.open)d.close();},[open]);
  const X=v?.X,stops=(v?.stops||[]).filter(s=>!kind||s.k===kind);
  const per:Record<string,{d:number;o:number}>={};(v?.stops||[]).forEach(s=>{const t=per[s.r]||(per[s.r]={d:0,o:0});t[s.k]++;});
  const recipes=Object.keys({...(X?.faults||{}),...per}).sort();
  return <dialog className="edit-dialog wide qhelp" ref={ref} aria-labelledby="defTitle" onClose={onClose}>
    <span className="step">지표 설명</span><h3 id="defTitle">Defect 과다 중단 — 어떻게 판정하나요?</h3>
    <p className="lead">작업자 중단(앞에 Error 없이 <code>Aborted.</code>로 멈춘 Batch Report) 가운데, <b>멈출 때 wafer의 Faults가 그 레시피 정상 wafer Faults 상위 1% 값보다 많으면</b> Defect가 너무 많아 멈춘 것(Defect 과다 중단)으로 봅니다.</p>
    <ul className="formula">
      <li>멈출 때 wafer = 마지막 Pass wafer, 또는 스캔 도중 멈춘 wafer(Aborted. 행에 Faults가 남은 것). 웨이퍼 표 순서가 곧 스캔 순서입니다.</li>
      <li>정상 wafer = Error · 중단 없는 Batch Report의 Pass wafer. 레시피(Job · Recipe(s))마다 따로 구합니다(제품 · 레시피마다 Defect 수준이 다르므로).</li>
      <li>정상 wafer가 {X?.min_base??100}장 미만인 레시피는 기준이 불안정해 판정하지 않고 <b>그 외 중단</b>으로 셉니다(아래 표 '기준 부족').</li></ul>
    <h4>왜 이 기준인가요?</h4>
    <p>몇 개에서 멈출지는 작업자 재량이라 정해진 개수가 없습니다. 끝까지 스캔한 Batch Report에도 Faults가 아주 많은 wafer가 있습니다(그때는 멈추지 않음). 그래서 개수를 정하지 않고, 그 레시피에서 <b>평소 100장 중 1장도 안 나오는 수준</b>을 넘었을 때만 Defect 때문에 멈춘 것으로 봅니다. 이 규칙을 정할 때 본 실자료(2D_WBG 420개)에서는 Defect로 멈춘 경우가 430 ~ 1,634개, 그 외 중단은 12개 이하로 기준(약 25개)에서 멀리 떨어져 있어 기준값이 조금 달라져도 판정이 바뀌지 않았습니다.</p>
    <h4>레시피별 기준값 <small>조사 범위(호기 · 기간)가 바뀌면 기준값도 다시 구합니다</small></h4>
    <div className="table-scroll" style={{maxHeight:240}}><table className="t-compact"><thead><tr><th>레시피(Job · Recipe(s))</th><th className="num">정상 wafer</th><th className="num">상위 1% Faults(기준)</th><th className="num">Defect 과다 중단</th><th className="num">그 외 중단</th></tr></thead>
      <tbody>{recipes.map(r=>{const f=X?.faults[r],p=per[r]||{d:0,o:0};return <tr key={r}><td>{r}</td><td className="num">{num(f?.[1]||0)}</td>
        <td className="num">{f&&f[0]!=null?<b>{num(f[0],1)}</b>:<span className="v4">기준 부족</span>}</td><td className="num">{p.d}</td><td className="num">{p.o}</td></tr>;})}
        {!recipes.length&&<tr><td colSpan={5}>조사 결과가 없습니다.</td></tr>}</tbody></table></div>
    <h4>이번 조사의 작업자 중단 <small>행을 누르면 Batch Report 원문</small></h4>
    <div className="chips" style={{margin:'0 0 8px'}}>{([['','전체'],['d',STOPK.d],['o',STOPK.o]] as const).map(([k,l])=>
      <button key={k} type="button" className={'chip'+(kind===k?' on':'')} aria-pressed={kind===k} onClick={()=>setKind(k)}>{k&&<i className="sw" style={{background:k==='d'?C_DEFECT:C_STOP}}/>}{l}</button>)}</div>
    <div className="table-scroll" style={{maxHeight:300}}><table className="t-compact"><thead><tr><th>시작</th><th>호기</th><th>Lot</th><th>레시피</th><th className="num">멈추기 전 Pass</th><th className="num">멈출 때 Faults</th><th className="num">기준</th><th>판정</th></tr></thead>
      <tbody>{stops.map(s=>{const r=v!.R[s.g];return <tr key={s.g} className="clickable" onClick={()=>showRaw(s.g)}><td>{r.s}</td><td>{s.m}</td>
        <td><button type="button" className="linklike" onClick={e=>{e.stopPropagation();openLot(s.li);}}>{v!.lots[s.li].label}</button></td><td>{s.r}</td>
        <td className="num">{s.ps}</td><td className="num"><b>{s.f==null?'—':num(s.f)}</b></td><td className="num">{s.base==null?'기준 부족':num(s.base,1)}</td>
        <td><span className={'st '+(s.k==='d'?'sd':'so')}>{STOPK[s.k]}</span></td></tr>;})}
        {!stops.length&&<tr><td colSpan={8}>작업자 중단이 없습니다.</td></tr>}</tbody></table></div>
    <div className="dialog-actions"><button type="button" className="primary" onClick={()=>ref.current?.close()}>닫기</button></div>
  </dialog>;
}
