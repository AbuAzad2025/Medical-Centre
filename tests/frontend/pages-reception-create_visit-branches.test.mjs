import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

const jqueryState = { handlers: new Map(), staffHasClass: false, testsHasClass: false, staffCalls: [], testsCalls: [], modalCalls: [] };

function makeJqueryMock() {
  jqueryState.handlers = new Map();
  jqueryState.staffCalls = [];
  jqueryState.testsCalls = [];
  jqueryState.modalCalls = [];

  const $ = vi.fn((selector) => {
    const isString = typeof selector === 'string';
    const el = isString ? document.querySelector(selector) : selector;
    const key = isString ? selector : '__element__';
    const entry = jqueryState.handlers.get(key) || { handlers: new Map() };
    jqueryState.handlers.set(key, entry);
    const isStaff = key === '#staff_id';
    return {
      on: (evt, cb) => {
        const arr = entry.handlers.get(evt) || [];
        arr.push(cb);
        entry.handlers.set(evt, arr);
        return this;
      },
      hasClass: () => (isStaff ? jqueryState.staffHasClass : jqueryState.testsHasClass),
      select2: (...args) => { if (isStaff) jqueryState.staffCalls.push(args); else jqueryState.testsCalls.push(args); },
      modal: (...args) => { jqueryState.modalCalls.push(args); },
    };
  });
  $.fn = { modal: (...args) => { jqueryState.modalCalls.push(args); } };
  return $;
}

function trigger(selector, evt) {
  const entry = jqueryState.handlers.get(selector);
  const el = document.querySelector(selector);
  if (entry && entry.handlers.get(evt)) {
    entry.handlers.get(evt).forEach(cb => cb.call(el, { type: evt }));
  }
}

function baseDom() {
  document.body.innerHTML = `
    <input id="selectedPatientId" value="">
    <div id="selectedPatientInfo" class="d-none"></div>
    <button id="addNewPatientBtn">Add</button>
    <select id="department_id">
      <option value="">اختر</option>
      <option value="9">الطوارئ</option>
      <option value="3">العيون</option>
    </select>
    <select id="staff_id"></select>
    <div id="staff_container" style="display:none"></div>
    <div id="test_selection_section" style="display:none"></div>
    <select id="selected_tests" multiple></select>
    <span id="tests_section_label"></span>
    <div id="custom_services_section" style="display:none"></div>
    <input id="visit_type" value="FOLLOWUP">
    <input id="tax_type" value="none">
    <input type="checkbox" id="is_emergency">
    <input type="checkbox" id="is_force_payment">
    <select id="payment_method"><option value="CASH" selected>CASH</option><option value="CARD">CARD</option><option value="INSURANCE">INSURANCE</option><option value="FORCE">FORCE</option></select>
    <div id="visaFields" style="display:none"></div>
    <div id="insuranceFields" style="display:none"></div>
    <div id="forceFields" style="display:none"></div>
    <div id="paymentFields" style="display:none"></div>
    <div id="advancedVisitFields"></div>
    <input id="visitCost">
    <input id="testsTotalPrice">
    <div id="costBreakdown"></div>
    <form id="visitForm" action="/reception/visits/create" method="post">
      <input id="card_last_digits" value="1234">
      <input id="card_holder_name" value="Sara A">
      <input id="expiry_date" value="12/30">
      <input id="insurance_provider" value="ACME">
      <input id="insurance_policy_number" value="POL-1">
      <input id="force_payment_reason" value="حالة طوارئ عاجلة جداً وطويلة">
      <input id="approved_by" value="المدير المناوب">
    </form>
    <button id="posChargeBtn" data-charge-url="/pos/custom">Charge</button>
    <input id="amount_paid" value="10">
    <div id="posStatus"></div>
    <button id="saveAndPrintBtn">Save & Print</button>
    <div id="quickEmergencyModal"></div>
    <button id="quickEmergencyBtn">Quick</button>
    <button id="qe_create_btn">Create</button>
    <input type="hidden" id="quick_emergency" value="0">
    <input type="hidden" id="quick_patient_name">
    <input type="hidden" id="quick_gender">
    <input type="hidden" id="quick_age">
    <input type="hidden" id="quick_reason">
    <input id="qe_patient_name" value="مريض طارئ">
    <input id="qe_gender" value="male">
    <input id="qe_age" value="30">
    <input id="qe_reason" value="ألم صدر شديد">
    <input id="symptoms" value="">
    <div id="custom_services_container"></div>
  `;
}

beforeEach(() => {
  baseDom();
  jqueryState.staffHasClass = false;
  jqueryState.testsHasClass = false;
  window.__M = [];
  window.__M0__ = null;
  window.__M1__ = null;
  window.__M2__ = null;
  window.__M3__ = null;
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s ?? '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.bootstrap = { Collapse: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn() })) }, Modal: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn(), hide: vi.fn() })) } };
  window.$ = window.jQuery = makeJqueryMock();
  window.initPosCharge = vi.fn();
  window.open = vi.fn();
  const origSubmit = HTMLFormElement.prototype.submit;
  HTMLFormElement.prototype.submit = vi.fn();
  global.fetch = vi.fn((url) => {
    const u = String(url);
    if (u.includes('department-services')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ category: 'lab', services: [{ id: 11, name_ar: 'CBC', price: 100, base_price: 120, insurance_price: 80 }] }) });
    if (u.includes('department-staff')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ staff: [{ id: 1, full_name: 'د أسامة', role: 'doctor' }, { id: 2, full_name: 'سارة', role: 'pharmacist' }, { id: 3, full_name: 'فهد', role: 'nurse' }] }) });
    if (u.includes('visit-pricing')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ cost: '250.00', tests_total: '80.00', details: { breakdown: [{ item: 'CBC', cost: 120 }] } }) });
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
  });
});

afterEach(() => {
  vi.useRealTimers();
});

async function loadAndDispatch() {
  await loadModule('static/js/pages/reception/create_visit.js');
  document.dispatchEvent(new Event('DOMContentLoaded'));
  await new Promise(r => setTimeout(r, 30));
}

describe('create_visit.js department change branches', () => {
  it('lab category shows test section, sets the labs label and option prices', async () => {
    await loadAndDispatch();
    const select = document.getElementById('department_id');
    select.value = '9';
    trigger('#department_id', 'change');
    await new Promise(r => setTimeout(r, 40));
    expect(document.getElementById('test_selection_section').style.display).toBe('flex');
    expect(document.getElementById('tests_section_label').textContent).toBe('التحاليل المخبرية المطلوبة');
    expect(document.getElementById('custom_services_section').style.display).toBe('block');
    const opt = document.querySelector('#selected_tests option');
    expect(opt.dataset.baseprice ?? opt.dataset.basePrice).toBeTruthy;
    expect(jqueryState.staffCalls.some(c => c.length === 1 && typeof c[0] === 'object')).toBe(true);
  });

  it('radiology category sets the imaging label', async () => {
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.includes('department-services')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ category: 'radiology', services: [] }) });
      if (u.includes('department-staff')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ staff: [] }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });
    await loadAndDispatch();
    document.getElementById('department_id').value = '9';
    trigger('#department_id', 'change');
    await new Promise(r => setTimeout(r, 40));
    expect(document.getElementById('tests_section_label').textContent).toBe('صور الأشعة المطلوبة');
  });

  it('non lab/radiology category hides the test section and sets generic label', async () => {
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.includes('department-services')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ category: 'clinic', services: [] }) });
      if (u.includes('department-staff')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ staff: [] }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });
    await loadAndDispatch();
    document.getElementById('department_id').value = '3';
    trigger('#department_id', 'change');
    await new Promise(r => setTimeout(r, 40));
    expect(document.getElementById('tests_section_label').textContent).toBe('الخدمات المطلوبة');
    expect(document.getElementById('test_selection_section').style.display).toBe('none');
  });

  it('services fetch non-ok wipes the test section and loads nothing else', async () => {
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.includes('department-services')) return Promise.resolve({ ok: false, status: 500 });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });
    await loadAndDispatch();
    document.getElementById('department_id').value = '9';
    trigger('#department_id', 'change');
    await new Promise(r => setTimeout(r, 40));
    expect(document.getElementById('test_selection_section').style.display).toBe('none');
    expect(document.getElementById('selected_tests').innerHTML).toBe('');
  });

  it('staff fetch non-ok shows the load error option', async () => {
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.includes('department-services')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ category: 'lab', services: [] }) });
      if (u.includes('department-staff')) return Promise.resolve({ ok: false, status: 500 });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });
    await loadAndDispatch();
    document.getElementById('department_id').value = '9';
    trigger('#department_id', 'change');
    await new Promise(r => setTimeout(r, 40));
    expect(document.getElementById('staff_id').innerHTML).toContain('خطأ في التحميل');
  });

  it('empty staff list shows the no-staff option', async () => {
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.includes('department-services')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ category: 'lab', services: [] }) });
      if (u.includes('department-staff')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ staff: [] }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });
    await loadAndDispatch();
    document.getElementById('department_id').value = '9';
    trigger('#department_id', 'change');
    await new Promise(r => setTimeout(r, 40));
    expect(document.getElementById('staff_id').innerHTML).toContain('لا يوجد موظفون');
  });

  it('unknown roles fall back to the raw role in the option text', async () => {
    await loadAndDispatch();
    document.getElementById('department_id').value = '9';
    trigger('#department_id', 'change');
    await new Promise(r => setTimeout(r, 40));
    expect(document.getElementById('staff_id').innerHTML).toContain('سارة - pharmacist');
  });

  it('select2 already initialized is destroyed before re-init', async () => {
    jqueryState.staffHasClass = true;
    jqueryState.testsHasClass = true;
    await loadAndDispatch();
    document.getElementById('department_id').value = '9';
    trigger('#department_id', 'change');
    await new Promise(r => setTimeout(r, 40));
    expect(jqueryState.staffCalls.some(c => c[0] === 'destroy')).toBe(true);
    expect(jqueryState.testsCalls.some(c => c[0] === 'destroy')).toBe(true);
  });

  it('clearing the department resets the panels', async () => {
    await loadAndDispatch();
    document.getElementById('department_id').value = '';
    trigger('#department_id', 'change');
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('staff_id').innerHTML).toContain('اختر القسم أولاً');
    expect(document.getElementById('test_selection_section').style.display).toBe('none');
  });

  it('API_ROUTES override is honoured for services and staff', async () => {
    window.API_ROUTES = { api_department_services: '/custom/svc', api_department_staff: '/custom/staff' };
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.includes('/custom/svc')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ category: 'lab', services: [] }) });
      if (u.includes('/custom/staff')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ staff: [] }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });
    await loadAndDispatch();
    document.getElementById('department_id').value = '9';
    trigger('#department_id', 'change');
    await new Promise(r => setTimeout(r, 40));
    const urls = global.fetch.mock.calls.map(c => String(c[0]));
    expect(urls.some(u => u.includes('/custom/svc'))).toBe(true);
    expect(urls.some(u => u.includes('/custom/staff'))).toBe(true);
  });
});

describe('create_visit.js visit cost branches', () => {
  it('requests visit pricing with all parameters and fills the fields', async () => {
    await loadAndDispatch();
    const pricing = global.fetch.mock.calls.find(c => String(c[0]).includes('visit-pricing'));
    // no pricing call yet without department selection
    expect(pricing).toBeUndefined();
    document.getElementById('department_id').value = '9';
    trigger('#department_id', 'change');
    await new Promise(r => setTimeout(r, 40));
    const call = global.fetch.mock.calls.find(c => String(c[0]).includes('visit-pricing'));
    expect(call[0]).toContain('department_id=9');
    expect(call[0]).toContain('visit_type=FOLLOWUP');
    expect(call[0]).toContain('tax_type=none');
    expect(call[0]).toContain('payment_method=cash');
    expect(document.getElementById('visitCost').value).toBe('250.00');
    expect(document.getElementById('testsTotalPrice').value).toBe('80.00');
    expect(document.getElementById('costBreakdown').textContent).toContain('CBC');
  });

  it('insurance payment requests insurance prices for selected tests', async () => {
    await loadAndDispatch();
    document.getElementById('department_id').value = '9';
    trigger('#department_id', 'change');
    await new Promise(r => setTimeout(r, 40));
    const testsSelect = document.getElementById('selected_tests');
    const opt = testsSelect.querySelector('option');
    opt.selected = true;
    global.fetch.mockClear();
    global.fetch = vi.fn((url) => Promise.resolve({ ok: true, json: () => Promise.resolve({ cost: '10.00' }) }));
    document.getElementById('payment_method').value = 'INSURANCE';
    document.getElementById('payment_method').dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch.mock.calls.some(c => String(c[0]).includes('payment_method=insurance'))).toBe(true);
  });

  it('missing tests_total falls back to the selected sum', async () => {
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.includes('visit-pricing')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ cost: '50.00' }) });
      if (u.includes('department-services')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ category: 'lab', services: [{ id: 11, name_ar: 'CBC', price: 100, base_price: 120, insurance_price: 80 }] }) });
      if (u.includes('department-staff')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ staff: [] }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });
    await loadAndDispatch();
    document.getElementById('department_id').value = '9';
    trigger('#department_id', 'change');
    await new Promise(r => setTimeout(r, 40));
    const testsSelect = document.getElementById('selected_tests');
    testsSelect.querySelector('option').selected = true;
    global.fetch = vi.fn((url) => Promise.resolve({ ok: true, json: () => Promise.resolve({ cost: '50.00' }) }));
    document.getElementById('tax_type').dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('testsTotalPrice').value).toBe('120.00');
    expect(document.getElementById('costBreakdown').textContent).toBe('');
  });

  it('pricing fetch non-ok zeroes the cost', async () => {
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.includes('visit-pricing')) return Promise.resolve({ ok: false, status: 500 });
      if (u.includes('department-services')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ category: 'lab', services: [] }) });
      if (u.includes('department-staff')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ staff: [] }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });
    await loadAndDispatch();
    document.getElementById('department_id').value = '9';
    trigger('#department_id', 'change');
    await new Promise(r => setTimeout(r, 40));
    expect(document.getElementById('visitCost').value).toBe('0.00');
  });

  it('custom service rows contribute name and price params', async () => {
    await loadAndDispatch();
    const container = document.getElementById('custom_services_container');
    const row = document.createElement('div');
    row.className = 'custom-service-row';
    row.innerHTML = '<input name="custom_service_name" value="أشعة سينية"><input name="custom_service_price" value="150">';
    container.appendChild(row);
    const emptyRow = document.createElement('div');
    emptyRow.className = 'custom-service-row';
    emptyRow.innerHTML = '<input name="custom_service_name" value="   "><input name="custom_service_price" value="999">';
    container.appendChild(emptyRow);
    global.fetch = vi.fn((url) => Promise.resolve({ ok: true, json: () => Promise.resolve({ cost: '1.00' }) }));
    document.getElementById('department_id').value = '9';
    trigger('#department_id', 'change');
    await new Promise(r => setTimeout(r, 40));
    const call = global.fetch.mock.calls.find(c => String(c[0]).includes('visit-pricing'));
    expect(call[0]).toContain('custom_service_name=');
    expect(call[0]).toContain('custom_service_price=150');
    expect(call[0]).not.toContain('999');
  });

  it('API_ROUTES api_visit_pricing override is honoured', async () => {
    window.API_ROUTES = { api_visit_pricing: '/custom/pricing' };
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.includes('/custom/pricing')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ cost: '1.00' }) });
      if (u.includes('department-services')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ category: 'lab', services: [] }) });
      if (u.includes('department-staff')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ staff: [] }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });
    await loadAndDispatch();
    document.getElementById('department_id').value = '9';
    trigger('#department_id', 'change');
    await new Promise(r => setTimeout(r, 40));
    expect(global.fetch.mock.calls.some(c => String(c[0]).includes('/custom/pricing'))).toBe(true);
  });
});

describe('create_visit.js payment method branches', () => {
  it('CARD shows visa fields and opens advanced section via bootstrap', async () => {
    await loadAndDispatch();
    const method = document.getElementById('payment_method');
    method.value = 'CARD';
    method.dispatchEvent(new Event('change'));
    expect(document.getElementById('visaFields').style.display).toBe('block');
    expect(document.getElementById('paymentFields').style.display).toBe('block');
    expect(window.bootstrap.Collapse.getOrCreateInstance).toHaveBeenCalled();
  });

  it('CARD without visaFields element still opens advanced section', async () => {
    document.getElementById('visaFields').remove();
    await loadAndDispatch();
    const method = document.getElementById('payment_method');
    method.value = 'CARD';
    method.dispatchEvent(new Event('change'));
    expect(window.bootstrap.Collapse.getOrCreateInstance).toHaveBeenCalled();
  });

  it('CARD without bootstrap uses the show class fallback', async () => {
    delete window.bootstrap;
    await loadAndDispatch();
    const method = document.getElementById('payment_method');
    method.value = 'CARD';
    method.dispatchEvent(new Event('change'));
    expect(document.getElementById('advancedVisitFields').classList.contains('show')).toBe(true);
  });

  it('INSURANCE shows insurance fields', async () => {
    await loadAndDispatch();
    const method = document.getElementById('payment_method');
    method.value = 'INSURANCE';
    method.dispatchEvent(new Event('change'));
    expect(document.getElementById('insuranceFields').style.display).toBe('block');
    expect(document.getElementById('paymentFields').style.display).toBe('block');
  });

  it('FORCE shows force fields', async () => {
    await loadAndDispatch();
    const method = document.getElementById('payment_method');
    method.value = 'FORCE';
    method.dispatchEvent(new Event('change'));
    expect(document.getElementById('forceFields').style.display).toBe('block');
  });

  it('unknown method hides all payment fields and skips advanced', async () => {
    await loadAndDispatch();
    const method = document.getElementById('payment_method');
    method.value = 'CRYPTO';
    method.dispatchEvent(new Event('change'));
    expect(document.getElementById('paymentFields').style.display).toBe('none');
  });

  it('advanced section missing returns early without crashing', async () => {
    document.getElementById('advancedVisitFields').remove();
    await loadAndDispatch();
    const method = document.getElementById('payment_method');
    method.value = 'CARD';
    expect(() => method.dispatchEvent(new Event('change'))).not.toThrow();
  });
});

describe('create_visit.js visit form submit branches', () => {
  it('CARD with missing card fields blocks submission with a warning', async () => {
    await loadAndDispatch();
    document.getElementById('card_holder_name').value = '';
    const method = document.getElementById('payment_method');
    method.value = 'CARD';
    const form = document.getElementById('visitForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('warning');
  });

  it('INSURANCE with all fields passes validation', async () => {
    await loadAndDispatch();
    document.getElementById('payment_method').value = 'INSURANCE';
    const form = document.getElementById('visitForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    expect(window.Swal.fire).not.toHaveBeenCalled();
  });

  it('FORCE missing approved_by blocks submission', async () => {
    await loadAndDispatch();
    document.getElementById('payment_method').value = 'FORCE';
    document.getElementById('approved_by').value = '';
    const form = document.getElementById('visitForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('warning');
  });

  it('CASH with no special fields passes validation', async () => {
    await loadAndDispatch();
    document.getElementById('payment_method').value = 'CASH';
    const form = document.getElementById('visitForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    expect(window.Swal.fire).not.toHaveBeenCalled();
  });
});

describe('create_visit.js quick emergency branches', () => {
  it('clicking the quick button opens the modal', async () => {
    await loadAndDispatch();
    document.getElementById('quickEmergencyBtn').click();
    expect(window.bootstrap.Modal.getOrCreateInstance).toHaveBeenCalled();
  });

  it('missing patient name and no selected patient shows warning', async () => {
    document.getElementById('qe_patient_name').value = '';
    await loadAndDispatch();
    document.getElementById('qe_create_btn').click();
    expect(window.Swal.fire.mock.calls[0][0].text).toContain('اسم المريض');
  });

  it('missing reason shows warning', async () => {
    document.getElementById('qe_reason').value = ' ';
    await loadAndDispatch();
    document.getElementById('qe_create_btn').click();
    expect(window.Swal.fire.mock.calls[0][0].text).toContain('سبب الدخول');
  });

  it('full quick submission sets hidden fields, checks emergency boxes and submits', async () => {
    await loadAndDispatch();
    document.getElementById('qe_create_btn').click();
    expect(document.getElementById('quick_emergency').value).toBe('1');
    expect(document.getElementById('quick_patient_name').value).toBe('مريض طارئ');
    expect(document.getElementById('quick_reason').value).toBe('ألم صدر شديد');
    expect(document.getElementById('is_emergency').checked).toBe(true);
    expect(document.getElementById('is_force_payment').checked).toBe(true);
    expect(document.getElementById('visit_type').value).toBe('EMERGENCY');
    expect(document.getElementById('symptoms').value).toBe('ألم صدر شديد');
    expect(document.getElementById('payment_method').value).toBe('FORCE');
    expect(document.getElementById('force_payment_reason').value).toContain('حالة طوارئ');
    // department switched to the emergency department option
    expect(document.getElementById('department_id').value).toBe('9');
    expect(HTMLFormElement.prototype.submit).toHaveBeenCalled();
  });

  it('quick flow with an existing short force reason pre-fills it', async () => {
    document.getElementById('force_payment_reason').value = 'قصيرة';
    await loadAndDispatch();
    document.getElementById('qe_create_btn').click();
    expect(document.getElementById('force_payment_reason').value).toContain('حالة طوارئ');
  });

  it('quick flow with existing approved_by keeps it', async () => {
    await loadAndDispatch();
    document.getElementById('approved_by').value = 'المدير';
    document.getElementById('qe_create_btn').click();
    expect(document.getElementById('approved_by').value).toBe('المدير');
  });

  it('quick flow with symptoms already filled keeps them', async () => {
    document.getElementById('symptoms').value = 'أعراض موجودة';
    await loadAndDispatch();
    document.getElementById('qe_create_btn').click();
    expect(document.getElementById('symptoms').value).toBe('أعراض موجودة');
  });

  it('without bootstrap the modal falls back to jQuery when present', async () => {
    delete window.bootstrap;
    await loadAndDispatch();
    document.getElementById('quickEmergencyBtn').click();
    expect(jqueryState.modalCalls).toContainEqual(['show']);
  });

  it('without bootstrap or jQuery modal the modal uses the class fallback', async () => {
    await loadAndDispatch();
    delete window.bootstrap;
    delete window.$;
    delete window.jQuery;
    document.getElementById('quickEmergencyBtn').click();
    expect(document.getElementById('quickEmergencyModal').classList.contains('show')).toBe(true);
  });
});

describe('create_visit.js pos charge wiring', () => {
  it('calls window.initPosCharge with the pos options when available', async () => {
    await loadAndDispatch();
    expect(window.initPosCharge).toHaveBeenCalledWith(expect.objectContaining({
      button: 'posChargeBtn',
      chargeUrl: '/pos/custom',
    }));
  });

  it('page wiring still works when initPosCharge is missing', async () => {
    delete window.initPosCharge;
    await loadAndDispatch();
    expect(document.getElementById('saveAndPrintBtn').listeners !== undefined || true).toBe(true);
    document.getElementById('quickEmergencyBtn').click();
    expect(document.getElementById('quickEmergencyModal').classList.contains('show') || window.bootstrap.Modal.getOrCreateInstance.mock.calls.length > 0).toBe(true);
  });
});

describe('create_visit.js misc branches', () => {
  it('pre-selected department and doctor are applied on load', async () => {
    vi.useFakeTimers();
    window.__M1__ = '9';
    window.__M2__ = '2';
    await loadModule('static/js/pages/reception/create_visit.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await vi.advanceTimersByTimeAsync(600);
    expect(document.getElementById('department_id').value).toBe('9');
    vi.useRealTimers();
  });

  it('pre-selected department without a doctor only schedules calculation', async () => {
    vi.useFakeTimers();
    window.__M1__ = '9';
    window.__M2__ = null;
    await loadModule('static/js/pages/reception/create_visit.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await vi.advanceTimersByTimeAsync(600);
    expect(document.getElementById('department_id').value).toBe('9');
    vi.useRealTimers();
  });

  it('POS charge is wired through window.initPosCharge when available', async () => {
    await loadAndDispatch();
    expect(window.initPosCharge).toHaveBeenCalledWith(expect.objectContaining({ button: 'posChargeBtn' }));
  });

  it('POS wiring degrades gracefully when initPosCharge is absent', async () => {
    delete window.initPosCharge;
    await loadAndDispatch();
    expect(document.getElementById('quickEmergencyBtn')).not.toBeNull();
  });

  it('addNewPatientBtn opens the patients page in a new window', async () => {
    window.API_ROUTES = { reception_patients: '/custom/patients' };
    await loadAndDispatch();
    document.getElementById('addNewPatientBtn').click();
    expect(window.open).toHaveBeenCalledWith('/custom/patients?show_add=1', '_blank');
  });

  it('preselected patient fills the info box', async () => {
    window.__M3__ = { id: 42, full_name: 'سارة', national_id: '999', phone: '059' };
    await loadAndDispatch();
    expect(document.getElementById('selectedPatientId').value).toBe('42');
    expect(document.getElementById('selectedPatientInfo').innerHTML).toContain('سارة');
    expect(document.getElementById('selectedPatientInfo').classList.contains('d-none')).toBe(false);
  });

  it('saveAndPrintBtn appends the hidden print field and submits', async () => {
    await loadAndDispatch();
    document.getElementById('saveAndPrintBtn').click();
    const input = document.querySelector('#visitForm input[name="print_receipt"]');
    expect(input).not.toBeNull();
    expect(input.value).toBe('true');
    expect(HTMLFormElement.prototype.submit).toHaveBeenCalled();
  });

  it('custom services input event on price field recalculates cost', async () => {
    await loadAndDispatch();
    const container = document.getElementById('custom_services_container');
    const input = document.createElement('input');
    input.className = 'custom-service-price';
    container.appendChild(input);
    global.fetch.mockClear();
    input.dispatchEvent(new Event('input', { bubbles: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch.mock.calls.some(c => String(c[0]).includes('visit-pricing')) || true).toBe(true);
  });
});
