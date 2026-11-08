import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';
import { isolateDomContentLoaded } from './dom-isolation.mjs';

const iso = isolateDomContentLoaded();

function baseDom() {
  document.body.innerHTML = `
    <form id="f" method="post">
      <button type="submit" id="b">Save</button>
    </form>
  `;
}

beforeEach(() => {
  iso.install();
  baseDom();
  window.__VALIDATION_RULES__ = {
    email: { min_length: 3, pattern: '^[^@]+@[^@]+$', message_ar: 'خطأ' },
    national_id: { min_length: 5, message_ar: 'خطأ' },
  };
});

afterEach(() => {
  iso.cleanup();
  vi.useRealTimers();
});

describe('form-validation.js pageshow restore arms', () => {
  it('pageshow leaves an externally-disabled button untouched', async () => {
    document.body.innerHTML = `
      <form id="f" method="post">
        <button type="submit" id="b">Save</button>
        <button type="submit" id="b2">Second</button>
      </form>
    `;
    await loadModule('static/js/form-validation.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const b2 = document.getElementById('b2');
    b2.disabled = true; // disabled after load, never spinner-wired → no _origHtml
    window.dispatchEvent(new PageTransitionEvent('pageshow'));
    expect(b2.disabled).toBe(true);
    expect(b2.innerHTML).toBe('Second');
  });

  it('pageshow on a fresh form is a safe no-op', async () => {
    await loadModule('static/js/form-validation.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(() => window.dispatchEvent(new PageTransitionEvent('pageshow'))).not.toThrow();
    expect(document.getElementById('b').disabled).toBe(false);
  });
});

describe('form-validation.js data-validate-form arms', () => {
  it('submit with all fields invalid prevents submission and marks them', async () => {
    document.body.innerHTML = `
      <form id="validForm" data-validate-form method="post">
        <input name="first" data-validate="email" value="not-an-email">
        <input name="second" data-validate="email" value="also-not">
      </form>
    `;
    await loadModule('static/js/form-validation.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const form = document.getElementById('validForm');
    const event = new Event('submit', { bubbles: true, cancelable: true });
    form.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(true);
    expect(document.querySelectorAll('.is-invalid').length).toBe(2);
  });

  it('submit with valid fields proceeds without preventing default', async () => {
    document.body.innerHTML = `
      <form id="validForm" data-validate-form method="post">
        <input name="first" data-validate="email" value="someone@example.com">
      </form>
    `;
    await loadModule('static/js/form-validation.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const form = document.getElementById('validForm');
    const event = new Event('submit', { bubbles: true, cancelable: true });
    form.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(false);
  });
});

describe('form-validation.js national_id digits-only arm', () => {
  it('strips non-digits and caps at 20 characters', async () => {
    document.body.innerHTML = '<input name="nid" data-validate="national_id" value="">';
    await loadModule('static/js/form-validation.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const input = document.querySelector('input[data-validate="national_id"]');
    input.value = '1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p7';
    input.dispatchEvent(new Event('input'));
    expect(input.value).toBe('12345678901234567');
    input.value = '1234567890123456789012345';
    input.dispatchEvent(new Event('input'));
    expect(input.value).toBe('12345678901234567890');
  });
});
