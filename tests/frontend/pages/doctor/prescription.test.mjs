import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <table id="rxItemsTable"><tbody></tbody></table>
    <button id="addRxItemBtn"></button>
    <select id="templateSelect"><option value="">None</option></select>
    <button id="applyTemplateBtn"></button>
    <form id="prescriptionForm" action="/test" data-success-url="/success">
      <input name="csrf_token" value="test" />
    </form>
    <div id="prescriptionError" class="d-none"></div>
  `;
  window.__M0__ = [{ id: '1', name: 'Template 1', items: [{ medication_id: '10', medication_label: 'Aspirin', dosage: '1 tab', frequency: 'daily', duration_days: 7, quantity: 1, instructions: 'After meal' }] }];
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.Toast = { fire: vi.fn() };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
});

describe('doctor/prescription.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/doctor/prescription.js');
  });
});
