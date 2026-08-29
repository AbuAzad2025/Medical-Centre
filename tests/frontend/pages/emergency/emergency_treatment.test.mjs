import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <form id="emergencyTreatmentForm">
      <input name="csrf_token" value="test" />
    </form>
  `;
  window.__M0__ = '/api/test/treatment';
  window.__M1__ = '/emergency/dashboard';
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
  delete window.location;
  window.location = { href: '', reload: vi.fn() };
});

describe('emergency/emergency_treatment.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/emergency/emergency_treatment.js');
  });
});
