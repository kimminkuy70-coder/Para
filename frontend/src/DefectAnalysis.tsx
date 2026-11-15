import {useState} from 'react';
import {sessionToken} from './desktop';
import {ColorGray} from './ColorGray';

/* v14 Defect 분석 탭(소유자 2026-11-15: "Color·Gray 매칭 탭 이름을 Defect 분석으로, 기존 매칭은 그 안에,
   하위 탭 = 기존 Color·Gray 매칭 + 대규모 Defect 분석(HTML Step 5), Step 1 ~ 4 다이어그램 분석은 체크로 선택").
   대규모 Defect 분석 · 다이어그램 분석 = AOI Contrast Wizard(HTML rev6, frontend/public/defect/) 를 같은 출처 iframe 으로 —
   HTML 의 PARA 연결부가 폴더 고르기 · 읽기를 엔진(/api/native defect_pick, GET /api/fs/*, 읽기 전용)에 맡긴다:
   브라우저 '업로드'(폴더 전체 · 사진까지 목록, 50만 파일 ≈ 1시간) 없음, Windows Chromium 의 .ini 거부 없음, 전체 경로 자동.
   하위 탭을 옮겨도 작업은 그대로 남는다(숨기기만, 한 번 연 화면은 계속 둠). */
const WIZARD='/defect/AOI_Contrast_Wizard_rev6.html';
type Sub='big'|'cg'|'diagram';
const DIAG_KEY='para.defect.diagram';

export function DefectAnalysis(){
  const [diagram,setDiagram]=useState(()=>{try{return localStorage.getItem(DIAG_KEY)==='1';}catch{return false;}});
  const [sub,setSub]=useState<Sub>('big');
  const [opened,setOpened]=useState<Sub[]>(['big']);
  const go=(s:Sub)=>{setSub(s);setOpened(v=>v.includes(s)?v:[...v,s]);};
  const toggle=(on:boolean)=>{setDiagram(on);try{localStorage.setItem(DIAG_KEY,on?'1':'0');}catch{/* 이 PC 기억 실패는 무시 */}
    if(on)go('diagram');else if(sub==='diagram')setSub('big');};
  const subs:[Sub,string][]=[['big','대규모 Defect 분석'],['cg','Color·Gray 매칭'],...(diagram?[['diagram','다이어그램 분석 (Step 1 ~ 4)'] as [Sub,string]]:[])];
  const src=(mode:'big'|'diagram')=>`${WIZARD}?t=${encodeURIComponent(sessionToken())}&mode=${mode}`;
  return <>
    <div className="subtabs defect-subtabs" role="tablist" aria-label="Defect 분석">{subs.map(([id,label])=>
      <button key={id} role="tab" aria-selected={sub===id} className={sub===id?'active':''} onClick={()=>go(id)}>{label}</button>)}
      <label className="defect-opt" title="켜면 AOI Contrast Wizard 의 Step 1 ~ 4(두 Step Lot 비교 · Wafer Map 분석 · Escape Defect 리뷰)를 하위 탭으로 씁니다. 이 PC 에 기억합니다.">
        <input type="checkbox" checked={diagram} onChange={e=>toggle(e.target.checked)}/> 다이어그램 분석(Step 1 ~ 4) 보이기</label>
    </div>
    {opened.includes('big')&&<iframe className="defect-frame" title="대규모 Defect 분석" hidden={sub!=='big'} src={src('big')} allow="fullscreen"/>}
    {opened.includes('cg')&&<div hidden={sub!=='cg'}><ColorGray/></div>}
    {diagram&&opened.includes('diagram')&&<iframe className="defect-frame" title="다이어그램 분석" hidden={sub!=='diagram'} src={src('diagram')} allow="fullscreen"/>}
  </>;
}
