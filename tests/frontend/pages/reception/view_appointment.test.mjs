import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = '<div id="app"></div>';
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
});

describe('reception/view_appointment.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/reception/view_appointment.js');
  });

  test('confirmAppointment is a function', async () => {
    await loadScript('static/js/pages/reception/view_appointment.js');
    expect(typeof confirmAppointment).toBe('function');
  });

  test('cancelAppointment is a function', async () => {
    await loadScript('static/js/pages/reception/view_appointment.js');
    expect(typeof cancelAppointment).toBe('function');
  });
});
