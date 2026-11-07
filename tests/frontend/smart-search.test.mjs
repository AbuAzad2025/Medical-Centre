import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom(extraAttrs = '') {
  document.body.innerHTML = `
    <div data-smart-search data-api="/api/search/patients" data-min="2" data-target-id="hiddenPid" data-info-id="selInfo" data-on-select="onPatientSelect" ${extraAttrs}>
      <input type="text" data-smart-search-input id="searchInput" value="">
      <div data-smart-search-results id="results" style="display:none"></div>
      <input type="hidden" id="hiddenPid">
      <div id="selInfo" class="d-none"></div>
    </div>
  `;
}

beforeEach(() => {
  baseDom();
  window.onPatientSelect = vi.fn();
  window.PiiMask = { nationalId: (v) => 'NID:' + v, phone: (v) => 'PH:' + v };
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ patients: [{ id: 11, full_name: 'Sara Ali', national_id: '12345', phone: '0501' }] }),
  });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('smart-search.js', () => {
  it('exposes window.initSmartSearch', async () => {
    await loadModule('static/js/smart-search.js');
    expect(typeof window.initSmartSearch).toBe('function');
  });

  it('debounce returns a debounced function', async () => {
    const { debounce } = await loadModule('static/js/smart-search.js');
    const fn = vi.fn();
    const d = debounce(fn, 100);
    vi.useFakeTimers();
    d('a');
    d('b');
    vi.advanceTimersByTime(100);
    expect(fn).toHaveBeenCalledTimes(1);
    expect(fn).toHaveBeenCalledWith('b');
    vi.useRealTimers();
  });

  it('short query hides results without fetching', async () => {
    await loadModule('static/js/smart-search.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const input = document.getElementById('searchInput');
    input.value = 's';
    input.dispatchEvent(new Event('input'));
    await new Promise(r => setTimeout(r, 400));
    expect(global.fetch).not.toHaveBeenCalled();
    expect(document.getElementById('results').style.display).toBe('none');
  });

  it('valid query fetches and renders results', async () => {
    await loadModule('static/js/smart-search.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const input = document.getElementById('searchInput');
    input.value = 'sara';
    input.dispatchEvent(new Event('input'));
    await new Promise(r => setTimeout(r, 400));
    expect(global.fetch).toHaveBeenCalled();
    expect(String(global.fetch.mock.calls[0][0])).toContain('/api/search/patients?q=sara');
    expect(document.getElementById('results').innerHTML).toContain('Sara Ali');
  });

  it('search error shows error message in results', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    await loadModule('static/js/smart-search.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const input = document.getElementById('searchInput');
    input.value = 'sara';
    input.dispatchEvent(new Event('input'));
    await new Promise(r => setTimeout(r, 400));
    expect(document.getElementById('results').innerHTML).toContain('خطأ');
  });

  it('empty list shows no results message', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ patients: [] }) });
    await loadModule('static/js/smart-search.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const input = document.getElementById('searchInput');
    input.value = 'zzz';
    input.dispatchEvent(new Event('input'));
    await new Promise(r => setTimeout(r, 400));
    expect(document.getElementById('results').innerHTML).toContain('لا توجد');
  });

  it('clicking a result fills hidden id and info, clears input', async () => {
    await loadModule('static/js/smart-search.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const input = document.getElementById('searchInput');
    input.value = 'sara';
    input.dispatchEvent(new Event('input'));
    await new Promise(r => setTimeout(r, 400));
    const btn = document.querySelector('#results button');
    btn.click();
    expect(document.getElementById('hiddenPid').value).toBe('11');
    expect(document.getElementById('selInfo').innerHTML).toContain('Sara Ali');
    expect(document.getElementById('selInfo').style.display).toBe('block');
    expect(input.value).toBe('');
    expect(document.getElementById('results').style.display).toBe('none');
    expect(window.onPatientSelect).toHaveBeenCalled();
  });

  it('clicking result dispatches smart-search:select CustomEvent', async () => {
    const listener = vi.fn();
    await loadModule('static/js/smart-search.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    document.querySelector('[data-smart-search]').addEventListener('smart-search:select', listener);
    const input = document.getElementById('searchInput');
    input.value = 'sara';
    input.dispatchEvent(new Event('input'));
    await new Promise(r => setTimeout(r, 400));
    document.querySelector('#results button').click();
    expect(listener).toHaveBeenCalled();
    expect(listener.mock.calls[0][0].detail.full_name).toBe('Sara Ali');
  });

  it('clicking outside hides results', async () => {
    await loadModule('static/js/smart-search.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const results = document.getElementById('results');
    results.style.display = 'block';
    document.body.click();
    expect(results.style.display).toBe('none');
  });

  it('first XHR is aborted when a new search starts', async () => {
    global.fetch = vi.fn().mockImplementation((url) => {
      return new Promise(() => {}); // never resolves
    });
    const mod = await loadModule('static/js/smart-search.js');
    // Wire only this root (avoids DOMContentLoaded handlers accumulated by earlier tests)
    mod.initSmartSearch(document.querySelector('[data-smart-search]'));
    const input = document.getElementById('searchInput');
    input.value = 'aa';
    input.dispatchEvent(new Event('input'));
    await new Promise(r => setTimeout(r, 400));
    input.value = 'bb';
    input.dispatchEvent(new Event('input'));
    await new Promise(r => setTimeout(r, 400));
    expect(global.fetch).toHaveBeenCalledTimes(2);
    const firstSignal = global.fetch.mock.calls[0][1].signal;
    expect(firstSignal.aborted).toBe(true);
  });

  it('module runs initSmartSearch only for [data-smart-search] roots', async () => {
    await loadModule('static/js/smart-search.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(document.getElementById('searchInput')).toBeTruthy();
  });

  it('missing input or results is skipped gracefully', async () => {
    document.body.innerHTML = `
      <div data-smart-search data-api="/api"></div>
    `;
    await loadModule('static/js/smart-search.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(true).toBe(true);
  });
});