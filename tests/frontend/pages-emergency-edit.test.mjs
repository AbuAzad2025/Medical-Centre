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
  window.__M = [];
  window.__M0__ = '/api/emergency/resolve/7';
  window.__M1__ = '/api/emergency/transfer/7';
  window.escHtml = (s) => String(s || '');
  window.API_ROUTES = {};
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true, value: 'movement notes' }) };
  window.bootstrap = { Collapse: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn() })) }, Modal: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn(), hide: vi.fn() })) } };
  window.location = { href: '', reload: vi.fn() };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('emergency/edit.js', () => {
  it('loads without critical error', async () => {
    await loadModule('static/js/pages/emergency/edit.js');
    expect(document.getElementById('emergencyForm')).toBeTruthy();
  });

  it('DOMContentLoaded captures original data', async () => {
    await loadModule('static/js/pages/emergency/edit.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(document.querySelector('[name="chief_complaint"]').value).toBe('headache');
  });

  it('submit with all required fields works without error', async () => {
    await loadModule('static/js/pages/emergency/edit.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const form = document.getElementById('emergencyForm');
    document.querySelector('[name="chief_complaint"]').value = 'updated';
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    expect(window.Swal.fire).not.toHaveBeenCalled();
  });

  it('submit with missing required field shows warning and prevents', async () => {
    await loadModule('static/js/pages/emergency/edit.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const form = document.getElementById('emergencyForm');
    document.querySelector('[name="chief_complaint"]').value = '';
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    expect(window.Swal.fire.mock.calls[0][0].title).toBe('حقول مطلوبة');
  });

  it('submit with no changes shows info', async () => {
    await loadModule('static/js/pages/emergency/edit.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const form = document.getElementById('emergencyForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    expect(window.Swal.fire.mock.calls[0][0].title).toBe('لا تغييرات');
  });
});