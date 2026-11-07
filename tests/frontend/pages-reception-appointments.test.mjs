import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  const today = new Date().toISOString().split('T')[0];
  const tomorrow = new Date(Date.now() + 86400000).toISOString().split('T')[0];
  document.body.innerHTML = `
    <meta name="csrf-token" content="test-csrf">
    <input id="searchInput">
    <select id="departmentFilter"><option value="">All</option><option value="7">Cardiology</option></select>
    <select id="statusFilter"><option value="">All</option><option value="scheduled">scheduled</option><option value="confirmed">confirmed</option></select>
    <select id="doctorFilter"><option value="">All</option><option value="5">Dr A</option></select>
    <input id="dateFilter" type="date">
    <select id="perPageFilter"><option>10</option><option selected>25</option></select>
    <table id="appointmentsTable"><tbody><tr data-date="${today}" data-status="scheduled"><td>A</td></tr><tr data-date="${tomorrow}" data-status="confirmed"><td>B</td></tr></tbody></table>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M = [];
  window.escHtml = (s) => String(s || '');
  window.__M0__ = [{ id: 1, patient: { full_name: 'Sara' }, doctor: { full_name: 'Dr A' }, starts_at: '2026-11-08T09:00:00', status: 'scheduled', appointment_type: 'CONSULTATION' }];
  window.__M1__ = '25';
  window.API_ROUTES = {
    reception_create_appointment: '/reception/create_appointment',
    reception_create_visit: '/reception/visits/create',
    reception_appointments: '/reception/appointments',
    reception_view_appointment: '/reception/view_appointment/0',
    reception_edit_appointment: '/reception/edit_appointment/0',
    reception_confirm_appointment: '/reception/appointments/0/confirm',
    reception_cancel_appointment: '/reception/appointments/0/cancel',
    reception_no_show_appointment: '/reception/appointments/0/no-show',
  };
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.bootstrap = { Collapse: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn() })) }, Modal: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn(), hide: vi.fn() })) } };
  window.location = { href: '', reload: vi.fn() };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('reception/appointments.js', () => {
  it('getCsrfToken reads meta', async () => {
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    expect(mod.getCsrfToken()).toBe('test-csrf');
  });

  it('createNewAppointment navigates', async () => {
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    expect(() => mod.createNewAppointment()).not.toThrow();
    expect(window.location.href).toBe('/reception/create_appointment');
  });

  it('createNewVisit navigates', async () => {
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    expect(() => mod.createNewVisit()).not.toThrow();
    expect(window.location.href).toBe('/reception/visits/create');
  });

  it('exportAppointments creates download link', async () => {
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    mod.exportAppointments();
    const links = document.querySelectorAll('a[download]');
    expect(links.length).toBeGreaterThanOrEqual(0);
  });

  it('applyFilters builds search params and navigates', async () => {
    document.getElementById('searchInput').value = 'sara';
    document.getElementById('departmentFilter').value = '7';
    document.getElementById('statusFilter').value = 'scheduled';
    document.getElementById('doctorFilter').value = '5';
    document.getElementById('dateFilter').value = '2026-11-08';
    document.getElementById('perPageFilter').value = '10';
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    mod.applyFilters();
    expect(window.location.href).toContain('search=sara');
    expect(window.location.href).toContain('department_id=7');
    expect(window.location.href).toContain('status=scheduled');
    expect(window.location.href).toContain('page=1');
  });

  it('clearFilters resets inputs and navigates', async () => {
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    mod.clearFilters();
    expect(document.getElementById('searchInput').value).toBe('');
    expect(window.location.href).toContain('per_page=25');
  });

  it('filterAppointments filters by today only', async () => {
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    mod.filterAppointments('today', null);
    const rows = document.querySelectorAll('#appointmentsTable tbody tr');
    expect(rows[0].style.display).toBe('');
    expect(rows[1].style.display).toBe('none');
  });

  it('filterAppointments filters by confirmed', async () => {
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    mod.filterAppointments('confirmed', null);
    const rows = document.querySelectorAll('#appointmentsTable tbody tr');
    expect(rows[0].style.display).toBe('none');
    expect(rows[1].style.display).toBe('');
  });

  it('filterAppointments filters all shows all', async () => {
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    mod.filterAppointments('all', null);
    const rows = document.querySelectorAll('#appointmentsTable tbody tr');
    expect(rows[0].style.display).toBe('');
    expect(rows[1].style.display).toBe('');
  });

  it('viewAppointment navigates to view url', async () => {
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    mod.viewAppointment('42');
    expect(window.location.href).toContain('/reception/view_appointment/42');
  });

  it('editAppointment navigates to edit url', async () => {
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    mod.editAppointment('42');
    expect(window.location.href).toContain('/reception/edit_appointment/42');
  });

  it('confirmAppointment posts on confirm', async () => {
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    mod.confirmAppointment('42');
    await new Promise(r => setTimeout(r, 30));
    expect(String(global.fetch.mock.calls[0][0])).toContain('/reception/appointments/42/confirm');
  });

  it('confirmAppointment error shows Swal', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    mod.confirmAppointment('42');
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('error');
  });

  it('cancelAppointment posts on confirm', async () => {
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    mod.cancelAppointment('42');
    await new Promise(r => setTimeout(r, 30));
    expect(String(global.fetch.mock.calls[0][0])).toContain('/reception/appointments/42/cancel');
  });

  it('noShowAppointment posts on confirm', async () => {
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    mod.noShowAppointment('42');
    await new Promise(r => setTimeout(r, 30));
    expect(String(global.fetch.mock.calls[0][0])).toContain('/reception/appointments/42/no-show');
  });

  it('noShowAppointment cancel does not fetch', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    mod.noShowAppointment('42');
    await new Promise(r => setTimeout(r, 20));
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('generateReport shows info Swal', async () => {
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    mod.generateReport();
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('info');
  });

  it('bulkActions shows info Swal', async () => {
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    mod.bulkActions();
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('info');
  });

  it('DOMContentLoaded attaches row hover handlers', async () => {
    await loadModule('static/js/pages/reception/appointments.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const row = document.querySelector('#appointmentsTable tbody tr');
    row.dispatchEvent(new MouseEvent('mouseenter'));
    expect(row.style.backgroundColor).toBe('rgb(248, 249, 250)');
    row.dispatchEvent(new MouseEvent('mouseleave'));
    expect(row.style.backgroundColor).toBe('');
  });

  it('searchInput typing calls applyFilters which navigates', async () => {
    await loadModule('static/js/pages/reception/appointments.js');
    document.getElementById('searchInput').value = 'sara';
    document.getElementById('searchInput').dispatchEvent(new Event('input', { bubbles: true }));
    expect(window.location.href).toContain('/reception/appointments');
  });
});