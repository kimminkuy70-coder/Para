import { defineConfig, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';
import { readFileSync } from 'node:fs';

/** Defect 분석 HTML(rev6) · para-skin.js 의 스크립트를 함수로 감싼 .js(dist/defect/*.run.js) — 프로그램 화면 안(DefectHost.ts)에서 돌린다.
 *  화면의 보안 정책(CSP script-src 'self' — 문자열 실행 금지)을 그대로 두려고 빌드 때 파일로 만든다. HTML 을 고치면 빌드가 다시 만든다.
 *  인자 이름 = DefectHost.ts RUN_PARAMS(같아야 함 — tests/test_defect_host.py). */
export const RUN_PARAMS = 'document,window,location,localStorage,addEventListener,removeEventListener,self,globalThis,scrollTo,paraHost';
export function wrapRun(name: string, src: string) {
  return `/* 자동 생성(frontend/vite.config.ts defectRun) — 원본 = frontend/public/defect/${name}. 이 파일은 고치지 말 것 */\n`
    + `(window.__dfxRun=window.__dfxRun||{})[${JSON.stringify(name)}]=function(${RUN_PARAMS}){\n${src}\n};\n`;
}
function defectRun(): Plugin {
  return {
    name: 'para-defect-run', apply: 'build',
    generateBundle() {
      const html = readFileSync('public/defect/AOI_Contrast_Wizard_rev6.html', 'utf8');
      const script = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]).join('\n;\n');
      if (!script.trim()) throw new Error('AOI_Contrast_Wizard_rev6.html 에 <script> 가 없음');
      this.emitFile({type: 'asset', fileName: 'defect/AOI_Contrast_Wizard_rev6.run.js', source: wrapRun('AOI_Contrast_Wizard_rev6.html', script)});
      this.emitFile({type: 'asset', fileName: 'defect/para-skin.run.js', source: wrapRun('para-skin.js', readFileSync('public/defect/para-skin.js', 'utf8'))});
    },
  };
}
// Static bundles only: project policy prohibits local HTTP/TCP dev servers.
export default defineConfig({plugins:[react(), defectRun()],clearScreen:false,build:{target:'es2022'}});
