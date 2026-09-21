import { Channel, invoke, isTauri } from '@tauri-apps/api/core';
export type Metric = 'M01'|'M02'|'M03'|'M04'|'M05'|'M06'|'M08'|'M09'|'M10'|'M11';
export type Options = {metrics: Metric[]; valid_wafers: number; min_baseline: number; yield_drop: number; by_recipe: boolean};
export type Target = {machine: string; query: string; start: string; end: string};
export type Table = {index: number; key: string; title: string; headers: string[]; total: number};
export type Configuration = {machines: {id: string; folder: string}[]; local_root: string; last?: {targets?: Target[]; options?: Options}};
export type Reply = {version: number; id: number|null; event: string; code?: string; message?: string;
  job?: number; tables?: Table[]; summary?: Record<string, number>; rows?: (string|number|null)[][];
  artifacts?: Record<string,string>; collection?: {parsed: number; reused: number; errors: number; cached_only: number}; reports?: unknown;
  current?: number; total?: number; recipe?: unknown; document?: unknown; commonality?: unknown; form?: unknown; cmsurvey?: unknown; history?: unknown} & Partial<Configuration>;
type Pending = {resolve: (v: Reply) => void; reject: (e: Error) => void; progress?: (v: Reply) => void};
class DesktopClient {
  private next = 0;
  private pending = new Map<number, Pending>();
  private connecting?: Promise<void>;
  private sends: Promise<unknown> = Promise.resolve();
  private disconnected = false;
  connect() {
    if (!isTauri()) return Promise.reject(new Error('desktop_required'));
    if (!this.connecting) {
      const channel = new Channel<Reply>();
      channel.onmessage = message => {
        if (message.version !== 1) return;
        if (message.id === null) {
          this.disconnected = true;
          this.pending.forEach(p => p.reject(new Error(message.code || 'engine_closed')));
          this.pending.clear(); return;
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
      this.connecting = invoke<void>('desktop_connect', {onEvent: channel});
    }
    return this.connecting;
  }
  request(method: string, params: object = {}, progress?: (v: Reply) => void) {
    const id = ++this.next;
    const promise = new Promise<Reply>((resolve, reject) => {
      if (this.disconnected) { reject(new Error('engine_closed')); return; }
      this.pending.set(id, {resolve, reject, progress});
      // Serialize writes only; cancellation does not wait for analysis completion.
      this.sends = this.sends.catch(() => undefined).then(() =>
        invoke('desktop_send', {request: {version: 1, id, method, params}})
      ).catch(error => { this.pending.delete(id); reject(new Error(String(error))); });
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
    engine_closed:'분석 엔진 연결이 종료되었습니다. 앱을 다시 실행해 주세요.',
    already_running:'기존 Camtek AOI 프로그램이 실행 중입니다. 기존 창 또는 트레이에서 종료한 뒤 다시 실행해 주세요.',
    investigation_failed:'조사를 완료하지 못했습니다. 폴더 접근과 로컬 저장 공간을 확인해 주세요.',
    configuration_failed:'기존 설정을 불러오지 못했습니다. 설정 파일과 로컬 폴더를 확인해 주세요.'} as Record<string,string>)[raw] || raw;
}
