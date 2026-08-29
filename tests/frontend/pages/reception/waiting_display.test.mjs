import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <div id="app"></div>
    <span id="live-clock"></span>
    <div id="current-list"></div>
    <div id="called-list"></div>
    <div id="waiting-list"></div>
  `;
  window.__M0__ = '/api/test/waiting';
  window.io = vi.fn(() => ({ on: vi.fn() }));
  window.escHtml = (s) => String(s || '');
  window.__MOTION_ENABLED__ = () => false;
});

describe('reception/waiting_display.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/reception/waiting_display.js');
  });
});
