import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <form id="appointmentForm">
      <input id="patient_id" value="" />
      <input id="patient_search" value="" />
      <div id="patient_suggestions" style="display:none"></div>
      <select id="doctor_id"><option value="">Select</option></select>
      <select id="appointment_type"></select>
      <select id="department_id"><option value="">Select</option></select>
      <input type="date" id="appointment_date" />
      <select id="appointment_time"></select>
    </form>
  `;
  window.__M0__ = false;
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.Toast = { fire: vi.fn() };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, doctors: [], available_times: [] }) });
});

describe('reception/create_appointment.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/reception/create_appointment.js');
  });

  test('saveAppointment is a function', async () => {
    await loadScript('static/js/pages/reception/create_appointment.js');
    expect(typeof saveAppointment).toBe('function');
  });

  test('selectPatient is a function', async () => {
    await loadScript('static/js/pages/reception/create_appointment.js');
    expect(typeof selectPatient).toBe('function');
  });

  test('selectPatient sets patient_id and search value', async () => {
    await loadScript('static/js/pages/reception/create_appointment.js');
    selectPatient('123', 'John Doe');
    expect(document.getElementById('patient_id').value).toBe('123');
    expect(document.getElementById('patient_search').value).toBe('John Doe');
  });

  test('saveAppointment validates required fields', async () => {
    await loadScript('static/js/pages/reception/create_appointment.js');
    saveAppointment();
    expect(window.Swal.fire).toHaveBeenCalled();
  });
});
