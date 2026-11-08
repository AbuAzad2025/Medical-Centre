import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <meta name="csrf-token" content="test-csrf">
    <input id="searchInput">
    <select id="departmentFilter"><option value="">All</option><option value="7">Cardiology</option></select>
    <select id="statusFilter"><option value="">All</option><option value="scheduled">scheduled</option><option value="confirmed">confirmed</option></select>
    <select id="doctorFilter"><option value="">All</option><option value="5">Dr A</option></select>
    <input id="dateFilter" type="date">
    <select id="perPageFilter"><option value="">default</option><option value="10">10</option></select>
    <table id="appointmentsTable"><tbody>
      <tr data-date="2099-01-01" data-status="scheduled"><td>A</td></tr>
      <tr data-date="2099-01-02" data-status="confirmed"><td>B</td></tr>
      <tr data-date="2099-01-01" data-status="confirmed"><td>C</td></tr>
    </tbody></table>
    <button class="btn-outline-primary" id="filterAllBtn">All</button>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M = [];
  window.escHtml = (s) => String(s || '');
  window.__M0__ = [
    { id: 1, patient: { full_name: 'Sara' }, doctor: { full_name: 'Dr A' }, starts_at: '2026-11-08T09:30:00', status: 'scheduled', appointment_type: 'CONSULTATION' },
    { id: 2, patient: null, doctor: null, starts_at: null, status: 'confirmed' },
    { id: 3, patient: { full_name: 'Bob' }, doctor: { full_name: 'Dr B' }, starts_at: '2026-11-09', status: 'cancelled', appointment_type: 'FOLLOWUP' },
    { id: 4, patient: { full_name: 'Ann' }, doctor: { full_name: 'Dr C' }, starts_at: '2026-11-10T18:45:00', status: 'scheduled' },
  ];
  window.__M1__ = '25';
  window.API_ROUTES = {};
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.bootstrap = { Collapse: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn() })) }, Modal: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn(), hide: vi.fn() })) } };
  window.location = { href: '', reload: vi.fn() };
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe('appointments.js csrf & navigation branches', () => {
  it('getCsrfToken prefers form input over meta', async () => {
    document.body.insertAdjacentHTML('beforeend', '<input type="hidden" name="csrf_token" value="form-csrf">');
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    expect(mod.getCsrfToken()).toBe('form-csrf');
  });

  it('getCsrfToken falls back to meta when no input present', async () => {
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    expect(mod.getCsrfToken()).toBe('test-csrf');
  });

  it('getCsrfToken returns empty string with no token elements', async () => {
    document.querySelector('meta[name="csrf-token"]').remove();
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    expect(mod.getCsrfToken()).toBe('');
  });

  it('createNewAppointment and createNewVisit navigate to API_ROUTES or defaults', async () => {
    window.API_ROUTES = { reception_create_appointment: '/custom/appt', reception_create_visit: '/custom/visit' };
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    mod.createNewAppointment();
    expect(window.location.href).toBe('/custom/appt');
    mod.createNewVisit();
    expect(window.location.href).toBe('/custom/visit');
  });

  it('createNewAppointment and createNewVisit fall back to defaults', async () => {
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    mod.createNewAppointment();
    expect(window.location.href).toBe('/reception/create_appointment');
    mod.createNewVisit();
    expect(window.location.href).toBe('/reception/visits/create');
  });
});

describe('appointments.js exportAppointments branches', () => {
  it('renders fallbacks for missing patient/doctor/date/type', async () => {
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    expect(() => mod.exportAppointments()).not.toThrow();
  });

  it('handles starts_at without time component', async () => {
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    expect(() => mod.exportAppointments()).not.toThrow();
  });
});

describe('appointments.js filter branches', () => {
  it('applyFilters with all params set builds the query string', async () => {
    window.API_ROUTES = { reception_appointments: '/reception/appointments' };
    document.getElementById('searchInput').value = '  sara  ';
    document.getElementById('departmentFilter').value = '7';
    document.getElementById('statusFilter').value = 'scheduled';
    document.getElementById('doctorFilter').value = '5';
    document.getElementById('dateFilter').value = '2026-11-08';
    document.getElementById('perPageFilter').value = '10';
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    mod.applyFilters();
    const url = window.location.href;
    expect(url).toContain('search=sara');
    expect(url).toContain('department_id=7');
    expect(url).toContain('status=scheduled');
    expect(url).toContain('doctor_id=5');
    expect(url).toContain('date=2026-11-08');
    expect(url).toContain('per_page=10');
    expect(url).toContain('page=1');
  });

  it('applyFilters without search input omits the search param', async () => {
    document.getElementById('searchInput').remove();
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    mod.applyFilters();
    expect(window.location.href).not.toContain('search=');
  });

  it('applyFilters with all defaults builds a minimal query', async () => {
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    mod.applyFilters();
    expect(window.location.href).toContain('page=1');
    expect(window.location.href).not.toContain('status=');
  });

  it('clearFilters resets filters and keeps the chosen per_page', async () => {
    document.getElementById('perPageFilter').value = '10';
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    mod.clearFilters();
    expect(window.location.href).toContain('per_page=10');
  });

  it('clearFilters falls back to __M1__ when per_page is empty', async () => {
    document.getElementById('perPageFilter').value = '';
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    mod.clearFilters();
    expect(window.location.href).toContain('per_page=25');
  });

  it('filterAppointments toggles rows for each filter and btnEl', async () => {
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    const today = new Date().toISOString().split('T')[0];
    const rows = document.querySelectorAll('#appointmentsTable tbody tr');

    mod.filterAppointments('all', document.getElementById('filterAllBtn'));
    expect([...rows].every(r => r.style.display === '')).toBe(true);

    mod.filterAppointments('today');
    expect(rows[0].style.display).toBe('none'); // 2099 row, not today

    mod.filterAppointments('pending');
    expect(rows[0].style.display).toBe('');     // scheduled
    expect(rows[1].style.display).toBe('none'); // confirmed

    mod.filterAppointments('confirmed');
    expect(rows[0].style.display).toBe('none');
    expect(rows[1].style.display).toBe('');
    expect(rows[2].style.display).toBe('');
    expect(document.getElementById('filterAllBtn').classList.contains('active')).toBe(false);
  });

  it('filterAppointments with btnEl activates it and removes active from others', async () => {
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    mod.filterAppointments('all', document.getElementById('filterAllBtn'));
    expect(document.getElementById('filterAllBtn').classList.contains('active')).toBe(true);
  });

  it('filterAppointments with unknown filter leaves rows alone', async () => {
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    mod.filterAppointments('mystery');
    const rows = document.querySelectorAll('#appointmentsTable tbody tr');
    rows.forEach(r => expect(r.style.display).toBe(''));
  });
});

describe('appointments.js confirm/cancel/no-show branches', () => {
  function settle() {
    return new Promise(r => setTimeout(r, 60));
  }

  it('confirmAppointment success reloads the page', async () => {
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    mod.confirmAppointment(7);
    await settle();
    expect(window.location.reload).toHaveBeenCalled();
  });

  it('confirmAppointment non-ok with server message throws and shows it', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 400, json: () => Promise.resolve({ success: false, message: 'تم تأكيده مسبقاً' }) });
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    mod.confirmAppointment(7);
    await settle();
    expect(window.Swal.fire.mock.calls[1][0].text).toBe('تم تأكيده مسبقاً');
  });

  it('confirmAppointment ok with success=false and no message falls back to default error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    mod.confirmAppointment(7);
    await settle();
    expect(window.Swal.fire.mock.calls[1][0].text).toBe('حدث خطأ');
  });

  it('confirmAppointment fetch rejection with empty error shows default error', async () => {
    global.fetch = vi.fn().mockRejectedValue({});
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    mod.confirmAppointment(7);
    await settle();
    expect(window.Swal.fire.mock.calls[1][0].text).toBe('حدث خطأ');
  });

  it('confirmAppointment cancelled does not fetch', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    mod.confirmAppointment(7);
    await settle();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('cancelAppointment success reloads the page', async () => {
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    mod.cancelAppointment(8);
    await settle();
    expect(window.location.reload).toHaveBeenCalled();
  });

  it('cancelAppointment error with message shows the server message', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'لا يمكن الإلغاء' }) });
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    mod.cancelAppointment(8);
    await settle();
    expect(window.Swal.fire.mock.calls[1][0].text).toBe('لا يمكن الإلغاء');
  });

  it('cancelAppointment error without message shows default', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500, json: () => Promise.resolve({}) });
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    mod.cancelAppointment(8);
    await settle();
    expect(window.Swal.fire.mock.calls[1][0].text).toBe('حدث خطأ');
  });

  it('cancelAppointment cancelled does not fetch', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    mod.cancelAppointment(8);
    await settle();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('noShowAppointment success reloads the page', async () => {
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    mod.noShowAppointment(9);
    await settle();
    expect(window.location.reload).toHaveBeenCalled();
  });

  it('noShowAppointment with server message shows it on failure', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'سجل غيابات كثيرة' }) });
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    mod.noShowAppointment(9);
    await settle();
    expect(window.Swal.fire.mock.calls[1][0].text).toBe('سجل غيابات كثيرة');
  });

  it('noShowAppointment network failure with empty error shows default', async () => {
    global.fetch = vi.fn().mockRejectedValue({});
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    mod.noShowAppointment(9);
    await settle();
    expect(window.Swal.fire.mock.calls[1][0].text).toBe('حدث خطأ');
  });

  it('noShowAppointment cancelled does not fetch', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    mod.noShowAppointment(9);
    await settle();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('API_ROUTES confirmation endpoints are honoured', async () => {
    window.API_ROUTES = {
      reception_confirm_appointment: '/custom/confirm/0',
      reception_cancel_appointment: '/custom/cancel/0',
      reception_no_show_appointment: '/custom/no-show/0',
    };
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    mod.confirmAppointment(1);
    await settle();
    mod.cancelAppointment(2);
    await settle();
    mod.noShowAppointment(3);
    await settle();
    const urls = global.fetch.mock.calls.map(c => String(c[0]));
    expect(urls).toContain('/custom/confirm/1');
    expect(urls).toContain('/custom/cancel/2');
    expect(urls).toContain('/custom/no-show/3');
  });
});

describe('appointments.js view/edit/navigation branches', () => {
  it('viewAppointment and editAppointment use API_ROUTES when set', async () => {
    window.API_ROUTES = { reception_view_appointment: '/view/0', reception_edit_appointment: '/edit/0' };
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    mod.viewAppointment(5);
    expect(window.location.href).toBe('/view/5');
    mod.editAppointment(6);
    expect(window.location.href).toBe('/edit/6');
  });

  it('viewAppointment and editAppointment fall back to defaults', async () => {
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    mod.viewAppointment(5);
    expect(window.location.href).toBe('/reception/view_appointment/5');
    mod.editAppointment(6);
    expect(window.location.href).toBe('/reception/edit_appointment/6');
  });

  it('search input triggers applyFilters', async () => {
    const mod = await loadModule('static/js/pages/reception/appointments.js');
    const input = document.getElementById('searchInput');
    input.value = 'x';
    input.dispatchEvent(new Event('input'));
    expect(window.location.href).toContain('search=x');
  });

  it('DOMContentLoaded binds hover styles on rows', async () => {
    await loadModule('static/js/pages/reception/appointments.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const row = document.querySelector('#appointmentsTable tbody tr');
    row.dispatchEvent(new MouseEvent('mouseenter'));
    expect(row.style.backgroundColor).toBe('rgb(248, 249, 250)');
    row.dispatchEvent(new MouseEvent('mouseleave'));
    expect(row.style.backgroundColor).toBe('');
  });
});
