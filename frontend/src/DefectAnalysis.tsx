import {useEffect, useRef, useState} from 'react';
import {sessionToken} from './desktop';
import {ColorGray} from './ColorGray';

/* v14 Defect 분석 탭 — 하위 탭 3개(소유자 2026-11-15: "color gray 매칭, Defect 분석(대규모), Defect 분석(기본) 으로 탭 3개, 순서도 동일,
   다이어그램 보이기 체크 삭제, 프로그램 UX 디자인 테마에 맞게 재구성").
   Defect 분석(대규모 · 기본) = AOI Contrast Wizard(HTML rev6, frontend/public/defect/)를 같은 출처 iframe 으로 — 대규모 = Step 5, 기본 = Step 1 ~ 4.
   HTML 파일은 그대로 두고(실자료로 검증한 동작), 겉모습만 para-skin.css · para-skin.js 를 넣어 프로그램 테마로 맞춘다.
   HTML 의 PARA 연결부가 폴더 고르기 · 읽기를 엔진(/api/native defect_pick, GET /api/fs/*, 읽기 전용)에 맡긴다.
   스크롤 한 겹: iframe 높이 = 내용 높이(para-skin.js 가 알림) → 페이지만 스크롤. 하위 탭을 옮겨도 작업은 그대로 남는다(숨기기만). */
const WIZARD = '/defect/AOI_Contrast_Wizard_rev6.html', SKIN = '/defect/para-skin';
type Sub = 'cg' | 'big' | 'basic';
const TABS: [Sub, string, string][] = [
  ['cg', 'Color·Gray 매칭', 'Lot · Wafer 폴더 또는 최종 목록 CSV → 사진 · Excel'],
  ['big', 'Defect 분석(대규모)', 'Contrast · 분류로 걸러 사진 조사 · 최종 목록'],
  ['basic', 'Defect 분석(기본)', '스캔 결과 비교 · Wafer Map · Escape 리뷰'],
];

function Wizard({mode, title, hidden}: {mode: 'big' | 'diagram'; title: string; hidden: boolean}) {
  const ref = useRef<HTMLIFrameElement>(null);
  const [height, setHeight] = useState(900);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    const f = ref.current!, y0 = window.scrollY;
    // 로딩창 · 같은 창 사진 칸이 iframe 의 '보이는 부분'에 뜨도록 알려 준다.
    const view = () => {
      const w = f.contentWindow; if (!w) return;
      const r = f.getBoundingClientRect(), top = Math.max(0, -r.top), bottom = Math.min(r.height, window.innerHeight - r.top);
      w.postMessage({paraView: {top: Math.round(top), height: Math.max(0, Math.round(bottom - top))}}, location.origin);
    };
    const onMessage = (e: MessageEvent) => {
      if (e.source !== f.contentWindow || e.origin !== location.origin || !e.data) return;
      const m = e.data as {height?: number; overlay?: boolean; ready?: boolean; stage?: boolean};
      if (typeof m.height === 'number' && m.height > 0) setHeight(m.height);
      // 처음 열 때 HTML 이 목록에 준 포커스로 페이지가 내려갔으면 되돌린다
      if (m.ready) { setReady(true); window.scrollTo({top: y0}); }
      // 단계(5-1 · 5-2 · 5-3, Step 1 ~ 4)가 바뀌었는데 이 칸의 맨 위가 화면 위로 지나갔으면 맨 위(스텝퍼)를 보여 준다
      if (m.stage) { const top = f.getBoundingClientRect().top; if (top < 0) window.scrollBy({top: top - 12}); }
      if (typeof m.overlay === 'boolean') {
        if (m.overlay) f.scrollIntoView({block: 'start'});
        document.documentElement.style.overflow = m.overlay ? 'hidden' : '';
      }
      requestAnimationFrame(view);
    };
    window.addEventListener('message', onMessage);
    window.addEventListener('scroll', view, {passive: true});
    window.addEventListener('resize', view);
    const ro = new ResizeObserver(view); ro.observe(f);
    return () => {
      window.removeEventListener('message', onMessage); window.removeEventListener('scroll', view); window.removeEventListener('resize', view); ro.disconnect();
      document.documentElement.style.overflow = '';
    };
  }, []);
  const skin = () => {
    const doc = ref.current?.contentDocument;
    if (!doc || doc.getElementById('para-skin')) return;
    const link = doc.createElement('link');
    link.id = 'para-skin'; link.rel = 'stylesheet'; link.href = SKIN + '.css';
    link.onload = () => { const s = doc.createElement('script'); s.src = SKIN + '.js'; doc.head.append(s); };
    doc.head.append(link);
  };
  return <iframe ref={ref} className={'defect-frame' + (ready ? ' ready' : '')} title={title} hidden={hidden} scrolling="no" allow="fullscreen"
    src={`${WIZARD}?t=${encodeURIComponent(sessionToken())}&mode=${mode}`} style={{height}} onLoad={skin}/>;
}

export function DefectAnalysis() {
  const [sub, setSub] = useState<Sub>('cg');
  const [opened, setOpened] = useState<Sub[]>(['cg']);
  const go = (s: Sub) => { setSub(s); setOpened(v => v.includes(s) ? v : [...v, s]); };
  return <>
    <div className="defect-tabs" role="tablist" aria-label="Defect 분석">{TABS.map(([id, label, note]) =>
      <button key={id} role="tab" aria-selected={sub === id} className={sub === id ? 'active' : ''} title={note} onClick={() => go(id)}>{label}</button>)}
    </div>
    {opened.includes('cg') && <div hidden={sub !== 'cg'}><ColorGray/></div>}
    {opened.includes('big') && <Wizard mode="big" title="Defect 분석(대규모)" hidden={sub !== 'big'}/>}
    {opened.includes('basic') && <Wizard mode="diagram" title="Defect 분석(기본)" hidden={sub !== 'basic'}/>}
  </>;
}
