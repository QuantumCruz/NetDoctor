
import { defineConfig } from 'vite';

export default defineConfig({
  base: './',

  esbuild: {
    jsx: 'automatic',
    jsxImportSource: 'react',
  },

  server: {
    host: '127.0.0.1',
    port: 5173,
  },
});
