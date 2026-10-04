import {useEffect,useState} from 'react';
import {desktop,type Activity} from './desktop';

/* Friendly names for what the engine is doing (unlisted methods get a generic label). */
const LABEL:Record<string,string>={
  connect:'분석 엔진 시작',configuration:'기존 설정 읽기',config_state:'설정 읽기',config_set_save_dir:'저장폴더 확인',
  config_local_state:'로컬 작업 폴더 확인',config_about:'프로그램 정보 읽기',
  recipe_open:'Recipe 값 확인 — 최신 취합 불러오기',recipe_edit:'비고·색상 저장',recipe_export:'Excel 내보내기',recipe_paint:'셀 색칠 저장',
  recipe_delete:'레시피 삭제',recipe_delete_preview:'레시피 삭제 미리보기',
  document_open:'공유 문서 불러오기',document_edit:'문서 저장',document_append:'행 추가 저장',document_delete:'행 삭제 저장',
  form_catalog:'Recipe 양식 목록 읽기',form_versions:'양식 버전 읽기',form_open:'Recipe 양식 불러오기',form_scales:'변환계수 읽기',form_confirm:'Recipe 양식 확정 저장',
  formnew_prepare:'신규 Recipe 만들기 준비',formnew_collect:'장비/로컬에서 설정 수집',formnew_parse:'설정 파일 분석',formnew_scales:'변환계수 읽기',formnew_confirm:'신규 Recipe 양식 저장',
  update_prepare:'Recipe 업데이트 준비',update_set_local_source:'로컬 상위 폴더 확인',update_collect:'장비/로컬에서 설정 수집',
  update_preview:'취합 미리보기',update_commit:'취합 파일 저장',
  history_files:'취합 파일 목록 읽기',history_diff:'레시피 날짜별 비교',history_export:'변경내역 Excel 저장',
  commonality_catalog:'Commonality 결과 목록 읽기',commonality_compare:'Commonality 결과 비교',commonality_export:'비교표 Excel 저장',
  cmsurvey_preflight:'Scanresult 폴더 확인',cmrun_plan:'Scanresult 에서 S/M 폴더 찾기',cmrun_copy:'S/M 폴더 안전 복사',
  cmrun_detect:'레시피 구성 확인',cmrun_parse:'Lot 설정 분석',cmrun_confirm:'조사 양식 저장',cmrun_collate:'Lot 값 조사',
  batch_reports:'Report 목록 읽기',investigate:'Batch Report 조사',analyze:'Batch Report 분석',
  pwatch_state:'자동 감시 설정 읽기',pwatch_save:'자동 감시 설정 저장',pwatch_jobs:'장비 Job 폴더 읽기',pwatch_run:'파라미터 자동 감시 실행',
  cmwatch_state:'Commonality 감시 설정 읽기',cmwatch_save:'Commonality 감시 설정 저장',cmwatch_run:'Commonality 자동 감시 실행',
  cmwatch_candidates:'대표 S/M 후보 찾기',cmwatch_begin:'대표 S/M 복사',cmwatch_confirm:'감시 양식 저장',
  cgm_scan:'Color·Gray — Wafer 찾기',cgm_start:'Color·Gray — 좌표 매칭',cgm_finish:'Color·Gray — Excel 만들기',
  appupdate_check:'업데이트 확인',appupdate_apply:'업데이트 준비',appupdate_publish:'새 버전 게시',
};
// Background housekeeping that should never pop the panel up on its own.
const QUIET=new Set(['watch_status','document_close','recipe_close','document_page','recipe_page','form_page','history_page',
  'commonality_page','cmrun_page','cmwatch_page','formnew_page','table_page','release','cancel','contract','open_path','diag_client','cgm_read','cgm_put','cgm_fail','cgm_state','cgm_reset']);
const SHOW_AFTER_MS=700, SLOW_MS=15000;

/** Bottom-right card: what the engine is doing now and for how long. */
export function ActivityPanel(){
  const [items,setItems]=useState<Activity[]>([]),[now,setNow]=useState(Date.now()),[folded,setFolded]=useState(false);
  useEffect(()=>desktop.onActivity(setItems),[]);
  const visible=items.filter(a=>!QUIET.has(a.method)&&now-a.started>=SHOW_AFTER_MS);
  useEffect(()=>{
    if(!items.length)return;
    const t=window.setInterval(()=>setNow(Date.now()),500);
    return()=>window.clearInterval(t);
  },[items.length]);
  useEffect(()=>{if(!visible.length)setFolded(false);},[visible.length]);
  if(!visible.length)return null;
  const slow=visible.some(a=>now-a.started>=SLOW_MS);
  return <div className={'activity'+(folded?' folded':'')} role="status" aria-live="polite" aria-label="진행 상황">
    <div className="activity-head"><span className="spinner" aria-hidden="true"/><b>처리 중 {visible.length}건</b>
      <button className="x" aria-label={folded?'진행 상황 펼치기':'진행 상황 접기'} onClick={()=>setFolded(f=>!f)}>{folded?'▴':'▾'}</button></div>
    {!folded&&<><ul>{visible.map(a=>{const sec=Math.floor((now-a.started)/1000);return <li key={a.id}>
      <div className="activity-row"><span>{LABEL[a.method]||a.method}</span><span className="elapsed">{sec}초</span></div>
      {a.message&&<p>{a.message}</p>}</li>;})}</ul>
      {slow&&<p className="activity-hint">OneDrive 파일을 내려받거나 장비 폴더 응답을 기다리는 중일 수 있습니다. 창을 닫지 말고 기다려 주세요.
        단계별 소요시간은 자동 기록되며, [설정 › 정보 › 진단 로그 묶기]로 zip 하나를 만들어 전달하면 원인을 분석할 수 있습니다.</p>}</>}
  </div>;
}
