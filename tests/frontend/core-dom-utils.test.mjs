import { describe, it, expect, vi, afterEach } from 'vitest';
import { loadModule } from './test-utils.mjs';

afterEach(() => {
  vi.useRealTimers();
});

describe('core/dom-utils.js', () => {
  it('escHtml escapes all five entities', async () => {
    const { escHtml } = await loadModule('static/js/core/dom-utils.js');
    expect(escHtml('<a href="x">&\'</a>')).toBe('&lt;a href=&quot;x&quot;&gt;&amp;&#39;&lt;/a&gt;');
  });

  it('escHtml handles null and undefined', async () => {
    const { escHtml } = await loadModule('static/js/core/dom-utils.js');
    expect(escHtml(null)).toBe('');
    expect(escHtml(undefined)).toBe('');
  });

  it('debounce delays and preserves `this`', async () => {
    const { debounce } = await loadModule('static/js/core/dom-utils.js');
    vi.useFakeTimers();
    const fn = vi.fn(function () { return this; });
    const obj = { debounced: debounce(fn, 100) };
    obj.debounced('a', 'b');
    obj.debounced('c');
    expect(fn).not.toHaveBeenCalled();
    vi.advanceTimersByTime(150);
    expect(fn).toHaveBeenCalledTimes(1);
    expect(fn).toHaveBeenCalledWith('c');
    expect(fn.mock.instances[0]).toBe(obj);
  });

  it('digitsOnly strips non-digits and respects max length', async () => {
    const { digitsOnly } = await loadModule('static/js/core/dom-utils.js');
    expect(digitsOnly('a1b2c3d4e5')).toBe('1234');
    expect(digitsOnly('hello')).toBe('');
    expect(digitsOnly('123456789', 3)).toBe('123');
    expect(digitsOnly('999999', 10)).toBe('999999');
    expect(digitsOnly(null)).toBe('');
    expect(digitsOnly('123456', 0)).toBe('1234');
  });

  it('formatMoney formats number to 2 decimals', async () => {
    const { formatMoney } = await loadModule('static/js/core/dom-utils.js');
    expect(formatMoney(10)).toBe('10.00');
    expect(formatMoney('3.5')).toBe('3.50');
    expect(formatMoney('nope')).toBe('0.00');
    expect(formatMoney(NaN)).toBe('0.00');
  });
});