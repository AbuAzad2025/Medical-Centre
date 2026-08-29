import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <form id="emergencyForm">
      <input name="patient_id" value="1" />
      <input name="doctor_id" value="1" />
      <input name="emergency_date" value="2026-08-29" />
      <input name="emergency_time" value="10:00" />
      <input name="chief_complaint" value="Chest pain" />
    </form>
  `;
  window.__M0__ = '/api/test/resolve';
  window.__M1__ = '/api/test/transfer';
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
  delete window.location;
  window.location = { href: '', reload: vi.fn() };
});

describe('emergency/edit.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/emergency/edit.js');
  });

  test('form submit validates required fields', async () => {
    await loadScript('static/js/pages/emergency/edit.js');
    const form = document.getElementById('emergencyForm');
    const input = form.querySelector('[name="chief_complaint"]');
    input.value = '';
    form.dispatchEvent(new Event('submit', { cancelable: true }));
    expect(window.Swal.fire).toHaveBeenCalled();
  });
});
