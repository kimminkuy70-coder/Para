import {useEffect, useRef, useState} from 'react';
import {sessionToken} from './desktop';
import {mountDefect, type DefectHostApi, type DefectMode} from './DefectHost';
import {ColorGray} from './ColorGray';

/* v14 Defect 분석 탭 — 하위 탭 3개(소유자 2026-11-15: "color gray 매칭, Defect 분석(대규모), Defect 분석(기본) 으로 탭 3개, 순서도 동일,
   다이어그램 보이기 체크 삭제, 프로그램 UX 디자인 테마에 맞게 재구성").
   Defect 분석(대규모 · 기본) = AOI Contrast Wizard(HTML rev6, frontend/public/defect/)를 이 화면 안(Shadow DOM, DefectHost.ts)에서 — 대규모 = Step 5, 기본 = Step 1 ~ 4.
   HTML 파일은 그대로 두고(실자료로 검증한 동작), 겉모습만 para-skin.css · para-skin.js 를 넣어 프로그램 테마로 맞춘다(2026-11-25 까지는 같은 출처 iframe).
   HTML 의 PARA 연결부가 폴더 고르기 · 읽기를 엔진(/api/native defect_pick, GET /api/fs/*, 읽기 전용)에 맡긴다.
   스크롤 한 겹(페이지만 스크롤). 하위 탭을 옮겨도 작업은 그대로 남는다(숨기기만). */
type Sub = 'cg' | 'big' | 'basic';
const TABS: [Sub, string, string][] = [
  ['cg', 'Color·Gray 매칭', 'Lot · Wafer 폴더 또는 최종 목록 CSV → 사진 · Excel'],
  ['big', 'Defect 분류', 'Contrast · 분류로 걸러 사진 조사 · 최종 목록'],
  ['basic', 'Defect Map', '스캔 결과 비교 · Wafer Map · Escape 리뷰'],
];

/** 2026-11-25(소유자 "프로그램에 제대로 이식"): iframe 대신 이 칸 안(Shadow DOM)에서 HTML 을 돌린다 — DefectHost.ts. 페이지 스크롤 한 겹 그대로,
 *  로딩창 · 같은 창 사진 칸 = 이 칸의 보이는 부분에 고정. 단계가 바뀌면 이 칸 맨 위를 보여 주고, 같은 창 사진 칸이 뜨면 페이지 스크롤을 잠근다. */
function Wizard({mode, title, hidden}: {mode: DefectMode; title: string; hidden: boolean}) {
  const ref = useRef<HTMLDivElement>(null);
  const [ready, setReady] = useState(false), [error, setError] = useState('');
  useEffect(() => {
    const host = ref.current!, y0 = window.scrollY;
    let api: DefectHostApi | null = null, alive = true;
    mountDefect(host, mode, sessionToken(), {
      onReady: () => { if (!alive) return; setReady(true); window.scrollTo({top: y0}); },
      onStage: () => { const top = host.getBoundingClientRect().top; if (top < 0) window.scrollBy({top: top - 12}); },
      onOverlay: on => { if (on) host.scrollIntoView({block: 'start'}); document.documentElement.style.overflow = on ? 'hidden' : ''; },
    }).then(a => { if (alive) api = a; else a.stop(); }, e => { if (alive) setError(String(e && (e as Error).message || e)); });
    return () => { alive = false; api?.stop(); document.documentElement.style.overflow = ''; };
  }, [mode]);
  return <>
    {error && <p className="hint warn-text" role="alert">Defect 분석 화면을 열지 못했습니다: {error}</p>}
    <div ref={ref} className={'dfx-host' + (ready ? ' ready' : '')} data-title={title} role="region" aria-label={title} hidden={hidden}/>
  </>;
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
    {opened.includes('big') && <Wizard mode="big" title="Defect 분류" hidden={sub !== 'big'}/>}
    {opened.includes('basic') && <Wizard mode="diagram" title="Defect Map" hidden={sub !== 'basic'}/>}
  </>;
}
