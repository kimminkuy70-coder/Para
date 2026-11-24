// v14.4 (owner 2026-11-23): two editions of one program — AOI Manager (every feature) and
// AOI Manager Mini (fewer features, for people outside the AOI process). The engine hands the
// edition to the page once as ?e=mini (param_manager/webserver.py page_url, AOI_Manager_Mini.bat
// = the start file + --mini); a reload keeps it in sessionStorage like the token (desktop.ts).
//
// What Mini shows is decided HERE (MINI_TABS · MINI_BATCH_FIND_ONLY). A feature that Mini shows is
// the very same screen as in AOI Manager, so every change to it reaches Mini with the same update.
export type Edition = 'full'|'mini';
export const EDITION: Edition = (() => {
  try {
    const q = new URLSearchParams(location.search).get('e');
    if (q === 'mini' || q === 'full') { sessionStorage.setItem('para.e', q); return q; }
    return sessionStorage.getItem('para.e') === 'mini' ? 'mini' : 'full';
  } catch { return 'full'; }
})();
export const isMini = EDITION === 'mini';
export const APP_NAME = isMini ? 'AOI Manager Mini' : 'AOI Manager';

/** Tabs AOI Manager Mini shows (owner pick 2026-11-23; TB500 Review 조회 added in v14.4.2). 설정 is always there. */
export const MINI_TABS: readonly string[] = ['Batch Report 분석', 'Defect 분석', 'Wafer Map 수정하기', 'KLA 자재 찾기', 'TB500 Review 조회', '설정'];
/** Mini: Batch Report 분석 = only [Batch Report 찾기 · 취합] (no 가동률 조사 및 분석, no 자동 분석). */
export const MINI_BATCH_FIND_ONLY = true;
/** Tab label shown for a tab id (the id stays the same everywhere — navigation events use it). */
const MINI_LABEL: Record<string, string> = {'Batch Report 분석': 'Batch Report 찾기 · 취합'};

export function hasTab(tab: string): boolean { return !isMini || MINI_TABS.includes(tab); }
export function tabLabel(tab: string): string { return (isMini && MINI_LABEL[tab]) || tab; }
