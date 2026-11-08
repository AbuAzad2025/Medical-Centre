import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <select id="department_id"><option value="">All</option><option value="9">Cardio</option></select>
    <select id="doctor_id"><option value="">اختر الطبيب</option><option value="7">د 7</option><option value="42">د 42</option></select>
    <input id="appointment_date" type="date" value="2026-11-09">
    <select id="appointment_time"><option value="">Pick</option></select>
    <div id="smartSlotsHint"></div>
  `;
}

function mockFetch(handlers) {
  global.fetch = vi.fn((url) => {
    for (const [needle, response] of Object.entries(handlers)) {
      if (String(url).includes(needle)) {
        return Promise.resolve(typeof response === 'function' ? response() : response);
      }
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
  });
}

beforeEach(() => {
  baseDom();
  window.__M = [];
  window.__M0__ = null;
  window.__M1__ = null;
  window.__M2__ = '/api/doctors';
  window.__M3__ = '/api/times';
  window.__M4__ = '/api/smart-slots';
});

afterEach(() => {
  vi.useRealTimers();
});

describe('booking/create.js loadDoctors gaps', () => {
  it('non-ok response leaves the select as the placeholder only', async () => {
    mockFetch({ '/api/doctors': { ok: false, status: 500 } });
    const mod = await loadModule('static/js/pages/booking/create.js');
    await mod.loadDoctors();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('doctor_id').innerHTML).toContain('اختر الطبيب');
  });

  it('response without doctors key renders an empty select', async () => {
    mockFetch({ '/api/doctors': { ok: true, json: () => Promise.resolve({}) } });
    const mod = await loadModule('static/js/pages/booking/create.js');
    await mod.loadDoctors();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('doctor_id').querySelectorAll('option').length).toBe(1);
  });

  it('preset doctor id is preselected when the select has no current value', async () => {
    window.__M0__ = '42';
    mockFetch({ '/api/doctors': { ok: true, json: () => Promise.resolve({ doctors: [{ id: 42, full_name: 'Dr S' }] }) } });
    const mod = await loadModule('static/js/pages/booking/create.js');
    document.getElementById('doctor_id').value = '';
    await mod.loadDoctors();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('doctor_id').value).toBe('42');
  });

  it('no preset and no current value leaves nothing selected', async () => {
    mockFetch({ '/api/doctors': { ok: true, json: () => Promise.resolve({ doctors: [{ id: 42, full_name: 'Dr S' }] }) } });
    const mod = await loadModule('static/js/pages/booking/create.js');
    await mod.loadDoctors();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('doctor_id').value).toBe('');
  });

  it('department id from the select is appended to the request', async () => {
    mockFetch({ '/api/doctors': { ok: true, json: () => Promise.resolve({ doctors: [] }) } });
    const mod = await loadModule('static/js/pages/booking/create.js');
    document.getElementById('department_id').value = '9';
    await mod.loadDoctors();
    expect(global.fetch.mock.calls[0][0]).toContain('department_id=9');
  });
});

describe('booking/create.js loadTimes gaps', () => {
  it('non-ok response leaves the time select untouched', async () => {
    mockFetch({ '/api/times': { ok: false, status: 500 } });
    const mod = await loadModule('static/js/pages/booking/create.js');
    document.getElementById('doctor_id').value = '7';
    document.getElementById('appointment_time').innerHTML = '<option value="10:00">10:00</option>';
    document.getElementById('appointment_time').value = '10:00';
    await mod.loadTimes();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('appointment_time').value).toBe('10:00');
  });

  it('missing times array yields an empty select', async () => {
    mockFetch({ '/api/times': { ok: true, json: () => Promise.resolve({}) } });
    const mod = await loadModule('static/js/pages/booking/create.js');
    document.getElementById('doctor_id').value = '7';
    await mod.loadTimes();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('appointment_time').querySelectorAll('option').length).toBe(1);
  });

  it('preset time is preselected when the time select has no value', async () => {
    window.__M1__ = '11:30';
    mockFetch({ '/api/times': { ok: true, json: () => Promise.resolve({ available_times: ['11:30', '12:00'] }) } });
    const mod = await loadModule('static/js/pages/booking/create.js');
    document.getElementById('doctor_id').value = '7';
    document.getElementById('appointment_time').value = '';
    await mod.loadTimes();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('appointment_time').value).toBe('11:30');
  });

  it('without doc or date and an empty time select the placeholder is preserved', async () => {
    global.fetch = vi.fn();
    const mod = await loadModule('static/js/pages/booking/create.js');
    document.getElementById('doctor_id').value = '';
    document.getElementById('appointment_time').value = '';
    await mod.loadTimes();
    expect(global.fetch).not.toHaveBeenCalled();
    expect(document.getElementById('appointment_time').innerHTML).toContain('اختر الوقت');
  });
});

describe('booking/create.js loadSmartSlots gaps', () => {
  it('non-ok response leaves the hint unchanged', async () => {
    mockFetch({ '/api/smart-slots': { ok: false, status: 500 } });
    const mod = await loadModule('static/js/pages/booking/create.js');
    document.getElementById('doctor_id').value = '7';
    document.getElementById('smartSlotsHint').textContent = 'keep';
    await mod.loadSmartSlots();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('smartSlotsHint').textContent).toBe('keep');
  });

  it('suggested times are rendered into the hint', async () => {
    mockFetch({ '/api/smart-slots': { ok: true, json: () => Promise.resolve({ suggested_times: ['09:00', '09:30'] }) } });
    const mod = await loadModule('static/js/pages/booking/create.js');
    document.getElementById('doctor_id').value = '7';
    await mod.loadSmartSlots();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('smartSlotsHint').textContent).toContain('09:00');
  });

  it('empty suggested times show the no-suggestions message', async () => {
    mockFetch({ '/api/smart-slots': { ok: true, json: () => Promise.resolve({ suggested_times: [] }) } });
    const mod = await loadModule('static/js/pages/booking/create.js');
    document.getElementById('doctor_id').value = '7';
    await mod.loadSmartSlots();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('smartSlotsHint').textContent).toContain('لا توجد أوقات مقترحة');
  });

  it('response without suggested_times key shows the no-suggestions message', async () => {
    mockFetch({ '/api/smart-slots': { ok: true, json: () => Promise.resolve({}) } });
    const mod = await loadModule('static/js/pages/booking/create.js');
    document.getElementById('doctor_id').value = '7';
    await mod.loadSmartSlots();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('smartSlotsHint').textContent).toContain('لا توجد أوقات مقترحة');
  });

  it('an already-chosen time is not overridden by suggestions', async () => {
    mockFetch({ '/api/smart-slots': { ok: true, json: () => Promise.resolve({ suggested_times: ['10:00'] }) } });
    const mod = await loadModule('static/js/pages/booking/create.js');
    document.getElementById('doctor_id').value = '7';
    document.getElementById('appointment_time').innerHTML = '<option value="09:00" selected>09:00</option>';
    document.getElementById('appointment_time').value = '09:00';
    await mod.loadSmartSlots();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('appointment_time').value).toBe('09:00');
  });

  it('hint element missing does not crash and no value is set', async () => {
    document.getElementById('smartSlotsHint').remove();
    mockFetch({ '/api/smart-slots': { ok: true, json: () => Promise.resolve({ suggested_times: ['10:00'] }) } });
    const mod = await loadModule('static/js/pages/booking/create.js');
    document.getElementById('doctor_id').value = '7';
    expect(() => mod.loadSmartSlots()).not.toThrow();
  });

  it('missing doc or date sets the placeholder hint text', async () => {
    const mod = await loadModule('static/js/pages/booking/create.js');
    document.getElementById('doctor_id').value = '';
    document.getElementById('smartSlotsHint').textContent = '';
    await mod.loadSmartSlots();
    expect(document.getElementById('smartSlotsHint').textContent).toContain('اختر الطبيب');
  });
});
