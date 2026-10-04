import {useSyncExternalStore} from 'react';

/* 개발자 기능(설정 › 정보) — 중복 Pass 를 사람이 직접 고르고 저장하는 '고치는 화면'만 연다.
   결과 숫자는 엔진이 추천 + 저장된 사람 선택(로컬 Cache)으로만 정하므로 이 토글은 엔진에 보내지 않는다.
   ① 저장 안 한 선택(draft)이 있으면 끄기 전에 저장/버리기를 묻는다 ② 조사 중에는 바꿀 수 없다.
   켜짐 여부는 이 PC 의 화면 설정(localStorage)에만 남는다. */
export type DevState={on:boolean;locked:boolean;drafts:number};
const KEY='para.batch.developer';
function stored(){try{return localStorage.getItem(KEY)==='1';}catch{return false;}}
let state:DevState={on:stored(),locked:false,drafts:0};
const subs=new Set<()=>void>();
const emit=()=>subs.forEach(f=>f());
function update(next:Partial<DevState>){state={...state,...next};emit();}
export function useDev(){return useSyncExternalStore(cb=>{subs.add(cb);return()=>{subs.delete(cb);};},()=>state);}
export function setDevOn(on:boolean){try{localStorage.setItem(KEY,on?'1':'0');}catch{/* 이 PC 설정 저장 불가: 이번 실행 동안만 */}update({on});}
export function setDevLocked(locked:boolean){if(state.locked!==locked)update({locked});}
export function setDevDrafts(drafts:number){if(state.drafts!==drafts)update({drafts});}
// Batch Report 화면이 저장 안 한 선택을 저장/버리는 방법을 알려 준다(설정 화면의 끄기 확인창이 쓴다).
let handlers:{save?:()=>Promise<boolean>;drop?:()=>void}={};
export function registerDraftHandlers(h:{save:()=>Promise<boolean>;drop:()=>void}){handlers=h;return()=>{if(handlers===h)handlers={};};}
export async function saveDrafts(){return handlers.save?await handlers.save():true;}
export function dropDrafts(){handlers.drop?.();}
