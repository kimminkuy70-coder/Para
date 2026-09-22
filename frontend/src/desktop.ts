import { Channel, invoke, isTauri } from '@tauri-apps/api/core';
export type Metric = 'M01'|'M02'|'M03'|'M04'|'M05'|'M06'|'M08'|'M09'|'M10'|'M11';
export type Options = {metrics: Metric[]; valid_wafers: number; min_baseline: number; yield_drop: number; by_recipe: boolean};
export type Target = {machine: string; query: string; start: string; end: string; names?: string[]};
export type Table = {index: number; key: string; title: string; headers: string[]; total: number};
export type Configuration = {machines: {id: string; folder: string; extra?: string[]}[]; local_root: string; last?: {targets?: Target[]; options?: Options};
  auto?: {enabled: boolean; due: boolean; last_run: string; last_result: string}; metrics?: {id: string; title: string}[]};
export type Reply = {version: number; id: number|null; event: string; code?: string; message?: string;
  job?: number; tables?: Table[]; summary?: Record<string, number>; rows?: (string|number|null)[][];
  artifacts?: Record<string,string>; collection?: {parsed: number; reused: number; errors: number; cached_only: number}; reports?: unknown;
  current?: number; total?: number; recipe?: unknown; document?: unknown; commonality?: unknown; form?: unknown; cmsurvey?: unknown; history?: unknown; config?: unknown; update?: unknown; opened?: unknown; cmrun?: unknown; formnew?: unknown} & Partial<Configuration>;

// Native folder chooser (Tauri command). Returns the user-selected absolute
// path, or null if cancelled or not running inside the desktop shell (then the
// user types/pastes the path instead).
export async function pickFolder(): Promise<string|null> {
  if (!isTauri()) return null;
  try { return (await invoke<string|null>('pick_folder')) ?? null; }
  catch { return null; }
}
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
  onStatus(listener: (connected: boolean, code: string) => void) { this.listeners.add(listener); return () => { this.listeners.delete(listener); }; }
  get closed() { return this.disconnected; }
  connect() {
    if (!isTauri()) return Promise.reject(new Error('desktop_required'));
    if (this.disconnected) {
      // Start a fresh engine (the previous one exited) instead of staying dead.
      this.disconnected = false; this.connecting = undefined; this.closeCode = 'engine_closed';
    }
    if (!this.connecting) {
      const channel = new Channel<Reply>();
      channel.onmessage = message => {
        if (message.version !== 1) return;
        if (message.id === null) {
          this.disconnected = true;
          // engine_closed follows an earlier, more specific reason: keep the first one.
          if (message.code && (this.closeCode === 'engine_closed' || message.code !== 'engine_closed')) this.closeCode = message.code;
          this.pending.forEach(p => p.reject(new Error(this.closeCode)));
          this.pending.clear();
          this.listeners.forEach(l => l(false, this.closeCode));
          return;
        }
        const pending = this.pending.get(message.id);
        if (!pending) return;
        if (message.event === 'accepted' || message.event === 'progress') pending.progress?.(message);
        else {
          this.pending.delete(message.id);
          if (message.event === 'error') pending.reject(new Error(message.message || message.code));
          else pending.resolve(message);
        }
      };
      this.connecting = invoke<void>('desktop_connect', {onEvent: channel}).then(() => this.listeners.forEach(l => l(true, '')));
      this.connecting.catch(() => { this.connecting = undefined; });
    }
    return this.connecting;
  }
  request(method: string, params: object = {}, progress?: (v: Reply) => void) {
    const id = ++this.next;
    const promise = new Promise<Reply>((resolve, reject) => {
      if (this.disconnected) { reject(new Error(this.closeCode)); return; }
      this.pending.set(id, {resolve, reject, progress});
      // Serialize writes only; cancellation does not wait for analysis completion.
      this.sends = this.sends.catch(() => undefined).then(() =>
        invoke('desktop_send', {request: {version: 1, id, method, params}})
      ).catch(async error => {
        this.pending.delete(id);
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
export const defaults: Options = {metrics:['M01','M02','M03','M04','M05','M06','M08','M09','M10','M11'],valid_wafers:25,min_baseline:20,yield_drop:5,by_recipe:true};
export function errorText(error: unknown): string {
  const raw = error instanceof Error ? error.message : String(error);
  return ({desktop_required:'데스크톱 앱에서 열면 기존 호기 설정을 불러올 수 있습니다.',
    engine_not_packaged:'분석 엔진이 포함되지 않은 빌드입니다. 엔진 패키징 후 이용할 수 있습니다.',
    engine_closed:'분석 엔진 연결이 종료되었습니다. 상단의 [다시 연결]을 눌러 주세요.',
    already_running:'기존 Camtek AOI 프로그램(트레이 포함)이 켜져 있어 웹 엔진을 시작할 수 없습니다. 기존 프로그램을 종료한 뒤 상단의 [다시 연결]을 누르세요.',
    engine_busy_or_closed:'분석 엔진이 응답하지 않습니다. 상단의 [다시 연결]을 눌러 주세요.',
    engine_start_failed:'분석 엔진을 시작하지 못했습니다. 설치 폴더의 sidecar 폴더가 있는지 확인하세요.',
    access_denied:'파일이나 폴더에 접근할 권한이 없습니다. 다른 사람이 열어 두었거나 OneDrive 동기화 중인지 확인하세요.',
    file_missing:'필요한 파일을 찾지 못했습니다. 이동·삭제되었는지 확인하고 새로고침하세요.',
    io_failed:'파일을 읽거나 쓰지 못했습니다. 네트워크·OneDrive 연결과 저장 공간을 확인하세요.',
    engine_failed:'처리 중 예상하지 못한 오류가 났습니다. 설정 › 정보의 오류 로그 폴더를 담당자에게 전달하세요.',
    investigation_failed:'조사를 완료하지 못했습니다. 폴더 접근과 로컬 저장 공간을 확인해 주세요.',
    configuration_failed:'기존 설정을 불러오지 못했습니다. 설정 파일과 로컬 폴더를 확인해 주세요.'} as Record<string,string>)[raw] || raw;
}
