import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <meta name="csrf-token" content="test-csrf">
    <form id="emergencyForm">
      <input name="patient_id" value="1">
      <input name="doctor_id" value="2">
      <input name="emergency_date" type="date" value="2026-11-08">
      <input name="emergency_time" type="time" value="14:00">
      <input name="chief_complaint" value="headache">
      <input name="notes" value="initial">
      <button type="submit">Save</button>
    </form>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M0__ = '/api/emergency/resolve/7';
  window.__M1__ = '/api/emergency/transfer/7';
  window.escHtml = (s) => String(s || '');
  window.API_ROUTES = {};
  window.Swal = {
    fire: vi.fn().mockResolvedValue({ isConfirmed: true, value: 'movement notes' }),
  };
  window.bootstrap = { Collapse: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn() })) }, Modal: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn(), hide: vi.fn() })) } };
  window.location = { href: '', reload: vi.fn() };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('emergency/edit.js comprehensive', () => {
  it('resolveEmergency confirms, posts and reloads', async () => {
    const mod = await loadModule('static/js/pages/emergency/edit.js');
    mod.resolveEmergency();
    await new Promise(r => setTimeout(r, 30));
    expect(String(global.fetch.mock.calls[0][0])).toBe('/api/emergency/resolve/7');
    expect(global.fetch.mock.calls[0][1].method).toBe('POST');
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('resolveEmergency with server failure shows error Swal', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'already resolved' }) });
    const mod = await loadModule('static/js/pages/emergency/edit.js');
    mod.resolveEmergency();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('error');
  });

  it('resolveEmergency non-ok http status shows error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/emergency/edit.js');
    mod.resolveEmergency();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('error');
  });

  it('resolveEmergency network failure shows error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/emergency/edit.js');
    mod.resolveEmergency();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('error');
  });

  it('resolveEmergency cancel does not fetch', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/emergency/edit.js');
    mod.resolveEmergency();
    await new Promise(r => setTimeout(r, 20));
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('transferEmergency confirms, posts notes and reloads', async () => {
    const mod = await loadModule('static/js/pages/emergency/edit.js');
    mod.transferEmergency();
    await new Promise(r => setTimeout(r, 30));
    expect(String(global.fetch.mock.calls[0][0])).toBe('/api/emergency/transfer/7');
    expect(JSON.parse(global.fetch.mock.calls[0][1].body).transfer_notes).toBe('movement notes');
  });

  it('transferEmergency with failure shows error Swal', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'no beds' }) });
    const mod = await loadModule('static/js/pages/emergency/edit.js');
    mod.transferEmergency();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('error');
  });

  it('transferEmergency non-ok status shows error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/emergency/edit.js');
    mod.transferEmergency();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('error');
  });

  it('transferEmergency network failure shows error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/emergency/edit.js');
    mod.transferEmergency();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('error');
  });

  it('transferEmergency cancel does not fetch', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/emergency/edit.js');
    mod.transferEmergency();
    await new Promise(r => setTimeout(r, 20));
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('exposes functions on window for inline handlers', async () => {
    await loadModule('static/js/pages/emergency/edit.js');
    expect(typeof window.resolveEmergency).toBe('function');
    expect(typeof window.transferEmergency).toBe('function');
  });

  it('submit without changes blocks and shows info', async () => {
    await loadModule('static/js/pages/emergency/edit.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const form = document.getElementById('emergencyForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('info');
  });

  it('submit with invalid required field blocks and shows warning', async () => {
    await loadModule('static/js/pages/emergency/edit.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    document.querySelector('[name="chief_complaint"]').value = '';
    const form = document.getElementById('emergencyForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('warning');
    expect(document.querySelector('[name="chief_complaint"]').classList.contains('is-invalid')).toBe(true);
  });

  it('submit with changes does not block', async () => {
    await loadModule('static/js/pages/emergency/edit.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    document.querySelector('[name="chief_complaint"]').value = 'updated';
    const form = document.getElementById('emergencyForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    expect(window.Swal.fire).not.toHaveBeenCalled();
  });
});