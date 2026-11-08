import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

let pendingDomListeners = [];
const realAdd = document.addEventListener.bind(document);

beforeEach(() => {
  document.body.innerHTML = `
    <table id="rxItemsTable"><tbody></tbody></table>
    <form id="prescriptionForm" action="/rx/save" data-success-url="/rx/done"></form>
    <div id="prescriptionError" class="d-none"></div>
    <button id="addRxItemBtn">Add item</button>
    <select id="templateSelect"><option value="">none</option><option value="1">Template 1</option><option value="x">Unknown</option></select>
    <button id="applyTemplateBtn">Apply</button>
    <datalist id="medications_list"></datalist>
  `;
  window.__M = [];
  window.__M0__ = [{ id: '1', name: 'Template 1', items: [{ medication_id: '10', medication_label: 'Aspirin', dosage: '1 tab', frequency: 'daily' }] }];
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s ?? '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
  pendingDomListeners = [];
  document.addEventListener = (type, listener, options) => {
    if (type === 'DOMContentLoaded') { pendingDomListeners.push(listener); return; }
    return realAdd(type, listener, options);
  };
});

afterEach(() => {
  document.addEventListener = realAdd;
  vi.useRealTimers();
});

function fireDomContentLoaded() {
  for (const listener of pendingDomListeners) listener();
}

describe('prescription.js parseMedicationRef branches', () => {
  it('empty and nullish values return empty parts', async () => {
    const { parseMedicationRef } = await loadModule('static/js/pages/doctor/prescription.js');
    expect(parseMedicationRef('')).toEqual({ id: '', label: '' });
    expect(parseMedicationRef('   ')).toEqual({ id: '', label: '' });
    expect(parseMedicationRef(null)).toEqual({ id: '', label: '' });
    expect(parseMedicationRef(undefined)).toEqual({ id: '', label: '' });
  });

  it('id|label splits on the first pipe only', async () => {
    const { parseMedicationRef } = await loadModule('static/js/pages/doctor/prescription.js');
    expect(parseMedicationRef('10|Aspirin')).toEqual({ id: '10', label: 'Aspirin' });
    expect(parseMedicationRef('10|Aspirin|Extra')).toEqual({ id: '10', label: 'Aspirin|Extra' });
    expect(parseMedicationRef('10|')).toEqual({ id: '10', label: '' });
    expect(parseMedicationRef('|OnlyLabel')).toEqual({ id: '', label: 'OnlyLabel' });
    expect(parseMedicationRef('|')).toEqual({ id: '', label: '' });
  });

  it('value without pipe is treated as label only', async () => {
    const { parseMedicationRef } = await loadModule('static/js/pages/doctor/prescription.js');
    expect(parseMedicationRef('JustText')).toEqual({ id: '', label: 'JustText' });
  });
});

describe('prescription.js showSafetyModal branches', () => {
  it('removes an existing modal before creating a new one', async () => {
    document.body.insertAdjacentHTML('beforeend', '<div id="safetyOverrideModal">stale</div>');
    const { showSafetyModal } = await loadModule('static/js/pages/doctor/prescription.js');
    showSafetyModal([{ severity: 'warning', message: 'mild' }], vi.fn());
    expect(document.querySelectorAll('#safetyOverrideModal').length).toBe(1);
    expect(document.getElementById('safetyOverrideModal').textContent).toContain('تنبيه أمان');
  });

  it('hard_stop severity renders the danger badge, others render warning', async () => {
    const { showSafetyModal } = await loadModule('static/js/pages/doctor/prescription.js');
    showSafetyModal([{ severity: 'hard_stop', message: 'fatal' }, { severity: 'moderate', message: 'mild' }], vi.fn());
    const html = document.getElementById('safetyOverrideModal').innerHTML;
    expect(html).toContain('list-group-item-danger');
    expect(html).toContain('list-group-item-warning');
  });

  it('confirm button enables only after a non-empty note is typed', async () => {
    const { showSafetyModal } = await loadModule('static/js/pages/doctor/prescription.js');
    showSafetyModal([{ severity: 'hard_stop', message: 'x' }], vi.fn());
    const confirmBtn = document.querySelector('#safetyOverrideModal .btn-danger');
    const noteInput = document.querySelector('#overrideNote');
    expect(confirmBtn.disabled).toBe(true);
    noteInput.value = 'real reason';
    noteInput.dispatchEvent(new Event('input', { bubbles: true }));
    expect(confirmBtn.disabled).toBe(false);
    noteInput.value = '   ';
    noteInput.dispatchEvent(new Event('input', { bubbles: true }));
    expect(confirmBtn.disabled).toBe(true);
  });

  it('clicking confirm with an empty note does not call onOverride', async () => {
    const onOverride = vi.fn();
    const { showSafetyModal } = await loadModule('static/js/pages/doctor/prescription.js');
    showSafetyModal([{ severity: 'hard_stop', message: 'x' }], onOverride);
    const confirmBtn = document.querySelector('#safetyOverrideModal .btn-danger');
    confirmBtn.disabled = false;
    confirmBtn.click();
    expect(onOverride).not.toHaveBeenCalled();
  });

  it('confirm click disables the button, shows progress text and calls onOverride', async () => {
    const onOverride = vi.fn();
    const { showSafetyModal } = await loadModule('static/js/pages/doctor/prescription.js');
    showSafetyModal([{ severity: 'hard_stop', message: 'x' }], onOverride);
    const modal = document.getElementById('safetyOverrideModal');
    document.querySelector('#overrideNote').value = 'documented';
    const confirmBtn = modal.querySelector('.btn-danger');
    confirmBtn.disabled = false;
    confirmBtn.click();
    expect(confirmBtn.disabled).toBe(true);
    expect(confirmBtn.textContent).toContain('جاري');
    expect(onOverride).toHaveBeenCalledWith('documented');
  });

  it('Escape key removes the modal and the backdrop', async () => {
    const { showSafetyModal } = await loadModule('static/js/pages/doctor/prescription.js');
    showSafetyModal([{ severity: 'hard_stop', message: 'x' }], vi.fn());
    expect(document.querySelector('.modal-backdrop')).toBeTruthy();
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    expect(document.getElementById('safetyOverrideModal')).toBeNull();
    expect(document.querySelector('.modal-backdrop')).toBeNull();
  });

  it('cancel button removes the modal', async () => {
    const { showSafetyModal } = await loadModule('static/js/pages/doctor/prescription.js');
    showSafetyModal([{ severity: 'hard_stop', message: 'x' }], vi.fn());
    const cancel = document.querySelector('#safetyOverrideModal .btn-secondary');
    cancel.click();
    expect(document.getElementById('safetyOverrideModal')).toBeNull();
  });
});

describe('prescription.js createRxRow branches', () => {
  function seed(initial) {
    return loadModule('static/js/pages/doctor/prescription.js').then(mod => mod.createRxRow(initial));
  }

  it('initial medication_id with medication_label composes id|label ref', async () => {
    const mod = await loadModule('static/js/pages/doctor/prescription.js');
    mod.createRxRow({ medication_id: '42', medication_label: 'Amoxicillin', dosage: '2 tabs', frequency: 'twice', duration_days: 5, quantity: 2, instructions: 'after food' });
    const ref = document.querySelector('.medication-ref');
    expect(ref.value).toBe('42|Amoxicillin');
    expect(document.querySelector('.medication-id').value).toBe('42');
    expect(document.querySelector('[name="item_dosage[]"]').value).toBe('2 tabs');
    expect(document.querySelector('[name="item_frequency[]"]').value).toBe('twice');
    expect(document.querySelector('[name="item_duration_days[]"]').value).toBe('5');
    expect(document.querySelector('[name="item_quantity[]"]').value).toBe('2');
    expect(document.querySelector('[name="item_instructions[]"]').value).toBe('after food');
  });

  it('initial medication_id without medication_label uses the bare id', async () => {
    const mod = await loadModule('static/js/pages/doctor/prescription.js');
    mod.createRxRow({ medication_id: 42 });
    expect(document.querySelector('.medication-ref').value).toBe('42');
    expect(document.querySelector('.medication-id').value).toBe('42');
  });

  it('initial medication_ref without medication_id parses the ref', async () => {
    const mod = await loadModule('static/js/pages/doctor/prescription.js');
    mod.createRxRow({ medication_ref: '15|Metformin' });
    expect(document.querySelector('.medication-id').value).toBe('15');
  });

  it('initial without any medication data leaves fields empty', async () => {
    const mod = await loadModule('static/js/pages/doctor/prescription.js');
    mod.createRxRow({});
    expect(document.querySelector('.medication-ref').value).toBe('');
    expect(document.querySelector('[name="item_duration_days[]"]').value).toBe('7');
    expect(document.querySelector('[name="item_quantity[]"]').value).toBe('1');
    expect(document.querySelector('[name="item_instructions[]"]').value).toBe('');
  });

  it('typing into the ref input syncs the hidden id', async () => {
    const mod = await loadModule('static/js/pages/doctor/prescription.js');
    mod.createRxRow();
    const ref = document.querySelector('.medication-ref');
    ref.value = '77|Clopidogrel';
    ref.dispatchEvent(new Event('input', { bubbles: true }));
    expect(document.querySelector('.medication-id').value).toBe('77');
  });

  it('removing the only row recreates a fresh empty one', async () => {
    const mod = await loadModule('static/js/pages/doctor/prescription.js');
    mod.createRxRow();
    const removeBtn = document.querySelector('.remove-item-btn');
    removeBtn.click();
    expect(document.querySelectorAll('#rxItemsTable tbody tr').length).toBe(1);
    expect(document.querySelector('.medication-ref').value).toBe('');
  });
});

describe('prescription.js templates and buttons', () => {
  it('applyTemplateBtn with empty template id does nothing', async () => {
    await loadModule('static/js/pages/doctor/prescription.js');
    fireDomContentLoaded();
    document.getElementById('applyTemplateBtn').click();
    expect(document.querySelectorAll('#rxItemsTable tbody tr').length).toBe(1);
  });

  it('applyTemplateBtn with unknown template id does nothing', async () => {
    await loadModule('static/js/pages/doctor/prescription.js');
    fireDomContentLoaded();
    document.getElementById('templateSelect').value = 'x';
    document.getElementById('applyTemplateBtn').click();
    expect(document.querySelectorAll('#rxItemsTable tbody tr').length).toBe(1);
  });

  it('applyTemplateBtn with a valid template replaces all rows', async () => {
    await loadModule('static/js/pages/doctor/prescription.js');
    fireDomContentLoaded();
    document.getElementById('templateSelect').value = '1';
    document.getElementById('applyTemplateBtn').click();
    const rows = document.querySelectorAll('#rxItemsTable tbody tr');
    expect(rows.length).toBe(1);
    expect(document.querySelector('.medication-ref').value).toBe('10|Aspirin');
  });

  it('applyTemplateBtn with RX_TEMPLATES undefined does not crash', async () => {
    delete window.__M0__;
    await loadModule('static/js/pages/doctor/prescription.js');
    fireDomContentLoaded();
    document.getElementById('templateSelect').value = '1';
    expect(() => document.getElementById('applyTemplateBtn').click()).not.toThrow();
  });

  it('addRxItemBtn adds a new row', async () => {
    await loadModule('static/js/pages/doctor/prescription.js');
    fireDomContentLoaded();
    const before = document.querySelectorAll('#rxItemsTable tbody tr').length;
    document.getElementById('addRxItemBtn').click();
    expect(document.querySelectorAll('#rxItemsTable tbody tr').length).toBe(before + 1);
  });

  it('missing addRxItemBtn and applyTemplateBtn do not crash', async () => {
    document.getElementById('addRxItemBtn').remove();
    document.getElementById('applyTemplateBtn').remove();
    await loadModule('static/js/pages/doctor/prescription.js');
    expect(() => fireDomContentLoaded()).not.toThrow();
  });

  it('template with empty items array yields a fresh default row', async () => {
    window.__M0__ = [{ id: '1', name: 'Empty', items: [] }];
    await loadModule('static/js/pages/doctor/prescription.js');
    fireDomContentLoaded();
    document.getElementById('templateSelect').value = '1';
    document.getElementById('applyTemplateBtn').click();
    expect(document.querySelectorAll('#rxItemsTable tbody tr').length).toBe(1);
    expect(document.querySelector('.medication-ref').value).toBe('');
  });
});

describe('prescription.js submit branches', () => {
  function seedRowWithId(id) {
    document.getElementById('prescriptionForm').insertAdjacentHTML('beforeend', `<input type="hidden" class="medication-id" value="${id}">`);
  }

  it('form without prescriptionForm returns early without crashing', async () => {
    document.getElementById('prescriptionForm').remove();
    await loadModule('static/js/pages/doctor/prescription.js');
    expect(() => fireDomContentLoaded()).not.toThrow();
  });

  it('submit with no medication items is not prevented', async () => {
    await loadModule('static/js/pages/doctor/prescription.js');
    fireDomContentLoaded();
    // ensureAtLeastOneRow seeds one row on DOMContentLoaded; remove it to simulate none
    document.querySelector('#rxItemsTable tbody').innerHTML = '';
    const form = document.getElementById('prescriptionForm');
    const event = new Event('submit', { bubbles: true, cancelable: true });
    form.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(false);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('submit posts without csrf header when neither form input nor meta token exists', async () => {
    seedRowWithId('99');
    document.querySelector('meta[name="csrf-token"]');
    const mod = await loadModule('static/js/pages/doctor/prescription.js');
    fireDomContentLoaded();
    const form = document.getElementById('prescriptionForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    expect(global.fetch).toHaveBeenCalled();
    const call = global.fetch.mock.calls[0];
    expect(call[1].headers['X-CSRFToken']).toBeUndefined();
  });

  it('submit uses meta csrf when the form has no csrf input', async () => {
    document.head.innerHTML = '<meta name="csrf-token" content="meta-csrf">';
    seedRowWithId('99');
    await loadModule('static/js/pages/doctor/prescription.js');
    fireDomContentLoaded();
    document.getElementById('prescriptionForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBe('meta-csrf');
  });

  it('server non-ok shows the connection error', async () => {
    seedRowWithId('99');
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    await loadModule('static/js/pages/doctor/prescription.js');
    fireDomContentLoaded();
    document.getElementById('prescriptionForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    expect(document.getElementById('prescriptionError').textContent).toContain('حدث خطأ في الاتصال');
  });

  it('success response replaces location with data-success-url', async () => {
    seedRowWithId('99');
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
    window.location = { href: '' };
    await loadModule('static/js/pages/doctor/prescription.js');
    fireDomContentLoaded();
    document.getElementById('prescriptionForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    expect(window.location.href).toBe('/rx/done');
  });

  it('success response without data-success-url keeps the current location', async () => {
    document.getElementById('prescriptionForm').removeAttribute('data-success-url');
    seedRowWithId('99');
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
    window.location = { href: '/rx/stay' };
    await loadModule('static/js/pages/doctor/prescription.js');
    fireDomContentLoaded();
    document.getElementById('prescriptionForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    expect(window.location.href).toBe('/rx/stay');
  });

  it('server failure without hard_stops shows the server message', async () => {
    seedRowWithId('99');
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'وزن غير واقعي' }) });
    await loadModule('static/js/pages/doctor/prescription.js');
    fireDomContentLoaded();
    document.getElementById('prescriptionForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    expect(document.getElementById('prescriptionError').textContent).toContain('وزن غير واقعي');
  });

  it('server failure without message falls back to the default error', async () => {
    seedRowWithId('99');
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    await loadModule('static/js/pages/doctor/prescription.js');
    fireDomContentLoaded();
    document.getElementById('prescriptionForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    expect(document.getElementById('prescriptionError').textContent).toContain('حدث خطأ غير متوقع');
  });

  it('network failure shows the connection error', async () => {
    seedRowWithId('99');
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    await loadModule('static/js/pages/doctor/prescription.js');
    fireDomContentLoaded();
    document.getElementById('prescriptionForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    expect(document.getElementById('prescriptionError').textContent).toContain('حدث خطأ في الاتصال');
  });

  it('override flow: second POST success navigates to data-success-url', async () => {
    seedRowWithId('99');
    global.fetch = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ success: false, hard_stops: [{ severity: 'hard_stop', message: 'allergy' }] }) })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ success: true }) });
    window.location = { href: '' };
    await loadModule('static/js/pages/doctor/prescription.js');
    fireDomContentLoaded();
    document.getElementById('prescriptionForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    const modal = document.getElementById('safetyOverrideModal');
    modal.querySelector('#overrideNote').value = 'reason';
    const confirmBtn = modal.querySelector('.btn-danger');
    confirmBtn.disabled = false;
    confirmBtn.click();
    await new Promise(r => setTimeout(r, 40));
    expect(window.location.href).toBe('/rx/done');
  });

  it('override flow: second POST server failure re-shows the safety modal with server message', async () => {
    seedRowWithId('99');
    global.fetch = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ success: false, hard_stops: [{ severity: 'hard_stop', message: 'allergy' }] }) })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ success: false, message: 'dose mismatch' }) });
    await loadModule('static/js/pages/doctor/prescription.js');
    fireDomContentLoaded();
    document.getElementById('prescriptionForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    const modal = document.getElementById('safetyOverrideModal');
    modal.querySelector('#overrideNote').value = 'reason';
    const confirmBtn = modal.querySelector('.btn-danger');
    confirmBtn.disabled = false;
    confirmBtn.click();
    await new Promise(r => setTimeout(r, 40));
    const second = document.getElementById('safetyOverrideModal');
    expect(second.textContent).toContain('dose mismatch');
  });

  it('override flow: second POST without message shows the unknown error modal', async () => {
    seedRowWithId('99');
    global.fetch = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ success: false, hard_stops: [{ severity: 'hard_stop', message: 'allergy' }] }) })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ success: false }) });
    await loadModule('static/js/pages/doctor/prescription.js');
    fireDomContentLoaded();
    document.getElementById('prescriptionForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    const modal = document.getElementById('safetyOverrideModal');
    modal.querySelector('#overrideNote').value = 'reason';
    const confirmBtn = modal.querySelector('.btn-danger');
    confirmBtn.disabled = false;
    confirmBtn.click();
    await new Promise(r => setTimeout(r, 40));
    expect(document.getElementById('safetyOverrideModal').textContent).toContain('خطأ غير معروف');
  });

  it('override flow: second POST non-ok surfaces the connection error', async () => {
    seedRowWithId('99');
    global.fetch = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ success: false, hard_stops: [{ severity: 'hard_stop', message: 'allergy' }] }) })
      .mockResolvedValueOnce({ ok: false, status: 500 });
    await loadModule('static/js/pages/doctor/prescription.js');
    fireDomContentLoaded();
    document.getElementById('prescriptionForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    const modal = document.getElementById('safetyOverrideModal');
    modal.querySelector('#overrideNote').value = 'reason';
    const confirmBtn = modal.querySelector('.btn-danger');
    confirmBtn.disabled = false;
    confirmBtn.click();
    await new Promise(r => setTimeout(r, 40));
    expect(document.getElementById('prescriptionError').textContent).toContain('حدث خطأ في الاتصال');
  });
});
