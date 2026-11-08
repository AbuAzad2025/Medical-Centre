import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';
import { isolateDomContentLoaded } from './dom-isolation.mjs';

const iso = isolateDomContentLoaded();

beforeEach(() => {
  iso.install();
  document.body.innerHTML = '';
  window.__M = [];
  window.__VALIDATION_RULES__ = {
    email: { min_length: 3, pattern: '^[^@]+@[^@]+$', message_ar: 'خطأ' },
  };
});

afterEach(() => {
  iso.cleanup();
  vi.useRealTimers();
});

describe('form-validation.js remaining arms', () => {
  it('module loads cleanly when __VALIDATION_RULES__ is not set', async () => {
    delete window.__VALIDATION_RULES__;
    await expect(loadModule('static/js/form-validation.js')).resolves.toBeDefined();
  });

  it('setFieldState finds the feedback by input id when name is missing', async () => {
    document.body.innerHTML = `
      <div>
        <input id="anonfield" data-validate="email" value="x@y.z">
        <div class="invalid-feedback" data-error-for="anonfield"></div>
      </div>
    `;
    const mod = await loadModule('static/js/form-validation.js');
    const input = document.getElementById('anonfield');
    input.dispatchEvent(new Event('blur'));
    expect(document.querySelector('[data-error-for="anonfield"]').textContent).toBe('');
  });

  it('submit button with empty text falls back to the default spinner text', async () => {
    document.body.innerHTML = `
      <form method="post" id="f">
        <button type="submit" id="b"></button>
      </form>
    `;
    await loadModule('static/js/form-validation.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    document.getElementById('f').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    expect(document.getElementById('b').innerHTML).toContain('جاري الحفظ');
  });

  it('inputs without a name are skipped during the maxlength pass', async () => {
    document.body.innerHTML = '<input type="text">';
    await expect(loadModule('static/js/form-validation.js')).resolves.toBeDefined();
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(document.querySelector('input').hasAttribute('maxlength')).toBe(false);
  });

  it('is-invalid field re-validates on input and clears the error', async () => {
    document.body.innerHTML = `
      <form method="post">
        <input id="emailField" name="email" data-validate="email" value="bad">
        <div class="invalid-feedback"></div>
      </form>
    `;
    await loadModule('static/js/form-validation.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const input = document.getElementById('emailField');
    input.dispatchEvent(new Event('blur'));
    expect(input.classList.contains('is-invalid')).toBe(true);
    expect(input.getAttribute('aria-invalid')).toBe('true');
    input.value = 'someone@example.com';
    input.dispatchEvent(new Event('input'));
    expect(input.classList.contains('is-invalid')).toBe(false);
    expect(input.hasAttribute('aria-invalid')).toBe(false);
  });
});
