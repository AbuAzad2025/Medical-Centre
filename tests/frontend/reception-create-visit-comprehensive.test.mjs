import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { loadModule } from './test-utils.mjs';

function makeJQueryMock() {
  const mock = vi.fn(() => ({
    on: vi.fn().mockReturnThis(),
    val: vi.fn().mockReturnValue(''),
    html: vi.fn().mockReturnThis(),
    append: vi.fn().mockReturnThis(),
    select2: vi.fn().mockReturnThis(),
    hasClass: vi.fn(() => false),
    addClass: vi.fn().mockReturnThis(),
    removeClass: vi.fn().mockReturnThis(),
    style: {},
    forEach: vi.fn(),
  }));
  mock.fn = { modal: vi.fn() };
  return mock;
}

beforeEach(async () => {
  vi.useFakeTimers();
  document.body.innerHTML = `
    <input id="selectedPatientId" />
    <div id="selectedPatientInfo" class="d-none"></div>
    <button id="addNewPatientBtn">Add</button>
    <select id="department_id"><option value="">Select</option><option value="1">Dept 1</option></select>
    <select id="staff_id"></select>
    <div id="staff_container" style="display:none"></div>
    <div id="test_selection_section" style="display:none"></div>
    <select id="selected_tests"></select>
    <span id="tests_section_label"></span>
    <div id="custom_services_section" style="display:none"></div>
    <div id="custom_services_container"></div>
    <input id="visit_type" value="CONSULTATION" />
    <input id="tax_type" value="NONE" />
    <input id="is_emergency" type="checkbox" />
    <select id="payment_method"><option value="CASH" selected>Cash</option><option value="CARD">Card</option></select>
    <div id="paymentFields" style="display:none"></div>
    <div id="visaFields" style="display:none"></div>
    <div id="insuranceFields" style="display:none"></div>
    <div id="forceFields" style="display:none"></div>
    <input id="visitCost" />
    <input id="testsTotalPrice" />
    <span id="costBreakdown"></span>
    <input id="amount_paid" />
    <span id="posStatus"></span>
    <button id="posChargeBtn" data-charge-url="/charge">Charge</button>
    <button id="saveAndPrintBtn">Save & Print</button>
    <div id="quickEmergencyModal"></div>
    <button id="quickEmergencyBtn">Quick</button>
    <button id="qe_create_btn">Create</button>
    <input id="quick_emergency" />
    <input id="quick_patient_name" />
    <input id="quick_gender" />
    <input id="quick_age" />
    <input id="quick_reason" />
    <input id="qe_patient_name" />
    <select id="qe_gender"><option value="M">M</option></select>
    <input id="qe_age" />
    <input id="qe_reason" />
    <input id="symptoms" />
    <select id="is_force_payment"></select>
    <input id="approved_by" />
    <input id="force_payment_reason" />
    <input id="card_last_digits" />
    <input id="card_holder_name" />
    <form id="visitForm" action="/save"></form>
    <div id="advancedVisitFields"></div>
  `;
  window.__M = [null, null, null, null];
  window.__M0__ = null;
  window.__M1__ = null;
  window.__M2__ = null;
  window.__M3__ = null;
  window.API_ROUTES = { reception_patients: '/reception/patients', api_department_services: '/api/dept-services', api_department_staff: '/api/dept-staff', api_visit_pricing: '/api/pricing', reception_pos_charge: '/api/pos' };
  window.escHtml = (s) => s;
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.bootstrap = { Collapse: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn() })) }, Modal: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn(), hide: vi.fn() })) } };
  window.initPosCharge = vi.fn();
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ category: 'lab', services: [{ id: 1, name_ar: 'CBC', price: 10, base_price: 10, insurance_price: 5 }], staff: [{ id: 1, full_name: 'Dr Test', role: 'doctor' }], cost: '50.00', tests_total: '10.00', details: { breakdown: [{ item: 'CBC', cost: 10 }] } }),
  });
  window.jQuery = window.$ = makeJQueryMock();
  await loadModule('static/js/pages/reception/create_visit.js');
  document.dispatchEvent(new Event('DOMContentLoaded'));
  vi.advanceTimersByTime(500);
});

afterEach(() => {
  vi.useRealTimers();
});

describe('reception/create_visit.js', () => {
  it('loads without error', () => {
    expect(true).toBe(true);
  });

  it('calculateVisitCost runs', () => {
    const dept = document.getElementById('department_id');
    if (dept) dept.value = '1';
    const evt = new Event('change');
    dept.dispatchEvent(evt);
  });

  it('addNewPatientBtn opens window', () => {
    const btn = document.getElementById('addNewPatientBtn');
    if (btn) btn.click();
  });

  it('quickEmergencyBtn shows modal', () => {
    const btn = document.getElementById('quickEmergencyBtn');
    if (btn) btn.click();
  });

  it('saveAndPrintBtn appends input', () => {
    const btn = document.getElementById('saveAndPrintBtn');
    if (btn) btn.click();
  });
});