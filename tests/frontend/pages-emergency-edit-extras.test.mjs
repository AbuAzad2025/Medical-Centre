import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

const FORM = `
  <form id="emergencyForm" action="/emergency/save">
    <input name="patient_id" value="5">
    <input name="doctor_id" value="2">
    <input name="emergency_date" value="2026-11-08">
    <input name="emergency_time" value="09:00">
    <input name="chief_complaint" value="ألم صدر">
  </form>
`;

function baseDom(withMeta = true, withForm = true) {
  document.body.innerHTML = `
    ${withMeta ? '<meta name="csrf-token" content="meta-csrf">' : ''}
    ${withForm ? FORM : ''}
  `;
}

beforeEach(() => {
  baseDom();
  window.__M = [];
  window.__M0__ = '/emergency/5/resolve';
  window.__M1__ = '/emergency/5/transfer';
  window.escHtml = (s) => String(s ?? '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true, value: 'reason' }) };
  window.location = { href: '', reload: vi.fn() };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('emergency/edit.js csrf branches', () => {
  it('resolve uses form csrf input when present', async () => {
    document.body.insertAdjacentHTML('beforeend', '<input type="hidden" name="csrf_token" value="form-csrf">');
    const mod = await loadModule('static/js/pages/emergency/edit.js');
    mod.resolveEmergency();
    await new Promise(r => setTimeout(r, 40));
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBe('form-csrf');
  });

  it('resolve uses meta csrf when the form has none', async () => {
    const mod = await loadModule('static/js/pages/emergency/edit.js');
    mod.resolveEmergency();
    await new Promise(r => setTimeout(r, 40));
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBe('meta-csrf');
  });

  it('resolve sends no token header without any csrf source', async () => {
    document.querySelector('meta[name="csrf-token"]').remove();
    const mod = await loadModule('static/js/pages/emergency/edit.js');
    mod.resolveEmergency();
    await new Promise(r => setTimeout(r, 40));
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBeUndefined();
  });

  it('transfer uses form csrf input when present', async () => {
    document.body.insertAdjacentHTML('beforeend', '<input type="hidden" name="csrf_token" value="form-csrf">');
    const mod = await loadModule('static/js/pages/emergency/edit.js');
    mod.transferEmergency();
    await new Promise(r => setTimeout(r, 40));
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBe('form-csrf');
  });

  it('transfer sends no token header without any csrf source', async () => {
    document.querySelector('meta[name="csrf-token"]').remove();
    const mod = await loadModule('static/js/pages/emergency/edit.js');
    mod.transferEmergency();
    await new Promise(r => setTimeout(r, 40));
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBeUndefined();
  });
});

describe('emergency/edit.js failure fallback branches', () => {
  it('resolve failure without message shows the default text', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    const mod = await loadModule('static/js/pages/emergency/edit.js');
    mod.resolveEmergency();
    await new Promise(r => setTimeout(r, 40));
    expect(window.Swal.fire.mock.calls[1][0].text).toBe('حدث خطأ في الحل');
  });

  it('transfer failure without message shows the default text', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    const mod = await loadModule('static/js/pages/emergency/edit.js');
    mod.transferEmergency();
    await new Promise(r => setTimeout(r, 40));
    expect(window.Swal.fire.mock.calls[1][0].text).toBe('حدث خطأ في النقل');
  });
});

describe('emergency/edit.js transfer notes branches', () => {
  it('transfer with empty value sends empty transfer_notes', async () => {
    window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true, value: undefined }) };
    const mod = await loadModule('static/js/pages/emergency/edit.js');
    mod.transferEmergency();
    await new Promise(r => setTimeout(r, 40));
    expect(JSON.parse(global.fetch.mock.calls[0][1].body).transfer_notes).toBe('');
  });

  it('transfer with notes sends them through', async () => {
    const mod = await loadModule('static/js/pages/emergency/edit.js');
    mod.transferEmergency();
    await new Promise(r => setTimeout(r, 40));
    expect(JSON.parse(global.fetch.mock.calls[0][1].body).transfer_notes).toBe('reason');
  });
});

describe('emergency/edit.js form missing branch', () => {
  it('module loads cleanly without #emergencyForm', async () => {
    baseDom(true, false);
    await expect(loadModule('static/js/pages/emergency/edit.js')).resolves.toBeDefined();
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(window.resolveEmergency).toBeDefined();
  });
});
