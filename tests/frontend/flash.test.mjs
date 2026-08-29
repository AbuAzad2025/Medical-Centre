import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { loadScript } from './test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = '';
  vi.useFakeTimers();
  loadScript('static/js/flash.js');
});

afterEach(() => {
  vi.useRealTimers();
});

describe('flash.js', () => {
  it('showToast creates a toast element', () => {
    const toast = window.showToast('Test message', 'success');
    expect(toast).toBeDefined();
    expect(toast.classList.contains('toast')).toBe(true);
    expect(toast.classList.contains('success')).toBe(true);
    expect(toast.querySelector('.toast-body').textContent).toBe('Test message');
  });

  it('showToast defaults to info type', () => {
    const toast = window.showToast('Info message');
    expect(toast.classList.contains('info')).toBe(true);
  });

  it('removeToast removes the element', () => {
    const toast = window.showToast('Test', 'error');
    expect(document.body.contains(toast)).toBe(true);
    window.removeToast(toast);
    expect(toast.classList.contains('removing')).toBe(true);
    vi.advanceTimersByTime(400);
    expect(document.body.contains(toast)).toBe(false);
  });

  it('removeToast is idempotent', () => {
    const toast = window.showToast('Test', 'info');
    window.removeToast(toast);
    window.removeToast(toast);
    expect(toast.classList.contains('removing')).toBe(true);
  });

  it('showError creates error toast', () => {
    const toast = window.showError('Error occurred');
    expect(toast.classList.contains('error')).toBe(true);
  });

  it('showSuccess creates success toast', () => {
    const toast = window.showSuccess('Done!');
    expect(toast.classList.contains('success')).toBe(true);
  });
});
