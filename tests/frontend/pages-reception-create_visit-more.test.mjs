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
  if (entry && entry.handlers.get(evt)) entry.handlers.get(evt).forEach(cb => cb.call(el, { type: evt }));
}

function baseDom() {
  document.body.innerHTML = `
    <input id="selectedPatientId" value="">
    <div id="selectedPatientInfo" class="d-none"></div>
    <button id="addNewPatientBtn">Add</button>
    <select id="department_id"><option value="">اختر</option><option value="9">الطوارئ</option><option value="3">العيون</option></select>
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
    <select id="payment_method"><option value="">none</option><option value="CASH" selected>CASH</option><option value="CARD">CARD</option><option value="CRYPTO">CRYPTO</option></select>
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
      <input id="force_payment_reason" value="حالة طوارئ عاجلة جداً وملحّة">
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
  HTMLFormElement.prototype.submit = vi.fn();
  global.fetch = vi.fn((url) => {
    const u = String(url);
    if (u.includes('department-services')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ category: 'lab', services: [{ id: 11, name_ar: 'CBC', price: 100, base_price: 120, insurance_price: null }] }) });
    if (u.includes('department-staff')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ staff: [{ id: 1, full_name: 'د أسامة', role: 'doctor' }] }) });
    if (u.includes('visit-pricing')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ cost: '250.00', tests_total: 0, details: { breakdown: [{ item: 'CBC', cost: 120 }] } }) });
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

describe('create_visit.js remaining branch arms', () => {
  it('service without insurance_price sets insurancePrice dataset to empty string', async () => {
    await loadAndDispatch();
    document.getElementById('department_id').value = '9';
    trigger('#department_id', 'change');
    await new Promise(r => setTimeout(r, 40));
    const opt = document.querySelector('#selected_tests option');
    expect(opt.dataset.insurancePrice).toBe('');
  });

  it('tests_total 0 falls back to summing the selected test datasets', async () => {
    await loadAndDispatch();
    document.getElementById('department_id').value = '9';
    trigger('#department_id', 'change');
    await new Promise(r => setTimeout(r, 40));
    document.querySelector('#selected_tests option').selected = true;
    document.getElementById('tax_type').dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 40));
    expect(document.getElementById('testsTotalPrice').value).toBe('120.00');
  });

  it('option without a basePrice dataset contributes zero to insurance sums', async () => {
    await loadAndDispatch();
    document.getElementById('department_id').value = '9';
    trigger('#department_id', 'change');
    await new Promise(r => setTimeout(r, 40));
    const testsSelect = document.getElementById('selected_tests');
    testsSelect.innerHTML = '<option value="99" selected>Mystery</option>';
    document.getElementById('tax_type').dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 40));
    expect(document.getElementById('testsTotalPrice').value).toBe('0.00');
  });

  it('payment_method with an empty value falls back to cash for the pricing request', async () => {
    document.getElementById('payment_method').innerHTML = '<option value="">none</option><option value="CASH">CASH</option>';
    document.getElementById('payment_method').value = '';
    await loadAndDispatch();
    document.getElementById('department_id').value = '9';
    document.getElementById('payment_method').value = '';
    trigger('#department_id', 'change');
    await new Promise(r => setTimeout(r, 40));
    const call = global.fetch.mock.calls.find(c => String(c[0]).includes('visit-pricing'));
    expect(call[0]).toContain('payment_method=cash');
  });

  it('custom price row with empty price posts zero for that row', async () => {
    await loadAndDispatch();
    const container = document.getElementById('custom_services_container');
    const row = document.createElement('div');
    row.className = 'custom-service-row';
    row.innerHTML = '<input name="custom_service_name" value="أشعة"><input name="custom_service_price" value="">';
    container.appendChild(row);
    document.getElementById('department_id').value = '9';
    trigger('#department_id', 'change');
    await new Promise(r => setTimeout(r, 40));
    const call = global.fetch.mock.calls.find(c => String(c[0]).includes('visit-pricing'));
    expect(call[0]).toContain('custom_service_price=0');
  });

  it('custom service row with a name but no price input still posts a zero price', async () => {
    await loadAndDispatch();
    const container = document.getElementById('custom_services_container');
    const row = document.createElement('div');
    row.className = 'custom-service-row';
    row.innerHTML = '<input name="custom_service_name" value="تحليل">';
    container.appendChild(row);
    document.getElementById('department_id').value = '9';
    trigger('#department_id', 'change');
    await new Promise(r => setTimeout(r, 40));
    const call = global.fetch.mock.calls.find(c => String(c[0]).includes('visit-pricing'));
    expect(call[0]).toContain('custom_service_price=0');
  });

  it('unknown method with no required fields does not block the form', async () => {
    await loadAndDispatch();
    document.getElementById('payment_method').value = 'CRYPTO';
    document.getElementById('visitForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    expect(window.Swal.fire).not.toHaveBeenCalled();
  });

  it('posChargeBtn missing falls back to API_ROUTES for the charge URL', async () => {
    window.API_ROUTES = { reception_pos_charge: '/custom/pos-charge' };
    document.getElementById('posChargeBtn').remove();
    await loadAndDispatch();
    expect(window.initPosCharge).toHaveBeenCalledWith(expect.objectContaining({ chargeUrl: '/custom/pos-charge' }));
  });

  it('posChargeBtn without data-charge-url and no API_ROUTES uses the default endpoint', async () => {
    document.getElementById('posChargeBtn').removeAttribute('data-charge-url');
    await loadAndDispatch();
    expect(window.initPosCharge).toHaveBeenCalledWith(expect.objectContaining({ chargeUrl: '/reception/pos/charge' }));
  });

  it('missing quick emergency modal shows no modal instead of crashing', async () => {
    document.getElementById('quickEmergencyModal').remove();
    await loadAndDispatch();
    expect(() => document.getElementById('quickEmergencyBtn').click()).not.toThrow();
    expect(window.bootstrap.Modal.getOrCreateInstance).not.toHaveBeenCalled();
  });

  it('quick create flow without bootstrap falls back to jQuery modal hide', async () => {
    delete window.bootstrap;
    await loadAndDispatch();
    document.getElementById('qe_create_btn').click();
    await new Promise(r => setTimeout(r, 40));
    expect(jqueryState.modalCalls).toContainEqual(['hide']);
  });

  it('option with empty text is ignored when detecting the emergency department', async () => {
    document.getElementById('department_id').innerHTML = '<option value=""></option><option value="4">قسم آخر</option>';
    document.getElementById('visit_type').value = 'FOLLOWUP';
    await loadAndDispatch();
    expect(() => document.getElementById('qe_create_btn').click()).not.toThrow();
  });
});
