import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = '';
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('flash.js comprehensive', () => {
  it('creates toastContainer once', async () => {
    await loadModule('static/js/flash.js');
    expect(document.getElementById('toastContainer')).toBeTruthy();
    expect(document.querySelectorAll('#toastContainer').length).toBe(1);
  });

  it('showToast with unknown type falls back to info', async () => {
    const { showToast } = await loadModule('static/js/flash.js');
    const toast = showToast('msg', 'bogus');
    expect(toast.querySelector('.toast-header i').className).toContain('fa-info-circle');
  });

  it('showToast uses duration param', async () => {
    const { showToast } = await loadModule('static/js/flash.js');
    const t = showToast('msg', 'info', 1000);
    expect(t).toBeTruthy();
    vi.advanceTimersByTime(1001);
    expect(t.classList.contains('removing')).toBe(true);
  });

  it('default duration is 5000', async () => {
    const { showToast } = await loadModule('static/js/flash.js');
    const t = showToast('msg', 'error');
    vi.advanceTimersByTime(4999);
    expect(t.classList.contains('removing')).toBe(false);
    vi.advanceTimersByTime(1);
    expect(t.classList.contains('removing')).toBe(true);
  });

  it('progress bar advances', async () => {
    const { showToast } = await loadModule('static/js/flash.js');
    const t = showToast('msg', 'info', 1000);
    vi.advanceTimersByTime(200);
    const pct = parseFloat(t.querySelector('.toast-progress').style.width);
    expect(pct).toBeLessThan(100);
    vi.advanceTimersByTime(800);
  });

  it('mouseenter then mouseleave restarts the timer', async () => {
    const { showToast } = await loadModule('static/js/flash.js');
    const t = showToast('msg', 'warning', 1000);
    vi.advanceTimersByTime(100);
    t.dispatchEvent(new MouseEvent('mouseenter'));
    vi.advanceTimersByTime(500);
    expect(t.classList.contains('removing')).toBe(false);
    t.dispatchEvent(new MouseEvent('mouseleave'));
    vi.advanceTimersByTime(2000);
    expect(t.classList.contains('removing')).toBe(true);
  });

  it('close button removes the toast', async () => {
    const { showToast } = await loadModule('static/js/flash.js');
    const t = showToast('msg', 'info');
    t.querySelector('.toast-close').click();
    expect(t.classList.contains('removing')).toBe(true);
  });

  it('removeToast null is safe', async () => {
    const { removeToast } = await loadModule('static/js/flash.js');
    expect(() => removeToast(null)).not.toThrow();
  });

  it('showError wraps showToast with error/8000', async () => {
    const { showError } = await loadModule('static/js/flash.js');
    const t = showError('err');
    expect(t.classList.contains('error')).toBe(true);
    vi.advanceTimersByTime(8001);
    expect(t.classList.contains('removing')).toBe(true);
  });

  it('showSuccess wraps showToast with success/4000', async () => {
    const { showSuccess } = await loadModule('static/js/flash.js');
    const t = showSuccess('ok');
    expect(t.classList.contains('success')).toBe(true);
    vi.advanceTimersByTime(4001);
    expect(t.classList.contains('removing')).toBe(true);
  });

  it('showWarning wraps showToast with warning/6000', async () => {
    const { showWarning } = await loadModule('static/js/flash.js');
    const t = showWarning('warn');
    expect(t.classList.contains('warning')).toBe(true);
    vi.advanceTimersByTime(6001);
    expect(t.classList.contains('removing')).toBe(true);
  });

  it('showInfo wraps showToast with info/4000', async () => {
    const { showInfo } = await loadModule('static/js/flash.js');
    const t = showInfo('info');
    expect(t.classList.contains('info')).toBe(true);
  });

  it('initFlashAutoHide converts flash messages to toasts', async () => {
    document.body.innerHTML = `
      <div class="flash-message success">great</div>
      <div class="flash-message error">bad</div>
      <div class="flash-message warning">warn</div>
      <div class="flash-message info">note</div>
    `;
    const { initFlashAutoHide } = await loadModule('static/js/flash.js');
    initFlashAutoHide();
    expect(document.querySelectorAll('.toast').length).toBe(4);
    expect(document.querySelector('.flash-message').style.display).toBe('none');
  });

  it('initFlashAutoHide with empty DOM is no-op', async () => {
    const { initFlashAutoHide } = await loadModule('static/js/flash.js');
    expect(() => initFlashAutoHide()).not.toThrow();
  });

  it('exposes globals and default export', async () => {
    const mod = await loadModule('static/js/flash.js');
    expect(typeof window.showToast).toBe('function');
    expect(typeof window.removeToast).toBe('function');
    expect(typeof window.showError).toBe('function');
    expect(mod.default.showSuccess).toBe(mod.showSuccess);
  });
});