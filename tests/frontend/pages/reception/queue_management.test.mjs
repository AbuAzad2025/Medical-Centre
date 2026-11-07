import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from '../../test-utils.mjs';

let mod;

function setupDom() {
  document.body.innerHTML = `
    <meta name="csrf-token" content="test-csrf">
    <input type="checkbox" id="filterEmergency" checked>
    <input type="checkbox" id="filterForce" checked>
    <select id="filterDepartment"><option value=""></option><option value="7">Cardiology</option></select>
    <select id="filterStatus"><option value=""></option><option value="waiting">waiting</option></select>
    <select id="filterPriority"><option value=""></option><option value="normal">normal</option></select>
    <select id="filterDoctor"><option value=""></option><option value="5">Dr A</option></select>
    <input id="filterSearch" value="sara">
    <table id="queue-status-all"><tbody></tbody></table>
    <div id="avg-wait-today"></div>
    <div id="avg-wait-dept"></div>
    <div id="transferVisitModal"></div>
    <input id="transfer_visit_id" value="">
    <select id="transfer_department_id"></select>
    <select id="transfer_doctor_id"></select>
    <form id="transferVisitForm"></form>
    <div id="skipPatientModal"></div>
    <form id="skipPatientForm"></form>
    <div id="cancelTicketModal"></div>
    <form id="cancelTicketForm"></form>
    <div id="approveEmergencyDebtModal"></div>
    <form id="approveEmergencyDebtForm"></form>
    <div id="approveForceEntryModal"></div>
    <form id="approveForceEntryForm"></form>
    <div id="callPatientModal"></div>
  `;
  window.__M0__ = 'reception';
  window.__M1__ = '1';
  window.__M2__ = true;
  window.API_ROUTES = {
    api_queue_wait_metrics: '/reception/api/queue-wait-metrics',
    start_treatment: '/reception/queue/start-treatment/0',
    complete_treatment: '/reception/queue/complete-treatment/0',
    skip_patient: '/reception/queue/skip-patient/0',
    cancel_ticket: '/reception/queue/cancel-ticket/0',
    approve_emergency_debt: '/reception/queue/approve-emergency-debt/0',
    approve_force_entry: '/reception/queue/approve-force-entry/0',
    return_to_queue: '/reception/queue/return-to-queue/0',
    transfer_visit: '/reception/visits/0/transfer',
    api_department_staff: '/reception/api/department-staff',
  };
  window.escHtml = (s) => String(s || '');
  window.Swal = {
    fire: vi.fn().mockResolvedValue({ isConfirmed: true, value: 'reason' }),
    showLoading: vi.fn(),
  };
  window.Toast = { fire: vi.fn() };
  window.notify = { success: vi.fn(), error: vi.fn(), warning: vi.fn() };
  window.showToast = vi.fn();
  window.bootstrap = {
    Modal: vi.fn().mockImplementation(() => ({ show: vi.fn(), hide: vi.fn() })),
  };
  window.bootstrap.Modal.getOrCreateInstance = vi.fn(() => ({ show: vi.fn(), hide: vi.fn() }));
  window.Chart = vi.fn().mockImplementation(() => ({}));
  if (window.Chart) window.Chart.defaults = { plugins: { tooltip: {}, legend: { labels: { font: {} } } }, font: {} };
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ success: true, data: { tickets: [], overall_avg_wait_minutes: 12, by_department: [{ department_id: 7, avg_wait_minutes: 15 }] } }),
    text: () => Promise.resolve('ok'),
  });
}

beforeEach(async () => {
  setupDom();
  mod = await loadModule('static/js/pages/reception/queue_management.js');
});

afterEach(() => {
  vi.useRealTimers();
});

describe('reception/queue_management.js', () => {
  it('getCsrfToken returns meta content', () => {
    expect(mod.getCsrfToken()).toBe('test-csrf');
  });

  it('updateQueueStatus displays tickets with statuses and wait formats', async () => {
    const tickets = [
      { ticket_id: 1, ticket_number: 'T-001', patient_name: 'A', department_name: 'Cardio', doctor_name: 'Dr A', status: 'called', is_emergency: true, force_entry: false, priority_level: 'normal', queued_at_display: '10:00', wait_minutes: 75, called_at_display: '-', visit_id: 100 },
      { ticket_id: 2, ticket_number: 'T-002', patient_name: 'B', department_name: 'Lab', doctor_name: 'Dr B', status: 'in_progress', is_emergency: false, force_entry: true, priority_level: 'urgent', queued_at_display: '10:01', wait_minutes: null, called_at_display: '10:05', visit_id: 101 },
      { ticket_id: 3, ticket_number: 'T-003', patient_name: 'C', department_name: 'X', doctor_name: 'Dr C', status: 'skipped', priority_level: 'normal', queued_at_display: '10:02', wait_minutes: 5, called_at_display: '-', visit_id: null },
    ];
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, data: { tickets } }) });
    mod.updateQueueStatus();
    await new Promise(r => setTimeout(r, 30));
    const tbody = document.querySelector('#queue-status-all tbody');
    expect(tbody.innerHTML).toContain('T-001');
    expect(tbody.innerHTML).toContain('T-002');
    expect(tbody.innerHTML).toContain('T-003');
    expect(tbody.innerHTML).toContain('1 س 15 د');
    expect(tbody.innerHTML).toContain('دخول قوي');
  });

  it('updateQueueStatus with unsuccessful payload shows error row', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    mod.updateQueueStatus();
    await new Promise(r => setTimeout(r, 30));
    const row = document.querySelector('#queue-status-all tbody tr td');
    expect(row.textContent).toContain('خطأ في تحميل');
  });

  it('updateQueueStatus fetch failure shows connection error row', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    mod.updateQueueStatus();
    await new Promise(r => setTimeout(r, 30));
    const row = document.querySelector('#queue-status-all tbody tr td');
    expect(row.textContent).toContain('خطأ في الاتصال');
  });

  it('updateWaitMetrics renders overall and department values', async () => {
    mod.updateWaitMetrics('7');
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('avg-wait-today').textContent).toContain('12');
    expect(document.getElementById('avg-wait-dept').textContent).toContain('15');
  });

  it('updateWaitMetrics with no department shows placeholder', async () => {
    mod.updateWaitMetrics('');
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('avg-wait-dept').textContent).toBe('--');
  });

  it('updateWaitMetrics failure renders placeholders', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    mod.updateWaitMetrics('7');
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('avg-wait-today').textContent).toBe('--');
    expect(document.getElementById('avg-wait-dept').textContent).toBe('--');
  });

  it('displayQueueStatusAll renders empty state', () => {
    mod.displayQueueStatusAll({ tickets: [] });
    expect(document.querySelector('#queue-status-all tbody').innerHTML).toContain('لا مرضى في الطابور');
  });

  it('callNextPatient for reception role fetches without doctor id', async () => {
    mod.callNextPatient('7');
    await new Promise(r => setTimeout(r, 30));
    const [url] = global.fetch.mock.calls[0];
    expect(String(url)).toContain('call-next/7');
    expect(String(url)).not.toContain('doctor_id');
  });

  it('callNextForSelectedDepartment warns when no department selected', () => {
    const dep = document.getElementById('filterDepartment');
    dep.value = '';
    mod.callNextForSelectedDepartment();
    expect(window.Swal.fire).toHaveBeenCalled();
    expect(window.Swal.fire.mock.calls[0][0].title).toBe('تنبيه');
  });

  it('callNextForSelectedDepartment calls callNextPatient when selected', async () => {
    document.getElementById('filterDepartment').value = '7';
    mod.callNextForSelectedDepartment();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
  });

  it('callPatient opens modal', () => {
    mod.callPatient('99');
    expect(window.bootstrap.Modal).toHaveBeenCalled();
  });

  it('startTreatment fetch error shows error Swal', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    mod.startTreatment('99');
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire).toHaveBeenCalled();
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });

  it('startTreatment success fetches complete url', async () => {
    mod.startTreatment('99');
    await new Promise(r => setTimeout(r, 30));
    expect(String(global.fetch.mock.calls[0][0])).toContain('start-treatment/99');
  });

  it('completeTreatment success fetches complete url', async () => {
    mod.completeTreatment('99');
    await new Promise(r => setTimeout(r, 30));
    expect(String(global.fetch.mock.calls[0][0])).toContain('complete-treatment/99');
  });

  it('completeTreatment failure shows error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    mod.completeTreatment('99');
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });

  it('skipPatient opens modal', () => {
    mod.skipPatient('9');
    expect(window.bootstrap.Modal).toHaveBeenCalled();
  });

  it('cancelTicket opens modal', () => {
    mod.cancelTicket('9');
    expect(window.bootstrap.Modal).toHaveBeenCalled();
  });

  it('approveEmergencyDebt opens modal', () => {
    mod.approveEmergencyDebt('9');
    expect(window.bootstrap.Modal).toHaveBeenCalled();
  });

  it('approveForceEntry opens modal', () => {
    mod.approveForceEntry('9');
    expect(window.bootstrap.Modal).toHaveBeenCalled();
  });

  it('transferVisit sets visit id and loads doctors on department change', async () => {
    global.fetch = vi.fn((url) => {
      if (String(url).includes('department-staff')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ staff: [{ id: '5', full_name: 'Dr A', role: 'doctor' }] }) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true }) });
    });
    mod.transferVisit('123');
    expect(document.getElementById('transfer_visit_id').value).toBe('123');
    const deptSelect = document.getElementById('transfer_department_id');
    deptSelect.innerHTML = '<option value="7" selected>Cardiology</option>';
    deptSelect.value = '7';
    deptSelect.dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('transfer_doctor_id').innerHTML).toContain('Dr A');
    expect(window.bootstrap.Modal).toHaveBeenCalled();
  });

  it('returnToQueue confirm posts FormData and refreshes queue', async () => {
    mod.returnToQueue('77');
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
    expect(String(global.fetch.mock.calls[0][0])).toContain('return-to-queue/77');
  });

  it('returnToQueue cancel does not fetch', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    mod.returnToQueue('77');
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('transferVisitForm blocks missing department', async () => {
    const form = document.getElementById('transferVisitForm');
    document.getElementById('transfer_department_id').value = '';
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].title).toBe('تنبيه');
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('transferVisitForm submits and refreshes queue', async () => {
    const form = document.getElementById('transferVisitForm');
    document.getElementById('transfer_department_id').innerHTML = '<option value="7" selected>Cardiology</option>';
    document.getElementById('transfer_department_id').value = '7';
    document.getElementById('transfer_visit_id').value = '123';
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(String(global.fetch.mock.calls[0][0])).toContain('/reception/visits/123/transfer');
  });

  it('skipPatientForm success fetches skip url', async () => {
    mod.skipPatient('88');
    const form = document.getElementById('skipPatientForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(String(global.fetch.mock.calls[0][0])).toContain('skip-patient/88');
  });

  it('cancelTicketForm success resets form', async () => {
    mod.cancelTicket('88');
    const form = document.getElementById('cancelTicketForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(String(global.fetch.mock.calls[0][0])).toContain('cancel-ticket/88');
  });

  it('approveEmergencyDebtForm submits and hides modal', async () => {
    mod.approveEmergencyDebt('88');
    const form = document.getElementById('approveEmergencyDebtForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(String(global.fetch.mock.calls[0][0])).toContain('approve-emergency-debt/88');
  });

  it('approveForceEntryForm submits and hides modal', async () => {
    mod.approveForceEntry('88');
    const form = document.getElementById('approveForceEntryForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(String(global.fetch.mock.calls[0][0])).toContain('approve-force-entry/88');
  });
});