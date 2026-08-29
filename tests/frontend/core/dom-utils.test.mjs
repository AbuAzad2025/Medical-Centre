import { describe, it, expect, vi, beforeEach } from 'vitest';
import { escHtml, debounce, digitsOnly, formatMoney } from '../../../static/js/core/dom-utils.js';

describe('escHtml', () => {
  it('escapes ampersand', () => {
    expect(escHtml('a&b')).toBe('a&amp;b');
  });
  it('escapes less-than', () => {
    expect(escHtml('a<b')).toBe('a&lt;b');
  });
  it('escapes greater-than', () => {
    expect(escHtml('a>b')).toBe('a&gt;b');
  });
  it('escapes double quote', () => {
    expect(escHtml('a"b')).toBe('a&quot;b');
  });
  it('escapes single quote', () => {
    expect(escHtml("a'b")).toBe('a&#39;b');
  });
  it('returns empty string for null', () => {
    expect(escHtml(null)).toBe('');
  });
  it('returns empty string for undefined', () => {
    expect(escHtml(undefined)).toBe('');
  });
  it('converts numbers to string', () => {
    expect(escHtml(42)).toBe('42');
  });
  it('handles Arabic text', () => {
    expect(escHtml('مرحبا')).toBe('مرحبا');
  });
  it('escapes mixed special characters', () => {
    expect(escHtml('<script>alert("xss")&\'</script>')).toBe(
      '&lt;script&gt;alert(&quot;xss&quot;)&amp;&#39;&lt;/script&gt;'
    );
  });
});

describe('debounce', () => {
  beforeEach(() => { vi.useFakeTimers(); });

  it('fires only once for rapid calls', () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 100);
    debounced(); debounced(); debounced();
    vi.advanceTimersByTime(100);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('fires on trailing edge', () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 100);
    debounced();
    vi.advanceTimersByTime(50);
    expect(fn).not.toHaveBeenCalled();
    vi.advanceTimersByTime(50);
    expect(fn).toHaveBeenCalledTimes(1);
  });
});

describe('digitsOnly', () => {
  it('strips non-digits from mixed input', () => {
    expect(digitsOnly('abc123def456')).toBe('1234');
  });
  it('returns empty string for null', () => {
    expect(digitsOnly(null)).toBe('');
  });
  it('returns empty string for undefined', () => {
    expect(digitsOnly(undefined)).toBe('');
  });
  it('respects max length', () => {
    expect(digitsOnly('12345678', 4)).toBe('1234');
  });
});

describe('formatMoney', () => {
  it('formats zero', () => { expect(formatMoney(0)).toBe('0.00'); });
  it('formats negative numbers', () => { expect(formatMoney(-5)).toBe('-5.00'); });
  it('formats large numbers', () => { expect(formatMoney(1000000)).toBe('1000000.00'); });
  it('formats decimals', () => { expect(formatMoney(19.99)).toBe('19.99'); });
  it('returns 0.00 for NaN', () => { expect(formatMoney(NaN)).toBe('0.00'); });
  it('returns 0.00 for Infinity', () => { expect(formatMoney(Infinity)).toBe('0.00'); });
});
