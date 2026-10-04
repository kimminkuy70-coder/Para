import {useState} from 'react';
import {Documents} from './Documents';

/* 메모 — 공유 문서 3개(특이사항 · 참고자료 · 장비 IP)를 한 탭의 하위 탭으로 묶는다.
   하위 탭마다 기존 문서 화면을 그대로 쓰고(key 로 다시 그림), 다른 하위 탭으로 옮기면
   이전 문서 화면이 닫혀 편집 잠금도 종전처럼 반납된다. */
type Kind='special'|'reference'|'ip';
const SUBS:[Kind,string][]=[['special','특이사항'],['reference','참고자료'],['ip','장비 IP']];

export function Memo(){
  const [sub,setSub]=useState<Kind>('special');
  return <>
    <div className="subtabs" role="tablist" aria-label="메모 문서">{SUBS.map(([id,label])=>
      <button key={id} role="tab" aria-selected={sub===id} className={sub===id?'active':''} onClick={()=>setSub(id)}>{label}</button>)}</div>
    <Documents key={sub} kind={sub}/>
  </>;
}
