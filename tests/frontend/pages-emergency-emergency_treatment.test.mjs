import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function setup() {
  document.body.innerHTML = `
    <form id="emergencyTreatmentForm" action="/test">
      <input name="csrf_token" value="test-csrf">
      <textarea name="notes">treatment notes</textarea>
      <button type="submit">Save</button>
    </form>
  `;
  window.__M = [];
  window.API_ROUTES = {};
  window.__M0__ = '/emergency/treatment';
  window.__M1__ = '/emergency/queue';
  window.escHtml = (s) => s;
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
  await loadModule('static/js/pages/emergency/emergency_treatment.js');
});

afterEach(() => {
  vi.useRealTimers();
});

describe('emergency_treatment.js', () => {
  it('submit posts to treatment endpoint', async () => {
    document.getElementById('emergencyTreatmentForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
    expect(global.fetch.mock.calls[0][0]).toContain('/emergency/treatment');
  });

  it('submit success shows success Swal', async () => {
    document.getElementById('emergencyTreatmentForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('success');
  });

  it('submit failure shows error Swal', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, error: 'bad' }) });
    document.getElementById('emergencyTreatmentForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });

  it('submit fetch failure shows error Swal', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    document.getElementById('emergencyTreatmentForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });
});