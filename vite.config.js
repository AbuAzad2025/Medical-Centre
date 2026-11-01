import { defineConfig } from 'vite';
import { resolve } from 'path';
import { readdirSync } from 'fs';

// Auto-discover all JS/TS entry points
const jsDir = resolve(__dirname, 'static/js');
const entries = {};
readdirSync(jsDir).forEach((file) => {
  if (file.endsWith('.js') || file.endsWith('.ts')) {
    const name = file.replace(/\.(js|ts)$/, '');
    entries[name] = resolve(jsDir, file);
  }
});

export default defineConfig({
  root: '.',
  base: '/static/',
  build: {
    outDir: 'static/dist',
    emptyOutDir: true,
    rollupOptions: {
      input: entries,
      output: {
        entryFileNames: 'js/[name]-[hash].js',
        chunkFileNames: 'js/[name]-[hash].js',
        assetFileNames: (assetInfo) => {
          if (assetInfo.name.endsWith('.css')) {
            return 'css/[name]-[hash][extname]';
          }
          return 'assets/[name]-[hash][extname]';
        },
      },
    },
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: true,
        drop_debugger: true,
      },
    },
    sourcemap: true,
    cssCodeSplit: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/auth': 'http://localhost:8000',
    },
  },
});