import {useEffect,useRef,useState} from 'react';
import {notify} from './ui';

export type Question={kind:'match';machine:string;levels:string[];jobs:string[];suggested:Record<string,string[]>}
  |{kind:'setup';machine:string;job:string;title:string;options:string[]};
export type Answers={match:Record<string,Record<string,string[]>>;setup:Record<string,Record<string,string>>;skip?:string[]};
export const noAnswers=():Answers=>({match:{},setup:{},skip:[]});

/** Merge the user's answer to a collector question into the answers sent back. */
export function withAnswer(answers:Answers,question:Question,value:Record<string,string[]>|string):Answers{
  const next:Answers={match:{...answers.match},setup:{...answers.setup},skip:[...(answers.skip||[])]};
  if(question.kind==='match')next.match[question.machine]=value as Record<string,string[]>;
  else next.setup[question.machine]={...(next.setup[question.machine]||{}),[question.job]:value as string};
  return next;
}

/** The user skipped this machine (its recipe is not on the equipment, #22). */
export function withSkip(answers:Answers,machine:string):Answers{
  return {...answers,skip:[...(answers.skip||[]).filter(m=>m!==machine),machine]};
}

/** Collector questions (Job folders per recipe, or Setup) asked during equipment collection. */
export function QuestionDialog({question,onAnswer,onCancel,onSkip}:{question?:Question;onAnswer:(value:Record<string,string[]>|string)=>void;onCancel:()=>void;onSkip?:()=>void}){
  const dialog=useRef<HTMLDialogElement>(null);
  const [draft,setDraft]=useState<Record<string,string[]>|string>();
  const [find,setFind]=useState('');
  useEffect(()=>{
    if(question){
      setFind('');
      setDraft(question.kind==='match'?Object.fromEntries(question.levels.map(l=>[l,question.suggested[l]||[]])):(question.options[0]||''));
      dialog.current?.showModal();
    }else dialog.current?.close();
  },[question]);
  function submit(){
    if(!question||draft===undefined)return;
    if(question.kind==='match'&&!Object.values(draft as Record<string,string[]>).some(v=>v.length)){
      notify('레시피별 Job 폴더를 하나 이상 고르세요.','error');return;}
    onAnswer(draft);
  }
  return <dialog className="edit-dialog wide-dialog" ref={dialog} onCancel={e=>e.preventDefault()}>{question&&<>
    {question.kind==='match'?<>
      <h2>{question.machine} · 레시피 ↔ Job 폴더</h2>
      <p className="hint">레시피마다 장비 Job 폴더를 고르세요(복수 선택). 이름이 맞는 폴더는 미리 체크하고 '◀ 추천'을 붙였습니다. 고른 Job 안의 Recipe 를 전부 수집합니다. 다음 호기는 같은 Job 이름으로 자동 매칭합니다.</p>
      <p className="hint">레시피와 일치하는 이름이 없으면 추천이 없습니다 — 아래 목록에서 직접 찾아 고르세요. 이 호기에 해당 레시피가 없으면 [이 호기 건너뛰기]를 누르세요.</p>
      <label className="field">Job 폴더 이름 찾기<input value={find} onChange={e=>setFind(e.target.value)} placeholder="이름 일부" maxLength={200}/></label>
      {question.levels.map(l=>{const cur=(draft as Record<string,string[]>)?.[l]||[];const q=find.trim().toLowerCase();
        const shown=question.jobs.filter(j=>!q||j.toLowerCase().includes(q)||cur.includes(j));
        return <div key={l}><h3>{l}</h3>
        {!question.suggested[l]?.length&&question.jobs.length>0&&<p className="warn" role="note">'{l}' 레시피와 일치하는 이름이 없습니다. 목록에서 직접 찾아 주세요.</p>}
        <div className="pick-list short">{shown.map(j=>
          <label key={j} className="pick-item"><input type="checkbox" checked={cur.includes(j)} onChange={e=>setDraft(d=>{const o={...(d as Record<string,string[]>)};o[l]=e.target.checked?[...cur,j]:cur.filter(v=>v!==j);return o;})}/> {j}{question.suggested[l]?.includes(j)?'  ◀ 추천':''}</label>)}
        {question.jobs.length===0&&<p className="table-empty">장비에서 Job 폴더를 찾지 못했습니다.</p>}
        {question.jobs.length>0&&!shown.length&&<p className="table-empty">'{find}' 이(가) 들어간 Job 폴더가 없습니다.</p>}</div></div>;})}
    </>:<>
      <h2>{question.machine} · Setup 선택</h2><p className="hint">{question.title}</p>
      <div className="pick-list short">{question.options.map(o=><label key={o} className="pick-item"><input type="radio" name="setup" checked={draft===o} onChange={()=>setDraft(o)}/> {o}</label>)}</div>
    </>}
    <div className="dialog-actions"><button onClick={onCancel}>수집 취소</button>
      {onSkip&&<button onClick={onSkip} title="이 호기는 수집하지 않고 다음 호기로 넘어갑니다(취합에서는 직전 값 유지)">이 호기 건너뛰기</button>}
      <button className="primary" onClick={submit}>확인하고 계속</button></div></>}
  </dialog>;
}
