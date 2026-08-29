import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <div id="searchInput" class="form-control"></div>
    <select id="departmentFilter"></select>
    <select id="statusFilter"></select>
    <select id="doctorFilter"></select>
    <input type="date" id="dateFilter" />
    <select id="perPageFilter"></select>
    <table id="appointmentsTable"><tbody>
      <tr data-date="2026-08-29" data-status="scheduled"><td></td></tr>
      <tr data-date="2025-01-01" data-status="confirmed"><td></td></tr>
    </tbody></table>
  `;
  window.__M0__ = [{ id: 1, patient: { full_name: 'P1' }, doctor: { full_name: 'D1' }, starts_at: '2026-08-29T10:00', status: 'scheduled', appointment_type: 'visit' }];
  window.__M1__ = '10';
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.Toast = { fire: vi.fn() };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
  delete window.location;
  window.location = { href: '', reload: vi.fn() };
});

describe('reception/appointments.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/reception/appointments.js');
  });

  test('filterAppointments is a function', async () => {
    await loadScript('static/js/pages/reception/appointments.js');
    expect(typeof filterAppointments).toBe('function');
  });

  test('clearFilters is a function', async () => {
    await loadScript('static/js/pages/reception/appointments.js');
    expect(typeof clearFilters).toBe('function');
  });

  test('exportAppointments is a function', async () => {
    await loadScript('static/js/pages/reception/appointments.js');
    expect(typeof exportAppointments).toBe('function');
  });

  test('filterAppointments filters by today', async () => {
    await loadScript('static/js/pages/reception/appointments.js');
    const today = new Date().toISOString().split('T')[0];
    document.querySelector('#appointmentsTable tbody tr:first-child').dataset.date = today;
    filterAppointments('today');
    const rows = document.querySelectorAll('#appointmentsTable tbody tr');
    expect(rows[0].style.display).toBe('');
  });

  test('filterAppointments filters by pending', async () => {
    await loadScript('static/js/pages/reception/appointments.js');
    filterAppointments('pending');
    const rows = document.querySelectorAll('#appointmentsTable tbody tr');
    expect(rows[0].style.display).toBe('');
    expect(rows[1].style.display).toBe('none');
  });

  test('filterAppointments all shows all', async () => {
    await loadScript('static/js/pages/reception/appointments.js');
    filterAppointments('all');
    const rows = document.querySelectorAll('#appointmentsTable tbody tr');
    rows.forEach(r => expect(r.style.display).toBe(''));
  });
});
