import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <meta name="csrf-token" content="meta-csrf">
    <form id="convertForm" action="/emergency/convert" method="post">
      <input type="hidden" name="csrf_token" value="form-csrf">
      <input name="patient_id" value="5">
    </form>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M = [];
  window.__M0__ = '/reception/visits';
  window.escHtml = (s) => String(s ?? '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.location = { href: '', reload: vi.fn() };
  window.print = vi.fn();
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
});

afterEach(() => {
  vi.useRealTimers();
});

async function submitForm() {
  document.dispatchEvent(new Event('DOMContentLoaded'));
  await new Promise(r => setTimeout(r, 20));
  document.getElementById('convertForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
  await new Promise(r => setTimeout(r, 40));
}

describe('emergency/view.js convertForm csrf arms', () => {
  it('form csrf input is preferred over meta', async () => {
    await loadModule('static/js/pages/emergency/view.js');
    await submitForm();
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBe('form-csrf');
  });

  it('meta csrf is used when the form has none', async () => {
    document.querySelector('#convertForm input[name="csrf_token"]').remove();
    await loadModule('static/js/pages/emergency/view.js');
    await submitForm();
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBe('meta-csrf');
  });

  it('no csrf elements anywhere sends no token header', async () => {
    document.querySelector('#convertForm input[name="csrf_token"]').remove();
    document.querySelector('meta[name="csrf-token"]').remove();
    await loadModule('static/js/pages/emergency/view.js');
    await submitForm();
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBeUndefined();
  });

  it('non-ok response triggers the catch error path', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    await loadModule('static/js/pages/emergency/view.js');
    await submitForm();
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });

  it('success navigates to __M0__', async () => {
    await loadModule('static/js/pages/emergency/view.js');
    await submitForm();
    expect(window.location.href).toBe('/reception/visits');
  });

  it('server failure with a custom message shows it', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'الحالة مغلقة' }) });
    await loadModule('static/js/pages/emergency/view.js');
    await submitForm();
    expect(window.Swal.fire.mock.calls[0][0].text).toBe('الحالة مغلقة');
  });

  it('null json body falls back to the generic error message', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(null) });
    await loadModule('static/js/pages/emergency/view.js');
    await submitForm();
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });
});
