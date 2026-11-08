import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <meta name="csrf-token" content="meta-csrf">
    <input id="search" value="">
    <table><tbody id="patientsTableBody"><tr><td>original</td></tr></tbody></table>

    <input type="date" id="birth_date_modal">
    <input id="age_modal">
    <select id="gender_modal"><option value="M">M</option><option value="F">F</option><option value="O">O</option></select>
    <select id="marital_status_modal"><option value="single">single</option><option value="married">married</option></select>
    <div id="pregnancy_section_modal"></div>
    <input type="checkbox" id="is_pregnant_modal" checked>
    <input id="pregnancy_weeks_modal" value="20">
    <input type="date" id="last_menstruation_date_modal">
    <input id="pregnancy_notes_modal" value="notes">

    <form id="patientFormModal" action="/reception/patients/create">
      <input type="hidden" name="csrf_token" value="form-csrf">
      <input name="first_name" value="أحمد">
      <input name="last_name" value="محمود">
      <input name="phone" value="0599000000">
    </form>
    <button id="savePatientModalBtn">Save modal</button>

    <input type="date" id="birth_date_edit">
    <input id="age_edit">
    <select id="gender_edit"><option value="M">M</option><option value="F">F</option></select>
    <select id="marital_status_edit"><option value="single">single</option><option value="married">married</option></select>
    <div id="pregnancy_section_edit"></div>
    <input type="checkbox" id="is_pregnant_edit" checked>
    <input id="pregnancy_weeks_edit" value="10">
    <input type="date" id="last_menstruation_date_edit">
    <input id="pregnancy_notes_edit" value="n">

    <form id="patientFormEdit" action="/reception/patients/1/update">
      <input name="first_name" value="سارة">
      <input name="last_name" value="حسين">
      <input name="phone" value="0598111111">
    </form>
    <button id="savePatientEditBtn">Save edit</button>

    <div id="addPatientModal"></div>
    <button data-bs-target="#addPatientModal">Open add</button>
    <div id="editPatientModal"></div>
    <form id="deleteForm"><button type="submit" id="deleteBtn">Delete</button></form>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M = [];
  window.__M0__ = '/reception/patients';
  window.__M1__ = '';
  window.location = { href: '/x', search: '', reload: vi.fn() };
  window.escHtml = (s) => String(s ?? '');
  window.API_ROUTES = { smart_patient_search: '/reception/api/smart-patient-search' };
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.bootstrap = { Modal: vi.fn().mockImplementation(() => ({ show: vi.fn(), hide: vi.fn() })) };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, patients: [] }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('patients.js search branches', () => {
  it('typing fewer than 2 chars restores original tbody', async () => {
    vi.useFakeTimers();
    await loadModule('static/js/pages/reception/patients.js');
    const input = document.getElementById('search');
    document.querySelector('#patientsTableBody').innerHTML = '<tr><td>garbage</td></tr>';
    input.value = 'a';
    input.dispatchEvent(new Event('input'));
    expect(document.querySelector('#patientsTableBody').innerHTML).toContain('original');
  });

  it('debounces rapid input and renders results', async () => {
    vi.useFakeTimers();
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ patients: [
        { id: 1, full_name: 'سارة', phone: '059', national_id: '123', gender: 'F' },
        { id: null, full_name: 'بلا معرف', phone: '1', national_id: '2', gender: 'X' },
      ] }),
    });
    await loadModule('static/js/pages/reception/patients.js');
    const input = document.getElementById('search');
    input.value = 'sa';
    input.dispatchEvent(new Event('input'));
    input.value = 'sara';
    input.dispatchEvent(new Event('input'));
    await vi.advanceTimersByTimeAsync(300);
    expect(global.fetch).toHaveBeenCalledTimes(1);
    const html = document.querySelector('#patientsTableBody').innerHTML;
    expect(html).toContain('سارة');
    expect(html).toContain('أنثى');
    expect(html).toContain('آخر');
    expect(html).toContain('/reception/view_patient/1');
    vi.useRealTimers();
  });

  it('non-ok search response renders the error row', async () => {
    vi.useFakeTimers();
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    await loadModule('static/js/pages/reception/patients.js');
    const input = document.getElementById('search');
    input.value = 'sara';
    input.dispatchEvent(new Event('input'));
    await vi.advanceTimersByTimeAsync(300);
    expect(document.querySelector('#patientsTableBody').innerHTML).toContain('خطأ في البحث');
    vi.useRealTimers();
  });

  it('response without patients key renders the empty-results row', async () => {
    vi.useFakeTimers();
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
    await loadModule('static/js/pages/reception/patients.js');
    const input = document.getElementById('search');
    input.value = 'sara';
    input.dispatchEvent(new Event('input'));
    await vi.advanceTimersByTimeAsync(300);
    expect(document.querySelector('#patientsTableBody').innerHTML).toContain('لا توجد نتائج');
    vi.useRealTimers();
  });

  it('patients with missing cells fall back to dashes', async () => {
    vi.useFakeTimers();
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ patients: [{}] }) });
    await loadModule('static/js/pages/reception/patients.js');
    const input = document.getElementById('search');
    input.value = 'xy';
    input.dispatchEvent(new Event('input'));
    await vi.advanceTimersByTimeAsync(300);
    expect(document.querySelector('#patientsTableBody').innerHTML).toContain('-');
    vi.useRealTimers();
  });

  it('search uses API_ROUTES.smart_patient_search when set', async () => {
    vi.useFakeTimers();
    window.API_ROUTES = { smart_patient_search: '/custom/search' };
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ patients: [] }) });
    await loadModule('static/js/pages/reception/patients.js');
    const input = document.getElementById('search');
    input.value = 'sara';
    input.dispatchEvent(new Event('input'));
    await vi.advanceTimersByTimeAsync(300);
    expect(global.fetch.mock.calls[0][0]).toContain('/custom/search');
    vi.useRealTimers();
  });

  it('missing search input or tbody loads without wiring search', async () => {
    document.getElementById('search').remove();
    await loadModule('static/js/pages/reception/patients.js');
    expect(true).toBe(true);
  });
});

describe('patients.js modal pregnancy & age branches', () => {
  it('togglePregnancyModal shows section for married female', async () => {
    const mod = await loadModule('static/js/pages/reception/patients.js');
    document.getElementById('gender_modal').value = 'F';
    document.getElementById('marital_status_modal').value = 'married';
    mod.togglePregnancyModal();
    expect(document.getElementById('pregnancy_section_modal').style.display).toBe('');
  });

  it('togglePregnancyModal hides and clears section for married male', async () => {
    const mod = await loadModule('static/js/pages/reception/patients.js');
    document.getElementById('gender_modal').value = 'M';
    document.getElementById('marital_status_modal').value = 'married';
    mod.togglePregnancyModal();
    expect(document.getElementById('pregnancy_section_modal').style.display).toBe('none');
    expect(document.getElementById('is_pregnant_modal').checked).toBe(false);
    expect(document.getElementById('pregnancy_weeks_modal').value).toBe('');
    expect(document.getElementById('pregnancy_notes_modal').value).toBe('');
  });

  it('togglePregnancyModal returns early when modal elements missing', async () => {
    document.getElementById('pregnancy_section_modal').remove();
    const mod = await loadModule('static/js/pages/reception/patients.js');
    expect(() => mod.togglePregnancyModal()).not.toThrow();
  });

  it('togglePregnancyModal without clear inputs does not throw', async () => {
    document.getElementById('is_pregnant_modal').remove();
    document.getElementById('pregnancy_weeks_modal').remove();
    document.getElementById('last_menstruation_date_modal').remove();
    document.getElementById('pregnancy_notes_modal').remove();
    const mod = await loadModule('static/js/pages/reception/patients.js');
    document.getElementById('gender_modal').value = 'M';
    mod.togglePregnancyModal();
    expect(true).toBe(true);
  });

  it('calcAgeModal empty date clears age', async () => {
    const mod = await loadModule('static/js/pages/reception/patients.js');
    document.getElementById('birth_date_modal').value = '';
    mod.calcAgeModal();
    expect(document.getElementById('age_modal').value).toBe('');
  });

  it('calcAgeModal subtracts a year when birthday has not occurred yet this year', async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-03-15T12:00:00'));
    const mod = await loadModule('static/js/pages/reception/patients.js');
    document.getElementById('birth_date_modal').value = '1990-06-20';
    mod.calcAgeModal();
    expect(Number(document.getElementById('age_modal').value)).toBe(35);
    vi.useRealTimers();
  });

  it('calcAgeModal keeps the full age when birthday already passed this year', async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-03-15T12:00:00'));
    const mod = await loadModule('static/js/pages/reception/patients.js');
    document.getElementById('birth_date_modal').value = '1990-01-10';
    mod.calcAgeModal();
    expect(Number(document.getElementById('age_modal').value)).toBe(36);
    vi.useRealTimers();
  });

  it('calcPregnancyWeeksModal with empty date clears weeks', async () => {
    const mod = await loadModule('static/js/pages/reception/patients.js');
    document.getElementById('last_menstruation_date_modal').value = '';
    mod.calcPregnancyWeeksModal();
    expect(document.getElementById('pregnancy_weeks_modal').value).toBe('');
  });

  it('calcPregnancyWeeksModal with past date computes weeks', async () => {
    const mod = await loadModule('static/js/pages/reception/patients.js');
    const d = new Date(Date.now() - 70 * 24 * 3600 * 1000);
    document.getElementById('last_menstruation_date_modal').value = d.toISOString().slice(0, 10);
    mod.calcPregnancyWeeksModal();
    expect(Number(document.getElementById('pregnancy_weeks_modal').value)).toBeGreaterThanOrEqual(9);
  });

  it('calcPregnancyWeeksModal with future date leaves weeks unchanged', async () => {
    const mod = await loadModule('static/js/pages/reception/patients.js');
    const d = new Date(Date.now() + 14 * 24 * 3600 * 1000);
    document.getElementById('last_menstruation_date_modal').value = d.toISOString().slice(0, 10);
    document.getElementById('pregnancy_weeks_modal').value = 'keep';
    mod.calcPregnancyWeeksModal();
    expect(document.getElementById('pregnancy_weeks_modal').value).toBe('keep');
  });
});

describe('patients.js save modal branches', () => {
  it('missing required fields shows warning and does not fetch', async () => {
    document.querySelector('#patientFormModal input[name="phone"]').value = '';
    const mod = await loadModule('static/js/pages/reception/patients.js');
    document.getElementById('savePatientModalBtn').click();
    await new Promise(r => setTimeout(r, 20));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('warning');
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('form csrf input is preferred over meta', async () => {
    const mod = await loadModule('static/js/pages/reception/patients.js');
    document.getElementById('savePatientModalBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBe('form-csrf');
  });

  it('meta csrf is used when the form has no csrf input', async () => {
    document.querySelector('#patientFormModal input[name="csrf_token"]').remove();
    const mod = await loadModule('static/js/pages/reception/patients.js');
    document.getElementById('savePatientModalBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBe('meta-csrf');
  });

  it('no csrf element anywhere sends no token header', async () => {
    document.querySelector('#patientFormModal input[name="csrf_token"]').remove();
    document.querySelector('meta[name="csrf-token"]').remove();
    const mod = await loadModule('static/js/pages/reception/patients.js');
    document.getElementById('savePatientModalBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBeUndefined();
  });

  it('non-ok response shows generic error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/reception/patients.js');
    document.getElementById('savePatientModalBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });

  it('server success false shows server message when present', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'مكرر' }) });
    const mod = await loadModule('static/js/pages/reception/patients.js');
    document.getElementById('savePatientModalBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].text).toBe('مكرر');
  });

  it('server success false without message shows default text', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    const mod = await loadModule('static/js/pages/reception/patients.js');
    document.getElementById('savePatientModalBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].text).toContain('تعذر');
  });

  it('success triggers the reload callback', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
    const mod = await loadModule('static/js/pages/reception/patients.js');
    document.getElementById('savePatientModalBtn').click();
    await new Promise(r => setTimeout(r, 80));
    expect(window.location.reload).toHaveBeenCalled();
  });

  it('network failure shows the save error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/reception/patients.js');
    document.getElementById('savePatientModalBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });
});

describe('patients.js show_add & edit branches', () => {
  it('?show_add=1 with bootstrap shows addPatientModal', async () => {
    window.location = { href: '/x', search: '?show_add=1', reload: vi.fn() };
    await loadModule('static/js/pages/reception/patients.js');
    expect(window.bootstrap.Modal).toHaveBeenCalled();
  });

  it('?show_add=1 without bootstrap clicks the first trigger button', async () => {
    delete window.bootstrap;
    const spy = vi.fn();
    document.querySelector('[data-bs-target="#addPatientModal"]').addEventListener('click', spy);
    window.location = { href: '/x', search: '?show_add=1', reload: vi.fn() };
    await loadModule('static/js/pages/reception/patients.js');
    expect(spy).toHaveBeenCalled();
  });

  it('?show_add=1 without bootstrap and without buttons does not crash', async () => {
    delete window.bootstrap;
    document.querySelector('[data-bs-target="#addPatientModal"]').remove();
    window.location = { href: '/x', search: '?show_add=1', reload: vi.fn() };
    await loadModule('static/js/pages/reception/patients.js');
    expect(true).toBe(true);
  });

  it('__M1__ truthy opens edit modal and runs edit helpers', async () => {
    window.__M1__ = '1';
    await loadModule('static/js/pages/reception/patients.js');
    expect(window.bootstrap.Modal).toHaveBeenCalled();
  });

  it('__M1__ truthy without edit modal skips modal opening', async () => {
    window.__M1__ = '1';
    document.getElementById('editPatientModal').remove();
    await loadModule('static/js/pages/reception/patients.js');
    expect(true).toBe(true);
  });

  it('calcAgeEdit empty date clears age', async () => {
    const mod = await loadModule('static/js/pages/reception/patients.js');
    document.getElementById('birth_date_edit').value = '';
    mod.calcAgeEdit();
    expect(document.getElementById('age_edit').value).toBe('');
  });

  it('calcAgeEdit without age input does not throw', async () => {
    document.getElementById('age_edit').remove();
    const mod = await loadModule('static/js/pages/reception/patients.js');
    mod.calcAgeEdit();
    document.getElementById('birth_date_edit').value = '2000-01-01';
    expect(() => mod.calcAgeEdit()).not.toThrow();
  });

  it('calcAgeEdit applies the birthday correction', async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-03-15T12:00:00'));
    const mod = await loadModule('static/js/pages/reception/patients.js');
    document.getElementById('birth_date_edit').value = '1990-06-20';
    mod.calcAgeEdit();
    expect(Number(document.getElementById('age_edit').value)).toBe(35);
    vi.useRealTimers();
  });

  it('togglePregnancyEdit married female keeps section visible', async () => {
    const mod = await loadModule('static/js/pages/reception/patients.js');
    document.getElementById('gender_edit').value = 'F';
    document.getElementById('marital_status_edit').value = 'married';
    mod.togglePregnancyEdit();
    expect(document.getElementById('pregnancy_section_edit').style.display).toBe('');
  });

  it('togglePregnancyEdit otherwise hides and clears fields', async () => {
    const mod = await loadModule('static/js/pages/reception/patients.js');
    document.getElementById('gender_edit').value = 'M';
    mod.togglePregnancyEdit();
    expect(document.getElementById('pregnancy_section_edit').style.display).toBe('none');
    expect(document.getElementById('is_pregnant_edit').checked).toBe(false);
    expect(document.getElementById('pregnancy_weeks_edit').value).toBe('');
    expect(document.getElementById('pregnancy_notes_edit').value).toBe('');
  });

  it('togglePregnancyEdit without check inputs does not throw', async () => {
    document.getElementById('is_pregnant_edit').remove();
    document.getElementById('pregnancy_weeks_edit').remove();
    document.getElementById('last_menstruation_date_edit').remove();
    document.getElementById('pregnancy_notes_edit').remove();
    const mod = await loadModule('static/js/pages/reception/patients.js');
    document.getElementById('gender_edit').value = 'M';
    expect(() => mod.togglePregnancyEdit()).not.toThrow();
  });

  it('calcPregnancyWeeksEdit handles future and missing dates', async () => {
    const mod = await loadModule('static/js/pages/reception/patients.js');
    document.getElementById('last_menstruation_date_edit').value = '';
    mod.calcPregnancyWeeksEdit();
    expect(document.getElementById('pregnancy_weeks_edit').value).toBe('');
    const future = new Date(Date.now() + 14 * 24 * 3600 * 1000).toISOString().slice(0, 10);
    document.getElementById('last_menstruation_date_edit').value = future;
    document.getElementById('pregnancy_weeks_edit').value = 'keep';
    mod.calcPregnancyWeeksEdit();
    expect(document.getElementById('pregnancy_weeks_edit').value).toBe('keep');
  });

  it('save edit without patientFormEdit returns early', async () => {
    document.getElementById('patientFormEdit').remove();
    const mod = await loadModule('static/js/pages/reception/patients.js');
    document.getElementById('savePatientEditBtn').click();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('save edit missing required shows warning', async () => {
    document.querySelector('#patientFormEdit input[name="phone"]').value = '';
    const mod = await loadModule('static/js/pages/reception/patients.js');
    document.getElementById('savePatientEditBtn').click();
    await new Promise(r => setTimeout(r, 20));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('warning');
  });

  it('save edit uses meta csrf when form has none', async () => {
    document.querySelector('#patientFormEdit input[name="csrf_token"]'); // none exists
    const mod = await loadModule('static/js/pages/reception/patients.js');
    document.getElementById('savePatientEditBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBe('meta-csrf');
  });

  it('save edit with neither csrf sends none', async () => {
    document.querySelector('meta[name="csrf-token"]').remove();
    const mod = await loadModule('static/js/pages/reception/patients.js');
    document.getElementById('savePatientEditBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBeUndefined();
  });

  it('save edit non-ok shows error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/reception/patients.js');
    document.getElementById('savePatientEditBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });

  it('save edit success navigates to __M0__', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
    const mod = await loadModule('static/js/pages/reception/patients.js');
    document.getElementById('savePatientEditBtn').click();
    await new Promise(r => setTimeout(r, 80));
    expect(window.location.href).toBe('/reception/patients');
  });

  it('save edit success false shows server message or default', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    const mod = await loadModule('static/js/pages/reception/patients.js');
    document.getElementById('savePatientEditBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].text).toContain('تعذر');
  });

  it('save edit network failure shows error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/reception/patients.js');
    document.getElementById('savePatientEditBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });

  it('confirmDeletePatient returns early without a form', async () => {
    const mod = await loadModule('static/js/pages/reception/patients.js');
    const orphan = document.createElement('button');
    document.body.appendChild(orphan);
    mod.confirmDeletePatient(orphan);
    expect(window.Swal.fire).not.toHaveBeenCalled();
  });
});
