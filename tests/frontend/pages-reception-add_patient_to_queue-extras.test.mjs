import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <meta name="csrf-token" content="meta-csrf">
    <input type="checkbox" id="is_emergency">
    <div id="emergency_reason_group" style="display:none">
      <input id="emergency_reason" name="emergency_reason">
    </div>
    <input type="checkbox" id="force_entry">
    <div id="force_entry_reason_group" style="display:none">
      <input id="force_entry_reason" name="force_entry_reason">
    </div>
    <select id="department_id"><option value="">اختر</option><option value="4">Cardio</option></select>
    <select id="doctor_id"><option value="">اختر الطبيب</option></select>
    <form id="addPatientForm" action="/reception/queue/add">
      <select id="patient_id"><option value="7" selected>سارة محمود</option></select>
      <select id="queue_type"><option value="waiting" selected>انتظار</option></select>
      <select id="payment_status"><option value="unpaid" selected>غير مدفوع</option></select>
      <input name="department_id" type="hidden" value="4">
      <input name="notes" value="">
      <input type="hidden" name="csrf_token" value="form-csrf">
    </form>
    <div id="confirmInfo"></div>
    <div id="confirmAddModal"></div>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M = [];
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s ?? '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.showToast = vi.fn();
  window.alert = vi.fn();
  window.location = { href: '' };
  window.bootstrap = { Modal: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn() })) } };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, doctors: [{ id: 9, full_name: 'Dr Nine' }] }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('add_patient_to_queue.js department change branches', () => {
  it('non-ok response triggers showToast when available', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    await loadModule('static/js/pages/reception/add_patient_to_queue.js');
    const el = document.getElementById('department_id');
    el.value = '4';
    el.dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 30));
    expect(window.showToast).toHaveBeenCalled();
  });

  it('non-ok response falls back to alert without showToast', async () => {
    delete window.showToast;
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    await loadModule('static/js/pages/reception/add_patient_to_queue.js');
    const el = document.getElementById('department_id');
    el.value = '4';
    el.dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 30));
    expect(window.alert).toHaveBeenCalled();
  });

  it('network failure triggers alert without showToast', async () => {
    delete window.showToast;
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    await loadModule('static/js/pages/reception/add_patient_to_queue.js');
    const el = document.getElementById('department_id');
    el.value = '4';
    el.dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 30));
    expect(window.alert).toHaveBeenCalled();
  });

  it('success:false leaves the doctor select unchanged', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    await loadModule('static/js/pages/reception/add_patient_to_queue.js');
    const el = document.getElementById('department_id');
    el.value = '4';
    el.dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('doctor_id').querySelectorAll('option').length).toBe(1);
  });

  it('missing doctor select does not crash on fetch success', async () => {
    document.getElementById('doctor_id').remove();
    await loadModule('static/js/pages/reception/add_patient_to_queue.js');
    const el = document.getElementById('department_id');
    el.value = '4';
    expect(() => el.dispatchEvent(new Event('change'))).not.toThrow();
  });

  it('API_ROUTES health-check: uses api_doctors route when set', async () => {
    window.API_ROUTES = { api_doctors: '/custom/doctors' };
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, doctors: [{ id: 1, full_name: 'Dr X' }] }) });
    await loadModule('static/js/pages/reception/add_patient_to_queue.js');
    const el = document.getElementById('department_id');
    el.value = '4';
    el.dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch.mock.calls[0][0]).toContain('/custom/doctors');
  });

  it('missing emergency checkbox element does not crash the module', async () => {
    document.getElementById('is_emergency').remove();
    await expect(loadModule('static/js/pages/reception/add_patient_to_queue.js')).resolves.toBeDefined();
  });

  it('missing force-entry checkbox element does not crash the module', async () => {
    document.getElementById('force_entry').remove();
    await expect(loadModule('static/js/pages/reception/add_patient_to_queue.js')).resolves.toBeDefined();
  });
});

describe('add_patient_to_queue.js checkbox branches', () => {
  it('unchecking emergency hides and clears the reason', async () => {
    await loadModule('static/js/pages/reception/add_patient_to_queue.js');
    const chk = document.getElementById('is_emergency');
    chk.checked = true;
    chk.dispatchEvent(new Event('change'));
    expect(document.getElementById('emergency_reason_group').style.display).toBe('block');
    document.getElementById('emergency_reason').value = 'عاجل';
    chk.checked = false;
    chk.dispatchEvent(new Event('change'));
    expect(document.getElementById('emergency_reason_group').style.display).toBe('none');
    expect(document.getElementById('emergency_reason').required).toBe(false);
    expect(document.getElementById('emergency_reason').value).toBe('');
  });

  it('unchecking force_entry hides and clears the reason', async () => {
    await loadModule('static/js/pages/reception/add_patient_to_queue.js');
    const chk = document.getElementById('force_entry');
    chk.checked = true;
    chk.dispatchEvent(new Event('change'));
    expect(document.getElementById('force_entry_reason_group').style.display).toBe('block');
    document.getElementById('force_entry_reason').value = 'force';
    chk.checked = false;
    chk.dispatchEvent(new Event('change'));
    expect(document.getElementById('force_entry_reason_group').style.display).toBe('none');
    expect(document.getElementById('force_entry_reason').value).toBe('');
  });
});

describe('add_patient_to_queue.js confirmInfo branches', () => {
  it('confirmInfo includes notes when provided', async () => {
    const mod = await loadModule('static/js/pages/reception/add_patient_to_queue.js');
    const fd = new FormData();
    fd.set('patient_id', '7');
    fd.set('department_id', '4');
    fd.set('notes', 'تذكير بالمواعيد');
    mod.showConfirmModal(fd);
    expect(document.getElementById('confirmInfo').innerHTML).toContain('تذكير بالمواعيد');
  });

  it('confirmInfo uses غير محدد when no doctor is selected', async () => {
    const mod = await loadModule('static/js/pages/reception/add_patient_to_queue.js');
    const fd = new FormData();
    fd.set('patient_id', '7');
    fd.set('department_id', '4');
    mod.showConfirmModal(fd);
    expect(document.getElementById('confirmInfo').innerHTML).toContain('غير محدد');
  });

  it('confirmInfo uses the selected doctor when set', async () => {
    const doctor = document.getElementById('doctor_id');
    doctor.innerHTML = '<option value="9" selected>د سارة</option>';
    doctor.value = '9';
    const mod = await loadModule('static/js/pages/reception/add_patient_to_queue.js');
    const fd = new FormData();
    fd.set('patient_id', '7');
    fd.set('department_id', '4');
    mod.showConfirmModal(fd);
    expect(document.getElementById('confirmInfo').innerHTML).toContain('د سارة');
  });

  it('modalEl missing does not crash showConfirmModal', async () => {
    document.getElementById('confirmAddModal').remove();
    const mod = await loadModule('static/js/pages/reception/add_patient_to_queue.js');
    const fd = new FormData();
    fd.set('patient_id', '7');
    fd.set('department_id', '4');
    expect(() => mod.showConfirmModal(fd)).not.toThrow();
  });

  it('modalEl present but bootstrap missing does not crash', async () => {
    delete window.bootstrap;
    const mod = await loadModule('static/js/pages/reception/add_patient_to_queue.js');
    const fd = new FormData();
    fd.set('patient_id', '7');
    fd.set('department_id', '4');
    expect(() => mod.showConfirmModal(fd)).not.toThrow();
  });
});

describe('add_patient_to_queue.js submitForm branches', () => {
  it('form csrf input is preferred over meta', async () => {
    const mod = await loadModule('static/js/pages/reception/add_patient_to_queue.js');
    mod.submitForm();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBe('form-csrf');
  });

  it('meta csrf is used when form has none', async () => {
    document.querySelector('#addPatientForm input[name="csrf_token"]').remove();
    const mod = await loadModule('static/js/pages/reception/add_patient_to_queue.js');
    mod.submitForm();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBe('meta-csrf');
  });

  it('no csrf elements anywhere sends no token header', async () => {
    document.querySelector('#addPatientForm input[name="csrf_token"]').remove();
    document.querySelector('meta[name="csrf-token"]').remove();
    const mod = await loadModule('static/js/pages/reception/add_patient_to_queue.js');
    mod.submitForm();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBeUndefined();
  });

  it('API_ROUTES reception_queue override is honoured for the redirect', async () => {
    window.API_ROUTES = { reception_queue: '/custom/queue' };
    const mod = await loadModule('static/js/pages/reception/add_patient_to_queue.js');
    mod.submitForm();
    await new Promise(r => setTimeout(r, 40));
    expect(window.location.href).toBe('/custom/queue');
  });

  it('falls back to the default queue route when API_ROUTES is unset', async () => {
    delete window.API_ROUTES;
    const mod = await loadModule('static/js/pages/reception/add_patient_to_queue.js');
    mod.submitForm();
    await new Promise(r => setTimeout(r, 40));
    expect(window.location.href).toBe('/reception/queue');
  });

  it('missing addPatientForm makes submitForm reject', async () => {
    document.getElementById('addPatientForm').remove();
    const mod = await loadModule('static/js/pages/reception/add_patient_to_queue.js');
    expect(() => mod.submitForm()).toThrow();
  });
});
