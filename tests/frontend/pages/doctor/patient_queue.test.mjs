import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <input id="doctorPatientSearch" type="text" />
    <div id="doctorPatientResults" style="display:none"></div>
    <div class="container-fluid" data-dept="1"></div>
    <table><tbody><tr><td></td></tr></tbody></table>
  `;
  window.__M0__ = '/api/test/patient-search';
  window.__M1__ = '/doctor/patient/0';
  window.__M2__ = '1';
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  window.Toast = { fire: vi.fn() };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ patients: [] }) });
});

describe('doctor/patient_queue.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/doctor/patient_queue.js');
  });
});
