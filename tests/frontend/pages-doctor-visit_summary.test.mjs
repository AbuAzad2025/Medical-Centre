import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function setup() {
  document.body.innerHTML = `
    <form id="visitSummaryForm" action="/test">
      <input name="csrf_token" value="test-csrf">
      <textarea name="summary">summary</textarea>
      <button type="submit">Save</button>
    </form>
  `;
  window.__M = [];
  window.API_ROUTES = {};
  window.__M0__ = '/visit/summary/save';
  window.__M1__ = '/visit/detail';
  window.escHtml = (s) => s;
  window.notify = { success: vi.fn(), error: vi.fn() };
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.bootstrap = {
    Collapse: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn() })) },
    Modal: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn(), hide: vi.fn() })) },
  };
  window.Chart = vi.fn().mockImplementation(() => ({}));
  if (window.Chart) window.Chart.defaults = { plugins: { tooltip: {}, legend: { labels: { font: {} } } }, font: {} };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
}

beforeEach(async () => {
  setup();
  await loadModule('static/js/pages/doctor/visit_summary.js');
});

afterEach(() => {
  vi.useRealTimers();
});

describe('visit_summary.js', () => {
  it('submit posts to save endpoint', async () => {
    document.getElementById('visitSummaryForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
    expect(global.fetch.mock.calls[0][0]).toContain('/visit/summary/save');
  });

  it('submit success notifies success', async () => {
    document.getElementById('visitSummaryForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(window.notify.success).toHaveBeenCalled();
  });

  it('submit failure shows notify error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'bad' }) });
    document.getElementById('visitSummaryForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(window.notify.error).toHaveBeenCalled();
  });

  it('submit fetch failure shows notify error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    document.getElementById('visitSummaryForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(window.notify.error).toHaveBeenCalled();
  });
});