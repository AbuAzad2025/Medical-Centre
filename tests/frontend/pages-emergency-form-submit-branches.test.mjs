import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

const CASES = [
  ['static/js/pages/emergency/triage.js', 'triageForm'],
  ['static/js/pages/emergency/emergency_treatment.js', 'emergencyTreatmentForm'],
];

afterEach(() => {
  vi.useRealTimers();
});

for (const [modulePath, formId] of CASES) {
  describe(`${modulePath} submit branches`, () => {
    function baseDom(withCsrf = true) {
      document.body.innerHTML = `
        <form id="${formId}" action="/test">
          ${withCsrf ? '<input name="csrf_token" value="test-csrf">' : ''}
          <input name="blood_pressure" value="110/70">
          <button type="submit">Save</button>
        </form>
      `;
      window.__M = [];
      window.__M0__ = '/save';
      window.__M1__ = '/queue';
      window.escHtml = (s) => String(s ?? '');
      window.location = { href: '', reload: vi.fn() };
      window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
      global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
    }

    it('success navigates to __M1__', async () => {
      baseDom();
      await loadModule(modulePath);
      document.getElementById(formId).dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      await new Promise(r => setTimeout(r, 30));
      expect(window.location.href).toBe('/queue');
    });

    it('csrf token in form is sent as header', async () => {
      baseDom(true);
      await loadModule(modulePath);
      document.getElementById(formId).dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      await new Promise(r => setTimeout(r, 30));
      expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBe('test-csrf');
    });

    it('without csrf input the token header is omitted', async () => {
      baseDom(false);
      await loadModule(modulePath);
      document.getElementById(formId).dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      await new Promise(r => setTimeout(r, 30));
      expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBeUndefined();
    });

    it('non-ok response triggers the catch error path', async () => {
      baseDom();
      global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
      await loadModule(modulePath);
      document.getElementById(formId).dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      await new Promise(r => setTimeout(r, 30));
      expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
    });

    it('failure without an error field still shows the generic message', async () => {
      baseDom();
      global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
      await loadModule(modulePath);
      document.getElementById(formId).dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      await new Promise(r => setTimeout(r, 30));
      expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
      expect(window.Swal.fire.mock.calls[0][0].text).toContain(':');
    });

    it('module rejects when the form is missing', async () => {
      baseDom();
      document.getElementById(formId).remove();
      await expect(loadModule(modulePath)).rejects.toThrow();
    });
  });
}
