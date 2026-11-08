import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function tableDom(attrs = '', id = 'perfTable') {
  document.body.innerHTML = `<table id="${id}" ${attrs}><thead><tr><th data-sort="name">Name</th></tr></thead><tbody></tbody></table>`;
}

beforeEach(() => {
  document.body.innerHTML = '';
  delete window.$;
  delete window.performanceMonitor;
  delete window.optimizedCache;
  window.IntersectionObserver = class {
    constructor(cb) { this.cb = cb; }
    observe() {}
    unobserve() {}
  };
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe('performance.js FPS and API metrics branches', () => {
  it('records fps after a frame gap of over one second', async () => {
    const t0 = 1000000;
    vi.spyOn(performance, 'now').mockReturnValue(t0);
    let rafCb = null;
    const originalRaf = window.requestAnimationFrame;
    window.requestAnimationFrame = vi.fn((cb) => { rafCb = cb; return 1; });
    await loadModule('static/js/performance.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    vi.spyOn(performance, 'now').mockReturnValue(t0 + 1500);
    expect(rafCb).not.toBeNull();
    rafCb();
    expect(window.performanceMonitor.getMetrics().fps).toBeDefined();
    window.requestAnimationFrame = originalRaf;
    vi.useRealTimers();
  });

  it('picks up __apiMetrics on the 5s interval', async () => {
    vi.useFakeTimers();
    window.__apiMetrics = { calls: 7, time: 123 };
    await loadModule('static/js/performance.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await vi.advanceTimersByTimeAsync(5100);
    expect(window.performanceMonitor.getMetrics().apiCalls).toBe(7);
    expect(window.performanceMonitor.getMetrics().apiTime).toBe(123);
    delete window.__apiMetrics;
    vi.useRealTimers();
  });
});

describe('performance.js performSearch catch arm', () => {
  it('search rejection is swallowed silently', async () => {
    document.body.innerHTML = '<input id="sp" /><div id="sr"></div>';
    const mod = await loadModule('static/js/performance.js');
    const search = new window.OptimizedSearch('#sp', '#sr', () => Promise.reject(new Error('boom')));
    await expect(search.performSearch('query')).resolves.toBeUndefined();
    expect(document.getElementById('sr').innerHTML).toBe('');
  });
});

describe('performance.js OptimizedTable data-dt and $ guards', () => {
  it('table with data-dt does not get a search input', async () => {
    tableDom('data-dt="1"', 'dtTable');
    await loadModule('static/js/performance.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(document.querySelector('.form-control.mb-3')).toBeNull();
  });

  it('table with data-dt stays untouched even when jQuery says not a DataTable', async () => {
    tableDom('data-dt="1"', 'dtTable2');
    window.$ = function () {};
    window.$.fn = { DataTable: true, dataTable: { isDataTable: () => false } };
    await loadModule('static/js/performance.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(document.querySelector('.form-control.mb-3')).toBeNull();
  });

  it('table already a jQuery DataTable is skipped', async () => {
    tableDom('', 'dtTable3');
    window.$ = function () {};
    window.$.fn = { DataTable: true, dataTable: { isDataTable: () => true } };
    await loadModule('static/js/performance.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(document.querySelector('.form-control.mb-3')).toBeNull();
  });
});

describe('performance.js sort toggle arms', () => {
  it('toggling a header three times cycles asc → desc → asc', () => {
    tableDom('', 'cycleTable');
    const table = new window.OptimizedTable('#cycleTable');
    table.data = [{ name: 'b' }, { name: 'a' }, { name: 'c' }];
    table.filteredData = table.data.slice();
    table.sortData('name');
    expect(table.filteredData.map(r => r.name)).toEqual(['a', 'b', 'c']);
    table.sortData('name');
    expect(table.filteredData.map(r => r.name)).toEqual(['c', 'b', 'a']);
    table.sortData('name');
    expect(table.filteredData.map(r => r.name)).toEqual(['a', 'b', 'c']);
  });

  it('equal values in the sort comparator return 0 without crashing', () => {
    tableDom('', 'eqTable');
    const table = new window.OptimizedTable('#eqTable');
    table.data = [{ name: 'x' }, { name: 'x' }, { name: 'a' }];
    table.filteredData = table.data.slice();
    table.sortData('name');
    expect(table.filteredData.length).toBe(3);
  });

  it('sortData switches columns and resets to asc', () => {
    tableDom('', 'colTable');
    const table = new window.OptimizedTable('#colTable');
    table.data = [{ name: 'b', age: 30 }, { name: 'a', age: 25 }, { name: 'c', age: 40 }];
    table.filteredData = table.data.slice();
    table.sortData('age');
    expect(table.filteredData.map(r => r.age)).toEqual([25, 30, 40]);
    expect(table.sortDirection).toBe('asc');
    table.sortData('name');
    expect(table.sortColumn).toBe('name');
    expect(table.sortDirection).toBe('asc');
  });
});

describe('performance.js notification color fallback', () => {
  it('unknown type uses the info color', async () => {
    await loadModule('static/js/performance.js');
    const notes = new window.OptimizedNotifications();
    notes.show('msg', 'weird-type', 10000);
    const notification = document.querySelector('.notification');
    expect(notification.style.borderLeft).toContain('23, 162, 184');
    expect(notification.className).toContain('notification-weird-type');
  });
});

describe('performance.js form validator with no rules and cache LRU branches', () => {
  it('field with no rules validates clean', async () => {
    document.body.innerHTML = '<form id="f"><input name="plain" value="x"></form>';
    await loadModule('static/js/performance.js');
    const validator = new window.OptimizedFormValidator('#f');
    expect(validator.validateForm()).toBe(true);
  });

  it('evicts the least recently used entry when over capacity', () => {
    const c = new window.OptimizedCache(1);
    c.set('a', 'A');
    c.set('b', 'B');
    expect(c.get('a')).toBeNull();
    expect(c.get('b')).toBe('B');
  });
});
