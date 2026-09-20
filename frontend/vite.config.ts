import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
// Static bundles only: project policy prohibits local HTTP/TCP dev servers.
export default defineConfig({plugins:[react()],clearScreen:false,build:{target:'es2022'}});
