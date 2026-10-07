import {useCallback,useEffect,useLayoutEffect,useRef,useState,type ReactNode} from 'react';

/* 튜토리얼(사용자 요청 2026-10-06, v12.2.6) — 화면을 어둡게 하고 대상에 강조 테두리 + 화살표 말풍선을 띄워 한 단계씩 안내한다.
   설정 › [튜토리얼]에서 시작. 화면 이동은 'para:navigate'(주요 탭) · 'para:settings-sub'(설정 하위 탭) 이벤트로 한다.
   튜토리얼은 안내만 한다 — 아무 값도 저장하거나 바꾸지 않는다. */
export type TourKind='setup'|'features';
type Step={target?:string;title:string;body:ReactNode;go?:string;sub?:string};
export function startTour(kind:TourKind){window.dispatchEvent(new CustomEvent('para:tour',{detail:kind}));}

const nav=(name:string)=>`[data-tour="nav:${name}"]`;
const SETUP:Step[]=[
  {title:'초기 설정 튜토리얼',body:<>처음 쓰는 PC에서 한 번만 하면 되는 설정 3가지를 차례로 안내합니다.<ol><li><b>저장 폴더</b> — 개발자가 공유한 OneDrive 폴더 <b>(가장 중요)</b></li><li><b>장비 연결</b> — 장비마다 IP 폴더에 1회 로그인 <b>(가장 중요)</b> + AOI 장비 호기 폴더 등록</li><li><b>로컬 작업 폴더</b> — 이 PC의 작업 공간(선택)</li></ol>튜토리얼은 안내만 하고 아무것도 저장하지 않습니다. [다음]을 누르세요.</>},
  {target:nav('설정'),go:'설정',title:'설정 탭',body:'모든 초기 설정은 이 [설정] 탭에서 합니다. 튜토리얼도 여기서 언제든 다시 볼 수 있습니다.'},
  {target:'[data-tour="settings:tab:save"]',go:'설정',sub:'save',title:'① 저장 폴더 = 공유 OneDrive 폴더',body:<>팀이 함께 쓰는 산출물(공유 문서 · Recipe 양식 · 자동 감시 결과)과 <b>새 버전 업데이트</b>가 이 OneDrive 폴더로 오갑니다. [저장 폴더] 탭을 엽니다.</>},
  {target:'[data-tour="settings:onedrive"]',go:'설정',sub:'save',title:'먼저 OneDrive 에 공유 폴더 연결',body:<><ol><li>개발자가 보낸 <b>OneDrive 공유 링크</b>를 Edge 로 엽니다(회사 계정).</li><li>폴더 위쪽의 <b>[내 파일에 바로 가기 추가]</b>를 누릅니다.</li><li>회사 노트북은 OneDrive 가 이미 연결돼 있어서, 잠시 뒤 <b>파일 탐색기 › OneDrive - 회사이름</b> 아래에 그 폴더가 나타납니다.</li></ol>이 폴더 경로를 다음 칸에 넣습니다.</>},
  {target:'[data-tour="settings:save-path"]',go:'설정',sub:'save',title:'OneDrive 폴더 경로 넣기',body:<>[📁 찾기]를 눌러 위에서 연결한 폴더를 고르거나, 탐색기 주소창의 경로를 붙여넣습니다.<br/><code>예: C:\Users\이름\OneDrive - 회사\AOI 파라미터</code></>},
  {target:'[data-tour="settings:save-btn"]',go:'설정',sub:'save',title:'[저장]',body:'저장하면 처음 한 번 공유 문서(장비 IP 주소 · 참고자료 · 특이사항)가 만들어집니다. 업데이트도 이 폴더 옆 [프로그램] 폴더에서 자동으로 알림이 옵니다.'},
  {target:'[data-tour="settings:tab:aoi"]',go:'설정',sub:'aoi',title:'② 장비 연결 — AOI 장비 호기 루트',body:'장비(호기)마다 폴더를 하나씩 등록합니다. [AOI 장비 호기 루트] 탭을 엽니다.'},
  {go:'설정',sub:'aoi',title:'먼저 장비마다 IP 폴더에 1회 로그인 (가장 중요)',body:<>프로그램은 장비 아이디 · 암호를 다루지 않습니다. 그래서 <b>장비마다 한 번</b> Windows 에서 직접 연결해 두어야 장비 폴더를 읽을 수 있습니다.<ol><li>장비 IP 주소는 [메모] 탭 › <b>장비 IP</b> 하위 탭(공유 문서)에 있습니다.</li><li>파일 탐색기 주소창에 <code>\\장비IP</code> 또는 <code>\\장비IP\c$</code>(Win+R 에 넣어도 됨)를 넣고 Enter.</li><li>로그인 창이 뜨면 장비 <b>아이디 · 암호</b>를 넣고 <b>[내 자격 증명 기억]</b>을 체크한 뒤 [확인].</li><li>공유 폴더가 보이면 연결 끝 — 모든 호기에 같은 방법으로 1회씩.</li></ol>이 연결이 되어 있어야 쓸 수 있는 기능: <b>Recipe 관리</b>(파라미터 읽기 · 양식 업데이트) · <b>자동 감시</b> · <b>Commonality 조사</b>(Scanresult) · <b>Batch Report 분석 · 찾기</b>(Reports · Scanresult 경로 열기) · <b>Color·Gray 매칭</b>(장비 Lot 폴더). 저장 폴더 설정과 함께 <b>가장 중요한 단계</b>입니다. PC 를 바꾸거나 암호가 바뀌면 다시 연결하세요.</>},
  {target:'[data-tour="settings:aoi-form"]',go:'설정',sub:'aoi',title:'호기 이름 + 호기 폴더 → [추가]',body:<><ol><li>먼저 <b>파일 탐색기에서 장비 폴더가 열리는지</b> 확인합니다(네트워크 드라이브 예: <code>P:\AOI-17</code>, 또는 <code>\\장비IP\공유</code>).</li><li><b>호기</b>에 이름(예: AOI-17), <b>호기 폴더</b>에 그 폴더를 넣고 [추가].</li></ol>그 아래 <b>Reports</b>(Batch Report 분석)와 <b>Scanresult</b>(Commonality)를 자동으로 찾습니다. 장비 폴더는 읽기만 합니다.</>},
  {target:'[data-tour="settings:aoi-table"]',go:'설정',sub:'aoi',title:'등록 확인',body:'등록한 호기는 이 표에 나오고 [인식된 폴더]에 Reports · Scanresult 가 보이면 연결된 것입니다. "없음 · 미등록"이면 폴더 경로나 네트워크 연결을 확인하세요.'},
  {target:'[data-tour="settings:tab:local"]',go:'설정',sub:'local',title:'③ 로컬 작업 폴더 (선택)',body:'분석 결과 · 캐시 · 로그가 쌓이는 이 PC의 폴더입니다. 기본값을 그대로 써도 됩니다. OneDrive · 네트워크 폴더는 지정할 수 없습니다(대량 동기화 방지).'},
  {target:'[data-tour="settings:current"]',go:'설정',title:'현재 설정 한눈에 보기',body:'저장 폴더 · 로컬 작업 폴더 · 호기 수가 여기 요약됩니다. "⚠ 저장 폴더 미지정"이 없어지면 초기 설정 끝입니다.'},
  {target:'[data-tour="settings:tour"]',go:'설정',title:'초기 설정 끝',body:'수고하셨습니다! [기능 둘러보기]로 각 탭이 무엇을 하는지 볼 수 있습니다.'},
];
const FEATURES:Step[]=[
  {title:'기능 둘러보기',body:'위쪽 탭마다 무엇을 하는지 차례로 짚어 봅니다. 화면은 실제로 이동하지만 아무것도 실행하지 않습니다.'},
  {target:nav('Recipe 관리'),go:'Recipe 관리',title:'Recipe 관리',body:'장비 Recipe 파라미터 값을 확인 · 비교하고, 양식으로 여러 호기를 한 번에 업데이트합니다. 날짜별 변경 비교도 여기 있습니다.'},
  {target:nav('자동 감시'),go:'자동 감시',title:'자동 감시',body:'정해 둔 주기로 장비 파라미터 · Commonality 를 확인하고 바뀐 것이 있으면 알림과 보고서를 남깁니다. 켜 두면 트레이에서 계속 돕니다.'},
  {target:nav('Commonality 조사'),go:'Commonality 조사',title:'Commonality 조사',body:'Scanresult 를 모아 같은 Lot · 공정을 거친 호기 사이의 결함 공통점을 조사합니다.'},
  {target:nav('Batch Report 분석'),go:'Batch Report 분석',title:'Batch Report 분석',body:'호기와 기간을 골라 [조사 시작] — Lot 추적 · 가동률 · WPH · 레시피 비교를 봅니다. 결과는 HTML · Excel 로도 저장됩니다.'},
  {target:'[data-tour="batch:start"]',go:'Batch Report 분석',title:'[조사 시작]',body:'이미 읽은 Batch Report 는 다시 읽지 않아 두 번째부터는 빠릅니다. 설정에서 하루 1회 자동 분석도 켤 수 있습니다.'},
  {target:'[data-tour="batch:tabs"]',go:'Batch Report 분석',title:'Lot 추적 · 가동률 · WPH · 레시피 비교',body:<>조사가 끝나면 이 탭으로 결과를 봅니다. <b>레시피 비교</b>는 두 레시피 그룹(예: 기존 x20 ↔ 신규 x5)에 레시피를 끌어 넣어 속도 · 검출력을 같은 기준으로 비교합니다.</>},
  {target:nav('Color·Gray 매칭'),go:'Color·Gray 매칭',title:'Color·Gray 매칭',body:'Lot 폴더의 wafer 이미지로 Color · Gray 값을 맞춰 봅니다.'},
  {target:nav('Wafer Map 수정하기'),go:'Wafer Map 수정하기',title:'Wafer Map 수정하기',body:'Wafer Map 파일을 열어 값을 고치고 이미지로 확인한 뒤 저장합니다.'},
  {target:nav('메모'),go:'메모',title:'메모',body:'팀이 함께 보는 메모와 공유 문서(장비 IP · 특이사항)를 엽니다.'},
  {target:nav('설정'),go:'설정',title:'끝!',body:'튜토리얼은 언제든 [설정] › [튜토리얼]에서 다시 볼 수 있습니다.'},
];
const TOURS:Record<TourKind,Step[]>={setup:SETUP,features:FEATURES};

type Box={x:number;y:number;w:number;h:number}|null;
function find(sel?:string):HTMLElement|null{
  if(!sel)return null;
  const all=[...document.querySelectorAll<HTMLElement>(sel)];
  return all.find(el=>el.offsetParent!==null&&el.getClientRects().length>0)||null;
}

export function TourLayer(){
  const [kind,setKind]=useState<TourKind>(),[i,setI]=useState(0),[box,setBox]=useState<Box>(null);
  const bubble=useRef<HTMLDivElement>(null),[pos,setPos]=useState<{left:number;top:number;side:'top'|'bottom'|'center';ax:number}>({left:0,top:0,side:'center',ax:0});
  const steps=kind?TOURS[kind]:[],step=steps[i];
  useEffect(()=>{const on=(e:Event)=>{setKind((e as CustomEvent<TourKind>).detail);setI(0);};window.addEventListener('para:tour',on);return()=>window.removeEventListener('para:tour',on);},[]);
  const close=useCallback(()=>{setKind(undefined);setBox(null);},[]);
  // 단계가 바뀌면 그 화면으로 이동한 뒤 대상이 나타날 때까지(최대 2초) 기다린다.
  useEffect(()=>{
    if(!step)return;
    if(step.go)window.dispatchEvent(new CustomEvent('para:navigate',{detail:step.go}));
    if(step.sub)window.dispatchEvent(new CustomEvent('para:settings-sub',{detail:step.sub}));
    let tries=0,raf=0;
    const look=()=>{const el=find(step.target);
      if(el){el.scrollIntoView({block:'center',inline:'nearest'});const r=el.getBoundingClientRect();setBox({x:r.left,y:r.top,w:r.width,h:r.height});}
      else if(step.target&&tries++<120)raf=requestAnimationFrame(look);else setBox(null);};
    setBox(null);raf=requestAnimationFrame(look);
    return()=>cancelAnimationFrame(raf);
  },[kind,i]);
  // 창 크기 · 스크롤이 바뀌면 강조 위치를 다시 잰다.
  useEffect(()=>{
    if(!step?.target)return;
    const re=()=>{const el=find(step.target);if(el){const r=el.getBoundingClientRect();setBox({x:r.left,y:r.top,w:r.width,h:r.height});}};
    window.addEventListener('resize',re);window.addEventListener('scroll',re,true);
    return()=>{window.removeEventListener('resize',re);window.removeEventListener('scroll',re,true);};
  },[kind,i]);
  // 말풍선 위치: 대상 아래(자리가 없으면 위), 가로는 화면 안으로. 화살표는 대상 가운데를 가리킨다.
  useLayoutEffect(()=>{
    const b=bubble.current;if(!b)return;
    const bw=b.offsetWidth,bh=b.offsetHeight,W=innerWidth,H=innerHeight,gap=18;
    if(!box){setPos({left:(W-bw)/2,top:Math.max(16,(H-bh)/2),side:'center',ax:0});return;}
    const below=box.y+box.h+gap+bh<=H-8||box.y<bh+gap+8;
    const top=below?Math.min(H-bh-8,box.y+box.h+gap):Math.max(8,box.y-bh-gap);
    const cx=box.x+box.w/2,left=Math.min(W-bw-12,Math.max(12,cx-bw/2));
    setPos({left,top,side:below?'bottom':'top',ax:Math.min(bw-24,Math.max(24,cx-left))});
  },[box,i,kind]);
  useEffect(()=>{
    if(!kind)return;
    const key=(e:KeyboardEvent)=>{if(e.key==='Escape'){e.stopPropagation();close();}
      else if(e.key==='ArrowRight'||e.key==='Enter'){e.preventDefault();setI(n=>n+1<steps.length?n+1:n);}
      else if(e.key==='ArrowLeft'){setI(n=>Math.max(0,n-1));}};
    window.addEventListener('keydown',key,true);return()=>window.removeEventListener('keydown',key,true);
  },[kind,steps.length,close]);
  if(!kind||!step)return null;
  const last=i===steps.length-1,pad=6;
  return <div className="tour" role="dialog" aria-modal="true" aria-labelledby="tourTitle">
    {box?<div className="tour-spot" style={{left:box.x-pad,top:box.y-pad,width:box.w+pad*2,height:box.h+pad*2}}/>:<div className="tour-dim"/>}
    <div ref={bubble} className={'tour-bubble '+pos.side} style={{left:pos.left,top:pos.top,['--ax' as string]:pos.ax+'px'}}>
      <div className="tour-head"><span className="tour-kind">{kind==='setup'?'초기 설정':'기능 둘러보기'}</span><span className="tour-count">{i+1} / {steps.length}</span></div>
      <h3 id="tourTitle">{step.title}</h3>
      <div className="tour-body">{step.body}</div>
      <div className="tour-dots" aria-hidden="true">{steps.map((_,k)=><i key={k} className={k===i?'on':k<i?'done':''}/>)}</div>
      <div className="tour-actions"><button type="button" className="tour-skip" onClick={close}>{last?'닫기':'건너뛰기'}</button><span className="grow"/>
        <button type="button" disabled={i===0} onClick={()=>setI(n=>n-1)}>이전</button>
        <button type="button" className="primary" onClick={()=>last?close():setI(n=>n+1)}>{last?'완료':'다음 →'}</button></div>
    </div>
  </div>;
}
