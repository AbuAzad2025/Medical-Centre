import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function setup() {
  document.body.innerHTML = `
    <form id="triageForm" action="/test">
      <input name="csrf_token" value="test-csrf">
      <input name="blood_pressure" value="110/70">
      <input name="heart_rate" value="80">
      <input name="temperature" value="37.0">
      <input name="oxygen_saturation" value="98">
      <input name="respiratory_rate" value="18">
      <input name="pain_level" value="2">
      <button type="submit">Save</button>
    </form>
  `;
  window.__M = [];
  window.API_ROUTES = {};
  window.__M0__ = '/triage/save';
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
  await loadModule('static/js/pages/emergency/triage.js');
});

afterEach(() => {
  vi.useRealTimers();
});

describe('emergency/triage.js', () => {
  it('submit posts vital signs form', async () => {
    const form = document.getElementById('triageForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
    const [, opts] = global.fetch.mock.calls[0];
    expect(opts.body.get('vital_signs')).toContain('blood_pressure');
  });

  it('submit success shows Swal success', async () => {
    document.getElementById('triageForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire).toHaveBeenCalled();
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('success');
  });

  it('submit failure shows Swal error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, error: 'bad' }) });
    document.getElementById('triageForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });

  it('submit fetch failure shows Swal error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    document.getElementById('triageForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });
});