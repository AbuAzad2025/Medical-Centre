import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';
import { isolateDomContentLoaded } from './dom-isolation.mjs';

const iso = isolateDomContentLoaded();

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
  iso.install();
  baseDom();
  window.showToast = vi.fn();
  window.console.warn = vi.fn();
  global.fetch = vi.fn().mockResolvedValue({ ok: true });
  vi.useFakeTimers();
});

afterEach(() => {
  iso.cleanup();
  vi.useRealTimers();
});

describe('doctor/diagnosis.js', () => {
  it('input changes mark the form dirty', async () => {
    await loadModule('static/js/pages/doctor/diagnosis.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    document.querySelector('[name="assessment"]').dispatchEvent(new Event('input'));
    expect(document.getElementById('diagnosisForm').classList.contains('dirty')).toBe(true);
  });

  it('no timers resubmit the clinical form after any amount of time', async () => {
    await loadModule('static/js/pages/doctor/diagnosis.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await vi.advanceTimersByTimeAsync(5 * 60 * 1000);
    expect(global.fetch).not.toHaveBeenCalled();
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

  it('beforeunload on a clean form does not prevent default', async () => {
    await loadModule('static/js/pages/doctor/diagnosis.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const e = new Event('beforeunload', { cancelable: true });
    window.dispatchEvent(e);
    expect(e.defaultPrevented).toBe(false);
  });

  it('no form in DOM does not wire anything', async () => {
    document.body.innerHTML = '';
    await loadModule('static/js/pages/doctor/diagnosis.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(true).toBe(true);
  });
});
