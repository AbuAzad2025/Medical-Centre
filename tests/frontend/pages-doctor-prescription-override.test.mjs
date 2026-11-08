import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

let pendingDomListeners = [];
const realAdd = document.addEventListener.bind(document);

beforeEach(() => {
  document.body.innerHTML = `
    <table id="rxItemsTable"><tbody></tbody></table>
    <form id="prescriptionForm" action="/test" data-success-url="#/success">
      <input name="csrf_token" value="t"/>
      <input type="hidden" class="medication-id" value="10"/>
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

function triggerDomContentLoaded() {
  for (const listener of pendingDomListeners) listener();
}

afterEach(() => {
  vi.useRealTimers();
});

describe('doctor/prescription.js safety-override flow', () => {
  it('submit hard stops then confirm override re-posts with overridden=1', async () => {
    global.fetch = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ success: false, hard_stops: [{ severity: 'hard_stop', message: 'allergy' }] }) })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ success: true }) });
    await loadModule('static/js/pages/doctor/prescription.js');
    triggerDomContentLoaded();
    const form = document.getElementById('prescriptionForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    const modal = document.getElementById('safetyOverrideModal');
    expect(modal).toBeTruthy();
    const textarea = modal.querySelector('#overrideNote');
    textarea.value = 'patient stable';
    textarea.dispatchEvent(new Event('input', { bubbles: true }));
    const confirmBtn = modal.querySelector('.btn-danger');
    expect(confirmBtn.disabled).toBe(false);
    confirmBtn.click();
    await new Promise(r => setTimeout(r, 40));
    expect(global.fetch).toHaveBeenCalledTimes(2);
    const fd = global.fetch.mock.calls[1][1].body;
    expect(fd.get('overridden')).toBe('1');
    expect(fd.get('override_note')).toBe('patient stable');
  });

  it('submit hard stops override with server failure shows safety modal again', async () => {
    global.fetch = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ success: false, hard_stops: [{ severity: 'hard_stop', message: 'allergy' }] }) })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ success: false, message: 'dose mismatch' }) });
    await loadModule('static/js/pages/doctor/prescription.js');
    triggerDomContentLoaded();
    const form = document.getElementById('prescriptionForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    const modal = document.getElementById('safetyOverrideModal');
    const textarea = modal.querySelector('#overrideNote');
    textarea.value = 'reason';
    textarea.dispatchEvent(new Event('input', { bubbles: true }));
    modal.querySelector('.btn-danger').click();
    await new Promise(r => setTimeout(r, 40));
    expect(document.getElementById('safetyOverrideModal')).toBeTruthy();
  });

  it('submit hard stops override with non-ok response shows error', async () => {
    global.fetch = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ success: false, hard_stops: [{ severity: 'hard_stop', message: 'allergy' }] }) })
      .mockResolvedValueOnce({ ok: false, status: 500 });
    await loadModule('static/js/pages/doctor/prescription.js');
    triggerDomContentLoaded();
    const form = document.getElementById('prescriptionForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    const modal = document.getElementById('safetyOverrideModal');
    const textarea = modal.querySelector('#overrideNote');
    textarea.value = 'reason';
    textarea.dispatchEvent(new Event('input', { bubbles: true }));
    modal.querySelector('.btn-danger').click();
    await new Promise(r => setTimeout(r, 40));
    expect(document.getElementById('prescriptionError').classList.contains('d-none')).toBe(false);
  });

  it('submit server failure without hard stops shows message in prescriptionError', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'patient already dispensed' }) });
    await loadModule('static/js/pages/doctor/prescription.js');
    triggerDomContentLoaded();
    const form = document.getElementById('prescriptionForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    expect(document.getElementById('prescriptionError').classList.contains('d-none')).toBe(false);
    expect(document.getElementById('prescriptionError').textContent).toContain('patient already dispensed');
  });

  it('submit hard stops override with network failure shows error', async () => {
    global.fetch = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ success: false, hard_stops: [{ severity: 'hard_stop', message: 'allergy' }] }) })
      .mockRejectedValueOnce(new Error('network'));
    await loadModule('static/js/pages/doctor/prescription.js');
    triggerDomContentLoaded();
    const form = document.getElementById('prescriptionForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    const modal = document.getElementById('safetyOverrideModal');
    const textarea = modal.querySelector('#overrideNote');
    textarea.value = 'reason';
    textarea.dispatchEvent(new Event('input', { bubbles: true }));
    modal.querySelector('.btn-danger').click();
    await new Promise(r => setTimeout(r, 40));
    expect(document.getElementById('prescriptionError').classList.contains('d-none')).toBe(false);
  });
});