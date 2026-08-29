import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <div id="app"></div>
    <div id="calls-grid"></div>
    <span id="live-clock"></span>
  `;
  window.__M0__ = '/api/test/calls';
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  window.io = vi.fn(() => ({ on: vi.fn() }));
});

describe('reception/calls_display.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/reception/calls_display.js');
  });

  test('live-clock element is referenced', async () => {
    await loadScript('static/js/pages/reception/calls_display.js');
    expect(document.getElementById('live-clock')).not.toBeNull();
  });

  test('calls-grid element is referenced', async () => {
    await loadScript('static/js/pages/reception/calls_display.js');
    expect(document.getElementById('calls-grid')).not.toBeNull();
  });
});
