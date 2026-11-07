import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function setup() {
  document.body.innerHTML = '<meta name="csrf-token" content="meta-csrf"><input name="csrf_token" value="input-csrf">';
  window.__M = [];
  window.escHtml = (s) => s;
  window.API_ROUTES = {
    reception_confirm_appointment: '/reception/appointments/0/confirm',
    reception_cancel_appointment: '/reception/appointments/0/cancel',
    reception_no_show_appointment: '/reception/appointments/0/no-show',
  };
  window.Swal = {
    fire: vi.fn().mockResolvedValue({ isConfirmed: true }),
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
  setup();
  await loadModule('static/js/pages/reception/view_appointment.js');
});

afterEach(() => {
  vi.useRealTimers();
});

describe('view_appointment.js', () => {
  it('getCsrfToken prefers input value', async () => {
    const { getCsrfToken } = await loadModule('static/js/pages/reception/view_appointment.js');
    expect(getCsrfToken()).toBe('input-csrf');
  });

  it('confirmAppointment posts on confirm', async () => {
    const mod = await loadModule('static/js/pages/reception/view_appointment.js');
    mod.confirmAppointment('42');
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
    expect(global.fetch.mock.calls[0][0]).toContain('/reception/appointments/42/confirm');
  });

  it('confirmAppointment error shows Swal error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'bad' }) });
    const mod = await loadModule('static/js/pages/reception/view_appointment.js');
    mod.confirmAppointment('42');
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire).toHaveBeenCalledTimes(2);
  });

  it('confirmAppointment cancel does not fetch', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/reception/view_appointment.js');
    mod.confirmAppointment('42');
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('cancelAppointment posts on confirm', async () => {
    const mod = await loadModule('static/js/pages/reception/view_appointment.js');
    mod.cancelAppointment('42');
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
    expect(global.fetch.mock.calls[0][0]).toContain('/reception/appointments/42/cancel');
  });

  it('cancelAppointment error shows Swal error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/reception/view_appointment.js');
    mod.cancelAppointment('42');
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire).toHaveBeenCalledTimes(2);
  });

  it('noShowAppointment posts on confirm', async () => {
    const mod = await loadModule('static/js/pages/reception/view_appointment.js');
    mod.noShowAppointment('42');
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
    expect(global.fetch.mock.calls[0][0]).toContain('/reception/appointments/42/no-show');
  });

  it('noShowAppointment error shows Swal error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'bad' }) });
    const mod = await loadModule('static/js/pages/reception/view_appointment.js');
    mod.noShowAppointment('42');
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire).toHaveBeenCalledTimes(2);
  });
});