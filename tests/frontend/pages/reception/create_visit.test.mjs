import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <form id="visitForm">
      <select id="department_id"><option value="">Select</option></select>
      <select id="staff_id"><option value="">Select</option></select>
      <div id="staff_container"></div>
      <div id="test_selection_section" style="display:none"></div>
      <select id="selected_tests"></select>
      <select id="visit_type"><option value="REGULAR"></option></select>
      <select id="tax_type"><option value="NONE"></option></select>
      <input type="checkbox" id="is_emergency" />
      <select id="payment_method"><option value="CASH"></option><option value="CARD"></option><option value="INSURANCE"></option><option value="FORCE"></option></select>
      <div id="paymentFields" style="display:none"></div>
      <div id="insuranceFields" style="display:none"></div>
      <div id="forceFields" style="display:none"></div>
      <div id="visaFields" style="display:none"></div>
      <input id="visitCost" value="0.00" />
      <input id="testsTotalPrice" value="" />
      <span id="costBreakdown"></span>
      <input id="selectedPatientId" value="" />
      <div id="selectedPatientInfo" class="d-none"></div>
      <button id="addNewPatientBtn"></button>
      <div id="custom_services_container"></div>
      <div id="custom_services_section" style="display:none"></div>
      <div id="advancedVisitFields"></div>
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
      <div id="posStatus"></div>
      <input id="amount_paid" value="" />
      <input id="card_last_digits" value="" />
      <input id="card_holder_name" value="" />
      <input id="expiry_date" value="" />
      <input id="insurance_provider" value="" />
      <input id="insurance_policy_number" value="" />
      <input id="force_payment_reason" value="" />
      <input id="approved_by" value="" />
      <input id="symptoms" value="" />
    </form>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M0__ = '';
  window.__M1__ = '';
  window.__M2__ = '';
  window.__M3__ = null;
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.Toast = { fire: vi.fn() };
  window.initPosCharge = vi.fn();
  window.bootstrap = {
    Modal: { getOrCreateInstance: () => ({ show: vi.fn(), hide: vi.fn() }) },
    Collapse: { getOrCreateInstance: () => ({ show: vi.fn() }) }
  };
  const mockJqObj = { select2: vi.fn(), on: vi.fn(), modal: vi.fn() };
  const jq = vi.fn(() => mockJqObj);
  jq.fn = { select2: vi.fn(), modal: vi.fn() };
  window.$ = jq;
});

describe('reception/create_visit.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/reception/create_visit.js');
  });

  test('paymentFields element exists', async () => {
    await loadScript('static/js/pages/reception/create_visit.js');
    expect(document.getElementById('paymentFields')).not.toBeNull();
  });

  test('custom_services_container exists', async () => {
    await loadScript('static/js/pages/reception/create_visit.js');
    expect(document.getElementById('custom_services_container')).not.toBeNull();
  });

  test('quickEmergencyBtn is present', async () => {
    await loadScript('static/js/pages/reception/create_visit.js');
    expect(document.getElementById('quickEmergencyBtn')).not.toBeNull();
  });

  test('saveAndPrintBtn is present', async () => {
    await loadScript('static/js/pages/reception/create_visit.js');
    expect(document.getElementById('saveAndPrintBtn')).not.toBeNull();
  });
});
