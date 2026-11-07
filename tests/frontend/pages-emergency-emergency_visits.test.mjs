import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function setup() {
  window.__M = [];
  window.API_ROUTES = {};
  window.__M0__ = '/api/emergency/start/__VISIT_ID__';
  window.__M1__ = '/api/emergency/complete/__VISIT_ID__';
  window.Swal = {
    fire: vi.fn().mockResolvedValue({ isConfirmed: true, value: 'notes here' }),
    showLoading: vi.fn(),
  };
  window.bootstrap = {
    Collapse: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn() })) },
    Modal: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn(), hide: vi.fn() })) },
  };
  window.Chart = vi.fn().mockImplementation(() => ({}));
  if (window.Chart) window.Chart.defaults = { plugins: { tooltip: {}, legend: { labels: { font: {} } } }, font: {} };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
}

beforeEach(async () => {
  document.body.innerHTML = '<meta name="csrf-token" content="test-csrf">';
  setup();
  await loadModule('static/js/pages/emergency/emergency_visits.js');
});

afterEach(() => {
  vi.useRealTimers();
});

describe('emergency_visits.js', () => {
  it('startTreatment calls SWAL then fetch', async () => {
    const mod = await loadModule('static/js/pages/emergency/emergency_visits.js');
    mod.startTreatment('42');
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire).toHaveBeenCalled();
    expect(global.fetch).toHaveBeenCalled();
  });

  it('startTreatment success triggers success Swal', async () => {
    const mod = await loadModule('static/js/pages/emergency/emergency_visits.js');
    mod.startTreatment('42');
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire).toHaveBeenCalledTimes(2);
  });

  it('startTreatment failure shows error Swal', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'bad' }) });
    const mod = await loadModule('static/js/pages/emergency/emergency_visits.js');
    mod.startTreatment('42');
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire).toHaveBeenCalledTimes(2);
  });

  it('startTreatment fetch throws shows error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/emergency/emergency_visits.js');
    mod.startTreatment('42');
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire).toHaveBeenCalledTimes(2);
  });

  it('startTreatment cancel does not fetch', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/emergency/emergency_visits.js');
    mod.startTreatment('42');
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('completeVisit sends notes', async () => {
    const mod = await loadModule('static/js/pages/emergency/emergency_visits.js');
    mod.completeVisit('42');
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
    const [, opts] = global.fetch.mock.calls[0];
    expect(opts.body).toContain('notes here');
  });

  it('completeVisit success triggers success Swal', async () => {
    const mod = await loadModule('static/js/pages/emergency/emergency_visits.js');
    mod.completeVisit('42');
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire).toHaveBeenCalledTimes(2);
  });

  it('completeVisit failure shows error Swal', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'err' }) });
    const mod = await loadModule('static/js/pages/emergency/emergency_visits.js');
    mod.completeVisit('42');
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire).toHaveBeenCalledTimes(2);
  });

  it('completeVisit fetch throws shows error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/emergency/emergency_visits.js');
    mod.completeVisit('42');
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire).toHaveBeenCalledTimes(2);
  });

  it('completeVisit cancel does not fetch', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/emergency/emergency_visits.js');
    mod.completeVisit('42');
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).not.toHaveBeenCalled();
  });
});