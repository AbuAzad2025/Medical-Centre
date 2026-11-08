import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <meta name="csrf-token" content="meta-csrf">
    <form id="diagnosisForm" action="/doctor/diagnosis/save" method="post">
      <input name="csrf_token" value="form-csrf">
      <input name="assessment" value="initial">
      <textarea name="plan">plan</textarea>
    </form>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M = [];
  window.escHtml = (s) => String(s ?? '');
  window.showToast = vi.fn();
  window.console.warn = vi.fn();
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('diagnosis.js csrf branches', () => {
  it('form csrf input is preferred over meta for the health check', async () => {
    await loadModule('static/js/pages/doctor/diagnosis.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await vi.advanceTimersByTimeAsync(30000);
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBe('form-csrf');
  });

  it('meta csrf is used when the form has no csrf input', async () => {
    document.querySelector('#diagnosisForm input[name="csrf_token"]').remove();
    await loadModule('static/js/pages/doctor/diagnosis.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await vi.advanceTimersByTimeAsync(30000);
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBe('meta-csrf');
  });

  it('no csrf elements anywhere sends no token header', async () => {
    document.querySelector('#diagnosisForm input[name="csrf_token"]').remove();
    document.querySelector('meta[name="csrf-token"]').remove();
    await loadModule('static/js/pages/doctor/diagnosis.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await vi.advanceTimersByTimeAsync(30000);
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBeUndefined();
  });

  it('beforeunload without dirty form sets no returnValue', async () => {
    await loadModule('static/js/pages/doctor/diagnosis.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const event = new Event('beforeunload', { cancelable: true });
    window.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(false);
  });
});
