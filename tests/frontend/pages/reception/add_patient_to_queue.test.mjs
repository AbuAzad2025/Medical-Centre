import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <form id="addPatientForm" action="/test">
      <input type="checkbox" id="is_emergency" />
      <div id="emergency_reason_group" style="display:none"><input id="emergency_reason" value="" /></div>
      <input type="checkbox" id="force_entry" />
      <div id="force_entry_reason_group" style="display:none"><input id="force_entry_reason" value="" /></div>
      <select id="department_id"><option value="">Select</option><option value="1">D1</option></select>
      <select id="doctor_id"><option value="">Select</option></select>
      <select id="patient_id"><option value="1">P1</option></select>
      <select id="queue_type"><option value="regular">Regular</option></select>
      <select id="payment_status"><option value="paid">Paid</option></select>
      <input name="notes" value="" />
    </form>
    <div id="confirmAddModal"></div>
    <div id="confirmInfo"></div>
  `;
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.Toast = { fire: vi.fn() };
  window.bootstrap = { Modal: { getOrCreateInstance: () => ({ show: vi.fn(), hide: vi.fn() }) } };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, doctors: [] }) });
  delete window.location;
  window.location = { href: '', reload: vi.fn() };
});

describe('reception/add_patient_to_queue.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/reception/add_patient_to_queue.js');
  });

  test('showConfirmModal is a function', async () => {
    await loadScript('static/js/pages/reception/add_patient_to_queue.js');
    expect(typeof showConfirmModal).toBe('function');
  });

  test('submitForm is a function', async () => {
    await loadScript('static/js/pages/reception/add_patient_to_queue.js');
    expect(typeof submitForm).toBe('function');
  });

  test('emergency checkbox toggle shows reason group', async () => {
    await loadScript('static/js/pages/reception/add_patient_to_queue.js');
    const chk = document.getElementById('is_emergency');
    chk.checked = true;
    chk.dispatchEvent(new Event('change'));
    expect(document.getElementById('emergency_reason_group').style.display).toBe('block');
    expect(document.getElementById('emergency_reason').required).toBe(true);
  });

  test('emergency checkbox uncheck hides reason group', async () => {
    await loadScript('static/js/pages/reception/add_patient_to_queue.js');
    const chk = document.getElementById('is_emergency');
    chk.checked = false;
    chk.dispatchEvent(new Event('change'));
    expect(document.getElementById('emergency_reason_group').style.display).toBe('none');
  });
});
