/* Defect 분석(대규모 · 기본) = AOI Contrast Wizard HTML(rev6)을 프로그램 화면 안에서 돌린다(소유자 2026-11-25 "창이 분리되어 있어서
   로딩 중일 때 아래가 잘리는 등 버그 — 프로그램에 제대로 이식"). 종전 = 같은 출처 iframe + 높이 · 보이는 부분 알림(postMessage).
   HTML 파일은 그대로 둔다(분석 동작 · ccr 원본과 같은 내용 · 시험). 여기서 하는 일:
   - HTML 을 읽어 <style> · 본문 · <script> 로 나누고, 모드마다 Shadow DOM 하나에 넣는다(id · CSS 가 프로그램 · 다른 모드와 섞이지 않음).
     CSS 의 :root · html → :host, body → .dfx-body 로 바꿔 적는다(para-skin.css 도).
   - 스크립트는 빌드가 함수 하나로 감싼 파일(dist/defect/*.run.js, vite.config.ts)로 읽어 document · window · location · localStorage 를 이 칸 것으로 준다:
     document.getElementById · querySelector = 이 칸 안, body = .dfx-body, documentElement = 칸(:host — 지도 색 변수), createElement · hidden = 진짜 문서,
     location.search = ?t=토큰&mode=big|diagram(PARA 연결부가 켜짐), window.__cw = 이 칸의 시험 · 확인용 함수 묶음(host.__cw).
   - 키보드(↑↓ · Space · B …) = 이 칸이 보이고, 누른 곳이 이 칸 안(또는 마지막으로 누른 곳이 이 칸)일 때만 HTML 에 넘긴다(대상 = 실제 누른 칸).
   - localStorage 'storage' 알림 = 같은 문서 안 두 칸끼리도 전한다(µm 로 보기 · 설명 보기를 두 탭이 같이 — iframe 때는 브라우저가 해 줌).
   - 로딩창 · 같은 창 사진 칸 · 측정 원 창 = 프로그램 화면 전체(para-skin.css, 소유자 2026-11-27). --vt · --vl · --vw · --vh(이 칸의 보이는 부분)는 계속 적어 둔다(HTML 의 다른 자리 계산용). */

const WIZARD = '/defect/AOI_Contrast_Wizard_rev6.html', SKIN = '/defect/para-skin';
export type DefectMode = 'big' | 'diagram';

type Factory = (...a: unknown[]) => void;
type Parts = {css: string; body: string; skinCss: string; wizard: Factory; skin: Factory};
/** 빌드가 만든 함수 파일(frontend/vite.config.ts defectRun) — 화면 보안 정책(script-src 'self')이 문자열 실행을 막으므로 <script src> 로 읽는다.
 *  인자 = vite.config.ts RUN_PARAMS 와 같은 차례. ?v = HTML 내용 해시(업데이트 뒤 예전 파일을 쓰지 않게). */
function runFile(name: string, file: string, v: string): Promise<Factory> {
  const w = window as unknown as {__dfxRun?: Record<string, Factory>};
  if (w.__dfxRun?.[name]) return Promise.resolve(w.__dfxRun[name]);
  return new Promise((res, rej) => {
    const s = document.createElement('script'); s.src = `${file}?v=${v}`;
    s.onload = () => { const f = w.__dfxRun?.[name]; if (f) res(f); else rej(new Error(file + ' 에 함수가 없음')); };
    s.onerror = () => rej(new Error(file + ' 를 읽지 못했습니다'));
    document.head.append(s);
  });
}
const hash = (t: string) => { let h = 2166136261; for (let i = 0; i < t.length; i++) h = Math.imul(h ^ t.charCodeAt(i), 16777619); return (h >>> 0).toString(36); };
let partsP: Promise<Parts> | null = null;
const text = async (u: string) => { const r = await fetch(u, {cache: 'no-cache'}); if (!r.ok) throw new Error(`${u} ${r.status}`); return r.text(); };
function loadParts(): Promise<Parts> {
  return partsP ??= (async () => {
    const [html, skinCss, skinJs] = await Promise.all([text(WIZARD), text(SKIN + '.css'), text(SKIN + '.js')]);
    const doc = new DOMParser().parseFromString(html, 'text/html');
    const css = [...doc.querySelectorAll('style')].map(s => s.textContent || '').join('\n');
    doc.querySelectorAll('script').forEach(s => s.remove());
    const [wizard, skin] = await Promise.all([runFile('AOI_Contrast_Wizard_rev6.html', WIZARD.replace(/\.html$/, '.run.js'), hash(html)),
      runFile('para-skin.js', SKIN + '.run.js', hash(skinJs))]);
    return {css, body: doc.body.innerHTML, skinCss, wizard, skin};
  })().catch(e => { partsP = null; throw e; });
}

/** CSS 선택자: :root(조건) → :host(조건), :root · html → :host, body → .dfx-body. 선언 안(값)은 이 단어가 나오지 않는다. */
export function scopeCss(css: string) {
  return css
    .replace(/:root((?:\[[^\]]*\]|:not\((?:[^()]|\([^()]*\))*\))+)/g, ':host($1)')
    .replace(/:root(?![\w-])/g, ':host')
    .replace(/(^|[\s,>+~{}(])html(?![\w-])/g, '$1:host')
    .replace(/(^|[\s,>+~{}(])body(?![\w-])/g, '$1.dfx-body');
}
const scopeSel = (s: string) => s.replace(/(^|[\s,>+~(])body(?![\w-])/g, '$1.dfx-body').replace(/(^|[\s,>+~(])(?:html|:root)(?![\w-])/g, '$1:host');

/* 같은 문서 안 두 칸(대규모 · 기본) 사이의 localStorage 알림 */
const BUS = new Set<(e: {key: string | null; oldValue: string | null; newValue: string | null}) => void>();
const LIVE = new Set<HTMLElement>();
let lastDown: EventTarget | null = null;
let globalsOn = false;
function globals() {
  if (globalsOn) return; globalsOn = true;
  document.addEventListener('pointerdown', e => { lastDown = e.composedPath()[0] || null; }, true);
  // HTML 이 목록에 주는 focus() 가 프로그램 페이지를 끌어내리지 않게(이 칸 안 요소만 — 프로그램의 다른 focus 는 그대로)
  const focus0 = HTMLElement.prototype.focus;
  HTMLElement.prototype.focus = function (this: HTMLElement, o?: FocusOptions) {
    const r = this.getRootNode() as ShadowRoot;
    return focus0.call(this, r && r.host && LIVE.has(r.host as HTMLElement) ? {preventScroll: true, ...(o || {})} : o);
  };
}

export type DefectHostApi = {stop: () => void};
export type HostEvents = {onReady?: () => void; onStage?: () => void; onOverlay?: (on: boolean) => void};

/** host 안에 HTML 을 연다(모드마다 한 번 — 하위 탭을 옮겨도 숨기기만). */
export async function mountDefect(host: HTMLElement, mode: DefectMode, token: string, ev: HostEvents): Promise<DefectHostApi> {
  globals();
  const P = await loadParts();
  const root = host.shadowRoot || host.attachShadow({mode: 'open'});
  root.innerHTML = '';
  const st = (css: string) => { const s = document.createElement('style'); s.textContent = css; root.append(s); };
  st(scopeCss(P.css));
  st(scopeCss(P.skinCss));
  st(':host{display:block;position:relative}:host([hidden]){display:none}.dfx-body{position:relative}');
  const body = document.createElement('div'); body.className = 'dfx-body'; body.innerHTML = P.body; root.append(body);
  LIVE.add(host);

  const visible = () => host.isConnected && host.getClientRects().length > 0;
  const cleanups: (() => void)[] = [];
  const on = (t: EventTarget, type: string, fn: EventListener, opt?: boolean | AddEventListenerOptions) => { t.addEventListener(type, fn, opt); cleanups.push(() => t.removeEventListener(type, fn, opt)); };
  const realTarget = (e: Event) => new Proxy(e, {get: (t, k) => {
    if (k === 'target') return e.composedPath()[0] || e.target;
    const v = Reflect.get(t, k); return typeof v === 'function' ? v.bind(t) : v; }});
  const keyFns = new Map<unknown, EventListener>();
  const docAdd = (type: string, fn: EventListener, opt?: boolean | AddEventListenerOptions) => {
    if (!fn) return;
    if (type === 'visibilitychange') return on(document, type, fn, opt);
    if (type === 'keydown' || type === 'keyup') {   // 이 칸이 보이고, 이 칸 안(또는 빈 곳인데 마지막으로 누른 곳이 이 칸)일 때만
      const w: EventListener = e => {
        if (!visible()) return;
        const path = e.composedPath(), inside = path.includes(host);
        const free = e.target === document.body || e.target === document.documentElement;
        const lastIn = lastDown instanceof Node && (lastDown === host || host.contains(lastDown) || root.contains(lastDown));
        if (!inside && !(free && lastIn)) return;
        fn(realTarget(e));
      };
      keyFns.set(fn, w); return on(document, type, w, opt);
    }
    return on(root, type, fn, opt);
  };
  const docRemove = (type: string, fn: EventListener, opt?: boolean | EventListenerOptions) => {
    const w = keyFns.get(fn); if (w) { document.removeEventListener(type, w, opt); keyFns.delete(fn); return; }
    (type === 'visibilitychange' ? document : root).removeEventListener(type, fn, opt);
  };
  const doc = {
    getElementById: (id: string) => root.getElementById(id),
    querySelector: (s: string) => root.querySelector(scopeSel(s)),
    querySelectorAll: (s: string) => root.querySelectorAll(scopeSel(s)),
    getElementsByTagName: (s: string) => root.querySelectorAll(s),
    get body() { return body; }, get documentElement() { return host; }, get head() { return root; },
    get activeElement() { return root.activeElement || document.activeElement; },
    get hidden() { return document.hidden; }, get visibilityState() { return document.visibilityState; },
    get fullscreenElement() { return document.fullscreenElement; }, exitFullscreen: () => document.exitFullscreen(),
    createElement: (t: string, o?: ElementCreationOptions) => document.createElement(t, o),
    createElementNS: (n: string, t: string) => document.createElementNS(n, t),
    createTextNode: (t: string) => document.createTextNode(t),
    createDocumentFragment: () => document.createDocumentFragment(),
    createTreeWalker: (n: Node, w?: number, f?: NodeFilter | null) => document.createTreeWalker(n, w, f),
    elementFromPoint: (x: number, y: number) => root.elementFromPoint(x, y),
    execCommand: (c: string, u?: boolean, v?: string) => document.execCommand(c, u, v),
    addEventListener: docAdd, removeEventListener: docRemove,
    get fonts() { return document.fonts; }, get readyState() { return document.readyState; },
    get title() { return document.title; }, set title(_v: string) { /* 프로그램 창 제목은 그대로 */ },
    get defaultView() { return win; },
  };
  const search = `?t=${encodeURIComponent(token)}&mode=${mode}`;
  const loc = {protocol: location.protocol, hostname: location.hostname, host: location.host, port: location.port, origin: location.origin,
    pathname: WIZARD, search, hash: '', href: location.origin + WIZARD + search, reload: () => location.reload(), toString: () => location.origin + WIZARD + search};
  const storageFns = new Set<(e: unknown) => void>();
  const busFn = (e: {key: string | null; oldValue: string | null; newValue: string | null}) => storageFns.forEach(f => { try { f(Object.assign({storageArea: localStorage, url: loc.href}, e)); } catch (x) { console.error(x); } });
  BUS.add(busFn); cleanups.push(() => BUS.delete(busFn));
  const tell = (key: string | null, oldValue: string | null, newValue: string | null) => BUS.forEach(f => { if (f !== busFn) f({key, oldValue, newValue}); });
  const ls = {
    getItem: (k: string) => localStorage.getItem(k),
    setItem: (k: string, v: string) => { const o = localStorage.getItem(k); localStorage.setItem(k, v); const n = localStorage.getItem(k); if (o !== n) tell(k, o, n); },
    removeItem: (k: string) => { const o = localStorage.getItem(k); localStorage.removeItem(k); if (o != null) tell(k, o, null); },
    key: (i: number) => localStorage.key(i), clear: () => localStorage.clear(), get length() { return localStorage.length; },
  };
  const winAdd = (type: string, fn: EventListener, opt?: boolean | AddEventListenerOptions) => {
    if (!fn) return;
    if (type === 'storage') { storageFns.add(fn as never); on(window, type, fn, opt); return; }   // 다른 창(종전 iframe · 다른 Edge 창)에서 온 알림도
    if (type === 'keydown' || type === 'keyup') return docAdd(type, fn, opt);
    on(window, type, fn, opt);
  };
  const winRemove = (type: string, fn: EventListener, opt?: boolean | EventListenerOptions) => {
    if (type === 'storage') storageFns.delete(fn as never);
    window.removeEventListener(type, fn, opt);
  };
  const api: Record<string, unknown> = {};
  const win: Window = new Proxy(window, {
    get(t, k) {
      if (k === '__cw') return api.cw;
      if (k === 'document') return doc; if (k === 'location') return loc; if (k === 'localStorage') return ls;
      if (k === 'addEventListener') return winAdd; if (k === 'removeEventListener') return winRemove;
      if (k === 'window' || k === 'self' || k === 'globalThis') return win;
      const v = Reflect.get(t, k);
      return typeof v === 'function' && typeof k === 'string' && /^[a-z]/.test(k) ? v.bind(t) : v;
    },
    set(t, k, v) { if (k === '__cw') { api.cw = v; (host as unknown as {__cw: unknown}).__cw = v; return true; } return Reflect.set(t, k, v); },
  });
  const noScroll = () => { /* 프로그램 페이지를 맨 위로 올리지 않음(iframe 때의 iframe 안 스크롤 되돌림) */ };
  const paraHost = (m: {ready?: boolean; stage?: boolean; overlay?: boolean}) => {
    if (m.ready) ev.onReady?.(); if (m.stage) ev.onStage?.(); if (typeof m.overlay === 'boolean') ev.onOverlay?.(m.overlay);
  };
  // 인자 차례 = vite.config.ts RUN_PARAMS(document,window,location,localStorage,addEventListener,removeEventListener,self,globalThis,scrollTo,paraHost)
  const run = (f: Factory) => f.call(win, doc, win, loc, ls, winAdd, winRemove, win, win, noScroll, paraHost);
  // 보이는 부분(로딩창 · 같은 창 칸 · 측정 원 창의 자리)
  const view = () => {
    if (!visible()) return;
    const r = host.getBoundingClientRect(), t = Math.max(0, r.top), b = Math.min(innerHeight, r.bottom), l = Math.max(0, r.left), rr = Math.min(innerWidth, r.right);
    const s = host.style;
    s.setProperty('--vt', Math.round(t) + 'px'); s.setProperty('--vh', Math.max(0, Math.round(b - t)) + 'px');
    s.setProperty('--vl', Math.round(l) + 'px'); s.setProperty('--vw', Math.max(0, Math.round(rr - l)) + 'px');
  };
  on(window, 'scroll', view, {passive: true}); on(window, 'resize', view);
  const ro = new ResizeObserver(view); ro.observe(host); cleanups.push(() => ro.disconnect());
  view();
  host.dataset.mode = mode;
  run(P.wizard);
  run(P.skin);
  (host as unknown as {__dfx: unknown}).__dfx = {win, doc};   // 시험(tools/test_desktop_ui.mjs)이 이 칸 안에서 함수를 부를 때
  return {stop: () => { cleanups.forEach(f => f()); LIVE.delete(host); }};
}
