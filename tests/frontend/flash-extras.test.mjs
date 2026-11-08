import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = '<div id="toastContainer"></div>';
}

beforeEach(() => {
  baseDom();
  window.__M = [];
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('flash.js fallback arms', () => {
  it('reuses a pre-existing #toastContainer instead of creating a second one', async () => {
    await loadModule('static/js/flash.js');
    expect(document.querySelectorAll('#toastContainer').length).toBe(1);
  });

  it('unknown toast type uses the info title', async () => {
    await loadModule('static/js/flash.js');
    const toast = window.showToast('msg', 'weird-type');
    expect(toast.innerHTML).toContain('info-circle');
  });

  it('removeToast on an already-detached toast does not crash after timeout', async () => {
    await loadModule('static/js/flash.js');
    const toast = window.showToast('msg', 'info', 1000);
    toast.remove();
    vi.advanceTimersByTime(400);
    expect(document.querySelector('.toast')).toBeNull();
  });

  it('flash messages are converted to toasts with the right category', async () => {
    document.body.innerHTML = `
      <div class="flash-message success">Saved</div>
      <div class="flash-message error">Failed</div>
      <div class="flash-message warning">Careful</div>
      <div class="flash-message">Neutral</div>
    `;
    await loadModule('static/js/flash.js');
    window.initFlashAutoHide();
    const toasts = document.querySelectorAll('.toast');
    expect(toasts.length).toBe(4);
    expect(document.querySelectorAll('.toast.success').length).toBe(1);
    expect(document.querySelectorAll('.toast.error').length).toBe(1);
    expect(document.querySelectorAll('.toast.warning').length).toBe(1);
    expect(document.querySelectorAll('.toast.info').length).toBe(1);
    expect(document.querySelectorAll('.flash-message')[0].style.display).toBe('none');
  });
});
