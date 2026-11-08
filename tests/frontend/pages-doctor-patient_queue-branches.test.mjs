import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <input id="doctorPatientSearch">
    <div id="doctorPatientResults" style="display:none"></div>
    <div class="container-fluid" data-dept="4"></div>
    <span id="stat-total">0</span>
    <span id="stat-ready">0</span>
    <span id="stat-in-progress">0</span>
    <span id="stat-wait">0</span>
    <table><tbody><tr><td>row</td></tr></tbody></table>
    <button type="submit" id="doneBtn">Done</button>
    <button type="submit" id="otherBtn">Complete</button>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M = [];
  window.__M0__ = '/api/search';
  window.__M1__ = '/patient/0';
  window.__M2__ = '7';
  window.escHtml = (s) => String(s ?? '');
  window.API_ROUTES = { queue_status: '/reception/api/queue-status/0' };
  window.location = { href: '' };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ patients: [{ id: 1, full_name: 'سارة', national_id: '123', phone: '059', visit_count: 2 }] }), data: {} });
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('patient_queue.js search branches', () => {
  it('query shorter than 2 characters hides the results list', async () => {
    await loadModule('static/js/pages/doctor/patient_queue.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const input = document.getElementById('doctorPatientSearch');
    input.value = 's';
    input.dispatchEvent(new Event('input'));
    expect(document.getElementById('doctorPatientResults').style.display).toBe('none');
  });

  it('renders matching patients with link, visits and contact info', async () => {
    await loadModule('static/js/pages/doctor/patient_queue.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const input = document.getElementById('doctorPatientSearch');
    input.value = 'sara';
    input.dispatchEvent(new Event('input'));
    await vi.advanceTimersByTimeAsync(350);
    const results = document.getElementById('doctorPatientResults');
    expect(results.style.display).toBe('block');
    expect(results.innerHTML).toContain('سارة');
    expect(results.innerHTML).toContain('/patient/1');
    expect(results.innerHTML).toContain('059');
    expect(results.innerHTML).toContain('2');
  });

  it('patient with missing visit count and phone falls back to 0 and no pipe', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ patients: [{ id: 3, full_name: 'Ali', national_id: '999' }] }) });
    await loadModule('static/js/pages/doctor/patient_queue.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const input = document.getElementById('doctorPatientSearch');
    input.value = 'ali';
    input.dispatchEvent(new Event('input'));
    await vi.advanceTimersByTimeAsync(350);
    expect(document.getElementById('doctorPatientResults').innerHTML).toContain('0');
  });

  it('empty patient list renders the no-results notice', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ patients: [] }) });
    await loadModule('static/js/pages/doctor/patient_queue.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const input = document.getElementById('doctorPatientSearch');
    input.value = 'sara';
    input.dispatchEvent(new Event('input'));
    await vi.advanceTimersByTimeAsync(350);
    expect(document.getElementById('doctorPatientResults').innerHTML).toContain('لا توجد نتائج');
  });

  it('response without patients key renders the no-results notice', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
    await loadModule('static/js/pages/doctor/patient_queue.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const input = document.getElementById('doctorPatientSearch');
    input.value = 'sara';
    input.dispatchEvent(new Event('input'));
    await vi.advanceTimersByTimeAsync(350);
    expect(document.getElementById('doctorPatientResults').innerHTML).toContain('لا توجد نتائج');
  });

  it('non-ok response shows the search error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    await loadModule('static/js/pages/doctor/patient_queue.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const input = document.getElementById('doctorPatientSearch');
    input.value = 'sara';
    input.dispatchEvent(new Event('input'));
    await vi.advanceTimersByTimeAsync(350);
    expect(document.getElementById('doctorPatientResults').innerHTML).toContain('خطأ في البحث');
  });

  it('missing __M1__ prefixes patient links with #', async () => {
    delete window.__M1__;
    await loadModule('static/js/pages/doctor/patient_queue.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const input = document.getElementById('doctorPatientSearch');
    input.value = 'sara';
    input.dispatchEvent(new Event('input'));
    await vi.advanceTimersByTimeAsync(350);
    expect(document.querySelector('#doctorPatientResults a').getAttribute('href')).toBe('#');
  });

  it('missing list element does not crash the handler', async () => {
    document.getElementById('doctorPatientResults').remove();
    await loadModule('static/js/pages/doctor/patient_queue.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const input = document.getElementById('doctorPatientSearch');
    input.value = 's';
    expect(() => input.dispatchEvent(new Event('input'))).not.toThrow();
  });
});

describe('patient_queue.js refreshQueue branches', () => {
  it('missing container-fluid data-dept returns early without fetching', async () => {
    document.querySelector('.container-fluid').remove();
    const mod = await loadModule('static/js/pages/doctor/patient_queue.js');
    mod.refreshQueue();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('zero department id returns early', async () => {
    document.querySelector('.container-fluid').setAttribute('data-dept', '0');
    const mod = await loadModule('static/js/pages/doctor/patient_queue.js');
    mod.refreshQueue();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('success populates the stats counters', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ data: { waiting_patients: [1, 2, 3], called_patients: [4], current_patient: {}, estimated_wait_time: 22 } }) });
    const mod = await loadModule('static/js/pages/doctor/patient_queue.js');
    mod.refreshQueue();
    await vi.advanceTimersByTimeAsync(10);
    expect(document.getElementById('stat-total').textContent).toBe('5');
    expect(document.getElementById('stat-ready').textContent).toBe('3');
    expect(document.getElementById('stat-in-progress').textContent).toBe('1');
    expect(document.getElementById('stat-wait').textContent).toBe('22');
  });

  it('success with missing data fields falls back to zeroes', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
    const mod = await loadModule('static/js/pages/doctor/patient_queue.js');
    mod.refreshQueue();
    await vi.advanceTimersByTimeAsync(10);
    expect(document.getElementById('stat-total').textContent).toBe('0');
    expect(document.getElementById('stat-in-progress').textContent).toBe('0');
    expect(document.getElementById('stat-wait').textContent).toBe('15');
  });

  it('non-array waiting/called lists count as zero', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ data: { waiting_patients: 'x', called_patients: 5 } }) });
    const mod = await loadModule('static/js/pages/doctor/patient_queue.js');
    mod.refreshQueue();
    await vi.advanceTimersByTimeAsync(10);
    expect(document.getElementById('stat-ready').textContent).toBe('0');
  });

  it('non-ok response falls back to showToast when available', async () => {
    window.showToast = vi.fn();
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/doctor/patient_queue.js');
    mod.refreshQueue();
    await vi.advanceTimersByTimeAsync(10);
    expect(window.showToast).toHaveBeenCalled();
  });

  it('non-ok response without showToast uses console.warn fallback', async () => {
    delete window.showToast;
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/doctor/patient_queue.js');
    mod.refreshQueue();
    await vi.advanceTimersByTimeAsync(10);
    expect(warn).toHaveBeenCalled();
    warn.mockRestore();
  });

  it('API_ROUTES queue_status override is honoured', async () => {
    window.API_ROUTES = { queue_status: '/custom/queue/0' };
    const mod = await loadModule('static/js/pages/doctor/patient_queue.js');
    mod.refreshQueue();
    expect(global.fetch.mock.calls[0][0]).toContain('/custom/queue/4');
  });
});

describe('patient_queue.js DOMContentLoaded wiring', () => {
  it('table rows get hover background listeners', async () => {
    await loadModule('static/js/pages/doctor/patient_queue.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const row = document.querySelector('table tbody tr');
    row.dispatchEvent(new MouseEvent('mouseenter'));
    expect(row.style.backgroundColor).toBe('rgb(248, 249, 250)');
    row.dispatchEvent(new MouseEvent('mouseleave'));
    expect(row.style.backgroundColor).toBe('');
  });

  it('submit buttons swap to a spinner state on click', async () => {
    await loadModule('static/js/pages/doctor/patient_queue.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const btn = document.getElementById('doneBtn');
    btn.click();
    expect(btn.disabled).toBe(true);
    expect(btn.innerHTML).toContain('spinner-border');
  });
});
