import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = '<meta name="csrf-token" content="test-csrf">';
  window.__M = [];
  window.__M0__ = '/emergency/start/__VISIT_ID__';
  window.__M1__ = '/emergency/complete/__VISIT_ID__';
  window.escHtml = (s) => String(s ?? '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true, value: 'patient stable' }) };
  window.location = { href: '', reload: vi.fn() };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('emergency_visits.js startTreatment branches', () => {
  it('non-ok response triggers the catch error path', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/emergency/emergency_visits.js');
    mod.startTreatment('5');
    await new Promise(r => setTimeout(r, 40));
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('error');
  });

  it('success navigates to reload', async () => {
    const mod = await loadModule('static/js/pages/emergency/emergency_visits.js');
    mod.startTreatment('5');
    await new Promise(r => setTimeout(r, 60));
    expect(window.location.reload).toHaveBeenCalled();
  });

  it('failure with custom message shows it', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'patient discharged' }) });
    const mod = await loadModule('static/js/pages/emergency/emergency_visits.js');
    mod.startTreatment('5');
    await new Promise(r => setTimeout(r, 40));
    expect(window.Swal.fire.mock.calls[1][0].text).toBe('patient discharged');
  });

  it('failure without message shows the default text', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    const mod = await loadModule('static/js/pages/emergency/emergency_visits.js');
    mod.startTreatment('5');
    await new Promise(r => setTimeout(r, 40));
    expect(window.Swal.fire.mock.calls[1][0].text).toContain('خطأ');
  });

  it('without csrf meta sends no token header', async () => {
    document.querySelector('meta[name="csrf-token"]').remove();
    const mod = await loadModule('static/js/pages/emergency/emergency_visits.js');
    mod.startTreatment('5');
    await new Promise(r => setTimeout(r, 40));
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBeUndefined();
  });
});

describe('emergency_visits.js completeVisit branches', () => {
  it('non-ok response triggers the catch error path', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/emergency/emergency_visits.js');
    mod.completeVisit('5');
    await new Promise(r => setTimeout(r, 40));
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('error');
  });

  it('success navigates to reload', async () => {
    const mod = await loadModule('static/js/pages/emergency/emergency_visits.js');
    mod.completeVisit('5');
    await new Promise(r => setTimeout(r, 60));
    expect(window.location.reload).toHaveBeenCalled();
  });

  it('empty notes are sent as an empty string', async () => {
    window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true, value: undefined }) };
    const mod = await loadModule('static/js/pages/emergency/emergency_visits.js');
    mod.completeVisit('5');
    await new Promise(r => setTimeout(r, 40));
    expect(JSON.parse(global.fetch.mock.calls[0][1].body).notes).toBe('');
  });

  it('failure with custom message shows it', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'cannot complete' }) });
    const mod = await loadModule('static/js/pages/emergency/emergency_visits.js');
    mod.completeVisit('5');
    await new Promise(r => setTimeout(r, 40));
    expect(window.Swal.fire.mock.calls[1][0].text).toBe('cannot complete');
  });

  it('failure without message shows the default text', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    const mod = await loadModule('static/js/pages/emergency/emergency_visits.js');
    mod.completeVisit('5');
    await new Promise(r => setTimeout(r, 40));
    expect(window.Swal.fire.mock.calls[1][0].text).toContain('خطأ');
  });

  it('without csrf meta sends no token header', async () => {
    document.querySelector('meta[name="csrf-token"]').remove();
    const mod = await loadModule('static/js/pages/emergency/emergency_visits.js');
    mod.completeVisit('5');
    await new Promise(r => setTimeout(r, 40));
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBeUndefined();
  });
});
