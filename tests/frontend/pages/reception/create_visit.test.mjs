import { describe, test, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from '../../test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <form id="visitForm">
      <select id="department_id"><option value="">Select</option><option value="7">Emergency</option></select>
      <select id="staff_id"><option value="">Select</option><option value="5">Dr A</option></select>
      <div id="staff_container"></div>
      <div id="test_selection_section" style="display:none"></div>
      <select id="selected_tests" multiple></select>
      <select id="visit_type"><option value="REGULAR"></option><option value="EMERGENCY"></option></select>
      <select id="tax_type"><option value="NONE"></option><option value="INC"></option></select>
      <input type="checkbox" id="is_emergency" />
      <select id="payment_method"><option value="CASH"></option><option value="CARD"></option><option value="INSURANCE"></option><option value="FORCE"></option></select>
      <div id="paymentFields" style="display:none"></div>
      <div id="insuranceFields" style="display:none"></div>
      <div id="forceFields" style="display:none"></div>
      <div id="visaFields" style="display:none"></div>
      <div id="advancedVisitFields"></div>
      <input id="visitCost" value="0.00" />
      <input id="testsTotalPrice" value="" />
      <span id="costBreakdown"></span>
      <input id="selectedPatientId" value="" />
      <div id="selectedPatientInfo" class="d-none"></div>
      <button id="addNewPatientBtn"></button>
      <div id="custom_services_container"></div>
      <div id="custom_services_section" style="display:none"></div>
      <div id="posChargeBtn" data-charge-url="/pos/charge"></div>
      <input id="amount_paid" value="" />
      <div id="posStatus"></div>
      <button id="saveAndPrintBtn"></button>
      <div id="quickEmergencyModal"></div>
      <button id="quickEmergencyBtn"></button>
      <button id="qe_create_btn"></button>
      <input id="quick_emergency" value="" />
      <input id="quick_patient_name" value="" />
      <input id="quick_gender" value="" />
      <input id="quick_age" value="" />
      <input id="quick_reason" value="" />
      <input id="qe_patient_name" value="" />
      <input id="qe_gender" value="" />
      <input id="qe_age" value="" />
      <input id="qe_reason" value="" />
      <div id="tests_section_label"></div>
      <input id="card_last_digits" value="" />
      <input id="card_holder_name" value="" />
      <input id="expiry_date" value="" />
      <input id="insurance_provider" value="" />
      <input id="insurance_policy_number" value="" />
      <input id="force_payment_reason" value="" />
      <input id="approved_by" value="" />
      <input id="symptoms" value="" />
      <input id="is_force_payment" type="checkbox" />
    </form>
  `;
}

function makeJq() {
  const modalSpy = vi.fn();
  const select2Spy = vi.fn();
  const handlers = {};
  const jq = vi.fn((sel) => {
    if (!handlers[sel]) handlers[sel] = { event: {} };
    const bucket = handlers[sel];
    return {
      on: vi.fn((event, cb) => { (bucket.event[event] = bucket.event[event] || []).push(cb); }),
      hasClass: vi.fn(() => false),
      select2: select2Spy,
      modal: modalSpy,
    };
  });
  jq.fn = { select2: select2Spy, modal: modalSpy };
  jq.modalSpy = modalSpy;
  jq.select2Spy = select2Spy;
  jq.trigger = (sel, event, thisVal) => {
    const bucket = handlers[sel];
    if (!bucket) return;
    (bucket.event[event] || []).forEach(cb => cb.call(thisVal || {}));
  };
  return jq;
}

function setupFetch() {
  const services = { category: 'lab', services: [
    { id: '10', name_ar: 'CBC', price: 20, base_price: 20, insurance_price: 15 },
    { id: '11', name_ar: 'Glucose', price: 10, base_price: 10, insurance_price: 5 },
  ] };
  const staffData = { staff: [{ id: '5', full_name: 'Dr A', role: 'doctor' }] };
  const pricing = { cost: '100.00', tests_total: '30.00', details: { breakdown: [{ item: 'LAB', cost: 100 }] } };
  global.fetch = vi.fn((url) => {
    const u = String(url);
    if (u.includes('department-services')) return Promise.resolve({ ok: true, json: () => Promise.resolve(services) });
    if (u.includes('department-staff')) return Promise.resolve({ ok: true, json: () => Promise.resolve(staffData) });
    if (u.includes('visit-pricing')) return Promise.resolve({ ok: true, json: () => Promise.resolve(pricing) });
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
  });
}

beforeEach(() => {
  baseDom();
  window.__M0__ = '';
  window.__M1__ = '';
  window.__M2__ = '';
  window.__M3__ = null;
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.Toast = { fire: vi.fn() };
  window.notify = { success: vi.fn(), error: vi.fn(), warning: vi.fn() };
  window.initPosCharge = vi.fn();
  window.bootstrap = {
    Modal: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn(), hide: vi.fn() })) },
    Collapse: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn() })) }
  };
  window.open = vi.fn(() => ({}));
  window.$ = makeJq();
  setupFetch();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('reception/create_visit.js', () => {
  test('loads module and initializes PosCharge', async () => {
    await loadModule('static/js/pages/reception/create_visit.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(window.initPosCharge).toHaveBeenCalled();
  });

  test('payment method CARD shows card fields', async () => {
    await loadModule('static/js/pages/reception/create_visit.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const pm = document.getElementById('payment_method');
    pm.value = 'CARD';
    pm.dispatchEvent(new Event('change'));
    expect(document.getElementById('paymentFields').style.display).toBe('block');
    expect(document.getElementById('visaFields').style.display).toBe('block');
  });

  test('payment method INSURANCE shows insurance fields', async () => {
    await loadModule('static/js/pages/reception/create_visit.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const pm = document.getElementById('payment_method');
    pm.value = 'INSURANCE';
    pm.dispatchEvent(new Event('change'));
    expect(document.getElementById('insuranceFields').style.display).toBe('block');
  });

  test('payment method FORCE shows force fields', async () => {
    await loadModule('static/js/pages/reception/create_visit.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const pm = document.getElementById('payment_method');
    pm.value = 'FORCE';
    pm.dispatchEvent(new Event('change'));
    expect(document.getElementById('forceFields').style.display).toBe('block');
  });

  test('department change loads staff and tests', async () => {
    await loadModule('static/js/pages/reception/create_visit.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const dept = document.getElementById('department_id');
    dept.value = '7';
    window.$.trigger('#department_id', 'change', dept);
    await new Promise(r => setTimeout(r, 50));
    const staff = document.getElementById('staff_id');
    expect(staff.options.length).toBeGreaterThanOrEqual(2);
    expect(document.getElementById('test_selection_section').style.display).toBe('flex');
    expect(document.getElementById('tests_section_label').textContent).toBe('التحاليل المخبرية المطلوبة');
  });

  test('fetch department services failure resets selection', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    await loadModule('static/js/pages/reception/create_visit.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const dept = document.getElementById('department_id');
    dept.value = '7';
    window.$.trigger('#department_id', 'change', dept);
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('test_selection_section').style.display).toBe('none');
  });

  test('calculateVisitCost updates cost from pricing fetch', async () => {
    await loadModule('static/js/pages/reception/create_visit.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const dept = document.getElementById('department_id');
    dept.value = '7';
    window.$.trigger('#department_id', 'change', dept);
    await new Promise(r => setTimeout(r, 50));
    const testOption = document.createElement('option');
    testOption.value = '10';
    testOption.dataset.basePrice = '20';
    testOption.dataset.insurancePrice = '15';
    testOption.selected = true;
    document.getElementById('selected_tests').appendChild(testOption);
    document.getElementById('payment_method').value = 'INSURANCE';
    document.getElementById('payment_method').dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('visitCost').value).toBe('100.00');
    expect(document.getElementById('testsTotalPrice').value).toBe('30.00');
    expect(document.getElementById('costBreakdown').textContent).toContain('LAB');
  });

  test('visit_type change recalculates cost', async () => {
    await loadModule('static/js/pages/reception/create_visit.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const dept = document.getElementById('department_id');
    dept.value = '7';
    window.$.trigger('#department_id', 'change', dept);
    await new Promise(r => setTimeout(r, 50));
    const vt = document.getElementById('visit_type');
    vt.dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
  });

  test('submit blocked when card fields missing', async () => {
    await loadModule('static/js/pages/reception/create_visit.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const pm = document.getElementById('payment_method');
    pm.value = 'CARD';
    pm.dispatchEvent(new Event('change'));
    const form = document.getElementById('visitForm');
    const evt = new Event('submit', { bubbles: true, cancelable: true });
    form.dispatchEvent(evt);
    expect(window.Swal.fire).toHaveBeenCalled();
    expect(evt.defaultPrevented).toBe(true);
  });

  test('submit allowed when card fields complete', async () => {
    await loadModule('static/js/pages/reception/create_visit.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const pm = document.getElementById('payment_method');
    pm.value = 'CARD';
    pm.dispatchEvent(new Event('change'));
    document.getElementById('card_last_digits').value = '1234';
    document.getElementById('card_holder_name').value = 'Test';
    document.getElementById('expiry_date').value = '12/30';
    const form = document.getElementById('visitForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    expect(window.Swal.fire).not.toHaveBeenCalled();
  });

  test('preselected patient fills patient section', async () => {
    window.__M3__ = { id: '42', full_name: 'Ahmed Ali', national_id: '123', phone: '0500000000' };
    await loadModule('static/js/pages/reception/create_visit.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(document.getElementById('selectedPatientId').value).toBe('42');
    expect(document.getElementById('selectedPatientInfo').innerHTML).toContain('Ahmed Ali');
  });

  test('addNewPatientBtn opens patients page', async () => {
    await loadModule('static/js/pages/reception/create_visit.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    document.getElementById('addNewPatientBtn').click();
    expect(window.open).toHaveBeenCalledWith(expect.stringContaining('/reception/patients'), '_blank');
  });

  test('saveAndPrintBtn appends print_receipt field and submits', async () => {
    await loadModule('static/js/pages/reception/create_visit.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const form = document.getElementById('visitForm');
    form.submit = vi.fn();
    document.getElementById('saveAndPrintBtn').click();
    expect(document.querySelector('input[name="print_receipt"]')).toBeTruthy();
    expect(form.submit).toHaveBeenCalled();
  });

  test('quickEmergencyBtn shows modal', async () => {
    await loadModule('static/js/pages/reception/create_visit.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    document.getElementById('quickEmergencyBtn').click();
    expect(window.bootstrap.Modal.getOrCreateInstance).toHaveBeenCalled();
  });

  test('qe_create_btn validates reason required', async () => {
    await loadModule('static/js/pages/reception/create_visit.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    document.getElementById('qe_patient_name').value = 'Sara';
    document.getElementById('qe_reason').value = '';
    document.getElementById('qe_create_btn').click();
    expect(window.Swal.fire).toHaveBeenCalled();
    expect(window.Swal.fire.mock.calls[0][0].title).toBe('بيانات ناقصة');
  });
  test('qe_create_btn validates name or id required', async () => {
    await loadModule('static/js/pages/reception/create_visit.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    document.getElementById('selectedPatientId').value = '';
    document.getElementById('qe_patient_name').value = '';
    document.getElementById('qe_reason').value = 'سكتة';
    document.getElementById('qe_create_btn').click();
    expect(window.Swal.fire.mock.calls[0][0].title).toBe('بيانات ناقصة');
  });
  test('department change with empty value resets staff and tests', async () => {
    await loadModule('static/js/pages/reception/create_visit.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const dept = document.getElementById('department_id');
    dept.value = '';
    window.$.trigger('#department_id', 'change', dept);
    expect(document.getElementById('staff_id').innerHTML).toContain('اختر القسم أولاً');
    expect(document.getElementById('tests_section_label').textContent).toBeDefined();
  });
  test('department services with empty staff list still populates tests', async () => {
    const svc = { category: 'lab', services: [{ id: '10', name_ar: 'CBC', price: 20, base_price: 20, insurance_price: 15 }] };
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.includes('department-services')) return Promise.resolve({ ok: true, json: () => Promise.resolve(svc) });
      if (u.includes('department-staff')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ staff: [] }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ cost: '10.00' }) });
    });
    await loadModule('static/js/pages/reception/create_visit.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const dept = document.getElementById('department_id');
    dept.value = '7';
    window.$.trigger('#department_id', 'change', dept);
    await new Promise(r => setTimeout(r, 50));
    expect(document.getElementById('staff_id').innerHTML).toContain('لا يوجد موظفون');
  });
  test('department services non-lab category hides test section', async () => {
    const svc = { category: 'consultation', services: [] };
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.includes('department-services')) return Promise.resolve({ ok: true, json: () => Promise.resolve(svc) });
      if (u.includes('department-staff')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ staff: [{ id: '5', full_name: 'Dr A', role: 'doctor' }] }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ cost: '10.00' }) });
    });
    await loadModule('static/js/pages/reception/create_visit.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const dept = document.getElementById('department_id');
    dept.value = '7';
    window.$.trigger('#department_id', 'change', dept);
    await new Promise(r => setTimeout(r, 50));
    expect(document.getElementById('test_selection_section').style.display).toBe('none');
    expect(document.getElementById('tests_section_label').textContent).toBe('الخدمات المطلوبة');
  });
  test('visit cost fetch without tests_total sums selected tests', async () => {
    const svc = { category: 'lab', services: [] };
    const staffData = { staff: [{ id: '5', full_name: 'Dr A', role: 'doctor' }] };
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.includes('department-services')) return Promise.resolve({ ok: true, json: () => Promise.resolve(svc) });
      if (u.includes('department-staff')) return Promise.resolve({ ok: true, json: () => Promise.resolve(staffData) });
      if (u.includes('visit-pricing')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ cost: '10.00' }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });
    await loadModule('static/js/pages/reception/create_visit.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const opt = document.createElement('option');
    opt.value = '10';
    opt.dataset.basePrice = '20';
    opt.dataset.insurancePrice = '';
    opt.selected = true;
    document.getElementById('selected_tests').appendChild(opt);
    document.getElementById('department_id').value = '7';
    document.getElementById('visit_type').dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('testsTotalPrice').value).toBe('20.00');
    expect(document.getElementById('costBreakdown').textContent).toBe('');
  });
  test('pricing fetch failure keeps testsTotalPrice computed from selection', async () => {
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.includes('visit-pricing')) return Promise.reject(new Error('network'));
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ category: 'lab', services: [], staff: [] }) });
    });
    await loadModule('static/js/pages/reception/create_visit.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const opt = document.createElement('option');
    opt.value = '10';
    opt.dataset.basePrice = '30';
    opt.selected = true;
    document.getElementById('selected_tests').appendChild(opt);
    document.getElementById('department_id').value = '7';
    document.getElementById('visit_type').dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('visitCost').value).toBe('0.00');
  });
  test('quickEmergencyModal fallback via $.fn.modal when bootstrap Modal missing', async () => {
    window.bootstrap = { Collapse: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn() })) }, Modal: undefined };
    await loadModule('static/js/pages/reception/create_visit.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    document.getElementById('quickEmergencyBtn').click();
    expect(window.$.modalSpy).toHaveBeenCalledWith('show');
  });
  test('quickEmergencyModal fallback without bootstrap or $.fn.modal', async () => {
    window.bootstrap = { Collapse: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn() })) }, Modal: undefined };
    window.$.fn = { select2: vi.fn(), modal: undefined };
    await loadModule('static/js/pages/reception/create_visit.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    document.getElementById('quickEmergencyBtn').click();
    expect(document.getElementById('quickEmergencyModal').classList.contains('show')).toBe(true);
  });
  test('ensureAdvancedOpen falls back to classList when no bootstrap Collapse', async () => {
    window.bootstrap = { Modal: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn(), hide: vi.fn() })) }, Collapse: undefined };
    await loadModule('static/js/pages/reception/create_visit.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const pm = document.getElementById('payment_method');
    pm.value = 'CARD';
    pm.dispatchEvent(new Event('change'));
    expect(document.getElementById('advancedVisitFields').classList.contains('show')).toBe(true);
  });
  test('preselected department and doctor are applied', async () => {
    window.__M1__ = '7';
    window.__M2__ = '5';
    await loadModule('static/js/pages/reception/create_visit.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(document.getElementById('department_id').value).toBe('7');
    await new Promise(r => setTimeout(r, 450));
    expect(document.getElementById('staff_id').value).toBe('5');
  });

  test('qe_create_btn with valid data sets emergency state', async () => {
    await loadModule('static/js/pages/reception/create_visit.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    document.getElementById('qe_reason').value = 'سكتة دماغية';
    document.getElementById('qe_patient_name').value = 'Sara';
    document.getElementById('qe_age').value = '40';
    const form = document.getElementById('visitForm');
    form.submit = vi.fn();
    document.getElementById('qe_create_btn').click();
    expect(document.getElementById('visit_type').value).toBe('EMERGENCY');
    expect(document.getElementById('payment_method').value).toBe('FORCE');
    expect(document.getElementById('force_payment_reason').value).toContain('طوارئ');
    expect(document.getElementById('approved_by').value).toBe('في انتظار اعتماد المدير');
  });

  test('custom service row price input triggers calculateVisitCost via input event', async () => {
    document.getElementById('department_id').value = '7';
    await loadModule('static/js/pages/reception/create_visit.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    document.getElementById('department_id').value = '7';
    const container = document.getElementById('custom_services_container');
    const row = document.createElement('div');
    row.className = 'custom-service-row';
    row.innerHTML = '<input name="custom_service_name" value="CBC"><input name="custom_service_price" class="custom-service-price" value="25">';
    container.appendChild(row);
    const input = row.querySelector('.custom-service-price');
    input.dispatchEvent(new Event('input', { bubbles: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('visit-pricing'), expect.any(Object));
  });
});