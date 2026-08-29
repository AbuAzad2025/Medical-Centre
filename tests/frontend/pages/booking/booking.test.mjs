import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <div id="app"></div>
    <select id="department_id"><option value="1">Dept 1</option></select>
    <select id="doctor_id"></select>
    <select id="appointment_time"></select>
    <input type="date" id="appointment_date" />
    <form id="bookingForm">
      <input name="csrf_token" value="test" />
    </form>
  `;
  window.__M0__ = '/api/test/doctors';
  window.__M1__ = '/api/test/times';
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ doctors: [], available_times: [] }) });
});

describe('booking/booking.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/booking/index.js');
  });

  test('loadDoctors is a function', async () => {
    await loadScript('static/js/pages/booking/index.js');
    expect(typeof loadDoctors).toBe('function');
  });

  test('loadTimes is a function', async () => {
    await loadScript('static/js/pages/booking/index.js');
    expect(typeof loadTimes).toBe('function');
  });

  test('r.ok checks exist in loadDoctors fetch', async () => {
    await loadScript('static/js/pages/booking/index.js');
    const code = await import('fs').then(fs => fs.default.readFileSync('static/js/pages/booking/index.js', 'utf-8'));
    expect(code).toContain('r.ok');
  });
});
