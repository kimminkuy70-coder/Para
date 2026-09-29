import {useEffect,useState} from 'react';
import {Recipe} from './Recipe';
import {Update} from './Update';
import {Form} from './Form';
import {History} from './History';

/** Recipe 관리: the collation viewer plus the four recipe workflows as tabs. */
export const RECIPE_TABS:[string,string][]=[['view','Recipe 값 확인'],['update','Recipe 업데이트'],['new','신규 Recipe 만들기'],
  ['edit','Recipe 양식 편집하기'],['history','레시피 날짜별 비교하기']];

export function RecipeHub({active}:{active:boolean}){
  const [sub,setSub]=useState('view');
  // Workflow tabs stay mounted after the first visit (a half-done update or form is
  // kept). The value viewer holds a shared-file edit lock, so it is mounted only while
  // it is on screen — leaving it (or Recipe 관리) hands the lock back.
  const [visited,setVisited]=useState<string[]>([]);
  useEffect(()=>{if(sub!=='view')setVisited(v=>v.includes(sub)?v:[...v,sub]);},[sub]);
  return <>
    <div className="subtabs hub-tabs" role="tablist" aria-label="Recipe 관리">{RECIPE_TABS.map(([id,label])=>
      <button key={id} role="tab" aria-selected={sub===id} className={sub===id?'active':''} onClick={()=>setSub(id)}>{label}</button>)}</div>
    {active&&sub==='view'&&<Recipe/>}
    {visited.map(k=><div key={k} hidden={sub!==k} className="hub-screen">{
      k==='update'?<Update/>:k==='new'?<Form mode="new"/>:k==='edit'?<Form mode="edit"/>:<History/>}</div>)}
  </>;
}
