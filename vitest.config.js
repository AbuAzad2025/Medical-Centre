import { defineConfig } from 'vitest/config';
import path from 'path';

export default defineConfig({
  resolve: {
    alias: {
      '@src': path.resolve(__dirname, 'static/js'),
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./tests/frontend/setup.js'],
    include: ['tests/frontend/**/*.test.js', 'tests/frontend/**/*.test.mjs'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      include: ['static/js/**/*.js'],
      exclude: ['static/js/**/*.test.*', 'static/js/**/*.min.js'],
    },
    testTimeout: 10000,
    pool: 'forks',
    server: {
      deps: {
        inline: [/static\/js/],
      },
    },
  },
});
