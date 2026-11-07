import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <select id="department_id"><option value="">All</option><option value="9">Cardiology</option></select>
    <select id="doctor_id"></select>
    <input type="date" id="appointment_date" value="2026-11-20">
    <select id="appointment_time"></select>
    <div id="smartSlotsHint"></div>
  `;
  document.getElementById('department_id').value = '9';
  window.__M = [];
  window.escHtml = (s) => s;
  window.__M0__ = '9';
  window.__M1__ = '09:00';
  window.__M2__ = '/api/booking/doctors';
  window.__M3__ = '/api/booking/times';
  window.__M4__ = '/api/booking/slots';
  window.API_ROUTES = {};
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.bootstrap = { Collapse: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn() })) }, Modal: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn(), hide: vi.fn() })) } };
  window.Chart = vi.fn().mockImplementation(() => ({}));
  if (window.Chart) window.Chart.defaults = { plugins: { tooltip: {}, legend: { labels: { font: {} } } }, font: {} };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ doctors: [{ id: 1, full_name: 'Dr A' }], available_times: ['09:00', '11:00'], suggested_times: ['10:00', '11:00'] }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('booking/create.js', () => {
  it('loadDoctors populates dropdown and calls loadTimes', async () => {
    const mod = await loadModule('static/js/pages/booking/create.js');
    mod.loadDoctors();
    await new Promise(r => setTimeout(r, 30));
    const sel = document.getElementById('doctor_id');
    expect(sel.options.length).toBeGreaterThanOrEqual(1);
  });

  it('loadDoctors with no department calls loadTimes when empty', async () => {
    document.getElementById('department_id').value = '';
    const mod = await loadModule('static/js/pages/booking/create.js');
    mod.loadDoctors();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
  });

  it('loadTimes populates available times', async () => {
    document.getElementById('doctor_id').innerHTML = '<option value="1" selected>Dr A</option>';
    document.getElementById('doctor_id').value = '1';
    const mod = await loadModule('static/js/pages/booking/create.js');
    mod.loadTimes();
    await new Promise(r => setTimeout(r, 30));
    const sel = document.getElementById('appointment_time');
    expect(sel.options.length).toBeGreaterThanOrEqual(2);
  });

  it('loadTimes without doc/date does not fetch', async () => {
    document.getElementById('doctor_id').value = '';
    document.getElementById('appointment_time').innerHTML = '';
    const mod = await loadModule('static/js/pages/booking/create.js');
    mod.loadTimes();
    expect(global.fetch).not.toHaveBeenCalled();
    expect(document.getElementById('appointment_time').innerHTML).toContain('اختر الوقت');
  });

  it('loadSmartSlots shows suggested times', async () => {
    document.getElementById('doctor_id').innerHTML = '<option value="1" selected>Dr A</option>';
    document.getElementById('doctor_id').value = '1';
    document.getElementById('appointment_time').innerHTML = '<option value="" selected></option><option value="08:00">08:00</option><option value="10:00">10:00</option>';
    const mod = await loadModule('static/js/pages/booking/create.js');
    mod.loadSmartSlots();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('smartSlotsHint').textContent).toContain('الأوقات المقترحة');
    expect(document.getElementById('appointment_time').value).toBe('10:00');
  });

  it('loadSmartSlots without doc/date shows hint', async () => {
    document.getElementById('doctor_id').value = '';
    const mod = await loadModule('static/js/pages/booking/create.js');
    mod.loadSmartSlots();
    expect(document.getElementById('smartSlotsHint').textContent).toContain('اختر الطبيب والتاريخ');
  });

  it('DOMContentLoaded with preset department calls loadDoctors', async () => {
    await loadModule('static/js/pages/booking/create.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
  });
});