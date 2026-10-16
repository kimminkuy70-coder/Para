import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
// Wafer Map 전용판(특수 버전) 화면: wafermap/index.html → src/wafermap_main.tsx 만 묶는다.
// 본 앱 화면(main.tsx 와 다른 기능 화면)은 이 번들에 들어가지 않는다(tests/test_wafermap_edition.py).
// Static bundles only: project policy prohibits local HTTP/TCP dev servers.
export default defineConfig({plugins:[react()],clearScreen:false,root:'wafermap',
  build:{target:'es2022',outDir:'../dist-wafermap',emptyOutDir:true}});
