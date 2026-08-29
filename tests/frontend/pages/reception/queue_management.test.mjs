import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <div id="filterDepartment"></div>
    <div id="filterStatus"></div>
    <div id="filterPriority"></div>
    <div id="filterDoctor"></div>
    <div id="filterSearch"></div>
    <input type="checkbox" id="filterEmergency" />
    <input type="checkbox" id="filterForce" />
    <table id="queue-status-all"><tbody></tbody></table>
    <div id="avg-wait-today"></div>
    <div id="avg-wait-dept"></div>
    <div id="transferVisitModal"></div>
    <input id="transfer_visit_id" value="" />
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
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.Toast = { fire: vi.fn() };
  window.bootstrap = { Modal: { getOrCreateInstance: () => ({ show: vi.fn(), hide: vi.fn() }) } };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, data: { tickets: [] } }) });
});

describe('reception/queue_management.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/reception/queue_management.js');
  });

  test('updateQueueStatus is a function', async () => {
    await loadScript('static/js/pages/reception/queue_management.js');
    expect(typeof updateQueueStatus).toBe('function');
  });

  test('displayQueueStatusAll is a function', async () => {
    await loadScript('static/js/pages/reception/queue_management.js');
    expect(typeof displayQueueStatusAll).toBe('function');
  });

  test('callNextPatient is a function', async () => {
    await loadScript('static/js/pages/reception/queue_management.js');
    expect(typeof callNextPatient).toBe('function');
  });

  test('displayQueueStatusAll renders empty state', async () => {
    await loadScript('static/js/pages/reception/queue_management.js');
    displayQueueStatusAll({ tickets: [] });
    const tbody = document.querySelector('#queue-status-all tbody');
    expect(tbody.innerHTML).toContain('لا مرضى في الطابور');
  });

  test('displayQueueStatusAll renders ticket rows', async () => {
    await loadScript('static/js/pages/reception/queue_management.js');
    displayQueueStatusAll({
      tickets: [{
        ticket_id: 1,
        ticket_number: 'T-001',
        patient_name: 'Test Patient',
        department_name: 'Dept',
        doctor_name: 'Dr.',
        status: 'waiting',
        priority_level: 'normal',
        queued_at_display: '10:00',
        wait_minutes: 5,
        called_at_display: '-',
        is_emergency: false,
        force_entry: false,
        visit_id: 100
      }]
    });
    const tbody = document.querySelector('#queue-status-all tbody');
    expect(tbody.innerHTML).toContain('T-001');
    expect(tbody.innerHTML).toContain('Test Patient');
  });

  test('getCsrfToken reads meta tag', async () => {
    await loadScript('static/js/pages/reception/queue_management.js');
    expect(typeof getCsrfToken).toBe('function');
    const token = getCsrfToken();
    expect(typeof token).toBe('string');
  });
});
