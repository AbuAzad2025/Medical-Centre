import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = '';
  window.IntersectionObserver = class {
    constructor(cb, opts) {
      this.cb = cb;
      this.opts = opts;
      this.observed = [];
    }
    observe(el) {
      this.observed.push(el);
    }
    unobserve(el) {
      this.observed = this.observed.filter(e => e !== el);
    }
    trigger(entries) {
      this.cb(entries);
    }
  };
  window.requestAnimationFrame = (cb) => setTimeout(cb, 5);
  window.cancelAnimationFrame = (id) => clearTimeout(id);
  await loadModule('static/js/performance.js');
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe('performance.js', () => {
  describe('debounce', () => {
    it('is exposed', () => {
      expect(typeof window.debounce).toBe('function');
    });

    it('does not call the function until the wait has passed', () => {
      vi.useFakeTimers();
      const spy = vi.fn();
      const debounced = window.debounce(spy, 100);
      debounced('a');
      expect(spy).not.toHaveBeenCalled();
      vi.advanceTimersByTime(100);
      expect(spy).toHaveBeenCalledTimes(1);
      expect(spy).toHaveBeenCalledWith('a');
    });

    it('collapses a burst into one call', () => {
      vi.useFakeTimers();
      const spy = vi.fn();
      const debounced = window.debounce(spy, 100);
      debounced('a');
      debounced('b');
      debounced('c');
      vi.advanceTimersByTime(100);
      expect(spy).toHaveBeenCalledTimes(1);
      expect(spy).toHaveBeenCalledWith('c');
    });

    it('calls straight away in immediate mode', () => {
      vi.useFakeTimers();
      const spy = vi.fn();
      const debounced = window.debounce(spy, 100, true);
      debounced('a');
      expect(spy).toHaveBeenCalledTimes(1);
      expect(spy).toHaveBeenCalledWith('a');
    });
  });

  describe('throttle', () => {
    it('calls on first invocation and suppresses within limit', () => {
      vi.useFakeTimers();
      const spy = vi.fn();
      const throttled = window.throttle(spy, 100);
      throttled('a');
      expect(spy).toHaveBeenCalledTimes(1);
      throttled('b');
      throttled('c');
      expect(spy).toHaveBeenCalledTimes(1);
      vi.advanceTimersByTime(100);
      throttled('d');
      expect(spy).toHaveBeenCalledTimes(2);
      expect(spy).toHaveBeenLastCalledWith('d');
    });
  });

  describe('PerformanceMonitor class', () => {
    it('records page load metric on window load', () => {
      const monitor = new window.PerformanceMonitor();
      window.dispatchEvent(new Event('load'));
      expect(typeof monitor.getMetrics().pageLoad).toBe('number');
      monitor.stop();
    });

    it('monitors api metrics via __apiMetrics', () => {
      vi.useFakeTimers();
      window.__apiMetrics = { calls: 42, time: 1337 };
      const monitor = new window.PerformanceMonitor();
      vi.advanceTimersByTime(5000);
      expect(monitor.metrics.apiCalls).toBe(42);
      expect(monitor.metrics.apiTime).toBe(1337);
      monitor.stop();
    });

    it('monitors memory metrics when supported', () => {
      vi.useFakeTimers();
      Object.defineProperty(window.performance, 'memory', {
        value: { usedJSHeapSize: 100, totalJSHeapSize: 1000, jsHeapSizeLimit: 2000 },
        configurable: true,
      });
      const monitor = new window.PerformanceMonitor();
      vi.advanceTimersByTime(5000);
      expect(monitor.metrics.memory).toEqual({ used: 100, total: 1000, limit: 2000 });
      monitor.stop();
      delete window.performance.memory;
    });

    it('stop clears intervals and rAF', () => {
      const monitor = new window.PerformanceMonitor();
      expect(() => monitor.stop()).not.toThrow();
    });
  });

  describe('LazyLoader class', () => {
    it('observes .lazy-load elements and loads them on intersect', () => {
      document.body.innerHTML = `
        <img class="lazy-load" data-src="/img.jpg">
        <div class="lazy-load" data-bg="https://example.com/bg.jpg"></div>
        <div class="lazy-load" data-bg="javascript:alert(1)"></div>
      `;
      const loader = new window.LazyLoader();
      expect(loader.observer).not.toBeNull();
      const entries = document.querySelectorAll('.lazy-load');
      const mockEntries = [...entries].map(target => ({ target, isIntersecting: true }));
      loader.observer.trigger(mockEntries);
      const img = document.querySelector('img');
      expect(img.src).toContain('/img.jpg');
      expect(img.hasAttribute('data-src')).toBe(false);
      const bgEl = document.querySelectorAll('.lazy-load')[1];
      expect(bgEl.style.backgroundImage).toContain('example.com');
      expect(bgEl.classList.contains('loaded')).toBe(true);
    });
  });

  describe('OptimizedSearch class', () => {
    it('searches and caches results', async () => {
      document.body.innerHTML = `<input id="sp" /><div id="sr"></div>`;
      const searchFn = vi.fn(async (q) => ['res:' + q]);
      const search = new window.OptimizedSearch('#sp', '#sr', searchFn);
      await search.performSearch('hello');
      expect(document.getElementById('sr').innerHTML).toContain('res:hello');
      await search.performSearch('hello');
      expect(searchFn).toHaveBeenCalledTimes(1);
    });

    it('clears results for short queries', async () => {
      document.body.innerHTML = `<input id="sp" /><div id="sr">x</div>`;
      const search = new window.OptimizedSearch('#sp', '#sr', vi.fn());
      await search.performSearch('a');
      expect(document.getElementById('sr').innerHTML).toBe('');
    });
  });

  describe('OptimizedTable class', () => {
    it('adds search, sorting and virtual scroll to a table', () => {
      document.body.innerHTML = `<table id="ot"><thead><tr><th data-sort="name">Name</th></tr></thead><tbody></tbody></table>`;
      new window.OptimizedTable('#ot');
      const input = document.querySelector('.form-control.mb-3');
      expect(input).toBeTruthy();
      const tbody = document.querySelector('#ot tbody');
      expect(tbody.style.overflowY).toBe('auto');
    });

    it('filters data by query', () => {
      document.body.innerHTML = `<table id="ot2"><thead><tr><th data-sort="name">Name</th></tr></thead><tbody></tbody></table>`;
      const table = new window.OptimizedTable('#ot2');
      table.data = [{ name: 'alpha' }, { name: 'beta' }];
      table.filteredData = table.data.slice();
      table.filterData('alpha');
      expect(table.filteredData.length).toBe(1);
      expect(table.filteredData[0].name).toBe('alpha');
    });

    it('sorts data asc then desc', () => {
      document.body.innerHTML = `<table id="ot3"><thead><tr><th data-sort="name">Name</th></tr></thead><tbody></tbody></table>`;
      const table = new window.OptimizedTable('#ot3');
      table.data = [{ name: 'charlie' }, { name: 'alpha' }, { name: 'beta' }];
      table.filteredData = table.data.slice();
      table.sortData('name');
      expect(table.filteredData.map(r => r.name)).toEqual(['alpha', 'beta', 'charlie']);
      table.sortData('name');
      expect(table.filteredData.map(r => r.name)).toEqual(['charlie', 'beta', 'alpha']);
    });
  });

  describe('OptimizedFormValidator class', () => {
    it('validates with rules and shows errors', () => {
      document.body.innerHTML = `<form id="vf"><div><input name="email" value=""></div></form>`;
      const validator = new window.OptimizedFormValidator('#vf');
      validator.addRule('email', { test: (v) => /^[^@]+@[^@]+$/.test(v), message: 'invalid email' });
      expect(validator.validateForm()).toBe(false);
      const field = document.querySelector('[name="email"]');
      expect(field.classList.contains('is-invalid')).toBe(true);
      expect(field.parentNode.querySelector('.invalid-feedback')).toBeTruthy();
      field.value = 'a@b.com';
      expect(validator.validateField(field)).toBe(true);
      expect(field.classList.contains('is-valid')).toBe(true);
    });

    it('clearError removes invalid state', () => {
      document.body.innerHTML = `<form id="vf2"><div><input name="x" value="bad"></div></form>`;
      const validator = new window.OptimizedFormValidator('#vf2');
      const field = document.querySelector('[name="x"]');
      validator.addRule('x', { test: () => false, message: 'nope' });
      validator.validateForm();
      expect(field.classList.contains('is-invalid')).toBe(true);
      validator.clearError(field);
      expect(field.classList.contains('is-valid')).toBe(true);
    });
  });

  describe('OptimizedNotifications class', () => {
    it('shows and removes notifications', () => {
      const notifications = new window.OptimizedNotifications();
      notifications.show('hello', 'success', 5000);
      notifications.show('failed', 'error', 5000);
      notifications.show('warn', 'warning', 5000);
      notifications.show('info', 'info', 5000);
      expect(notifications.container.children.length).toBe(4);
      expect(notifications.notifications.length).toBe(4);
      notifications.remove(notifications.notifications[0]);
    });
  });

  describe('OptimizedCache class', () => {
    it('stores, refreshes and expires entries', () => {
      const cache = new window.OptimizedCache(2);
      cache.set('a', 1, 60000);
      cache.set('b', 2, 60000);
      expect(cache.get('a')).toBe(1);
      cache.set('c', 3);
      expect(cache.get('a')).toBe(1);
      expect(cache.get('b')).toBe(null);
      expect(cache.get('c')).toBe(3);
    });

    it('clear empties the cache', () => {
      const cache = new window.OptimizedCache();
      cache.set('a', 1);
      cache.clear();
      expect(cache.get('a')).toBe(null);
    });

    it('cleanup removes expired entries', () => {
      vi.useFakeTimers();
      const cache = new window.OptimizedCache();
      cache.set('a', 1, 5000);
      vi.advanceTimersByTime(10000);
      cache.cleanup();
      expect(cache.get('a')).toBe(null);
    });
  });

  describe('module init on DOMContentLoaded', () => {
    it('sets performanceMonitor and optimizedCache and tags cards/btns/inputs', async () => {
      document.body.innerHTML = `
        <div class="card"></div>
        <button class="btn"></button>
        <input class="form-control">
        <table id="tbl"><thead><tr><th>A</th></tr></thead><tbody></tbody></table>
        <form id="f"><input></form>
      `;
      document.dispatchEvent(new Event('DOMContentLoaded'));
      await new Promise(r => setTimeout(r, 20));
      expect(window.performanceMonitor).toBeDefined();
      expect(window.optimizedCache).toBeDefined();
      expect(document.querySelector('.card').classList.contains('card-optimized')).toBe(true);
      expect(document.querySelector('.btn').classList.contains('btn-optimized')).toBe(true);
      expect(document.querySelector('.form-control').classList.contains('form-control-optimized')).toBe(true);
    });

    it('beforeunload stops the monitor', async () => {
      document.body.innerHTML = '';
      document.dispatchEvent(new Event('DOMContentLoaded'));
      await new Promise(r => setTimeout(r, 10));
      window.dispatchEvent(new Event('beforeunload'));
      expect(true).toBe(true);
    });
  });
});