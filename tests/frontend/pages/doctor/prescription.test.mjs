import { describe, test, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from '../../test-utils.mjs';

let pendingDomListeners = [];
const realAdd = document.addEventListener.bind(document);
function triggerDomContentLoaded() {
  for (const listener of pendingDomListeners) listener();
}

async function setup() {
  const mod = await loadModule('static/js/pages/doctor/prescription.js');
  triggerDomContentLoaded();
  return mod;
}

beforeEach(() => {
  document.body.innerHTML = `
    <table id="rxItemsTable"><tbody></tbody></table>
    <button id="addRxItemBtn"></button>
    <select id="templateSelect"><option value="">None</option><option value="1">Template 1</option></select>
    <button id="applyTemplateBtn"></button>
    <form id="prescriptionForm" action="/test" data-success-url="#/success">
      <input name="csrf_token" value="t"/>
    </form>
    <div id="prescriptionError" class="d-none"></div>
  `;
  window.__M0__ = [{ id: '1', name: 'Template 1', items: [{ medication_id: '10', medication_label: 'Aspirin', dosage: '1 tab', frequency: 'daily', duration_days: 7, quantity: 1, instructions: 'After meal' }] }];
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.Toast = { fire: vi.fn() };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
  pendingDomListeners = [];
  document.addEventListener = (type, listener, options) => {
    if (type === 'DOMContentLoaded') {
      pendingDomListeners.push(listener);
      return;
    }
    return realAdd(type, listener, options);
  };
});

afterEach(() => {
  vi.useRealTimers();
});

describe('doctor/prescription.js', () => {
  test('parseMedicationRef returns parts', async () => {
    const { parseMedicationRef } = await setup();
    expect(parseMedicationRef('')).toEqual({ id: '', label: '' });
    expect(parseMedicationRef(null)).toEqual({ id: '', label: '' });
    expect(parseMedicationRef('42|Aspirin 100mg')).toEqual({ id: '42', label: 'Aspirin 100mg' });
    expect(parseMedicationRef('Aspirin 100mg')).toEqual({ id: '', label: 'Aspirin 100mg' });
  });

  test('createRxRow appends a row and parses medication ref', async () => {
    const { createRxRow } = await setup();
    document.querySelector('#rxItemsTable tbody').innerHTML = '';
    createRxRow({ medication_id: '10', medication_label: 'Amoxicillin', dosage: '500mg', frequency: 'TID', duration_days: 5, quantity: 2, instructions: 'after meal' });
    const table = document.querySelector('#rxItemsTable tbody');
    expect(table.children.length).toBe(1);
    const row = table.querySelector('tr');
    expect(row.querySelector('.medication-id').value).toBe('10');
    expect(row.querySelector('[name="item_dosage[]"]').value).toBe('500mg');
  });

  test('createRxRow parses ref format', async () => {
    const { createRxRow, parseMedicationRef } = await setup();
    document.querySelector('#rxItemsTable tbody').innerHTML = '';
    createRxRow({ medication_ref: '55|Metformin 500mg' });
    const row = document.querySelector('#rxItemsTable tbody tr');
    expect(row.querySelector('.medication-id').value).toBe(parseMedicationRef('55|Metformin 500mg').id);
  });

  test('createRxRow remove button removes row', async () => {
    const { createRxRow } = await setup();
    document.querySelector('#rxItemsTable tbody').innerHTML = '';
    createRxRow();
    createRxRow();
    expect(document.querySelectorAll('#rxItemsTable tbody tr').length).toBe(2);
    const rows = document.querySelectorAll('#rxItemsTable tbody tr');
    rows[0].querySelector('.remove-item-btn').click();
    expect(document.querySelectorAll('#rxItemsTable tbody tr').length).toBe(1);
  });

  test('ensureAtLeastOneRow adds a row when empty', async () => {
    const { ensureAtLeastOneRow } = await setup();
    document.querySelector('#rxItemsTable tbody').innerHTML = '';
    ensureAtLeastOneRow();
    expect(document.querySelectorAll('#rxItemsTable tbody tr').length).toBe(1);
  });

  test('addRxItemBtn creates a new row', async () => {
    await setup();
    document.querySelector('#rxItemsTable tbody').innerHTML = '';
    document.getElementById('addRxItemBtn').click();
    expect(document.querySelectorAll('#rxItemsTable tbody tr').length).toBe(1);
  });

  test('applyTemplateBtn loads template rows', async () => {
    await setup();
    document.querySelector('#rxItemsTable tbody').innerHTML = '';
    document.getElementById('templateSelect').value = '1';
    document.getElementById('applyTemplateBtn').click();
    expect(document.querySelectorAll('#rxItemsTable tbody tr').length).toBeGreaterThanOrEqual(1);
  });

  test('showSafetyModal renders and override calls onOverride', async () => {
    const { showSafetyModal } = await setup();
    const onOverride = vi.fn();
    showSafetyModal([{ severity: 'hard_stop', message: 'Drug interaction' }], onOverride);
    const modal = document.getElementById('safetyOverrideModal');
    expect(modal).toBeTruthy();
    const textarea = document.getElementById('overrideNote');
    textarea.value = 'Patient stable on this combo';
    textarea.dispatchEvent(new Event('input', { bubbles: true }));
    modal.querySelector('.btn-danger').click();
    expect(onOverride).toHaveBeenCalledWith('Patient stable on this combo');
  });

  test('showSafetyModal cancel button removes modal', async () => {
    const { showSafetyModal } = await setup();
    showSafetyModal([{ severity: 'soft_stop', message: 'Caution' }], vi.fn());
    const modal = document.getElementById('safetyOverrideModal');
    modal.querySelector('.btn-secondary').click();
    expect(document.getElementById('safetyOverrideModal')).toBeNull();
  });

  test('submit with no items does not call fetch', async () => {
    await setup();
    document.querySelector('#rxItemsTable tbody').innerHTML = '';
    document.getElementById('prescriptionForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 20));
    expect(global.fetch).not.toHaveBeenCalled();
  });

  test('submit success redirects', async () => {
    document.body.innerHTML = '';
    document.body.innerHTML = `
      <table id="rxItemsTable"><tbody></tbody></table>
      <form id="prescriptionForm" action="/test" data-success-url="#/success">
        <input name="csrf_token" value="t"/>
        <input type="hidden" class="medication-id" value="10"/>
      </form>
      <div id="prescriptionError" class="d-none"></div>
    `;
    await setup();
    const form = document.getElementById('prescriptionForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
  });

  test('showSafetyModal Escape key removes modal', async () => {
    const { showSafetyModal } = await loadModule('static/js/pages/doctor/prescription.js');
    showSafetyModal([{ severity: 'hard_stop', message: 'interaction' }], vi.fn());
    const modal = document.getElementById('safetyOverrideModal');
    expect(modal).toBeTruthy();
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    expect(document.getElementById('safetyOverrideModal')).toBeNull();
  });

  test('refInput input parses ref into medication-id', async () => {
    const mod = await loadModule('static/js/pages/doctor/prescription.js');
    triggerDomContentLoaded();
    document.querySelector('#rxItemsTable tbody').innerHTML = '';
    mod.createRxRow();
    const refInput = document.querySelector('.medication-ref');
    const idInput = document.querySelector('.medication-id');
    refInput.value = '55|Metformin 500mg';
    refInput.dispatchEvent(new Event('input', { bubbles: true }));
    expect(idInput.value).toBe('55');
    refInput.value = '';
    refInput.dispatchEvent(new Event('input', { bubbles: true }));
    expect(idInput.value).toBe('');
  });

  test('submit hard stops shows safety modal', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, hard_stops: [{ severity: 'hard_stop', message: 'allergy' }] }) });
    document.body.innerHTML = '';
    document.body.innerHTML = `
      <table id="rxItemsTable"><tbody></tbody></table>
      <form id="prescriptionForm" action="/test" data-success-url="#/success">
        <input name="csrf_token" value="t"/>
        <input type="hidden" class="medication-id" value="10"/>
      </form>
      <div id="prescriptionError" class="d-none"></div>
    `;
    await setup();
    const form = document.getElementById('prescriptionForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('safetyOverrideModal')).toBeTruthy();
  });

  test('submit failure shows prescriptionError', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    document.body.innerHTML = '';
    document.body.innerHTML = `
      <table id="rxItemsTable"><tbody></tbody></table>
      <form id="prescriptionForm" action="/test" data-success-url="#/success">
        <input name="csrf_token" value="t"/>
        <input type="hidden" class="medication-id" value="10"/>
      </form>
      <div id="prescriptionError" class="d-none"></div>
    `;
    await setup();
    const form = document.getElementById('prescriptionForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('prescriptionError').classList.contains('d-none')).toBe(false);
  });
});