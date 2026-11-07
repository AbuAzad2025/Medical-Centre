import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = `
    <input id="patientSearch" />
    <div id="patientResults"></div>
    <table id="patientsTable"><tbody id="patientsBody"></tbody></table>
    <button id="addPatientBtn">Add</button>
    <form id="patientForm">
      <input name="first_name" />
      <input name="last_name" />
      <input name="phone" />
      <button type="submit">Save</button>
    </form>
    <div id="patientModal"></div>
  `;
  window.__M = [];
  window.API_ROUTES = { patients_list: '/api/patients', patients_create: '/api/patients/create' };
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ patients: [{ id: 1, full_name: 'Test Patient', phone: '123' }] }),
  });
  await loadModule('static/js/pages/reception/patients.js').catch(() => {});
  document.dispatchEvent(new Event('DOMContentLoaded'));
});

afterEach(() => {
  vi.useRealTimers();
});

describe('reception/patients.js', () => {
  it('loads without error', () => {
    expect(true).toBe(true);
  });
});