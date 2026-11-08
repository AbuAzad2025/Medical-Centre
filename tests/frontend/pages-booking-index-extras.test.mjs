import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <select id="department_id"><option value="">All</option><option value="9">Cardio</option></select>
    <select id="doctor_id"></select>
    <input id="appointment_date" type="date" value="2026-11-09">
    <select id="appointment_time"></select>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M = ['preset'];
  window.__M0__ = '/api/doctors';
  window.__M1__ = '/api/times';
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ doctors: [{ id: 1, full_name: 'Dr A' }], available_times: ['09:00'] }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('booking/index.js remaining arms', () => {
  it('response without doctors key renders the placeholder only', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
    const mod = await loadModule('static/js/pages/booking/index.js');
    await mod.loadDoctors();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('doctor_id').querySelectorAll('option').length).toBe(1);
  });

  it('non-ok doctors response leaves the select untouched', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/booking/index.js');
    await mod.loadDoctors();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('doctor_id').querySelectorAll('option').length).toBe(0);
  });

  it('response without available_times key renders an empty time select', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
    const mod = await loadModule('static/js/pages/booking/index.js');
    document.getElementById('doctor_id').innerHTML = '<option value="5" selected>Dr</option>';
    await mod.loadTimes();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('appointment_time').querySelectorAll('option').length).toBe(1);
  });

  it('non-ok times response leaves the time select untouched', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/booking/index.js');
    document.getElementById('doctor_id').innerHTML = '<option value="5" selected>Dr</option>';
    await mod.loadTimes();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('appointment_time').querySelectorAll('option').length).toBe(0);
  });
});
