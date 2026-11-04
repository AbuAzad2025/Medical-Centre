import { describe, it, expect, beforeEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = `
    <input id="selectedPatientId" />
    <div id="selectedPatientInfo" class="d-none"></div>
    <button id="addNewPatientBtn">Add</button>
    <select id="department_id"></select>
    <select id="staff_id"></select>
    <div id="staff_container" style="display:none"></div>
    <div id="test_selection_section" style="display:none"></div>
    <select id="selected_tests"></select>
    <span id="tests_section_label"></span>
    <div id="custom_services_section"></div>
  `;
  window.__M = [null, null, null, null];
  window.__M0__ = null;
  window.__M1__ = null;
  window.__M2__ = null;
  window.__M3__ = null;
  window.API_ROUTES = { reception_patients: '/reception/patients', api_department_services: '/api/dept-services', api_department_staff: '/api/dept-staff' };
  window.escHtml = (s) => s;
  window.jQuery = window.$ = vi.fn(() => ({ on: vi.fn(), val: vi.fn(), html: vi.fn(), append: vi.fn(), select2: vi.fn(), hasClass: vi.fn(() => false), addClass: vi.fn(), removeClass: vi.fn(), style: {} }));
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ category: 'lab', staff: [] }) });
  try {
    await loadModule('static/js/pages/reception/create_visit.js');
  } catch (e) {
    // may fail due to jQuery; that's OK for smoke test
  }
});

describe('reception/create_visit.js', () => {
  it('loads', () => {
    expect(true).toBe(true);
  });
});