import {useEffect,useState} from 'react';
import {errorText} from './desktop';

/* ------------------------------------------------------------------ */
/* Toast notifications — errors and messages pop as top-right cards    */
/* instead of inline text, so screens stay clean.                      */
/* ------------------------------------------------------------------ */
type Kind='ok'|'error'|'info';
type Toast={id:number;msg:string;kind:Kind};
let seq=0;
let toasts:Toast[]=[];
const listeners=new Set<(t:Toast[])=>void>();
function emit(){for(const l of listeners)l(toasts);}
function drop(id:number){toasts=toasts.filter(t=>t.id!==id);emit();}

export function notify(msg:string,kind:Kind='info'){
  const t:Toast={id:++seq,msg,kind};
  toasts=[...toasts,t];emit();
  window.setTimeout(()=>drop(t.id),kind==='error'?6500:3400);
  return t.id;
}
/** Show an error toast from any thrown value (uses the shared errorText map). */
export function fail(e:unknown){return notify(errorText(e),'error');}

export function Toaster(){
  const [items,setItems]=useState<Toast[]>(toasts);
  useEffect(()=>{listeners.add(setItems);return()=>{listeners.delete(setItems);};},[]);
  return <div className="toaster" aria-live="polite">{items.map(t=>
    <div key={t.id} className={'toast '+t.kind} role={t.kind==='error'?'alert':'status'}>
      <span className="ic" aria-hidden="true">{t.kind==='error'?'!':t.kind==='ok'?'✓':'i'}</span>
      <span className="msg">{t.msg}</span>
      <button className="x" aria-label="알림 닫기" onClick={()=>drop(t.id)}>×</button>
    </div>)}</div>;
}

/* ------------------------------------------------------------------ */
/* Stepper header + step navigation footer                             */
/* ------------------------------------------------------------------ */
export function Stepper({labels,current,onJump}:{labels:string[];current:number;onJump?:(i:number)=>void}){
  return <ol className="stepper">{labels.map((l,i)=>{
    const state=i<current?'done':i===current?'now':'todo';
    const clickable=onJump&&i<current;
    return <li key={i} className={'st '+state}>
      <button className="stbtn" disabled={!clickable} onClick={()=>clickable&&onJump!(i)}>
        <span className="dot">{i<current?'✓':i+1}</span><span className="lbl">{l}</span></button>
      {i<labels.length-1&&<span className="bar" aria-hidden="true"/>}
    </li>;
  })}</ol>;
}

/** Footer with 이전 / 다음 (or a custom primary action on the last step). */
export function StepNav({step,total,onBack,onNext,nextLabel='다음',nextDisabled,busy}:{
  step:number;total:number;onBack:()=>void;onNext:()=>void;nextLabel?:string;nextDisabled?:boolean;busy?:boolean}){
  return <div className="stepnav">
    {step>0?<button className="btn" disabled={busy} onClick={onBack}>◀ 이전</button>:<span/>}
    <span className="stepcount">{step+1} / {total}</span>
    <button className="btn primary" disabled={nextDisabled||busy} onClick={onNext}>{busy?'처리 중…':nextLabel}{step<total-1?' ▶':''}</button>
  </div>;
}
