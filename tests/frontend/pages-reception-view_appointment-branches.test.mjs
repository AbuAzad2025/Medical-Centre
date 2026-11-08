import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = '<meta name="csrf-token" content="meta-csrf">';
}

beforeEach(() => {
  baseDom();
  window.__M = [];
  window.escHtml = (s) => String(s ?? '');
  window.API_ROUTES = {};
  window.location = { href: '', reload: vi.fn() };
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('view_appointment.js csrf branches', () => {
  it('prefers a form csrf input over the meta', async () => {
    document.body.insertAdjacentHTML('beforeend', '<input type="hidden" name="csrf_token" value="form-csrf">');
    const mod = await loadModule('static/js/pages/reception/view_appointment.js');
    expect(mod.getCsrfToken()).toBe('form-csrf');
  });

  it('falls back to meta csrf', async () => {
    const mod = await loadModule('static/js/pages/reception/view_appointment.js');
    expect(mod.getCsrfToken()).toBe('meta-csrf');
  });

  it('returns empty string without any token source', async () => {
    document.querySelector('meta[name="csrf-token"]').remove();
    const mod = await loadModule('static/js/pages/reception/view_appointment.js');
    expect(mod.getCsrfToken()).toBe('');
  });
});

const CASES = [
  ['confirmAppointment', 'reception_confirm_appointment', '/reception/view_confirm_test'],
  ['cancelAppointment', 'reception_cancel_appointment', '/reception/view_cancel_test'],
  ['noShowAppointment', 'reception_no_show_appointment', '/reception/view_noshow_test'],
];

for (const [fn, routeKey, customUrl] of CASES) {
  describe(`view_appointment.js ${fn} branches`, () => {
    it('success reloads the page', async () => {
      const mod = await loadModule('static/js/pages/reception/view_appointment.js');
      mod[fn]('11');
      await new Promise(r => setTimeout(r, 40));
      expect(window.location.reload).toHaveBeenCalled();
    });

    it('cancelled confirmation does not fetch', async () => {
      window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
      const mod = await loadModule('static/js/pages/reception/view_appointment.js');
      mod[fn]('11');
      await new Promise(r => setTimeout(r, 40));
      expect(global.fetch).not.toHaveBeenCalled();
    });

    it('server failure with message shows it', async () => {
      global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'حدث تكرار' }) });
      const mod = await loadModule('static/js/pages/reception/view_appointment.js');
      mod[fn]('11');
      await new Promise(r => setTimeout(r, 40));
      expect(window.Swal.fire.mock.calls[1][0].text).toBe('حدث تكرار');
    });

    it('server failure without message uses the default error', async () => {
      global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
      const mod = await loadModule('static/js/pages/reception/view_appointment.js');
      mod[fn]('11');
      await new Promise(r => setTimeout(r, 40));
      expect(window.Swal.fire.mock.calls[1][0].text).toContain('حدث خطأ');
    });

    it('non-ok response throws into the default error path', async () => {
      global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500, json: () => Promise.resolve({}) });
      const mod = await loadModule('static/js/pages/reception/view_appointment.js');
      mod[fn]('11');
      await new Promise(r => setTimeout(r, 40));
      expect(window.Swal.fire.mock.calls[1][0].text).toContain('حدث خطأ');
    });

    it('network failure with empty error uses the default error text', async () => {
      global.fetch = vi.fn().mockRejectedValue({});
      const mod = await loadModule('static/js/pages/reception/view_appointment.js');
      mod[fn]('11');
      await new Promise(r => setTimeout(r, 40));
      expect(window.Swal.fire.mock.calls[1][0].text).toContain('حدث خطأ');
    });

    it('sends no csrf header when no token source exists', async () => {
      document.querySelector('meta[name="csrf-token"]').remove();
      const mod = await loadModule('static/js/pages/reception/view_appointment.js');
      mod[fn]('11');
      await new Promise(r => setTimeout(r, 40));
      expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBeUndefined();
    });

    it('uses API_ROUTES endpoint when set', async () => {
      window.API_ROUTES = { [routeKey]: customUrl };
      const mod = await loadModule('static/js/pages/reception/view_appointment.js');
      mod[fn]('11');
      await new Promise(r => setTimeout(r, 40));
      expect(global.fetch.mock.calls[0][0]).toBe(customUrl);
    });

    it('falls back to the default route when API_ROUTES is unset', async () => {
      const mod = await loadModule('static/js/pages/reception/view_appointment.js');
      mod[fn]('11');
      await new Promise(r => setTimeout(r, 40));
      expect(global.fetch.mock.calls[0][0]).toContain('/reception/');
      expect(global.fetch.mock.calls[0][0]).toContain('/11');
    });
  });
}
