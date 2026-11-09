import { describe, test, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

// Covers the behaviour in create_visit.js that the main suites don't reach:
// the custom-service-row add/remove flow wired through the global data-action
// delegation, the select2 language callbacks, and window.saveVisit.

function baseDom() {
  document.body.innerHTML = `
    <form id="visitForm">
      <select id="department_id"><option value="">Select</option><option value="7">Emergency</option></select>
      <select id="staff_id"><option value="">Select</option></select>
      <div id="staff_container"></div>
      <div id="test_selection_section" style="display:none"></div>
      <select id="selected_tests" multiple></select>
      <select id="visit_type"><option value="REGULAR"></option></select>
      <select id="tax_type"><option value="NONE"></option></select>
      <input type="checkbox" id="is_emergency" />
      <select id="payment_method"><option value="CASH"></option></select>
      <div id="paymentFields" style="display:none"></div>
      <div id="visaFields" style="display:none"></div>
      <div id="insuranceFields" style="display:none"></div>
      <div id="forceFields" style="display:none"></div>
      <div id="advancedVisitFields"></div>
      <input id="visitCost" value="0.00" />
      <input id="testsTotalPrice" value="" />
      <span id="costBreakdown"></span>
      <button type="button" id="addServiceBtn" data-action="add-service-row">+</button>
      <div id="custom_services_container"></div>
      <div id="custom_services_section" style="display:none"></div>
      <button id="saveAndPrintBtn"></button>
      <button id="quickEmergencyBtn"></button>
      <button id="qe_create_btn"></button>
      <input id="quick_emergency" value="" />
      <input id="qe_patient_name" value="" />
      <input id="qe_reason" value="" />
      <input id="qe_reason2" value="" />
      <input id="symptoms" value="" />
      <div id="tests_section_label"></div>
    </form>
  `;
}

function makeJq() {
  const select2Spy = vi.fn();
  const handlers = {};
  const jq = vi.fn((sel) => {
    if (!handlers[sel]) handlers[sel] = { event: {} };
    const bucket = handlers[sel];
    return {
      on: vi.fn((event, cb) => { (bucket.event[event] = bucket.event[event] || []).push(cb); }),
      hasClass: vi.fn(() => false),
      select2: select2Spy,
      modal: vi.fn(),
    };
  });
  jq.fn = { select2: select2Spy, modal: vi.fn() };
  jq.select2Spy = select2Spy;
  jq.trigger = (sel, event, thisVal) => {
    const bucket = handlers[sel];
    if (!bucket) return;
    (bucket.event[event] || []).forEach((cb) => cb.call(thisVal || {}));
  };
  return jq;
}

beforeEach(() => {
  baseDom();
  window.__M0__ = '';
  window.__M1__ = '';
  window.__M2__ = '';
  window.__M3__ = null;
  window.escHtml = (s) => String(s ?? '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.Toast = { fire: vi.fn() };
  window.notify = { success: vi.fn(), error: vi.fn(), warning: vi.fn() };
  window.initPosCharge = vi.fn();
  window.bootstrap = { Modal: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn(), hide: vi.fn() })) } };
  window.$ = makeJq();
  global.fetch = vi.fn((url) => {
    const u = String(url);
    if (u.includes('department-services')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ category: 'lab', services: [] }) });
    }
    if (u.includes('visit-pricing')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ cost: '0.00' }) });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
  });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('reception/create_visit.js custom services + exports', () => {
  test('addServiceRow appends a row with name and price inputs', async () => {
    await loadModule('static/js/pages/reception/create_visit.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(typeof window.addServiceRow).toBe('function');
    window.addServiceRow();
    const rows = document.querySelectorAll('.custom-service-row');
    expect(rows.length).toBe(1);
    const row = rows[0];
    expect(row.querySelector('input[name="custom_service_name"]')).not.toBeNull();
    const price = row.querySelector('input[name="custom_service_price"]');
    expect(price).not.toBeNull();
    expect(price.value).toBe('0');
    expect(row.id).toMatch(/^custom_service_row_\d+$/);
  });

  test('addServiceRow can be triggered through the data-action delegation', async () => {
    await loadModule('static/js/pages/reception/create_visit.js');
    await loadModule('static/js/events.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const button = document.getElementById('addServiceBtn');
    button.click();
    expect(document.querySelectorAll('.custom-service-row').length).toBe(1);
  });

  test('removeCustomServiceRow removes the row and recalculates cost', async () => {
    await loadModule('static/js/pages/reception/create_visit.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    window.addServiceRow();
    window.addServiceRow();
    const rows = document.querySelectorAll('.custom-service-row');
    expect(rows.length).toBe(2);
    const firstId = rows[0].id;
    window.removeCustomServiceRow(firstId);
    expect(document.querySelectorAll('.custom-service-row').length).toBe(1);
    expect(document.getElementById(firstId)).toBeNull();
  });

  test('removeCustomServiceRow ignores an unknown rowId without crashing', async () => {
    await loadModule('static/js/pages/reception/create_visit.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(() => window.removeCustomServiceRow('custom_service_row_99999')).not.toThrow();
  });

  test('removeCustomServiceRow through data-action removes only that row', async () => {
    await loadModule('static/js/pages/reception/create_visit.js');
    await loadModule('static/js/events.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    window.addServiceRow();
    window.addServiceRow();
    const rows = [...document.querySelectorAll('.custom-service-row')];
    const removeButton = rows[1].querySelector('[data-action="remove-custom-service-row"]');
    expect(removeButton).not.toBeNull();
    removeButton.click();
    expect(document.querySelectorAll('.custom-service-row').length).toBe(1);
    expect(rows[1].isConnected).toBe(false);
    expect(rows[0].isConnected).toBe(true);
  });

  test('select2 language callbacks return Arabic strings the user sees', async () => {
    await loadModule('static/js/pages/reception/create_visit.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const dept = document.getElementById('department_id');
    dept.value = '7';
    window.$.trigger('#department_id', 'change', dept);
    await new Promise((r) => setTimeout(r, 40));
    const select2Calls = window.$.select2Spy.mock.calls.map((call) => call[0]).filter(Boolean);
    const languageConfigs = select2Calls.map((cfg) => cfg && cfg.language).filter(Boolean);
    expect(languageConfigs.length).toBeGreaterThan(0);
    for (const lang of languageConfigs) {
      expect(typeof lang.searching).toBe('function');
      expect(typeof lang.noResults).toBe('function');
      expect(lang.searching()).toBe('جاري البحث...');
      expect(lang.noResults()).toBe('لا توجد نتائج');
    }
  });

  test('window.saveVisit submits visitForm via requestSubmit', async () => {
    await loadModule('static/js/pages/reception/create_visit.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const form = document.getElementById('visitForm');
    const requestSubmitSpy = vi.fn();
    form.requestSubmit = requestSubmitSpy;
    window.saveVisit();
    expect(requestSubmitSpy).toHaveBeenCalledTimes(1);
  });
});
