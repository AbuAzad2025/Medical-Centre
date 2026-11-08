import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';
import { isolateDomContentLoaded } from './dom-isolation.mjs';

const iso = isolateDomContentLoaded();

function baseDom() {
  document.body.innerHTML = `
    <div class="command-center" data-widget-id="queue_live"><span data-metric-value>0</span></div>
  `;
}

beforeEach(() => {
  iso.install();
  baseDom();
  window.__M = [];
  window.API_ROUTES = { dashboard_snapshot: '/api/snapshot' };
  window.console.warn = vi.fn();
  window.escHtml = (s) => String(s ?? '');
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ metrics: { queue_count: 9 } }) });
});

afterEach(() => {
  iso.cleanup();
  vi.useRealTimers();
});

describe('dashboard-live.js edge arms', () => {
  it('poll without metrics in the response does not write widgets', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
    const mod = await loadModule('static/js/dashboard-live.js');
    mod.poll();
    await new Promise(r => setTimeout(r, 30));
    expect(document.querySelector('[data-metric-value]').textContent).toBe('0');
  });

  it('applyMetrics skips widgets whose metric is missing from the payload', async () => {
    const mod = await loadModule('static/js/dashboard-live.js');
    mod.applyMetrics({ /* nothing */ });
    expect(document.querySelector('[data-metric-value]').textContent).toBe('0');
  });

  it('applyMetrics skips a widget with no metric-value element', async () => {
    document.body.innerHTML = '<div class="command-center" data-widget-id="queue_live"></div>';
    const mod = await loadModule('static/js/dashboard-live.js');
    expect(() => mod.applyMetrics({ queue_count: 77 })).not.toThrow();
    expect(document.querySelector('[data-widget-id="queue_live"]')).not.toBeNull();
  });

  it('polling falls back to the default endpoint when API_ROUTES is unset', async () => {
    delete window.API_ROUTES;
    const mod = await loadModule('static/js/dashboard-live.js');
    mod.poll();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch.mock.calls[0][0]).toBe('/api/dashboard/snapshot');
  });

  it('DOMContentLoaded starts polling and visibilitychange toggles it', async () => {
    vi.useFakeTimers();
    await loadModule('static/js/dashboard-live.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(global.fetch).toHaveBeenCalled(); // initial poll
    Object.defineProperty(document, 'hidden', { value: true, configurable: true });
    document.dispatchEvent(new Event('visibilitychange'));
    global.fetch.mockClear();
    await vi.advanceTimersByTimeAsync(21000);
    expect(global.fetch).not.toHaveBeenCalled(); // stopped
    Object.defineProperty(document, 'hidden', { value: false, configurable: true });
    document.dispatchEvent(new Event('visibilitychange'));
    await vi.advanceTimersByTimeAsync(10);
    expect(global.fetch).toHaveBeenCalled(); // resumed
    vi.useRealTimers();
  });
});
