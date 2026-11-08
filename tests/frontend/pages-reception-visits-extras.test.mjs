import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <meta name="csrf-token" content="test-csrf">
    <table id="visitsTable">
      <tbody><tr data-visit-id="7"><td>Visit 7</td></tr></tbody>
    </table>
    <select id="transferDepartment"><option value="">اختر</option><option value="7">Cardiology</option></select>
    <select id="transferDoctor"><option value="">اختر الطبيب</option></select>
    <input id="transferVisitId" value="">
    <span id="transferStatus"></span>
    <div id="transferVisitModal"></div>
    <button id="confirmTransferBtn">Confirm</button>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M = [];
  window.escHtml = (s) => String(s ?? '');
  window.__M0__ = 'reception';
  window.__M1__ = true;
  window.API_ROUTES = {};
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.bootstrap = {
    Collapse: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn() })) },
    Modal: vi.fn().mockImplementation(() => ({ show: vi.fn(), hide: vi.fn() })),
  };
  window.bootstrap.Modal.getOrCreateInstance = vi.fn(() => ({ show: vi.fn(), hide: vi.fn() }));
  window.showToast = vi.fn();
  window.alert = vi.fn();
  window.open = vi.fn();
  window.location = { href: '', reload: vi.fn(), search: '?page=2' };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, staff: [{ id: '5', full_name: 'Dr A' }] }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('visits.js API_ROUTES fallback arms', () => {
  it('viewVisit/editVisit/processPayment fall back to default routes', async () => {
    await loadModule('static/js/pages/reception/visits.js');
    window.viewVisit('5');
    expect(window.location.href).toBe('/reception/view_visit/5');
    window.editVisit('6');
    expect(window.location.href).toBe('/reception/edit_visit/6');
    window.processPayment('7');
    expect(window.location.href).toBe('/payment/process/7');
  });

  it('printReceipt falls back to the default route', async () => {
    await loadModule('static/js/pages/reception/visits.js');
    window.printReceipt('9');
    expect(window.open).toHaveBeenCalledWith('/reception/print_receipt/9', '_blank');
  });

  it('printReceipt without a billing flag proceeds to print', async () => {
    delete window.__M1__;
    await loadModule('static/js/pages/reception/visits.js');
    window.printReceipt('9');
    expect(window.open).toHaveBeenCalled();
  });

  it('exportVisits falls back to the default export route', async () => {
    await loadModule('static/js/pages/reception/visits.js');
    window.exportVisits();
    expect(window.open).toHaveBeenCalledWith('/reception/export/visits?page=2', '_blank');
  });

  it('staff API falls back to the default endpoint', async () => {
    await loadModule('static/js/pages/reception/visits.js');
    const sel = document.getElementById('transferDepartment');
    sel.value = '7';
    sel.dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch.mock.calls[0][0]).toContain('/reception/api/department-staff');
  });

  it('transfer request falls back to the default endpoint', async () => {
    await loadModule('static/js/pages/reception/visits.js');
    document.getElementById('transferDepartment').value = '7';
    document.getElementById('transferVisitId').value = '42';
    document.getElementById('confirmTransferBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch.mock.calls[0][0]).toBe('/reception/visits/42/transfer');
  });
});

describe('visits.js staff fetch error arms', () => {
  it('staff fetch non-ok triggers showToast when available', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    await loadModule('static/js/pages/reception/visits.js');
    const sel = document.getElementById('transferDepartment');
    sel.value = '7';
    sel.dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 30));
    expect(window.showToast).toHaveBeenCalled();
  });

  it('staff fetch non-ok falls back to alert without showToast', async () => {
    delete window.showToast;
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    await loadModule('static/js/pages/reception/visits.js');
    const sel = document.getElementById('transferDepartment');
    sel.value = '7';
    sel.dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 30));
    expect(window.alert).toHaveBeenCalled();
  });

  it('response without a staff key renders nothing but does not crash', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
    await loadModule('static/js/pages/reception/visits.js');
    const sel = document.getElementById('transferDepartment');
    sel.value = '7';
    sel.dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('transferDoctor').querySelectorAll('option').length).toBe(1);
  });
});

describe('visits.js transfer form arms', () => {
  it('success reloads the page', async () => {
    await loadModule('static/js/pages/reception/visits.js');
    document.getElementById('transferDepartment').value = '7';
    document.getElementById('transferVisitId').value = '42';
    document.getElementById('confirmTransferBtn').click();
    await new Promise(r => setTimeout(r, 80));
    expect(window.location.reload).toHaveBeenCalled();
  });

  it('server error without a message falls back to the default text', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    await loadModule('static/js/pages/reception/visits.js');
    document.getElementById('transferDepartment').value = '7';
    document.getElementById('transferVisitId').value = '42';
    document.getElementById('confirmTransferBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].text).toBe('فشل التحويل');
  });

  it('transfer without any csrf token sends no token header', async () => {
    document.querySelector('meta[name="csrf-token"]').remove();
    await loadModule('static/js/pages/reception/visits.js');
    document.getElementById('transferDepartment').value = '7';
    document.getElementById('transferVisitId').value = '42';
    document.getElementById('confirmTransferBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBeUndefined();
  });

  it('form csrf input is preferred over meta for the transfer', async () => {
    document.body.insertAdjacentHTML('beforeend', '<input type="hidden" name="csrf_token" value="form-csrf">');
    await loadModule('static/js/pages/reception/visits.js');
    document.getElementById('transferDepartment').value = '7';
    document.getElementById('transferVisitId').value = '42';
    document.getElementById('confirmTransferBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBe('form-csrf');
  });

  it('missing confirmTransferBtn does not crash the module', async () => {
    document.getElementById('confirmTransferBtn').remove();
    await expect(loadModule('static/js/pages/reception/visits.js')).resolves.toBeDefined();
  });

  it('missing transferDepartment does not crash the module', async () => {
    document.getElementById('transferDepartment').remove();
    await expect(loadModule('static/js/pages/reception/visits.js')).resolves.toBeDefined();
  });
});

describe('visits.js auto-refresh and roles', () => {
  it('interval reloads when the page is visible', async () => {
    vi.useFakeTimers();
    Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true });
    await loadModule('static/js/pages/reception/visits.js');
    vi.advanceTimersByTime(31000);
    expect(window.location.reload).toHaveBeenCalled();
    vi.useRealTimers();
  });

  it('interval does not reload while the page is hidden', async () => {
    vi.useFakeTimers();
    Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true });
    await loadModule('static/js/pages/reception/visits.js');
    vi.advanceTimersByTime(31000);
    expect(window.location.reload).not.toHaveBeenCalled();
    Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true });
    vi.useRealTimers();
  });

  it('missing visitsTable does not register the reload interval', async () => {
    document.getElementById('visitsTable').remove();
    vi.useFakeTimers();
    await loadModule('static/js/pages/reception/visits.js');
    vi.advanceTimersByTime(31000);
    expect(window.location.reload).not.toHaveBeenCalled();
    vi.useRealTimers();
  });

  it('beforeunload clears the interval safely', async () => {
    vi.useFakeTimers();
    await loadModule('static/js/pages/reception/visits.js');
    expect(() => window.dispatchEvent(new Event('beforeunload'))).not.toThrow();
    vi.useRealTimers();
  });

  it('non-reception role skips wiring the confirm button and interval', async () => {
    window.__M0__ = 'doctor';
    vi.useFakeTimers();
    await loadModule('static/js/pages/reception/visits.js');
    vi.advanceTimersByTime(31000);
    expect(window.location.reload).not.toHaveBeenCalled();
    document.getElementById('confirmTransferBtn').click();
    expect(global.fetch).not.toHaveBeenCalled();
    vi.useRealTimers();
  });

  it('contextmenu outside a table row is a no-op', async () => {
    await loadModule('static/js/pages/reception/visits.js');
    const div = document.createElement('div');
    document.body.appendChild(div);
    expect(() => div.dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, cancelable: true }))).not.toThrow();
    expect(document.getElementById('transferVisitId').value).toBe('');
  });
});
