import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <div class="container-fluid" data-dept="7">
      <input type="text" id="doctorPatientSearch">
      <div id="doctorPatientResults" style="display:none"></div>
      <div id="stat-total">0</div>
      <div id="stat-ready">0</div>
      <div id="stat-in-progress">0</div>
      <div id="stat-wait">0</div>
      <table><tbody><tr id="row1"><td>row1</td></tr></tbody></table>
      <button type="submit">Save</button>
    </div>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M0__ = '/api/patients/search';
  window.__M1__ = '/doctor/view-patient/0';
  window.__M2__ = '12';
  window.API_ROUTES = { queue_status: '/reception/api/queue-status/0' };
  window.escHtml = (s) => String(s || '');
  window.showToast = vi.fn();
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.bootstrap = { Collapse: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn() })) }, Modal: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn(), hide: vi.fn() })) } };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ patients: [], data: { waiting_patients: [1,2], called_patients: [3], current_patient: { id: 1 }, estimated_wait_time: 15 } }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('doctor/patient_queue.js', () => {
  it('refreshQueue updates stats when department provided', async () => {
    const mod = await loadModule('static/js/pages/doctor/patient_queue.js');
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ data: { waiting_patients: [1, 2, 3], called_patients: [4], current_patient: { id: 9 }, estimated_wait_time: 20 } }) });
    mod.refreshQueue();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('stat-total').textContent).toBe('5');
    expect(document.getElementById('stat-ready').textContent).toBe('3');
    expect(document.getElementById('stat-in-progress').textContent).toBe('1');
    expect(document.getElementById('stat-wait').textContent).toBe('20');
  });

  it('refreshQueue with no department does nothing', async () => {
    document.body.innerHTML = '<div class="container-fluid" data-dept=""></div>';
    const mod = await loadModule('static/js/pages/doctor/patient_queue.js');
    expect(() => mod.refreshQueue()).not.toThrow();
  });

  it('refreshQueue error shows toast', async () => {
    const mod = await loadModule('static/js/pages/doctor/patient_queue.js');
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    mod.refreshQueue();
    await new Promise(r => setTimeout(r, 30));
    expect(window.showToast).toHaveBeenCalled();
  });

  it('search input renders patient list', async () => {
    const patients = [{ id: 9, full_name: 'Sara Ali', phone: '0500000000', national_id: '123', visit_count: 5 }];
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ patients }) });
    await loadModule('static/js/pages/doctor/patient_queue.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    vi.useFakeTimers();
    const input = document.getElementById('doctorPatientSearch');
    input.value = 'sara';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    vi.advanceTimersByTime(400);
    vi.useRealTimers();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('doctorPatientResults').innerHTML).toContain('Sara Ali');
  });

  it('search with short query hides results', async () => {
    await loadModule('static/js/pages/doctor/patient_queue.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const input = document.getElementById('doctorPatientSearch');
    input.value = 's';
    document.getElementById('doctorPatientResults').style.display = 'block';
    document.getElementById('doctorPatientResults').innerHTML = '<span>existing</span>';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    expect(document.getElementById('doctorPatientResults').style.display).toBe('none');
  });

  it('search with no results shows empty state', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ patients: [] }) });
    await loadModule('static/js/pages/doctor/patient_queue.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    vi.useFakeTimers();
    const input = document.getElementById('doctorPatientSearch');
    input.value = 'zzz';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    vi.advanceTimersByTime(400);
    vi.useRealTimers();
    await new Promise(r => setTimeout(r, 20));
    expect(document.getElementById('doctorPatientResults').innerHTML).toContain('لا توجد نتائج');
  });

  it('search fetch error shows error message', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    await loadModule('static/js/pages/doctor/patient_queue.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    vi.useFakeTimers();
    const input = document.getElementById('doctorPatientSearch');
    input.value = 'sof';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    vi.advanceTimersByTime(400);
    vi.useRealTimers();
    await new Promise(r => setTimeout(r, 20));
    expect(document.getElementById('doctorPatientResults').innerHTML).toContain('خطأ في البحث');
  });

  it('table row hover changes background', async () => {
    await loadModule('static/js/pages/doctor/patient_queue.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const row = document.getElementById('row1');
    row.dispatchEvent(new MouseEvent('mouseenter'));
    expect(row.style.backgroundColor).toBe('rgb(248, 249, 250)');
    row.dispatchEvent(new MouseEvent('mouseleave'));
    expect(row.style.backgroundColor).toBe('');
  });

  it('submit button click disables and shows spinner', async () => {
    await loadModule('static/js/pages/doctor/patient_queue.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const btn = document.querySelector('button[type="submit"]');
    btn.click();
    expect(btn.disabled).toBe(true);
    expect(btn.innerHTML).toContain('spinner-border');
  });
});