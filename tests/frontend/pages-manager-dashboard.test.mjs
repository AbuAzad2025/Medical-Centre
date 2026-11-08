import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <meta name="csrf-token" content="csrf-mgr">
    <input id="what_if_staff" type="number" value="3">
    <input id="what_if_rooms" type="number" value="2">
    <button id="runWhatIf">Run</button>
    <div id="whatIfThroughput">-</div>
    <div id="whatIfWait">-</div>
    <div id="whatIfRevenue">-</div>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M0__ = '/manager/api/what-if';
  window.__M = [];
  window.escHtml = (s) => String(s || '');
  window.API_ROUTES = {};
  window.alert = vi.fn();
  window.showToast = vi.fn();
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ predicted_throughput: 120, predicted_wait_minutes: 25, predicted_revenue: 9500 }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('manager/dashboard.js', () => {
  it('run click posts staff/rooms to the endpoint', async () => {
    await loadModule('static/js/pages/manager/dashboard.js');
    document.getElementById('runWhatIf').click();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalledWith('/manager/api/what-if', expect.objectContaining({ method: 'POST' }));
    const body = JSON.parse(global.fetch.mock.calls[0][1].body);
    expect(body.add_staff).toBe(3);
    expect(body.add_rooms).toBe(2);
  });

  it('success response updates the three prediction fields', async () => {
    await loadModule('static/js/pages/manager/dashboard.js');
    document.getElementById('runWhatIf').click();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('whatIfThroughput').textContent).toBe('120');
    expect(document.getElementById('whatIfWait').textContent).toContain('25');
    expect(document.getElementById('whatIfRevenue').textContent).toBe('9500');
  });

  it('missing prediction fields fall back to dash', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
    await loadModule('static/js/pages/manager/dashboard.js');
    document.getElementById('runWhatIf').click();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('whatIfThroughput').textContent).toBe('-');
    expect(document.getElementById('whatIfWait').textContent).toContain('-');
    expect(document.getElementById('whatIfRevenue').textContent).toBe('-');
  });

  it('non-ok status shows toast', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    await loadModule('static/js/pages/manager/dashboard.js');
    document.getElementById('runWhatIf').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.showToast).toHaveBeenCalled();
  });

  it('fetch rejection shows toast', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    await loadModule('static/js/pages/manager/dashboard.js');
    document.getElementById('runWhatIf').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.showToast).toHaveBeenCalled();
  });

  it('fetch rejection without showToast falls back to alert', async () => {
    delete window.showToast;
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    await loadModule('static/js/pages/manager/dashboard.js');
    document.getElementById('runWhatIf').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.alert).toHaveBeenCalled();
  });

  it('empty inputs default to zero', async () => {
    document.getElementById('what_if_staff').value = '';
    document.getElementById('what_if_rooms').value = '';
    await loadModule('static/js/pages/manager/dashboard.js');
    document.getElementById('runWhatIf').click();
    await new Promise(r => setTimeout(r, 30));
    const body = JSON.parse(global.fetch.mock.calls[0][1].body);
    expect(body.add_staff).toBe(0);
    expect(body.add_rooms).toBe(0);
  });

  it('missing runWhatIf button does not throw', async () => {
    document.getElementById('runWhatIf').remove();
    await loadModule('static/js/pages/manager/dashboard.js');
    expect(true).toBe(true);
  });
});