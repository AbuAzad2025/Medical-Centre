import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <form id="appointmentForm">
      <select id="patient_id" name="patient_id"><option value=""></option><option value="11" data-name="Ahmed Ali" data-phone="0501" data-national-id="123">Ahmed Ali</option><option value="12" data-name="Sara" data-phone="0502" data-national-id="456">Sara</option></select>
      <input id="patient_search" name="patient_search" class="form-control">
      <div id="patient_suggestions" style="display:none"></div>
      <select id="appointment_type" name="appointment_type"><option value=""></option><option value="CONSULTATION">Consultation</option></select>
      <select id="department_id" name="department_id" class="form-control"><option value=""></option><option value="7">Cardiology</option></select>
      <select id="doctor_id" name="doctor_id"><option value="">اختر الطبيب</option></select>
      <input id="appointment_date" name="appointment_date" type="date">
      <select id="appointment_time" name="appointment_time"></select>
    </form>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M0__ = null;
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.bootstrap = { Collapse: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn() })) }, Modal: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn(), hide: vi.fn() })) } };
  window.showToast = vi.fn();
  window.API_ROUTES = { available_doctors: '/booking/api/available-doctors', available_times: '/booking/api/available-times' };
  global.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, doctors: [{ id: '5', full_name: 'Dr A' }], available_times: ['09:00', '11:00'] }) }));
});

afterEach(() => {
  vi.useRealTimers();
});

describe('reception/create_appointment.js', () => {
  it('saveAppointment missing fields shows warning', async () => {
    const mod = await loadModule('static/js/pages/reception/create_appointment.js');
    mod.saveAppointment();
    expect(window.Swal.fire.mock.calls[0][0].title).toBe('حقول مطلوبة');
  });

  it('saveAppointment past date shows error', async () => {
    document.getElementById('patient_id').value = '11';
    document.getElementById('doctor_id').innerHTML = '<option value="5">Dr</option>';
    document.getElementById('doctor_id').value = '5';
    document.getElementById('appointment_date').value = '2020-01-01';
    document.getElementById('appointment_time').innerHTML = '<option value="09:00">09:00</option>';
    document.getElementById('appointment_time').value = '09:00';
    const mod = await loadModule('static/js/pages/reception/create_appointment.js');
    mod.saveAppointment();
    expect(window.Swal.fire.mock.calls[0][0].title).toBe('تاريخ غير صالح');
  });

  it('saveAppointment complete calls form.submit', async () => {
    document.getElementById('patient_id').value = '11';
    document.getElementById('doctor_id').innerHTML = '<option value="5">Dr</option>';
    document.getElementById('doctor_id').value = '5';
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 5);
    document.getElementById('appointment_date').value = tomorrow.toISOString().slice(0, 10);
    document.getElementById('appointment_time').innerHTML = '<option value="09:00">09:00</option>';
    document.getElementById('appointment_time').value = '09:00';
    const form = document.getElementById('appointmentForm');
    form.submit = vi.fn();
    const mod = await loadModule('static/js/pages/reception/create_appointment.js');
    mod.saveAppointment();
    expect(form.submit).toHaveBeenCalled();
  });

  it('resetForm cancel does not reset', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    document.getElementById('patient_search').value = 'x';
    const mod = await loadModule('static/js/pages/reception/create_appointment.js');
    mod.resetForm();
    await new Promise(r => setTimeout(r, 20));
    expect(document.getElementById('patient_search').value).toBe('x');
  });

  it('patient search renders matching suggestions', async () => {
    await loadModule('static/js/pages/reception/create_appointment.js');
    const input = document.getElementById('patient_search');
    input.value = 'sara';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    const suggestions = document.getElementById('patient_suggestions');
    expect(suggestions.style.display).toBe('block');
    expect(suggestions.innerHTML).toContain('Sara');
  });

  it('patient search shorter than 2 hides suggestions', async () => {
    await loadModule('static/js/pages/reception/create_appointment.js');
    const input = document.getElementById('patient_search');
    input.value = 's';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    expect(document.getElementById('patient_suggestions').style.display).toBe('none');
  });

  it('patient search with no matches hides suggestions', async () => {
    await loadModule('static/js/pages/reception/create_appointment.js');
    const input = document.getElementById('patient_search');
    input.value = 'zzzz';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    expect(document.getElementById('patient_suggestions').style.display).toBe('none');
  });

  it('selectPatient sets hidden id and search text', async () => {
    const mod = await loadModule('static/js/pages/reception/create_appointment.js');
    mod.selectPatient('11', 'Ahmed Ali');
    expect(document.getElementById('patient_id').value).toBe('11');
    expect(document.getElementById('patient_search').value).toBe('Ahmed Ali');
    expect(document.getElementById('patient_suggestions').style.display).toBe('none');
  });

  it('clicking outside suggestions hides them', async () => {
    await loadModule('static/js/pages/reception/create_appointment.js');
    document.getElementById('patient_suggestions').style.display = 'block';
    document.body.click();
    expect(document.getElementById('patient_suggestions').style.display).toBe('none');
  });

  it('loadDoctors populates doctor dropdown', async () => {
    const mod = await loadModule('static/js/pages/reception/create_appointment.js');
    document.getElementById('appointment_type').value = 'CONSULTATION';
    document.getElementById('department_id').value = '7';
    mod.loadDoctors();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('doctor_id').innerHTML).toContain('Dr A');
  });

  it('loadDoctors without department responds with fallback error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, doctors: [{ id: '6', full_name: 'Dr B' }] }) });
    const mod = await loadModule('static/js/pages/reception/create_appointment.js');
    mod.loadDoctors();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('doctor_id').innerHTML).toContain('Dr B');
  });

  it('doctor change fetches available times', async () => {
    await loadModule('static/js/pages/reception/create_appointment.js');
    document.getElementById('doctor_id').innerHTML = '<option value="5">Dr A</option>';
    document.getElementById('doctor_id').value = '5';
    document.getElementById('appointment_date').value = '2026-12-01';
    const docSelect = document.getElementById('doctor_id');
    docSelect.dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('appointment_time').innerHTML).toContain('09:00');
  });

  it('appointment_date change fetches available times', async () => {
    await loadModule('static/js/pages/reception/create_appointment.js');
    document.getElementById('doctor_id').innerHTML = '<option value="5">Dr A</option>';
    document.getElementById('doctor_id').value = '5';
    const dateInput = document.getElementById('appointment_date');
    dateInput.value = '2026-12-02';
    dateInput.dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('appointment_time').innerHTML).toContain('09:00');
  });

  it('DOMContentLoaded sets min date when creating', async () => {
    window.__M0__ = null;
    await loadModule('static/js/pages/reception/create_appointment.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(document.getElementById('appointment_date').getAttribute('min')).toBeTruthy();
  });

  it('focus/blur handlers toggle focused class on parent', async () => {
    await loadModule('static/js/pages/reception/create_appointment.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const input = document.querySelector('.form-control');
    input.dispatchEvent(new Event('focus'));
    expect(input.parentElement.classList.contains('focused')).toBe(true);
    input.dispatchEvent(new Event('blur'));
    expect(input.parentElement.classList.contains('focused')).toBe(false);
  });
});