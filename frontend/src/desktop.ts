// v13: the screen runs in an Edge app window on http://127.0.0.1:<port>/ served by the Python
// engine (param_manager/webserver.py). The per-run token arrives once as ?t=… and is kept in
// sessionStorage (a reload keeps working; the address no longer shows it).
const TOKEN: string = (() => {
  try {
    const q = new URLSearchParams(location.search).get('t');
    if (q) { sessionStorage.setItem('para.t', q); history.replaceState(null, '', location.pathname + location.hash); return q; }
    return sessionStorage.getItem('para.t') || '';
  } catch { return ''; }
})();
/** True inside the app window (the engine handed this page its token). */
export function isDesktop(): boolean { return !!TOKEN; }
async function post(path: string, body: unknown): Promise<Response> {
  return fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Para-Token': TOKEN}, body: JSON.stringify(body), cache: 'no-store'});
}
/** What the Tauri shell did natively (folder/file dialogs, tray residency, quit) — done by the engine now. */
async function native<T>(command: string, args: object = {}): Promise<T> {
  const r = await post('/api/native', {command, args});
  if (!r.ok) throw new Error('native_' + r.status);
  return (await r.json()).result as T;
}
export type Metric = 'M01'|'M02'|'M03'|'M04'|'M05'|'M06'|'M08'|'M10'|'M11';
export type Options = {metrics: Metric[]; valid_wafers: number; by_recipe: boolean};
export type Target = {machine: string; query: string; start: string; end: string; names?: string[]};
export type Table = {index: number; key: string; title: string; headers: string[]; total: number};
export type Configuration = {machines: {id: string; folder: string; extra?: string[]}[]; local_root: string; last?: {targets?: Target[]; options?: Options};
  auto?: {enabled: boolean; due: boolean; last_run: string; last_result: string; interval_hours?: number; time?: string; next_run?: string; publish?: boolean; kla?: boolean; kla_publish?: boolean}; metrics?: {id: string; title: string}[];
  lot_criteria?: {title: string; text: string; example: string}[]};
export type Reply = {version: number; id: number|null; event: string; code?: string; message?: string;
  job?: number; tables?: Table[]; summary?: Record<string, number>; rows?: (string|number|null)[][];
  artifacts?: Record<string,string>; collection?: {parsed: number; reused: number; errors: number; cached_only: number}; reports?: unknown;
  current?: number; total?: number; recipe?: unknown; document?: unknown; commonality?: unknown; form?: unknown; cmsurvey?: unknown; history?: unknown; config?: unknown; update?: unknown; opened?: unknown; cmrun?: unknown; formnew?: unknown; appupdate?: unknown; watch?: unknown; pwatch?: unknown; cmwatch?: unknown; diag?: unknown; colorgray?: unknown; wafermap?: unknown; kla?: unknown; batch?: unknown; view?: unknown; notice?: WatchNotice} & Partial<Configuration>;

// Native folder chooser (the engine opens the Windows dialog). Returns the user-selected
// absolute path, or null if cancelled / not in the app window (then the user types the path).
export async function pickFolder(): Promise<string|null> {
  if (!isDesktop()) return null;
  try { return (await native<string|null>('pick_folder')) ?? null; }
  catch { return null; }
}
/** Native file chooser for a Lot plan workbook (.xlsx/.xlsm); null if cancelled / not desktop. */
export async function pickFile(kind: 'excel'|'zip' = 'excel'): Promise<string|null> {
  if (!isDesktop()) return null;
  try { return (await native<string|null>('pick_file', {kind})) ?? null; }
  catch { return null; }
}
/** Files dragged onto the window (issue #29). A browser gives the file contents, not its path,
 * so a dropped .zip is uploaded to the engine (local Temp) and listeners get that local path. */
export type FileDrop = {kind: 'enter'|'leave'|'drop'; paths?: string[]};
const dropListeners = new Set<(d: FileDrop) => void>();
const hasFiles = (e: DragEvent) => !!e.dataTransfer && [...e.dataTransfer.types].includes('Files');
const tell = (d: FileDrop) => dropListeners.forEach(l => l(d));
let dragDepth = 0;
if (typeof window !== 'undefined') {
  // Always stop a dropped file from replacing the app page (the browser would open it).
  window.addEventListener('dragenter', e => { if (!hasFiles(e)) return; e.preventDefault(); if (dragDepth++ === 0) tell({kind: 'enter', paths: []}); }, true);
  window.addEventListener('dragover', e => { if (hasFiles(e)) e.preventDefault(); }, true);
  window.addEventListener('dragleave', e => { if (!hasFiles(e)) return; if (--dragDepth <= 0) { dragDepth = 0; tell({kind: 'leave'}); } }, true);
  window.addEventListener('drop', e => {
    if (!hasFiles(e)) return;
    e.preventDefault(); e.stopPropagation(); dragDepth = 0;
    const file = [...(e.dataTransfer?.files ?? [])].find(f => f.name.toLowerCase().endsWith('.zip'));
    if (!file || !dropListeners.size || !isDesktop()) { tell({kind: 'drop', paths: []}); return; }
    void fetch('/api/upload?name=' + encodeURIComponent(file.name), {method: 'POST', headers: {'X-Para-Token': TOKEN}, body: file})
      .then(r => r.ok ? r.json() : Promise.reject(new Error('upload_' + r.status)))
      .then((j: {path: string}) => tell({kind: 'drop', paths: [j.path]}))
      .catch(() => tell({kind: 'drop', paths: []}));
  }, true);
}
export function onFileDrop(listener: (d: FileDrop) => void): () => void {
  dropListeners.add(listener);
  return () => { dropListeners.delete(listener); };
}
/** Quit the app (used right after an update was staged): the engine saves, then exits. */
export async function exitApp(): Promise<void> {
  if (isDesktop()) { try { await native('app_exit'); } catch { /* already closing */ } }
  try { window.close(); } catch { /* not script-opened */ }
}
/** Pushed by the engine's watch scheduler (id null, event 'notice'). */
export type WatchNotice = {kind: string; title: string; summary: string; report?: string; at?: string; by_other?: boolean;
  /** which watch ('pwatch'|'cmwatch'); quiet = list only (no pop-up); live = the one '진행 중' line, replaced by the next notice */
  watch?: string; quiet?: boolean; live?: boolean};
/** Add a notice to the recent list: a watch's live '진행 중' line is replaced, not stacked. */
export function mergeNotice(list: WatchNotice[], n: WatchNotice): WatchNotice[] {
  const kept = n.watch ? list.filter(o => !(o.live && o.watch === n.watch)) : list;
  return [...kept, n].slice(-50);
}
/** Tray / hide-on-close: keep the app running in the notification area while a watch is on. */
export async function setBackground(enabled: boolean, tooltip: string): Promise<void> {
  if (isDesktop()) { try { await native('set_background', {enabled, tooltip}); } catch { /* engine closing */ } }
}
export type AppUpdate = {current: string; installed: boolean; available: string; newer: boolean; changelog: string;
  published_at: string; skipped: boolean; failed: boolean; program_dir: string};
/** One request (or the engine start) in flight, for the progress panel. */
export type Activity = {id: number; method: string; started: number; message: string};
type Pending = {resolve: (v: Reply) => void; reject: (e: Error) => void; progress?: (v: Reply) => void};
class DesktopClient {
  // Ids keep increasing across page reloads because a reload re-attaches to the
  // same engine, which rejects ids it has already seen (A7).
  private next = Date.now() * 1000;
  private pending = new Map<number, Pending>();
  private connecting?: Promise<void>;
  private sends: Promise<unknown> = Promise.resolve();
  private disconnected = false;
  /** Why the engine went away (e.g. already_running), kept for later requests (A5). */
  private closeCode = 'engine_closed';
  private listeners = new Set<(connected: boolean, code: string) => void>();
  private noticeListeners = new Set<(n: WatchNotice) => void>();
  // In-flight requests + engine start, shown by the progress panel so a slow
  // OneDrive/equipment read is visible instead of a silent "불러오는 중".
  private active = new Map<number, Activity>();
  private activityListeners = new Set<(a: Activity[]) => void>();
  onActivity(listener: (a: Activity[]) => void) { this.activityListeners.add(listener); listener([...this.active.values()]); return () => { this.activityListeners.delete(listener); }; }
  private track(id: number, method: string | null, message = '') {
    if (method === null) this.active.delete(id);
    else { const old = this.active.get(id); this.active.set(id, {id, method, started: old?.started ?? Date.now(), message: message || old?.message || ''}); }
    const list = [...this.active.values()];
    this.activityListeners.forEach(l => l(list));
  }
  // Screen-side timeline for the engine's detailed log (상세_진단_로그.txt): when the
  // page loaded, when the engine was started, when each request was sent/answered.
  // Compared with the engine's own lines it shows whether time went to engine
  // start-up, waiting in the pipe, or the work itself.
  private diag: {t: number; text: string}[] = [{t: performance.timeOrigin, text: '화면(웹뷰) 로딩 시작'}];
  private diagTimer?: number;
  private diagQuiet = new Set(['table_page','recipe_page','form_page','document_page','history_page','commonality_page',
    'cmrun_page','cmwatch_page','formnew_page','open_path','cgm_read','cgm_put']);
  private note(text: string) {
    if (this.diag.length < 400) this.diag.push({t: Date.now(), text});
    if (!this.diagTimer) this.diagTimer = window.setTimeout(() => { this.diagTimer = undefined; this.flushDiag(); }, 5000);
  }
  private flushDiag() {
    if (this.disconnected || !this.diag.length || !this.connecting) return;
    const events = this.diag.splice(0, 200);
    this.request('diag_client', {events}).promise.catch(() => undefined);
    if (this.diag.length) this.note('(이어서)');
  }
  onNotice(listener: (n: WatchNotice) => void) { this.noticeListeners.add(listener); return () => { this.noticeListeners.delete(listener); }; }
  onStatus(listener: (connected: boolean, code: string) => void) { this.listeners.add(listener); return () => { this.listeners.delete(listener); }; }
  get closed() { return this.disconnected; }
  private events?: EventSource;
  private onMessage(message: Reply) {
    if (message.version !== 1) return;
    if (message.id === null && message.event === 'notice') {
      // Unsolicited watch result; the engine is still connected.
      if (message.notice) this.noticeListeners.forEach(l => l(message.notice!));
      return;
    }
    if (message.id === null) { this.lost(message.code); return; }
    const pending = this.pending.get(message.id);
    if (!pending) return;
    if (message.event === 'accepted' || message.event === 'progress') {
      if (message.message) this.track(message.id, this.active.get(message.id)?.method ?? '', message.message);
      pending.progress?.(message);
    } else {
      this.pending.delete(message.id);
      const took = Date.now() - (this.active.get(message.id)?.started ?? Date.now());
      const method = this.active.get(message.id)?.method ?? '';
      this.track(message.id, null);
      if (method && method !== 'diag_client' && (took >= 300 || !this.diagQuiet.has(method))) {
        this.note(`응답 #${message.id} ${method} ${message.event} ${took}ms`);
        if (method === 'configuration' || took >= 3000) window.setTimeout(() => this.flushDiag(), 0);
      }
      if (message.event === 'error') pending.reject(new Error(message.message || message.code));
      else pending.resolve(message);
    }
  }
  private lost(code?: string) {
    if (this.disconnected) return;
    this.disconnected = true;
    // engine_closed follows an earlier, more specific reason: keep the first one.
    if (code && (this.closeCode === 'engine_closed' || code !== 'engine_closed')) this.closeCode = code;
    this.events?.close(); this.events = undefined;
    this.pending.forEach(p => p.reject(new Error(this.closeCode)));
    this.pending.clear();
    [...this.active.keys()].forEach(k => this.track(k, null));
    this.listeners.forEach(l => l(false, this.closeCode));
  }
  connect() {
    if (!isDesktop()) return Promise.reject(new Error('desktop_required'));
    if (this.disconnected) {
      // Try again (the engine may still be there after a network hiccup) instead of staying dead.
      this.disconnected = false; this.connecting = undefined; this.closeCode = 'engine_closed';
    }
    if (!this.connecting) {
      this.track(0, 'connect', '분석 엔진에 연결하고 있습니다…');
      const asked = Date.now();
      this.note('엔진 연결 요청(이벤트 스트림)');
      this.connecting = new Promise<void>((resolve, reject) => {
        const es = new EventSource('/api/events?t=' + encodeURIComponent(TOKEN));
        this.events = es;
        let opened = false;
        es.onopen = () => {
          if (opened) return;
          opened = true;
          this.note(`엔진 연결됨 ${Date.now() - asked}ms (엔진이 모듈을 다 읽어야 첫 응답)`);
          this.listeners.forEach(l => l(true, ''));
          resolve();
        };
        es.onmessage = ev => { try { this.onMessage(JSON.parse(ev.data) as Reply); } catch { /* malformed line */ } };
        // The stream ends when the engine exits; EventSource would retry forever — stop and report.
        es.onerror = () => { if (!opened) { es.close(); this.events = undefined; reject(new Error('engine_closed')); } this.lost('engine_closed'); };
      });
      this.connecting.then(() => this.track(0, null), () => { this.connecting = undefined; this.track(0, null); });
    }
    return this.connecting;
  }
  request(method: string, params: object = {}, progress?: (v: Reply) => void) {
    const id = ++this.next;
    const promise = new Promise<Reply>((resolve, reject) => {
      if (this.disconnected) { reject(new Error(this.closeCode)); return; }
      this.pending.set(id, {resolve, reject, progress});
      this.track(id, method);
      if (method !== 'diag_client' && !this.diagQuiet.has(method)) this.note(`요청 보냄 #${id} ${method}`);
      // Serialize writes only; cancellation does not wait for analysis completion.
      this.sends = this.sends.catch(() => undefined).then(() => this.connecting).then(async () => {
        const r = await post('/api/send', {version: 1, id, method, params});
        if (!r.ok) throw new Error(r.status === 503 ? 'engine_busy_or_closed' : 'send_' + r.status);
      }).catch(async error => {
        this.pending.delete(id);
        this.track(id, null);
        // A send can fail just before the engine's own exit reason arrives; give
        // that message a moment so the user sees the real cause (A5).
        if (String(error) === 'engine_busy_or_closed') await new Promise(r => setTimeout(r, 300));
        reject(new Error(this.disconnected ? this.closeCode : String(error)));
      });
    });
    return {id, promise};
  }
}
export const desktop = new DesktopClient();
export const defaults: Options = {metrics:['M01','M02','M03','M04','M05','M06','M08','M10','M11'],valid_wafers:25,by_recipe:true};
export function errorText(error: unknown): string {
  const raw = error instanceof Error ? error.message : String(error);
  return ({desktop_required:'바탕화면 바로가기로 연 프로그램 창에서만 동작합니다. 이 페이지를 직접 열지 말고 프로그램을 다시 실행해 주세요.',
    engine_not_packaged:'분석 엔진이 포함되지 않은 빌드입니다. 엔진 패키징 후 이용할 수 있습니다.',
    engine_closed:'분석 엔진 연결이 종료되었습니다. 상단의 [다시 연결]을 누르고, 안 되면 프로그램을 다시 실행해 주세요.',
    already_running:'기존 Camtek AOI 프로그램(트레이 포함)이 켜져 있어 웹 엔진을 시작할 수 없습니다. 기존 프로그램을 종료한 뒤 상단의 [다시 연결]을 누르세요.',
    engine_busy_or_closed:'분석 엔진이 응답하지 않습니다. 상단의 [다시 연결]을 누르고, 안 되면 프로그램을 다시 실행해 주세요.',
    engine_start_failed:'분석 엔진을 시작하지 못했습니다. 바탕화면 바로가기로 프로그램을 다시 실행해 주세요.',
    access_denied:'파일이나 폴더에 접근할 권한이 없습니다. 다른 사람이 열어 두었거나 OneDrive 동기화 중인지 확인하세요.',
    file_missing:'필요한 파일을 찾지 못했습니다. 이동·삭제되었는지 확인하고 새로고침하세요.',
    io_failed:'파일을 읽거나 쓰지 못했습니다. 네트워크·OneDrive 연결과 저장 공간을 확인하세요.',
    engine_failed:'처리 중 예상하지 못한 오류가 났습니다. 설정 › 정보의 오류 로그 폴더를 담당자에게 전달하세요.',
    investigation_failed:'조사를 완료하지 못했습니다. 폴더 접근과 로컬 저장 공간을 확인해 주세요.',
    configuration_failed:'기존 설정을 불러오지 못했습니다. 설정 파일과 로컬 폴더를 확인해 주세요.'} as Record<string,string>)[raw] || raw;
}
