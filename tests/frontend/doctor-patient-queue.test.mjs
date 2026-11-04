import { describe, it, expect, beforeEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = `
    <input id="doctorPatientSearch" />
    <div id="doctorPatientResults"></div>
  `;
  window.__M = [];
  window.__M0__ = '/api/search';
  window.__M1__ = '/patient/0';
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ patients: [{ id: 1, full_name: 'Test' }] }) });
  await loadModule('static/js/pages/doctor/patient_queue.js');
  document.dispatchEvent(new Event('DOMContentLoaded'));
});

describe('doctor/patient_queue.js', () => {
  it('loads without error', () => {
    expect(true).toBe(true);
  });
});