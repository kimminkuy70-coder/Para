/** Cross-screen navigation (e.g. Commonality → 설정 › Scanresult 루트 with the machine filled in). */
export type SettingsIntent = {sub: string; machine?: string};
let pending: SettingsIntent | undefined;
export function goToSettings(intent: SettingsIntent) {
  pending = intent;
  window.dispatchEvent(new CustomEvent('para:navigate', {detail: '설정'}));
}
/** Read once by the settings screen when it opens. */
export function takeSettingsIntent(): SettingsIntent | undefined {
  const out = pending; pending = undefined; return out;
}
