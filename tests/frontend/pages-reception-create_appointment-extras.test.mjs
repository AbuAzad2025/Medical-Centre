import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <meta name="csrf-token" content="test-csrf">
    <form id="appointmentForm" action="/booking/create" method="post">
      <input id="appointment_date" class="form-control" type="date">
      <select id="appointment_time"><option value="">اختر</option></select>
      <select id="appointment_type"><option value="">اختر</option><option value="follow">follow</option></select>
      <select id="department_id"><option value="">اختر</option><option value="2">Cardio</option></select>
      <select id="doctor_id"><option value="">اختر الطبيب</option><option value="3">د تري</option></select>
      <input id="patient_search" class="form-control">
      <select id="patient_id"><option value="">اختر</option><option value="7" data-name="سارة" data-phone="059" data-national-id="123">سارة محمود</option></select>
      <div id="patient_suggestions" class="list-group"></div>
    </form>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M = [];
  window.__M0__ = null;
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s ?? '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.showToast = vi.fn();
  window.alert = vi.fn();
  window.location = { href: '', reload: vi.fn() };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, doctors: [{ id: 3, full_name: 'Dr Three' }], available_times: ['09:00', '10:00'] }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('create_appointment.js non-ok arms', () => {
  it('loadDoctors non-ok falls back to alert without showToast', async () => {
    delete window.showToast;
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    await loadModule('static/js/pages/reception/create_appointment.js');
    const mod = await loadModule('static/js/pages/reception/create_appointment.js');
    mod.loadDoctors();
    await new Promise(r => setTimeout(r, 30));
    expect(window.alert).toHaveBeenCalled();
  });

  it('loadDoctors non-ok with showToast uses showToast', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/reception/create_appointment.js');
    mod.loadDoctors();
    await new Promise(r => setTimeout(r, 30));
    expect(window.showToast).toHaveBeenCalled();
  });

  it('doctor change non-ok falls back to alert without showToast', async () => {
    delete window.showToast;
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    await loadModule('static/js/pages/reception/create_appointment.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const doctor = document.getElementById('doctor_id');
    doctor.value = '3';
    document.getElementById('appointment_date').value = '2026-12-01';
    doctor.dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 30));
    expect(window.alert).toHaveBeenCalled();
  });

  it('doctor change non-ok with showToast uses showToast', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    await loadModule('static/js/pages/reception/create_appointment.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const doctor = document.getElementById('doctor_id');
    doctor.value = '3';
    document.getElementById('appointment_date').value = '2026-12-01';
    doctor.dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 30));
    expect(window.showToast).toHaveBeenCalled();
  });

  it('appointment_date change non-ok falls back to alert without showToast', async () => {
    delete window.showToast;
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    await loadModule('static/js/pages/reception/create_appointment.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    document.getElementById('doctor_id').value = '3';
    const date = document.getElementById('appointment_date');
    date.value = '2026-12-01';
    date.dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 30));
    expect(window.alert).toHaveBeenCalled();
  });

  it('appointment_date change non-ok with showToast uses showToast', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    await loadModule('static/js/pages/reception/create_appointment.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    document.getElementById('doctor_id').value = '3';
    const date = document.getElementById('appointment_date');
    date.value = '2026-12-01';
    date.dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 30));
    expect(window.showToast).toHaveBeenCalled();
  });
});

describe('create_appointment.js resetForm arms', () => {
  it('resetForm confirmed resets the form', async () => {
    window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
    const mod = await loadModule('static/js/pages/reception/create_appointment.js');
    document.getElementById('appointment_date').value = '2026-12-01';
    await mod.resetForm();
    expect(document.getElementById('appointment_date').value).toBe('');
  });

  it('resetForm dismissed keeps the current values', async () => {
    window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: false }) };
    const mod = await loadModule('static/js/pages/reception/create_appointment.js');
    document.getElementById('appointment_date').value = '2026-12-01';
    await mod.resetForm();
    expect(document.getElementById('appointment_date').value).toBe('2026-12-01');
  });
});

describe('create_appointment.js special arms', () => {
  it('patient option without dataset name does not crash the preselect', async () => {
    document.body.insertAdjacentHTML('beforeend', '<option value="8">Other</option>');
    await expect(loadModule('static/js/pages/reception/create_appointment.js')).resolves.toBeDefined();
  });

  it('API_ROUTES loadDoctors endpoint is honoured', async () => {
    window.API_ROUTES = { booking_available_doctors: '/custom/doctors' };
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, doctors: [] }) });
    const mod = await loadModule('static/js/pages/reception/create_appointment.js');
    mod.loadDoctors();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch.mock.calls[0][0]).toContain('/custom/doctors');
  });

  it('loadDoctors success false leaves the dropdown untouched', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    const mod = await loadModule('static/js/pages/reception/create_appointment.js');
    await mod.loadDoctors();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('doctor_id').innerHTML).toContain('اختر الطبيب');
  });
});
