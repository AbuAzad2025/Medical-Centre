import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <div class="smart-search" id="ss" data-api="/api/custom-search" data-min="2" data-target-id="externalHidden" data-info-id="infoBox" data-on-select="onPatientPicked">
      <input type="text" data-smart-search-input>
      <div class="smart-search-results" data-smart-search-results hidden></div>
    </div>
    <input type="hidden" id="externalHidden" value="">
    <div id="infoBox" class="d-none"></div>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M = [];
  window.escHtml = (s) => String(s ?? '');
  window.PiiMask = { nationalId: (v) => 'masked-nid', phone: (v) => 'masked-phone' };
  window.onPatientPicked = vi.fn();
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ patients: [{ id: 42, full_name: 'سارة محمود', national_id: '111222333', phone: '0599000000' }] }),
  });
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('smart-search.js data-attribute fallback arms', () => {
  it('uses data-api as the request URL and data-min as the threshold', async () => {
    const mod = await loadModule('static/js/smart-search.js');
    mod.initSmartSearch(document.getElementById('ss'));
    const input = document.querySelector('[data-smart-search-input]');
    input.value = 'sara';
    input.dispatchEvent(new Event('input'));
    await vi.advanceTimersByTimeAsync(350);
    expect(global.fetch.mock.calls[0][0]).toContain('/api/custom-search');
  });

  it('selectPatient writes the external hidden input from data-target-id', async () => {
    const mod = await loadModule('static/js/smart-search.js');
    mod.initSmartSearch(document.getElementById('ss'));
    const input = document.querySelector('[data-smart-search-input]');
    input.value = 'sara';
    input.dispatchEvent(new Event('input'));
    await vi.advanceTimersByTimeAsync(350);
    document.querySelector('.smart-search-results button').click();
    expect(document.getElementById('externalHidden').value).toBe('42');
  });

  it('selectPatient renders info text with PiiMask applied', async () => {
    const mod = await loadModule('static/js/smart-search.js');
    mod.initSmartSearch(document.getElementById('ss'));
    const input = document.querySelector('[data-smart-search-input]');
    input.value = 'sara';
    input.dispatchEvent(new Event('input'));
    await vi.advanceTimersByTimeAsync(350);
    document.querySelector('.smart-search-results button').click();
    expect(document.getElementById('infoBox').textContent).toContain('masked-nid');
    expect(document.getElementById('infoBox').textContent).toContain('masked-phone');
    expect(document.getElementById('infoBox').classList.contains('d-none')).toBe(false);
  });

  it('selectPatient invokes the window callback from data-on-select', async () => {
    const mod = await loadModule('static/js/smart-search.js');
    mod.initSmartSearch(document.getElementById('ss'));
    const input = document.querySelector('[data-smart-search-input]');
    input.value = 'sara';
    input.dispatchEvent(new Event('input'));
    await vi.advanceTimersByTimeAsync(350);
    document.querySelector('.smart-search-results button').click();
    expect(window.onPatientPicked).toHaveBeenCalledWith(expect.objectContaining({ id: 42 }));
  });

  it('selectPatient without PiiMask falls back to raw national_id and phone', async () => {
    delete window.PiiMask;
    const mod = await loadModule('static/js/smart-search.js');
    mod.initSmartSearch(document.getElementById('ss'));
    const input = document.querySelector('[data-smart-search-input]');
    input.value = 'sara';
    input.dispatchEvent(new Event('input'));
    await vi.advanceTimersByTimeAsync(350);
    document.querySelector('.smart-search-results button').click();
    expect(document.getElementById('infoBox').textContent).toContain('111222333');
    expect(document.getElementById('infoBox').textContent).toContain('0599000000');
  });

  it('data-on-select pointing at a non-function is ignored', async () => {
    window.onPatientPicked = 'not-a-function';
    const mod = await loadModule('static/js/smart-search.js');
    mod.initSmartSearch(document.getElementById('ss'));
    const input = document.querySelector('[data-smart-search-input]');
    input.value = 'sara';
    input.dispatchEvent(new Event('input'));
    await vi.advanceTimersByTimeAsync(350);
    expect(() => document.querySelector('.smart-search-results button').click()).not.toThrow();
  });

  it('root without hidden input and without data-target-id still completes the select', async () => {
    document.body.innerHTML = `
      <div class="smart-search" id="ss2" data-api="/api/custom-search">
        <input type="text" data-smart-search-input>
        <div class="smart-search-results" data-smart-search-results hidden></div>
      </div>
    `;
    const mod = await loadModule('static/js/smart-search.js');
    mod.initSmartSearch(document.getElementById('ss2'));
    const input = document.querySelector('[data-smart-search-input]');
    input.value = 'sara';
    input.dispatchEvent(new Event('input'));
    await vi.advanceTimersByTimeAsync(350);
    expect(() => document.querySelector('.smart-search-results button').click()).not.toThrow();
    expect(document.getElementById('externalHidden')).toBeNull();
  });

  it('init falls back to plain text input when data attribute is missing', async () => {
    document.body.innerHTML = `
      <div class="smart-search" id="ss3" data-api="/api/custom-search">
        <input type="text">
        <div class="smart-search-results" hidden></div>
      </div>
    `;
    const mod = await loadModule('static/js/smart-search.js');
    expect(() => mod.initSmartSearch(document.getElementById('ss3'))).not.toThrow();
  });
});

describe('smart-search.js remaining arms', () => {
  it('root without data-api falls back to the default endpoint', async () => {
    document.body.innerHTML = `
      <div class="smart-search" id="ss">
        <input type="text" data-smart-search-input>
        <div class="smart-search-results" data-smart-search-results hidden></div>
      </div>
    `;
    const mod = await loadModule('static/js/smart-search.js');
    mod.initSmartSearch(document.getElementById('ss'));
    const input = document.querySelector('[data-smart-search-input]');
    input.value = 'sara';
    input.dispatchEvent(new Event('input'));
    await vi.advanceTimersByTimeAsync(350);
    expect(String(global.fetch.mock.calls[0][0])).toContain('/api/search/patients');
  });

  it('renderResults patient without name/id/national_id/phone renders empty placeholders', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ patients: [{}] }) });
    const mod = await loadModule('static/js/smart-search.js');
    mod.initSmartSearch(document.getElementById('ss'));
    const input = document.querySelector('[data-smart-search-input]');
    input.value = 'sara';
    input.dispatchEvent(new Event('input'));
    await vi.advanceTimersByTimeAsync(350);
    const html = document.getElementById('externalHidden') ? document.querySelector('.smart-search-results').innerHTML : '';
    expect(html.length).toBeGreaterThan(0);
  });

  it('patient with fullName but missing national_id renders the fallback dash', async () => {
    window.PiiMask = { nationalId: (v) => 'masked-nid', phone: (v) => 'masked-phone' };
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ patients: [{ id: 1, full_name: 'Ali' }] }) });
    const mod = await loadModule('static/js/smart-search.js');
    mod.initSmartSearch(document.getElementById('ss'));
    const input = document.querySelector('[data-smart-search-input]');
    input.value = 'ali';
    input.dispatchEvent(new Event('input'));
    await vi.advanceTimersByTimeAsync(350);
    expect(document.querySelector('.smart-search-results').innerHTML).toContain('Ali');
  });

  it('empty object response data falls back to empty patient list', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
    const mod = await loadModule('static/js/smart-search.js');
    mod.initSmartSearch(document.getElementById('ss'));
    const input = document.querySelector('[data-smart-search-input]');
    input.value = 'sara';
    input.dispatchEvent(new Event('input'));
    await vi.advanceTimersByTimeAsync(350);
    expect(document.querySelector('.smart-search-results').textContent).toContain('لا توجد نتائج');
  });
});
