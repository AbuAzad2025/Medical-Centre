import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <select id="department_id"><option value=""></option><option value="7">Cardiology</option></select>
    <select id="doctor_id"></select>
    <input type="date" id="appointment_date" value="2026-11-20">
    <select id="appointment_time"></select>
  `;
  document.getElementById('department_id').value = '7';
  window.__M0__ = '/api/booking/doctors';
  window.__M1__ = '/api/booking/times';
  window.API_ROUTES = {};
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ doctors: [{ id: 1, full_name: 'Dr A' }], available_times: ['09:00', '11:00'] }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('booking/index.js', () => {
  it('exposes loadDoctors and loadTimes on window', async () => {
    await loadModule('static/js/pages/booking/index.js');
    expect(typeof window.loadDoctors).toBe('function');
    expect(typeof window.loadTimes).toBe('function');
  });

  it('loadDoctors renders doctors for department', async () => {
    const mod = await loadModule('static/js/pages/booking/index.js');
    mod.loadDoctors();
    await new Promise(r => setTimeout(r, 30));
    expect(String(global.fetch.mock.calls[0][0])).toContain('department_id=7');
    expect(document.getElementById('doctor_id').innerHTML).toContain('Dr A');
  });

  it('loadDoctors with empty department calls without query', async () => {
    document.getElementById('department_id').value = '';
    const mod = await loadModule('static/js/pages/booking/index.js');
    mod.loadDoctors();
    await new Promise(r => setTimeout(r, 30));
    expect(String(global.fetch.mock.calls[0][0])).not.toContain('department_id');
  });

  it('loadDoctors fetch failure resolves silently', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/booking/index.js');
    mod.loadDoctors();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
  });

  it('loadTimes renders available times', async () => {
    document.getElementById('doctor_id').innerHTML = '<option value="1" selected>Dr A</option>';
    document.getElementById('doctor_id').value = '1';
    const mod = await loadModule('static/js/pages/booking/index.js');
    mod.loadTimes();
    await new Promise(r => setTimeout(r, 30));
    expect(String(global.fetch.mock.calls[0][0])).toContain('doctor_id=1');
    expect(document.getElementById('appointment_time').innerHTML).toContain('09:00');
  });

  it('loadTimes without doctor or date does not fetch', async () => {
    document.getElementById('doctor_id').value = '';
    const mod = await loadModule('static/js/pages/booking/index.js');
    mod.loadTimes();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('loadTimes fetch failure resolves silently', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    document.getElementById('doctor_id').innerHTML = '<option value="1">A</option>';
    document.getElementById('doctor_id').value = '1';
    const mod = await loadModule('static/js/pages/booking/index.js');
    mod.loadTimes();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
  });
});