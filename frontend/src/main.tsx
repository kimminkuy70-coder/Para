import React from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

const tiles = [
  ['배치 리포트 분석', '11개 지표 · 증분 수집 · Excel / HTML', '엔진 연결 준비'],
  ['Recipe 비교', '좌측 파라미터 · 우측 다중 호기 비교', '전환 예정'],
  ['Commonality', '감시 상태 · 최근 결과 · 실패 원인', '기존 기능 보존'],
  ['설정 및 자료', '양식 · 참고자료 · 업데이트', '기존 기능 보존']
];

function App() {
  return <div className="app">
    <header><div><span className="eyebrow">CAMTEK AOI MANAGER</span><h1>공정 데이터 작업공간</h1><p>로컬 우선 · 읽기 전용 · 오프라인 분석</p></div><button className="primary">배치 분석 열기</button></header>
    <main><section className="summary"><div><span>현재 환경</span><strong>version_rev1</strong></div><div><span>분석 엔진</span><strong>11 metrics</strong></div><div><span>운영 방식</span><strong>Offline-first</strong></div></section>
    <section><h2>작업</h2><div className="grid">{tiles.map(([title, description, status]) => <article key={title}><span className="status">{status}</span><h3>{title}</h3><p>{description}</p><button>열기 →</button></article>)}</div></section></main>
  </div>;
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>);
