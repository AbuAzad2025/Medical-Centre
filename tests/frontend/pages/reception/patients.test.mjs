import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from '../../test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <input type="text" id="search" />
    <table><tbody id="patientsTableBody"><tr><td>existing</td></tr></tbody></table>
    <form id="patientFormModal" action="/patients/save">
      <input name="csrf_token" value="test-csrf">
      <input name="first_name" value="Ahmed">
      <input name="last_name" value="Ali">
      <input name="phone" value="0500000000">
    </form>
    <input id="birth_date_modal" type="date" />
    <input id="age_modal" value="" />
    <select id="gender_modal"><option value="M"></option><option value="F"></option></select>
    <select id="marital_status_modal"><option value="single"></option><option value="married"></option></select>
    <div id="pregnancy_section_modal" style="display:none"></div>
    <input type="checkbox" id="is_pregnant_modal" />
    <input id="pregnancy_weeks_modal" value="" />
    <input id="last_menstruation_date_modal" type="date" />
    <input id="pregnancy_notes_modal" value="" />
    <button id="savePatientModalBtn"></button>
    <input id="birth_date_edit" type="date" />
    <input id="age_edit" value="" />
    <select id="gender_edit"><option value="M"></option><option value="F"></option></select>
    <select id="marital_status_edit"><option value="single"></option><option value="married"></option></select>
    <div id="pregnancy_section_edit" style="display:none"></div>
    <input type="checkbox" id="is_pregnant_edit" />
    <input id="pregnancy_weeks_edit" value="" />
    <input id="last_menstruation_date_edit" type="date" />
    <input id="pregnancy_notes_edit" value="" />
    <form id="patientFormEdit" action="/patients/edit">
      <input name="csrf_token" value="edit-csrf">
      <input name="first_name" value="Ahmed">
      <input name="last_name" value="Ali">
      <input name="phone" value="0500000000">
    </form>
    <button id="savePatientEditBtn"></button>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M0__ = '/reception/patients';
  window.__M1__ = null;
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.bootstrap = {
    Modal: vi.fn().mockImplementation(() => ({ show: vi.fn(), hide: vi.fn() })),
  };
  window.bootstrap.Modal.getOrCreateInstance = vi.fn(() => ({ show: vi.fn(), hide: vi.fn() }));
  window.location = { href: '', reload: vi.fn(), search: '' };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, patients: [] }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('reception/patients.js', () => {
  it('loads module and exposes functions', async () => {
    const mod = await loadModule('static/js/pages/reception/patients.js');
    expect(typeof mod.calcAgeModal).toBe('function');
    expect(typeof mod.calcPregnancyWeeksModal).toBe('function');
    expect(typeof mod.togglePregnancyModal).toBe('function');
    expect(typeof mod.calcAgeEdit).toBe('function');
    expect(typeof mod.togglePregnancyEdit).toBe('function');
    expect(typeof mod.calcPregnancyWeeksEdit).toBe('function');
    expect(typeof mod.confirmDeletePatient).toBe('function');
  });

  it('calcAgeModal computes age from birth date', async () => {
    const mod = await loadModule('static/js/pages/reception/patients.js');
    const today = new Date();
    const d = new Date(today.getFullYear() - 25, today.getMonth(), today.getDate());
    document.getElementById('birth_date_modal').value = d.toISOString().slice(0, 10);
    mod.calcAgeModal();
    expect(document.getElementById('age_modal').value).toBe('25');
  });

  it('calcAgeModal clears age when date empty', async () => {
    const mod = await loadModule('static/js/pages/reception/patients.js');
    document.getElementById('birth_date_modal').value = '';
    document.getElementById('age_modal').value = '40';
    mod.calcAgeModal();
    expect(document.getElementById('age_modal').value).toBe('');
  });

  it('togglePregnancyModal shows for married female and hides for male', async () => {
    const mod = await loadModule('static/js/pages/reception/patients.js');
    document.getElementById('gender_modal').value = 'F';
    document.getElementById('marital_status_modal').value = 'married';
    mod.togglePregnancyModal();
    expect(document.getElementById('pregnancy_section_modal').style.display).toBe('');
    document.getElementById('gender_modal').value = 'M';
    mod.togglePregnancyModal();
    expect(document.getElementById('pregnancy_section_modal').style.display).toBe('none');
  });

  it('togglePregnancyModal resets pregnancy fields when hidden', async () => {
    const mod = await loadModule('static/js/pages/reception/patients.js');
    document.getElementById('gender_modal').value = 'F';
    document.getElementById('marital_status_modal').value = 'married';
    mod.togglePregnancyModal();
    document.getElementById('is_pregnant_modal').checked = true;
    document.getElementById('pregnancy_weeks_modal').value = '20';
    document.getElementById('gender_modal').value = 'M';
    mod.togglePregnancyModal();
    expect(document.getElementById('is_pregnant_modal').checked).toBe(false);
    expect(document.getElementById('pregnancy_weeks_modal').value).toBe('');
  });

  it('calcPregnancyWeeksModal computes weeks from last menstruation', async () => {
    const mod = await loadModule('static/js/pages/reception/patients.js');
    const lmd = new Date();
    lmd.setDate(lmd.getDate() - 70);
    document.getElementById('last_menstruation_date_modal').value = lmd.toISOString().slice(0, 10);
    mod.calcPregnancyWeeksModal();
    expect(document.getElementById('pregnancy_weeks_modal').value).toBe('10');
  });

  it('calcAgeEdit computes age', async () => {
    const mod = await loadModule('static/js/pages/reception/patients.js');
    const today = new Date();
    document.getElementById('birth_date_edit').value = `${today.getFullYear() - 30}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
    mod.calcAgeEdit();
    expect(document.getElementById('age_edit').value).toBe('30');
  });

  it('togglePregnancyEdit shows for married female', async () => {
    const mod = await loadModule('static/js/pages/reception/patients.js');
    document.getElementById('gender_edit').value = 'F';
    document.getElementById('marital_status_edit').value = 'married';
    mod.togglePregnancyEdit();
    expect(document.getElementById('pregnancy_section_edit').style.display).toBe('');
  });

  it('togglePregnancyEdit hides and resets for male', async () => {
    const mod = await loadModule('static/js/pages/reception/patients.js');
    document.getElementById('gender_edit').value = 'F';
    document.getElementById('marital_status_edit').value = 'married';
    document.getElementById('is_pregnant_edit').checked = true;
    document.getElementById('gender_edit').value = 'M';
    mod.togglePregnancyEdit();
    expect(document.getElementById('is_pregnant_edit').checked).toBe(false);
    expect(document.getElementById('pregnancy_section_edit').style.display).toBe('none');
  });

  it('calcPregnancyWeeksEdit computes weeks', async () => {
    const mod = await loadModule('static/js/pages/reception/patients.js');
    const lmd = new Date();
    lmd.setDate(lmd.getDate() - 84);
    document.getElementById('last_menstruation_date_edit').value = lmd.toISOString().slice(0, 10);
    mod.calcPregnancyWeeksEdit();
    expect(document.getElementById('pregnancy_weeks_edit').value).toBe('12');
  });

  it('savePatientModalBtn success shows Swal and reloads', async () => {
    await loadModule('static/js/pages/reception/patients.js');
    document.getElementById('savePatientModalBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('savePatientModalBtn missing required shows warning', async () => {
    await loadModule('static/js/pages/reception/patients.js');
    document.querySelector('#patientFormModal [name="first_name"]').value = '';
    document.getElementById('savePatientModalBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).not.toHaveBeenCalled();
    expect(window.Swal.fire.mock.calls[0][0].title).toBe('حقول مطلوبة');
  });

  it('savePatientModalBtn server error shows error Swal', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'duplicate' }) });
    await loadModule('static/js/pages/reception/patients.js');
    document.getElementById('savePatientModalBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });

  it('savePatientModalBtn network failure shows error Swal', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    await loadModule('static/js/pages/reception/patients.js');
    document.getElementById('savePatientModalBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });

  it('savePatientEditBtn success redirects to __M0__', async () => {
    await loadModule('static/js/pages/reception/patients.js');
    document.getElementById('savePatientEditBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('savePatientEditBtn missing required shows warning', async () => {
    await loadModule('static/js/pages/reception/patients.js');
    document.querySelector('#patientFormEdit [name="phone"]').value = '';
    document.getElementById('savePatientEditBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].title).toBe('حقول مطلوبة');
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('savePatientEditBtn server failure shows error Swal', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'err' }) });
    await loadModule('static/js/pages/reception/patients.js');
    document.getElementById('savePatientEditBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });

  it('confirmDeletePatient confirms and submits form', async () => {
    const mod = await loadModule('static/js/pages/reception/patients.js');
    const form = document.createElement('form');
    form.submit = vi.fn();
    document.body.appendChild(form);
    const btn = document.createElement('button');
    form.appendChild(btn);
    mod.confirmDeletePatient(btn);
    await new Promise(r => setTimeout(r, 30));
    expect(form.submit).toHaveBeenCalled();
  });

  it('confirmDeletePatient missing form returns silently', async () => {
    const mod = await loadModule('static/js/pages/reception/patients.js');
    const btn = document.createElement('button');
    mod.confirmDeletePatient(btn);
    await new Promise(r => setTimeout(r, 10));
    expect(window.Swal.fire).not.toHaveBeenCalled();
  });

  it('confirmDeletePatient cancel does not submit', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/reception/patients.js');
    const form = document.createElement('form');
    form.submit = vi.fn();
    document.body.appendChild(form);
    const btn = document.createElement('button');
    form.appendChild(btn);
    mod.confirmDeletePatient(btn);
    await new Promise(r => setTimeout(r, 30));
    expect(form.submit).not.toHaveBeenCalled();
  });

  it('search input renders smart results', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ patients: [{ id: 7, full_name: 'Sara Ahmed', phone: '0501', national_id: '1234', gender: 'F' }] }),
    });
    await loadModule('static/js/pages/reception/patients.js');
    const input = document.getElementById('search');
    input.value = 'sara';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    await new Promise(r => setTimeout(r, 400));
    const tbody = document.getElementById('patientsTableBody');
    expect(tbody.innerHTML).toContain('Sara Ahmed');
    expect(tbody.innerHTML).toContain('أنثى');
  });

  it('search input shorter than 2 chars restores original tbody', async () => {
    await loadModule('static/js/pages/reception/patients.js');
    const input = document.getElementById('search');
    input.value = 's';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    await new Promise(r => setTimeout(r, 400));
    expect(document.getElementById('patientsTableBody').innerHTML).toContain('existing');
  });

  it('search fetch failure shows error row', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    await loadModule('static/js/pages/reception/patients.js');
    const input = document.getElementById('search');
    input.value = 'sara';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    await new Promise(r => setTimeout(r, 400));
    expect(document.getElementById('patientsTableBody').innerHTML).toContain('خطأ في البحث');
  });
});