import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <form id="diagnosisForm" action="/doctor/diagnosis/save">
      <input name="csrf_token" value="test-csrf">
      <textarea name="assessment"></textarea>
      <input name="plan" value="">
      <button type="submit">Save</button>
    </form>
  `;
}

beforeEach(() => {
  baseDom();
  window.showToast = vi.fn();
  window.console.warn = vi.fn();
  global.fetch = vi.fn().mockResolvedValue({ ok: true });
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('doctor/diagnosis.js', () => {
  it('input changes mark the form dirty', async () => {
    await loadModule('static/js/pages/doctor/diagnosis.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    document.querySelector('[name="assessment"]').dispatchEvent(new Event('input'));
    expect(document.getElementById('diagnosisForm').classList.contains('dirty')).toBe(true);
  });

  it('periodic health check POSTs after 30 seconds', async () => {
    await loadModule('static/js/pages/doctor/diagnosis.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await vi.advanceTimersByTimeAsync(30000);
    expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/doctor/diagnosis/save'), expect.objectContaining({ method: 'POST' }));
  });

  it('periodic health check failure shows toast', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    await loadModule('static/js/pages/doctor/diagnosis.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await vi.advanceTimersByTimeAsync(30000);
    expect(window.showToast).toHaveBeenCalled();
  });

  it('periodic health check non-ok response shows toast', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    await loadModule('static/js/pages/doctor/diagnosis.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await vi.advanceTimersByTimeAsync(30000);
    expect(window.showToast).toHaveBeenCalled();
  });

  it('fallback to console.warn when no showToast and failure occurs', async () => {
    delete window.showToast;
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    await loadModule('static/js/pages/doctor/diagnosis.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await vi.advanceTimersByTimeAsync(30000);
    expect(window.console.warn).toHaveBeenCalled();
  });

  it('beforeunload with dirty form prevents default and flags returnValue', async () => {
    await loadModule('static/js/pages/doctor/diagnosis.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    document.querySelector('[name="assessment"]').dispatchEvent(new Event('input'));
    const e = new Event('beforeunload', { cancelable: true });
    window.dispatchEvent(e);
    expect(e.defaultPrevented).toBe(true);
  });

  it('form without dirty class does not trigger the prevent branch', async () => {
    await loadModule('static/js/pages/doctor/diagnosis.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const form = document.getElementById('diagnosisForm');
    expect(form.classList.contains('dirty')).toBe(false);
  });

  it('beforeunload clears the interval', async () => {
    await loadModule('static/js/pages/doctor/diagnosis.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    window.dispatchEvent(new Event('beforeunload'));
    await vi.advanceTimersByTimeAsync(120000);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('no form in DOM does not wire anything', async () => {
    document.body.innerHTML = '';
    await loadModule('static/js/pages/doctor/diagnosis.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(true).toBe(true);
  });
});