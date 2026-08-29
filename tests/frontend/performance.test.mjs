import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { readFileSync } from 'fs';
import { resolve } from 'path';

const ROOT = resolve(import.meta.dirname, '../..');

function debounce(func, wait, immediate = false) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      timeout = null;
      if (!immediate) func(...args);
    };
    const callNow = immediate && !timeout;
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
    if (callNow) func(...args);
  };
}

function throttle(func, limit) {
  let inThrottle;
  return function (...args) {
    if (!inThrottle) {
      func.apply(this, args);
      inThrottle = true;
      setTimeout(() => inThrottle = false, limit);
    }
  };
}

class OptimizedCache {
  constructor(maxSize = 100) {
    this.cache = new Map();
    this.maxSize = maxSize;
  }
  get(key) {
    if (this.cache.has(key)) {
      const item = this.cache.get(key);
      this.cache.delete(key);
      this.cache.set(key, item);
      return item.value;
    }
    return null;
  }
  set(key, value, ttl = 300000) {
    if (this.cache.size >= this.maxSize) {
      const firstKey = this.cache.keys().next().value;
      this.cache.delete(firstKey);
    }
    this.cache.set(key, { value, expiry: Date.now() + ttl });
  }
  has(key) { return this.cache.has(key); }
  delete(key) { return this.cache.delete(key); }
  clear() { this.cache.clear(); }
}

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('performance.js utilities', () => {
  describe('debounce', () => {
    it('debounces function calls', () => {
      const fn = vi.fn();
      const debounced = debounce(fn, 100);
      debounced(); debounced(); debounced();
      vi.advanceTimersByTime(100);
      expect(fn).toHaveBeenCalledTimes(1);
    });
    it('supports immediate mode', () => {
      const fn = vi.fn();
      const debounced = debounce(fn, 100, true);
      debounced();
      expect(fn).toHaveBeenCalledTimes(1);
      debounced();
      vi.advanceTimersByTime(100);
      expect(fn).toHaveBeenCalledTimes(1);
    });
  });

  describe('throttle', () => {
    it('fires at most once per interval', () => {
      const fn = vi.fn();
      const throttled = throttle(fn, 100);
      throttled(); throttled(); throttled();
      expect(fn).toHaveBeenCalledTimes(1);
      vi.advanceTimersByTime(100);
      throttled();
      expect(fn).toHaveBeenCalledTimes(2);
    });
  });

  describe('OptimizedCache', () => {
    it('get/set/has/delete/clear work correctly', () => {
      const cache = new OptimizedCache(5);
      cache.set('a', 1);
      cache.set('b', 2);
      expect(cache.get('a')).toBe(1);
      expect(cache.has('b')).toBe(true);
      cache.delete('b');
      expect(cache.has('b')).toBe(false);
      cache.clear();
      expect(cache.get('a')).toBe(null);
    });
    it('evicts oldest when max size reached', () => {
      const cache = new OptimizedCache(3);
      cache.set('a', 1); cache.set('b', 2); cache.set('c', 3);
      cache.set('d', 4);
      expect(cache.get('a')).toBe(null);
      expect(cache.get('d')).toBe(4);
    });
    it('LRU ordering - accessed items move to end', () => {
      const cache = new OptimizedCache(3);
      cache.set('a', 1); cache.set('b', 2); cache.set('c', 3);
      cache.get('a');
      cache.set('d', 4);
      expect(cache.get('a')).toBe(1);
      expect(cache.get('b')).toBe(null);
    });
  });
});
