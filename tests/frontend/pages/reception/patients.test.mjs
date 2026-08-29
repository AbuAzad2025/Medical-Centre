import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <input type="text" id="search" />
    <tbody id="patientsTableBody"><tr><td>existing</td></tr></tbody>
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
    <form id="patientFormModal" action="/test"></form>
  `;
  window.__M0__ = '/reception/patients';
  window.__M1__ = null;
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.Toast = { fire: vi.fn() };
  window.bootstrap = { Modal: { getOrCreateInstance: () => ({ show: vi.fn(), hide: vi.fn() }) } };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
  delete window.location;
  window.location = { href: '', reload: vi.fn(), search: '' };
});

describe('reception/patients.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/reception/patients.js');
  });

  test('calcAgeModal is a function', async () => {
    await loadScript('static/js/pages/reception/patients.js');
    expect(typeof calcAgeModal).toBe('function');
  });

  test('togglePregnancyModal is a function', async () => {
    await loadScript('static/js/pages/reception/patients.js');
    expect(typeof togglePregnancyModal).toBe('function');
  });

  test('calcPregnancyWeeksModal is a function', async () => {
    await loadScript('static/js/pages/reception/patients.js');
    expect(typeof calcPregnancyWeeksModal).toBe('function');
  });

  test('confirmDeletePatient is a function', async () => {
    await loadScript('static/js/pages/reception/patients.js');
    expect(typeof confirmDeletePatient).toBe('function');
  });

  test('calcAgeModal calculates age from birth date', async () => {
    await loadScript('static/js/pages/reception/patients.js');
    const input = document.getElementById('birth_date_modal');
    const today = new Date();
    input.value = `${today.getFullYear() - 25}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
    calcAgeModal();
    expect(document.getElementById('age_modal').value).toBe('25');
  });

  test('calcAgeModal clears age when empty', async () => {
    await loadScript('static/js/pages/reception/patients.js');
    document.getElementById('birth_date_modal').value = '';
    calcAgeModal();
    expect(document.getElementById('age_modal').value).toBe('');
  });

  test('togglePregnancyModal shows section for married female', async () => {
    await loadScript('static/js/pages/reception/patients.js');
    document.getElementById('gender_modal').value = 'F';
    document.getElementById('marital_status_modal').value = 'married';
    togglePregnancyModal();
    expect(document.getElementById('pregnancy_section_modal').style.display).toBe('');
  });

  test('togglePregnancyModal hides section for male', async () => {
    await loadScript('static/js/pages/reception/patients.js');
    document.getElementById('gender_modal').value = 'M';
    document.getElementById('marital_status_modal').value = 'married';
    togglePregnancyModal();
    expect(document.getElementById('pregnancy_section_modal').style.display).toBe('none');
  });

  test('confirmDeletePatient shows confirmation dialog', async () => {
    await loadScript('static/js/pages/reception/patients.js');
    const form = document.createElement('form');
    document.body.appendChild(form);
    const btn = document.createElement('button');
    form.appendChild(btn);
    btn.closest = () => form;
    confirmDeletePatient(btn);
    expect(window.Swal.fire).toHaveBeenCalled();
  });
});
