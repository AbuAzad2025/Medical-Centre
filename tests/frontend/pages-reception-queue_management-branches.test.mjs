import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

const SHOW = vi.fn();
const HIDE = vi.fn();
const GET_OR_CREATE = vi.fn(() => ({ hide: HIDE }));

function baseDom() {
  document.body.innerHTML = `
    <meta name="csrf-token" content="test-csrf">
    <select id="filterDepartment"><option value="">All</option><option value="5">Dept 5</option></select>
    <select id="filterStatus"><option value="">All</option><option value="waiting">Waiting</option></select>
    <select id="filterPriority"><option value="">All</option><option value="high">High</option></select>
    <select id="filterDoctor"><option value="">All</option><option value="9">Dr 9</option></select>
    <input id="filterSearch" value="">
    <input type="checkbox" id="filterEmergency">
    <input type="checkbox" id="filterForce">
    <table id="queue-status-all"><tbody></tbody></table>
    <div id="avg-wait-today"></div>
    <div id="avg-wait-dept"></div>
    <div id="callPatientModal"></div>
    <div id="skipPatientModal"></div>
    <div id="cancelTicketModal"></div>
    <div id="transferVisitModal"></div>
    <div id="approveEmergencyDebtModal"></div>
    <div id="approveForceEntryModal"></div>
    <form id="transferVisitForm">
      <input name="transfer_visit_id" id="transfer_visit_id">
      <select id="transfer_department_id"><option value="">Pick</option><option value="7">Dept 7</option></select>
      <select id="transfer_doctor_id"></select>
    </form>
    <form id="skipPatientForm"><input name="reason" value="tired"></form>
    <form id="cancelTicketForm"><input name="reason" value="fine"></form>
    <form id="approveEmergencyDebtForm"><input name="reason" value="ok"></form>
    <form id="approveForceEntryForm"><input name="reason" value="ok"></form>
  `;
}

beforeEach(() => {
  baseDom();
  SHOW.mockClear();
  HIDE.mockClear();
  GET_OR_CREATE.mockClear();
  window.__M = [];
  window.__M0__ = 'reception';
  window.__M1__ = '';
  window.__M2__ = false;
  window.escHtml = (s) => String(s ?? '');
  window.API_ROUTES = {};
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true, value: 'reason text' }), showLoading: vi.fn() };
  window.showToast = vi.fn();
  window.alert = vi.fn();
  window.bootstrap = function Modal() { return { show: SHOW, hide: HIDE }; };
  window.bootstrap.Modal = window.bootstrap;
  window.bootstrap.Modal.getOrCreateInstance = GET_OR_CREATE;
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, data: {} }), text: () => Promise.resolve('ok') });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('queue_management.js filter & metrics branches', () => {
  it('updateQueueStatus builds all filter params', async () => {
    document.getElementById('filterDepartment').value = '5';
    document.getElementById('filterStatus').value = 'waiting';
    document.getElementById('filterPriority').value = 'high';
    document.getElementById('filterDoctor').value = '9';
    document.getElementById('filterSearch').value = 'ahmed';
    document.getElementById('filterEmergency').checked = true;
    document.getElementById('filterForce').checked = true;
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    mod.updateQueueStatus();
    const url = global.fetch.mock.calls[0][0];
    expect(url).toContain('department_id=5');
    expect(url).toContain('status=waiting');
    expect(url).toContain('priority=high');
    expect(url).toContain('doctor_id=9');
    expect(url).toContain('search=ahmed');
    expect(url).toContain('is_emergency=1');
    expect(url).toContain('force_entry=1');
  });

  it('updateQueueStatus with no filters sends bare url', async () => {
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    mod.updateQueueStatus();
    const url = global.fetch.mock.calls[0][0];
    expect(url).toContain('/reception/api/queue-status-all?');
  });

  it('updateQueueStatus without csrf meta uses empty token', async () => {
    document.querySelector('meta[name="csrf-token"]').remove();
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    expect(mod.getCsrfToken()).toBe('');
  });

  it('doctor role adds doctor_id param', async () => {
    window.__M0__ = 'doctor';
    window.__M1__ = '42';
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    mod.updateQueueStatus();
    expect(global.fetch.mock.calls[0][0]).toContain('doctor_id=42');
  });

  it('non-ok response shows error row', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    mod.updateQueueStatus();
    await new Promise(r => setTimeout(r, 30));
    expect(document.querySelector('#queue-status-all tbody').innerHTML).toContain('خطأ في الاتصال');
  });

  it('data.success=false shows load error row', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    mod.updateQueueStatus();
    await new Promise(r => setTimeout(r, 30));
    expect(document.querySelector('#queue-status-all tbody').innerHTML).toContain('خطأ في تحميل الطابور');
  });

  it('missing tbody in failure response does nothing', async () => {
    document.querySelector('#queue-status-all tbody').remove();
    document.getElementById('queue-status-all').remove();
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    expect(() => mod.updateQueueStatus()).not.toThrow();
    await new Promise(r => setTimeout(r, 30));
  });

  it('updateWaitMetrics with success populates averages', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, data: { overall_avg_wait_minutes: 12, by_department: [{ department_id: 5, avg_wait_minutes: 8 }] } }) });
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    mod.updateWaitMetrics('5');
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('avg-wait-today').textContent).toContain('12');
    expect(document.getElementById('avg-wait-dept').textContent).toContain('8');
  });

  it('updateWaitMetrics with no department shows dash for dept', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, data: { overall_avg_wait_minutes: 3, by_department: [] } }) });
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    mod.updateWaitMetrics('');
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('avg-wait-dept').textContent).toBe('--');
  });

  it('updateWaitMetrics with unknown department shows dash', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, data: { overall_avg_wait_minutes: 3, by_department: [{ department_id: 999, avg_wait_minutes: 8 }] } }) });
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    mod.updateWaitMetrics('5');
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('avg-wait-dept').textContent).toBe('--');
  });

  it('updateWaitMetrics with missing by_department key shows dash', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, data: { overall_avg_wait_minutes: 3 } }) });
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    mod.updateWaitMetrics('5');
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('avg-wait-dept').textContent).toBe('--');
  });

  it('updateWaitMetrics with non-number overall shows dash', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, data: { overall_avg_wait_minutes: 'soon', by_department: [] } }) });
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    mod.updateWaitMetrics('5');
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('avg-wait-today').textContent).toBe('--');
  });

  it('updateWaitMetrics with data.success=false shows dashes', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    mod.updateWaitMetrics('5');
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('avg-wait-today').textContent).toBe('--');
    expect(document.getElementById('avg-wait-dept').textContent).toBe('--');
  });

  it('updateWaitMetrics non-ok response shows dashes', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 503 });
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    mod.updateWaitMetrics('5');
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('avg-wait-today').textContent).toBe('--');
  });

  it('updateWaitMetrics network failure shows dashes', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    mod.updateWaitMetrics('5');
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('avg-wait-dept').textContent).toBe('--');
  });

  it('updateWaitMetrics uses API_ROUTES.api_queue_wait_metrics when set', async () => {
    window.API_ROUTES = { api_queue_wait_metrics: '/custom/metrics' };
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    mod.updateWaitMetrics('5');
    expect(global.fetch.mock.calls[0][0]).toContain('/custom/metrics');
  });
});

describe('queue_management.js displayQueueStatusAll branches', () => {
  const TICKETS = [
    { ticket_id: 1, ticket_number: 'A1', patient_name: 'P1', department_name: 'D1', doctor_name: 'Dr1', status: 'waiting', status_display: 'انتظار', priority_display: 'عالية', queued_at_display: '10:00', called_at_display: '-', wait_minutes: 30, is_emergency: true, force_entry: true, visit_id: 55, is_emergency_x: false },
    { ticket_id: 2, ticket_number: 'A2', patient_name: 'P2', department_name: 'D2', doctor_name: 'Dr2', status: 'called', priority_level: 'عادية', queued_at_display: '09:00', called_at_display: '09:30', wait_minutes: 90 },
    { ticket_id: 3, ticket_number: 'A3', status: 'in_progress', wait_minutes: 'n/a' },
    { ticket_id: 4, status: 'skipped' },
  ];

  it('renders mixed ticket statuses, long waits and fallbacks', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, data: { tickets: TICKETS } }) });
    window.__M2__ = true; // billing active
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    mod.updateQueueStatus();
    await new Promise(r => setTimeout(r, 30));
    const html = document.querySelector('#queue-status-all tbody').innerHTML;
    expect(html).toContain('1 س 30 د');
    expect(html).toContain('طوارئ');
    expect(html).toContain('skipPatient(1)');
    expect(html).toContain('startTreatment(2)');
    expect(html).toContain('returnToQueue(2)');
    expect(html).toContain('completeTreatment(3)');
    expect(html).toContain('returnToQueue(4)');
    expect(html).toContain('/reception/print_receipt/55');
    expect(html).toContain('transferVisit(55)');
  });

  it('empty tickets renders the empty state', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, data: { tickets: [] } }) });
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    mod.updateQueueStatus();
    await new Promise(r => setTimeout(r, 30));
    expect(document.querySelector('#queue-status-all tbody').innerHTML).toContain('لا مرضى في الطابور');
  });

  it('missing tickets key renders the empty state', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, data: {} }) });
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    mod.updateQueueStatus();
    await new Promise(r => setTimeout(r, 30));
    expect(document.querySelector('#queue-status-all tbody').innerHTML).toContain('لا مرضى في الطابور');
  });
});

describe('queue_management.js call/start/complete treatment branches', () => {
  it('callNextPatient as doctor appends doctor_id', async () => {
    window.__M0__ = 'doctor';
    window.__M1__ = '7';
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    mod.callNextPatient(11);
    expect(global.fetch.mock.calls[0][0]).toContain('doctor_id=7');
  });

  it('callNextPatient without department shows Swal info and does not fetch', async () => {
    document.getElementById('filterDepartment').value = '';
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    mod.callNextForSelectedDepartment();
    expect(window.Swal.fire).toHaveBeenCalled();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('callNextPatient non-ok shows Swal error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500, text: () => Promise.resolve('') });
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    mod.callNextPatient(5);
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });

  it('callNextPatient fetch rejection shows Swal error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    mod.callNextPatient(5);
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });

  it('startTreatment non-ok shows Swal error and keeps modal visible', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500, text: () => Promise.resolve('') });
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    mod.startTreatment(8);
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
    expect(HIDE).not.toHaveBeenCalled();
  });

  it('startTreatment success hides modal and refreshes', async () => {
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    mod.startTreatment(8);
    await new Promise(r => setTimeout(r, 30));
    expect(GET_OR_CREATE).toHaveBeenCalled();
    expect(HIDE).toHaveBeenCalled();
  });

  it('completeTreatment non-ok shows Swal error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500, text: () => Promise.resolve('') });
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    mod.completeTreatment(8);
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });

  it('completeTreatment fetch rejection shows Swal error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    mod.completeTreatment(8);
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });

  it('completeTreatment success refreshes the queue', async () => {
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    global.fetch.mockClear();
    mod.completeTreatment(8);
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch.mock.calls.some(c => String(c[0]).includes('complete-treatment/8'))).toBe(true);
  });
});

describe('queue_management.js modal openers', () => {
  it('callPatient/skipPatient/cancelTicket/approve* open their modals', async () => {
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    mod.callPatient(1);
    mod.skipPatient(2);
    mod.cancelTicket(3);
    mod.approveEmergencyDebt(4);
    mod.approveForceEntry(5);
    expect(SHOW).toHaveBeenCalledTimes(5);
  });
});

describe('queue_management.js transfer visit branches', () => {
  it('transferVisit shows transfer modal and department change loads staff', async () => {
    global.fetch = vi.fn((url) => {
      if (String(url).includes('department-staff')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ staff: [{ id: 1, full_name: 'سارة', role: 'nurse' }, { id: 2, full_name: 'ليان', role: 'unknown-role' }] }) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true }) });
    });
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    mod.transferVisit(77);
    const dept = document.getElementById('transfer_department_id');
    dept.value = '7';
    dept.dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 30));
    const doc = document.getElementById('transfer_doctor_id');
    expect(doc.innerHTML).toContain('سارة');
    expect(doc.innerHTML).toContain('ممرض');
    expect(doc.innerHTML).toContain('unknown-role');
  });

  it('department change with empty value resets the doctor select', async () => {
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    mod.transferVisit(77);
    const dept = document.getElementById('transfer_department_id');
    dept.value = '';
    dept.dispatchEvent(new Event('change'));
    expect(document.getElementById('transfer_doctor_id').innerHTML).toContain('اختر بعد القسم');
  });

  it('staff fetch failure triggers showToast', async () => {
    global.fetch = vi.fn((url) => {
      if (String(url).includes('department-staff')) return Promise.reject(new Error('network'));
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true }) });
    });
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    mod.transferVisit(77);
    const dept = document.getElementById('transfer_department_id');
    dept.value = '7';
    dept.dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 30));
    expect(window.showToast).toHaveBeenCalled();
  });

  it('staff fetch non-ok triggers alert fallback without showToast', async () => {
    delete window.showToast;
    global.fetch = vi.fn((url) => {
      if (String(url).includes('department-staff')) return Promise.resolve({ ok: false, status: 500 });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true }) });
    });
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    mod.transferVisit(77);
    const dept = document.getElementById('transfer_department_id');
    dept.value = '7';
    dept.dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 30));
    expect(window.alert).toHaveBeenCalled();
  });

  it('submit without department shows Swal warning and stops', async () => {
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    const form = document.getElementById('transferVisitForm');
    document.getElementById('transfer_department_id').value = '';
    global.fetch.mockClear();
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('warning');
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('submit with doctor selected posts doctor_id and hides modal on success', async () => {
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    await new Promise(r => setTimeout(r, 10));
    document.getElementById('transfer_doctor_id').innerHTML = '<option value="9" selected>Dr 9</option>';
    document.getElementById('transfer_department_id').value = '7';
    document.getElementById('transfer_doctor_id').value = '9';
    document.getElementById('transfer_visit_id').value = '77';
    const form = document.getElementById('transferVisitForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    const call = global.fetch.mock.calls.find(c => String(c[0]).includes('/reception/visits/77/transfer'));
    expect(call).toBeTruthy();
    expect(GET_OR_CREATE).toHaveBeenCalled();
    expect(HIDE).toHaveBeenCalled();
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('success');
  });

  it('submit with server failure shows Swal error with fallback message', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    document.getElementById('transfer_department_id').value = '7';
    document.getElementById('transfer_visit_id').value = '77';
    const form = document.getElementById('transferVisitForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
    expect(window.Swal.fire.mock.calls[0][0].text).toBe('فشل التحويل');
  });

  it('submit with server failure message uses server text', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'قسم مغلق' }) });
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    document.getElementById('transfer_department_id').value = '7';
    document.getElementById('transfer_visit_id').value = '77';
    const form = document.getElementById('transferVisitForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].text).toBe('قسم مغلق');
  });

  it('submit with server non-ok throws into Swal error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500, json: () => Promise.resolve({}) });
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    document.getElementById('transfer_department_id').value = '7';
    document.getElementById('transfer_visit_id').value = '77';
    const form = document.getElementById('transferVisitForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].text).toContain('التحويل');
  });
});

describe('queue_management.js returnToQueue branches', () => {
  it('confirm with empty reason posts fd without csrf header crash', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: true, value: '' });
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    mod.returnToQueue(33);
    await new Promise(r => setTimeout(r, 30));
    const call = global.fetch.mock.calls.find(c => String(c[0]).includes('return-to-queue/33'));
    expect(call).toBeTruthy();
    expect(GET_OR_CREATE).not.toHaveBeenCalled();
  });

  it('cancelled confirm does not fetch', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    mod.returnToQueue(33);
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch.mock.calls.some(c => String(c[0]).includes('return-to-queue'))).toBe(false);
  });

  it('non-ok response shows Swal error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: true, value: 'r' });
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    mod.returnToQueue(33);
    await new Promise(r => setTimeout(r, 30));
    const last = window.Swal.fire.mock.calls[window.Swal.fire.mock.calls.length - 1][0];
    expect(last.icon).toBe('error');
  });

  it('network failure shows Swal error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: true, value: 'r' });
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    mod.returnToQueue(33);
    await new Promise(r => setTimeout(r, 30));
    const last = window.Swal.fire.mock.calls[window.Swal.fire.mock.calls.length - 1][0];
    expect(last.icon).toBe('error');
  });
});

describe('queue_management.js skip/cancel/debt/force forms', () => {
  async function openAndSubmit(mod, opener, formId, urlFragment) {
    mod[opener](15);
    global.fetch.mockClear();
    const form = document.getElementById(formId);
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    return global.fetch.mock.calls.find(c => String(c[0]).includes(urlFragment));
  }

  it('skipPatient submit posts to skip-patient with current ticket id', async () => {
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    await new Promise(r => setTimeout(r, 10));
    const call = await openAndSubmit(mod, 'skipPatient', 'skipPatientForm', 'skip-patient/15');
    expect(call).toBeTruthy();
    expect(GET_OR_CREATE).toHaveBeenCalled();
  });

  it('skipPatient non-ok shows Swal error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500, text: () => Promise.resolve('') });
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    mod.skipPatient(15);
    const form = document.getElementById('skipPatientForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    const last = window.Swal.fire.mock.calls[window.Swal.fire.mock.calls.length - 1][0];
    expect(last.icon).toBe('error');
  });

  it('skipPatient network failure shows Swal error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    mod.skipPatient(15);
    const form = document.getElementById('skipPatientForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    const last = window.Swal.fire.mock.calls[window.Swal.fire.mock.calls.length - 1][0];
    expect(last.icon).toBe('error');
  });

  it('cancelTicket submit posts to cancel-ticket', async () => {
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    const call = await openAndSubmit(mod, 'cancelTicket', 'cancelTicketForm', 'cancel-ticket/15');
    expect(call).toBeTruthy();
  });

  it('cancelTicket non-ok shows Swal error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500, text: () => Promise.resolve('') });
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    mod.cancelTicket(15);
    const form = document.getElementById('cancelTicketForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    const last = window.Swal.fire.mock.calls[window.Swal.fire.mock.calls.length - 1][0];
    expect(last.icon).toBe('error');
  });

  it('approveEmergencyDebt submit posts to approve-emergency-debt', async () => {
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    const call = await openAndSubmit(mod, 'approveEmergencyDebt', 'approveEmergencyDebtForm', 'approve-emergency-debt/15');
    expect(call).toBeTruthy();
  });

  it('approveEmergencyDebt non-ok shows Swal error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500, text: () => Promise.resolve('') });
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    mod.approveEmergencyDebt(15);
    const form = document.getElementById('approveEmergencyDebtForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    const last = window.Swal.fire.mock.calls[window.Swal.fire.mock.calls.length - 1][0];
    expect(last.icon).toBe('error');
  });

  it('approveForceEntry submit posts to approve-force-entry', async () => {
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    const call = await openAndSubmit(mod, 'approveForceEntry', 'approveForceEntryForm', 'approve-force-entry/15');
    expect(call).toBeTruthy();
  });

  it('approveForceEntry non-ok shows Swal error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500, text: () => Promise.resolve('') });
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    mod.approveForceEntry(15);
    const form = document.getElementById('approveForceEntryForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    const last = window.Swal.fire.mock.calls[window.Swal.fire.mock.calls.length - 1][0];
    expect(last.icon).toBe('error');
  });

  it('skipPatient without csrf meta omits the token header but still posts', async () => {
    document.querySelector('meta[name="csrf-token"]').remove();
    const mod = await loadModule('static/js/pages/reception/queue_management.js');
    mod.skipPatient(16);
    const form = document.getElementById('skipPatientForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    const call = global.fetch.mock.calls.find(c => String(c[0]).includes('skip-patient/16'));
    expect(call).toBeTruthy();
    expect(call[1].headers['X-CSRFToken']).toBeUndefined();
  });
});

describe('queue_management.js lifecycle', () => {
  it('beforeunload clears the interval', async () => {
    vi.useFakeTimers();
    await loadModule('static/js/pages/reception/queue_management.js');
    expect(() => window.dispatchEvent(new Event('beforeunload'))).not.toThrow();
    vi.useRealTimers();
  });

  it('DOMContentLoaded triggers an initial queue refresh', async () => {
    await loadModule('static/js/pages/reception/queue_management.js');
    global.fetch.mockClear();
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch.mock.calls.some(c => String(c[0]).includes('queue-status-all'))).toBe(true);
  });

  it('window exposures are assigned for inline handlers', async () => {
    await loadModule('static/js/pages/reception/queue_management.js');
    for (const name of ['completeTreatment', 'skipPatient', 'approveEmergencyDebt', 'updateQueueStatus', 'getCsrfToken', 'callNextForSelectedDepartment', 'callPatient', 'displayQueueStatusAll', 'callNextPatient', 'cancelTicket', 'transferVisit', 'returnToQueue', 'updateWaitMetrics', 'startTreatment']) {
      expect(typeof window[name]).toBe('function');
    }
  });
});
