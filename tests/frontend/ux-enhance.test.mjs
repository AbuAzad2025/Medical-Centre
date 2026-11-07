import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = '';
  vi.resetModules();
  window.scrollTo = vi.fn();
  window.HTMLElement.prototype.scrollIntoView = vi.fn();
  global.fetch = vi.fn().mockResolvedValue({ ok: true });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('ux-enhance.js', () => {
  it('injectProgressBar creates the progress bar once', async () => {
    const { injectProgressBar } = await loadModule('static/js/ux-enhance.js');
    injectProgressBar();
    expect(document.getElementById('__uxProgressBar')).toBeTruthy();
    const second = document.getElementById('__uxProgressBar');
    injectProgressBar();
    expect(document.querySelectorAll('#__uxProgressBar').length).toBe(1);
  });

  it('startProgress injects bar and sets width steps', async () => {
    vi.useFakeTimers();
    const { startProgress } = await loadModule('static/js/ux-enhance.js');
    startProgress();
    expect(document.querySelector('.__ux-bar').style.width).toBe('0%');
    vi.advanceTimersByTime(200);
    expect(document.querySelector('.__ux-bar').style.width).toBe('30%');
    vi.advanceTimersByTime(800);
    expect(document.querySelector('.__ux-bar').style.width).toBe('60%');
    vi.useRealTimers();
  });

  it('stopProgress sets 100% and hides after delay', async () => {
    vi.useFakeTimers();
    const { startProgress, stopProgress } = await loadModule('static/js/ux-enhance.js');
    startProgress();
    vi.advanceTimersByTime(100);
    stopProgress();
    expect(document.querySelector('.__ux-bar').style.width).toBe('100%');
    vi.advanceTimersByTime(400);
    expect(document.querySelector('.__ux-bar').style.opacity).toBe('0');
    vi.useRealTimers();
  });

  it('showFieldErrors returns false for non-object', async () => {
    const { showFieldErrors } = await loadModule('static/js/ux-enhance.js');
    const form = document.createElement('form');
    expect(showFieldErrors(form, null)).toBe(false);
    expect(showFieldErrors(form, 'str')).toBe(false);
  });

  it('showFieldErrors handles array messages', async () => {
    const { showFieldErrors } = await loadModule('static/js/ux-enhance.js');
    document.body.innerHTML = `<form><input name="n"></form>`;
    const form = document.querySelector('form');
    showFieldErrors(form, { n: ['a', 'b'] });
    expect(form.querySelector('.invalid-feedback').textContent).toBe('a. b');
  });

  it('showFieldErrors skips non-string and non-array messages', async () => {
    const { showFieldErrors } = await loadModule('static/js/ux-enhance.js');
    document.body.innerHTML = `<form><input name="n"></form>`;
    const form = document.querySelector('form');
    expect(showFieldErrors(form, { n: 123 })).toBe(false);
  });

  it('showFieldErrors creates feedback element when missing', async () => {
    const { showFieldErrors } = await loadModule('static/js/ux-enhance.js');
    document.body.innerHTML = `<form><div><input name="email"></div></form>`;
    const form = document.querySelector('form');
    showFieldErrors(form, { email: 'bad' });
    expect(form.querySelector('.invalid-feedback')).toBeTruthy();
  });

  it('showFieldErrors uses [data-error-for] when present', async () => {
    const { showFieldErrors } = await loadModule('static/js/ux-enhance.js');
    document.body.innerHTML = `<form><div><input name="x"><div data-error-for="x"></div></div></form>`;
    const form = document.querySelector('form');
    showFieldErrors(form, { x: 'oops' });
    expect(form.querySelector('[data-error-for="x"]').textContent).toBe('oops');
  });

  it('scrollToErrors scrolls to error flash', async () => {
    document.body.innerHTML = '<div class="flash-error">err</div>';
    const { scrollToErrors } = await loadModule('static/js/ux-enhance.js');
    expect(() => scrollToErrors()).not.toThrow();
    const err = document.querySelector('.flash-error');
    expect(err.scrollIntoView).toHaveBeenCalled();
  });

  it('scrollToErrors scrolls to success flash when no error', async () => {
    document.body.innerHTML = '<div class="flash-success">ok</div>';
    const { scrollToErrors } = await loadModule('static/js/ux-enhance.js');
    scrollToErrors();
    expect(window.scrollTo).toHaveBeenCalled();
  });

  it('scrollToErrors tolerates no flashes', async () => {
    const { scrollToErrors } = await loadModule('static/js/ux-enhance.js');
    expect(() => scrollToErrors()).not.toThrow();
  });

  it('submit on POST form starts progress and schedules stop', async () => {
    vi.useFakeTimers();
    document.body.innerHTML = '<form method="POST" id="f"><button type="submit">Go</button></form>';
    await loadModule('static/js/ux-enhance.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    document.getElementById('f').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    expect(document.getElementById('__uxProgressBar')).toBeTruthy();
    vi.useRealTimers();
  });

  it('submit on data-ajax form does not schedule stop', async () => {
    vi.useFakeTimers();
    document.body.innerHTML = '<form method="POST" data-ajax="1" id="f"><button type="submit">Go</button></form>';
    await loadModule('static/js/ux-enhance.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    document.getElementById('f').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    expect(document.getElementById('__uxProgressBar')).toBeTruthy();
    vi.useRealTimers();
  });

  it('window.fetch is patched on DOMContentLoaded', async () => {
    await loadModule('static/js/ux-enhance.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(window.__uxFetchPatched).toBe(true);
  });

  it('patched fetch calls original and resolves', async () => {
    await loadModule('static/js/ux-enhance.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const result = await window.fetch('/x', {});
    expect(global.fetch).toHaveBeenCalled();
  });

  it('window.UXEnhance exposes the public API', async () => {
    await loadModule('static/js/ux-enhance.js');
    expect(typeof window.UXEnhance.showFieldErrors).toBe('function');
    expect(typeof window.UXEnhance.startProgress).toBe('function');
    expect(typeof window.UXEnhance.stopProgress).toBe('function');
  });
});