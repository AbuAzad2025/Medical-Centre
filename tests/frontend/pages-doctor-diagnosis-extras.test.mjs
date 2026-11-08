import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';
import { isolateDomContentLoaded } from './dom-isolation.mjs';

const iso = isolateDomContentLoaded();

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
  iso.install();
  baseDom();
  window.__M = [];
  window.escHtml = (s) => String(s ?? '');
  window.showToast = vi.fn();
  window.console.warn = vi.fn();
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
  vi.useFakeTimers();
});

afterEach(() => {
  iso.cleanup();
  vi.useRealTimers();
});

describe('diagnosis.js removed periodic writes', () => {
  it('advancing five minutes never fires a fetch', async () => {
    await loadModule('static/js/pages/doctor/diagnosis.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await vi.advanceTimersByTimeAsync(5 * 60 * 1000);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('beforeunload on clean form does not prevent default', async () => {
    await loadModule('static/js/pages/doctor/diagnosis.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const event = new Event('beforeunload', { cancelable: true });
    window.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(false);
  });

  it('typing in the form makes beforeunload block accidental navigation', async () => {
    await loadModule('static/js/pages/doctor/diagnosis.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    document.querySelector('[name="assessment"]').dispatchEvent(new Event('input'));
    const event = new Event('beforeunload', { cancelable: true });
    window.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(true);
  });
});
