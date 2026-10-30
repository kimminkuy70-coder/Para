// Batch Report 즉시 실행(#33): 자동 분석이 꺼져 있어도 지난 조사 조건으로 바로 한 번 실행한다.
// 설정 화면에서 누르면 Batch Report 분석 화면으로 옮겨 가 그 화면이 실행한다 — 화면이 아직
// 한 번도 안 열렸으면 열린 뒤 takeBatchRunNow() 로 받는다.
let pending=false;
export function requestBatchRunNow(){
  pending=true;
  window.dispatchEvent(new CustomEvent('para:navigate',{detail:'Batch Report 분석'}));
  window.dispatchEvent(new CustomEvent('para:batch-run-now'));
}
export function takeBatchRunNow(){const p=pending;pending=false;return p;}

// Batch Report 자동 분석 설정은 CAMTEK › 자동 분석 및 취합 › [Batch Report 자동 분석] 탭에 있다(#39).
// 다른 화면(설정 › 현재 설정 · Batch Report 분석)에서 그 탭을 열 때 쓴다 — 화면이 아직 안 열렸으면 열린 뒤 takeWatchTab() 으로 받는다.
let watchTab='';
export function openBatchAutoSettings(){
  watchTab='batch';
  window.dispatchEvent(new CustomEvent('para:navigate',{detail:'자동 분석 및 취합'}));
  window.dispatchEvent(new CustomEvent('para:watch-tab'));
}
export function takeWatchTab(){const t=watchTab;watchTab='';return t;}
