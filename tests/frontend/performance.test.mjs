import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { loadModule } from './test-utils.mjs';

/**
 * This file used to declare its own copies of debounce and throttle and
 * assert on those. The production file was never loaded, so 609 lines of
 * static/js/performance.js had no coverage, and the cases could not fail
 * however the real implementations behaved. The script is loaded here and the
 * assertions run against it.
 */
beforeEach(async () => {
  document.body.innerHTML = '';
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

    it('collapses a burst into one call, with the last arguments', () => {
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
    it('is exposed', () => {
      expect(typeof window.throttle).toBe('function');
    });

    it('calls on the first invocation', () => {
      vi.useFakeTimers();
      const spy = vi.fn();
      const throttled = window.throttle(spy, 100);
      throttled('a');
      expect(spy).toHaveBeenCalledTimes(1);
      expect(spy).toHaveBeenCalledWith('a');
    });

    it('suppresses the calls inside the limit', () => {
      vi.useFakeTimers();
      const spy = vi.fn();
      const throttled = window.throttle(spy, 100);
      throttled('a');
      throttled('b');
      throttled('c');
      expect(spy).toHaveBeenCalledTimes(1);
      vi.advanceTimersByTime(100);
      throttled('d');
      expect(spy).toHaveBeenCalledTimes(2);
      expect(spy).toHaveBeenLastCalledWith('d');
    });
  });

  describe('the classes are exposed', () => {
    it('PerformanceMonitor', () => {
      expect(typeof window.PerformanceMonitor).toBe('function');
    });

    it('LazyLoader', () => {
      expect(typeof window.LazyLoader).toBe('function');
    });

    it('OptimizedSearch', () => {
      expect(typeof window.OptimizedSearch).toBe('function');
    });

    it('OptimizedCache', () => {
      expect(typeof window.OptimizedCache).toBe('function');
    });
  });
});
