import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <meta name="csrf-token" content="test-csrf">
    <form id="addPatientForm" action="/reception/queue/add">
      <input name="csrf_token" value="test-csrf">
      <input type="checkbox" id="is_emergency" name="is_emergency">
      <div id="emergency_reason_group" style="display:none">
        <input id="emergency_reason" name="emergency_reason" value="" required>
      </div>
      <input type="checkbox" id="force_entry" name="force_entry">
      <div id="force_entry_reason_group" style="display:none">
        <input id="force_entry_reason" name="force_entry_reason" value="">
      </div>
      <select id="department_id" name="department_id" required><option value="">اختر</option><option value="7">Cardiology</option></select>
      <select id="doctor_id" name="doctor_id"><option value="">اختر الطبيب</option></select>
      <select id="patient_id" name="patient_id"><option value="42" data-name="Ahmed">Ahmed Ali</option><option value="43" data-name="Sara">Sara</option></select>
      <select id="queue_type" name="queue_type"><option value="outpatient">خارجية</option></select>
      <select id="payment_status" name="payment_status"><option value="PAID">مدفوع</option></select>
      <input name="notes" value="">
      <button type="submit">Add</button>
    </form>
    <div id="confirmInfo"></div>
    <div id="confirmAddModal"></div>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M = [];
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.bootstrap = { Collapse: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn() })) }, Modal: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn(), hide: vi.fn() })) } };
  window.bootstrap.Modal.getOrCreateInstance = vi.fn(() => ({ show: vi.fn(), hide: vi.fn() }));
  window.showToast = vi.fn();
  window.API_ROUTES = { api_doctors: '/reception/api/doctors', reception_queue: '/reception/queue' };
  window.location = { href: '' };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, doctors: [{ id: '5', full_name: 'Dr A' }] }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('reception/add_patient_to_queue.js', () => {
  it('emergency checkbox toggles reason group', async () => {
    await loadModule('static/js/pages/reception/add_patient_to_queue.js');
    const cb = document.getElementById('is_emergency');
    cb.checked = true;
    cb.dispatchEvent(new Event('change'));
    expect(document.getElementById('emergency_reason_group').style.display).toBe('block');
    expect(document.getElementById('emergency_reason').required).toBe(true);
    cb.checked = false;
    cb.dispatchEvent(new Event('change'));
    expect(document.getElementById('emergency_reason_group').style.display).toBe('none');
  });

  it('force_entry checkbox toggles reason group', async () => {
    await loadModule('static/js/pages/reception/add_patient_to_queue.js');
    const cb = document.getElementById('force_entry');
    cb.checked = true;
    cb.dispatchEvent(new Event('change'));
    expect(document.getElementById('force_entry_reason_group').style.display).toBe('block');
    expect(document.getElementById('force_entry_reason').required).toBe(true);
    cb.checked = false;
    cb.dispatchEvent(new Event('change'));
    expect(document.getElementById('force_entry_reason_group').style.display).toBe('none');
  });

  it('department change populates doctors', async () => {
    await loadModule('static/js/pages/reception/add_patient_to_queue.js');
    const select = document.getElementById('department_id');
    select.value = '7';
    select.dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('doctor_id').innerHTML).toContain('Dr A');
  });

  it('department change with no value resets doctors', async () => {
    await loadModule('static/js/pages/reception/add_patient_to_queue.js');
    const select = document.getElementById('department_id');
    select.value = '';
    select.dispatchEvent(new Event('change'));
    expect(document.getElementById('doctor_id').innerHTML).toContain('اختر الطبيب');
  });

  it('addPatientForm submit missing fields shows warning', async () => {
    await loadModule('static/js/pages/reception/add_patient_to_queue.js');
    document.getElementById('department_id').value = '';
    const form = document.getElementById('addPatientForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 20));
    expect(window.Swal.fire.mock.calls[0][0].title).toBe('حقول مطلوبة');
  });

  it('addPatientForm submit emergency without reason shows warning', async () => {
    await loadModule('static/js/pages/reception/add_patient_to_queue.js');
    const cb = document.getElementById('is_emergency');
    cb.checked = true;
    cb.dispatchEvent(new Event('change'));
    const form = document.getElementById('addPatientForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 20));
    expect(window.Swal.fire.mock.calls[0][0].title).toBe('حقول مطلوبة');
  });

  it('addPatientForm submit valid with emergency calls showConfirmModal', async () => {
    await loadModule('static/js/pages/reception/add_patient_to_queue.js');
    document.getElementById('department_id').value = '7';
    document.getElementById('is_emergency').checked = true;
    document.getElementById('emergency_reason').value = 'chest pain';
    const form = document.getElementById('addPatientForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 20));
    expect(window.bootstrap.Modal.getOrCreateInstance).toHaveBeenCalled();
  });

  it('showConfirmModal builds confirmInfo and opens modal', async () => {
    document.getElementById('department_id').value = '7';
    const mod = await loadModule('static/js/pages/reception/add_patient_to_queue.js');
    const form = document.getElementById('addPatientForm');
    const fd = new FormData(form);
    mod.showConfirmModal(fd);
    expect(document.getElementById('confirmInfo').innerHTML).toContain('Ahmed Ali');
    expect(document.getElementById('confirmInfo').innerHTML).toContain('Cardiology');
    expect(window.bootstrap.Modal.getOrCreateInstance).toHaveBeenCalled();
  });

  it('showConfirmModal includes emergency and force entry details when set', async () => {
    document.getElementById('department_id').value = '7';
    document.getElementById('emergency_reason').value = 'chest pain';
    document.getElementById('force_entry_reason').value = 'urgent';
    document.querySelector('[name="notes"]').value = 'critical';
    const mod = await loadModule('static/js/pages/reception/add_patient_to_queue.js');
    const form = document.getElementById('addPatientForm');
    const fd = new FormData(form);
    fd.set('is_emergency', 'on');
    fd.set('force_entry', 'on');
    mod.showConfirmModal(fd);
    expect(document.getElementById('confirmInfo').innerHTML).toContain('chest pain');
    expect(document.getElementById('confirmInfo').innerHTML).toContain('urgent');
    expect(document.getElementById('confirmInfo').innerHTML).toContain('critical');
  });

  it('submitForm posts to action and redirects', async () => {
    const mod = await loadModule('static/js/pages/reception/add_patient_to_queue.js');
    mod.submitForm();
    await new Promise(r => setTimeout(r, 30));
    expect(String(global.fetch.mock.calls[0][0])).toContain('/reception/queue/add');
    expect(window.location.href).toBe('/reception/queue');
  });

  it('submitForm failure shows error Swal', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/reception/add_patient_to_queue.js');
    mod.submitForm();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });

  it('submitForm non-ok response shows error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/reception/add_patient_to_queue.js');
    mod.submitForm();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });

  it('DOMContentLoaded wires blur handlers on required fields', async () => {
    await loadModule('static/js/pages/reception/add_patient_to_queue.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const deptSelect = document.getElementById('department_id');
    deptSelect.value = '';
    deptSelect.dispatchEvent(new Event('blur'));
    expect(deptSelect.classList.contains('is-invalid')).toBe(true);
    deptSelect.value = '7';
    deptSelect.dispatchEvent(new Event('blur'));
    expect(deptSelect.classList.contains('is-valid')).toBe(true);
  });
});