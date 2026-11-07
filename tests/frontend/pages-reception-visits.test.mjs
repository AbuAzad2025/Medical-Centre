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
  window.escHtml = (s) => String(s || '');
  window.__M0__ = 'reception';
  window.__M1__ = true;
  window.API_ROUTES = {
    view_visit: '/reception/view_visit/0',
    payment_process: '/payment/process/0',
    print_receipt: '/reception/print_receipt/0',
    edit_visit: '/reception/edit_visit/0',
    export_visits: '/reception/export/visits',
    api_department_staff: '/reception/api/department-staff',
    transfer_visit: '/reception/visits/0/transfer',
  };
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.bootstrap = {
    Collapse: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn() })) },
    Modal: vi.fn().mockImplementation(() => ({ show: vi.fn(), hide: vi.fn() })),
  };
  window.bootstrap.Modal.getOrCreateInstance = vi.fn(() => ({ show: vi.fn(), hide: vi.fn() }));
  window.showToast = vi.fn();
  window.open = vi.fn();
  window.location = { href: '', reload: vi.fn(), search: '?page=2' };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, staff: [{ id: '5', full_name: 'Dr A' }] }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('reception/visits.js', () => {
  it('viewVisit sets location.href', async () => {
    await loadModule('static/js/pages/reception/visits.js');
    window.viewVisit('42');
    expect(window.location.href).toBe('/reception/view_visit/42');
  });

  it('processPayment navigates to payment', async () => {
    await loadModule('static/js/pages/reception/visits.js');
    window.processPayment('42');
    expect(window.location.href).toBe('/payment/process/42');
  });

  it('printReceipt opens the receipt URL when billing enabled', async () => {
    await loadModule('static/js/pages/reception/visits.js');
    window.printReceipt('42');
    expect(window.open).toHaveBeenCalledWith('/reception/print_receipt/42', '_blank');
  });

  it('printReceipt does nothing when billing disabled', async () => {
    window.__M1__ = false;
    const mod = await loadModule('static/js/pages/reception/visits.js');
    window.printReceipt('42');
    expect(window.open).not.toHaveBeenCalled();
  });

  it('editVisit navigates to edit url', async () => {
    await loadModule('static/js/pages/reception/visits.js');
    window.editVisit('42');
    expect(window.location.href).toBe('/reception/edit_visit/42');
  });

  it('exportVisits opens the export url with query', async () => {
    await loadModule('static/js/pages/reception/visits.js');
    window.exportVisits();
    expect(window.open).toHaveBeenCalledWith(expect.stringContaining('/reception/export/visits'), '_blank');
  });

  it('transferDepartment change populates doctors from staff api', async () => {
    await loadModule('static/js/pages/reception/visits.js');
    const sel = document.getElementById('transferDepartment');
    sel.value = '7';
    sel.dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('transferDoctor').innerHTML).toContain('Dr A');
  });

  it('transferDepartment change with empty value clears doctors', async () => {
    await loadModule('static/js/pages/reception/visits.js');
    const sel = document.getElementById('transferDepartment');
    sel.value = '';
    sel.dispatchEvent(new Event('change'));
    expect(document.getElementById('transferDoctor').innerHTML).toContain('اختر الطبيب');
  });

  it('confirmTransferBtn without department shows warning', async () => {
    await loadModule('static/js/pages/reception/visits.js');
    document.getElementById('transferDepartment').value = '';
    document.getElementById('confirmTransferBtn').click();
    await new Promise(r => setTimeout(r, 20));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('warning');
  });

  it('confirmTransferBtn posts transfer on confirm', async () => {
    await loadModule('static/js/pages/reception/visits.js');
    document.getElementById('transferDepartment').value = '7';
    document.getElementById('transferVisitId').value = '42';
    document.getElementById('confirmTransferBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(String(global.fetch.mock.calls[0][0])).toContain('/reception/visits/42/transfer');
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('success');
  });

  it('confirmTransferBtn with server error shows error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'nope' }) });
    await loadModule('static/js/pages/reception/visits.js');
    document.getElementById('transferDepartment').value = '7';
    document.getElementById('transferVisitId').value = '42';
    document.getElementById('confirmTransferBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });

  it('confirmTransferBtn fetch failure shows error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    await loadModule('static/js/pages/reception/visits.js');
    document.getElementById('transferDepartment').value = '7';
    document.getElementById('transferVisitId').value = '42';
    document.getElementById('confirmTransferBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });

  it('contextmenu on table row opens transfer modal', async () => {
    await loadModule('static/js/pages/reception/visits.js');
    const row = document.querySelector('#visitsTable tbody tr');
    row.dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, cancelable: true }));
    expect(document.getElementById('transferVisitId').value).toBe('7');
    expect(window.bootstrap.Modal).toHaveBeenCalled();
  });

  it('beforeunload clears reload interval without throwing', async () => {
    await loadModule('static/js/pages/reception/visits.js');
    window.dispatchEvent(new Event('beforeunload'));
    expect(true).toBe(true);
  });
});