import {useEffect,useRef,useState} from 'react';
import {notify} from './ui';

export type Question={kind:'match';machine:string;levels:string[];jobs:string[];suggested:Record<string,string[]>}
  |{kind:'setup';machine:string;job:string;title:string;options:string[]};
export type Answers={match:Record<string,Record<string,string[]>>;setup:Record<string,Record<string,string>>};
export const noAnswers=():Answers=>({match:{},setup:{}});

/** Merge the user's answer to a collector question into the answers sent back. */
export function withAnswer(answers:Answers,question:Question,value:Record<string,string[]>|string):Answers{
  const next:Answers={match:{...answers.match},setup:{...answers.setup}};
  if(question.kind==='match')next.match[question.machine]=value as Record<string,string[]>;
  else next.setup[question.machine]={...(next.setup[question.machine]||{}),[question.job]:value as string};
  return next;
}

/** Collector questions (Job folders per recipe, or Setup) asked during equipment collection. */
export function QuestionDialog({question,onAnswer,onCancel}:{question?:Question;onAnswer:(value:Record<string,string[]>|string)=>void;onCancel:()=>void}){
  const dialog=useRef<HTMLDialogElement>(null);
  const [draft,setDraft]=useState<Record<string,string[]>|string>();
  useEffect(()=>{
    if(question){
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
      <p className="hint">레시피마다 장비 Job 폴더를 고르세요(복수 선택). 이름이 맞는 폴더는 미리 체크했습니다. 고른 Job 안의 Recipe 를 전부 수집합니다. 다음 호기는 같은 Job 이름으로 자동 매칭합니다.</p>
      {question.levels.map(l=><div key={l}><h3>{l}</h3><div className="pick-list short">{question.jobs.map(j=>{const cur=(draft as Record<string,string[]>)?.[l]||[];
        return <label key={j} className="pick-item"><input type="checkbox" checked={cur.includes(j)} onChange={e=>setDraft(d=>{const o={...(d as Record<string,string[]>)};o[l]=e.target.checked?[...cur,j]:cur.filter(v=>v!==j);return o;})}/> {j}{question.suggested[l]?.includes(j)?'  ◀ 추천':''}</label>;})}
        {question.jobs.length===0&&<p className="table-empty">장비에서 Job 폴더를 찾지 못했습니다.</p>}</div></div>)}
    </>:<>
      <h2>{question.machine} · Setup 선택</h2><p className="hint">{question.title}</p>
      <div className="pick-list short">{question.options.map(o=><label key={o} className="pick-item"><input type="radio" name="setup" checked={draft===o} onChange={()=>setDraft(o)}/> {o}</label>)}</div>
    </>}
    <div className="dialog-actions"><button onClick={onCancel}>수집 취소</button><button className="primary" onClick={submit}>확인하고 계속</button></div></>}
  </dialog>;
}
