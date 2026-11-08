import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <meta name="csrf-token" content="test-csrf">
    <input id="what_if_staff" value="2">
    <input id="what_if_rooms" value="1">
    <button id="runWhatIf">Run</button>
    <span id="whatIfThroughput">-</span>
    <span id="whatIfWait">-</span>
    <span id="whatIfRevenue">-</span>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M = ['preset'];
  window.__M0__ = '/api/what-if';
  window.escHtml = (s) => String(s ?? '');
  window.showToast = vi.fn();
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ predicted_throughput: 100, predicted_wait_minutes: 10, predicted_revenue: 500 }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('manager/dashboard.js fallback arms', () => {
  it('save without csrf meta sends no token header', async () => {
    document.querySelector('meta[name="csrf-token"]').remove();
    await loadModule('static/js/pages/manager/dashboard.js');
    document.getElementById('runWhatIf').click();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBeUndefined();
  });

  it('json parse failure shows dashes and does not crash', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.reject(new Error('bad json')) });
    await loadModule('static/js/pages/manager/dashboard.js');
    document.getElementById('runWhatIf').click();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('whatIfThroughput').textContent).toBe('-');
    expect(document.getElementById('whatIfRevenue').textContent).toBe('-');
  });

  it('module loads with no __M preset as well', async () => {
    delete window.__M;
    await expect(loadModule('static/js/pages/manager/dashboard.js')).resolves.toBeDefined();
  });
});
