import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = '';
  window.ScrollIntoView = vi.fn();
  window.__VALIDATION_RULES__ = {
    email: { pattern: '^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$', message_ar: 'invalid' },
    phone: { pattern: '^[\\+]?[1-9][\\d]{0,15}$', message_ar: 'bad phone' },
    name: { min_length: 2, max_length: 50, message_ar: 'bad name' },
    zip: { min_length: 1, max_length: 999, message_ar: 'bad zip' },
    digits: { pattern: '^\\d{4}$', message_ar: 'bad digits' },
    broken: { pattern: '([', message_ar: 'broken regex' },
  };
});

afterEach(() => {
  vi.useRealTimers();
});

describe('form-validation.js', () => {
  describe('validateValue', () => {
    it('returns null for empty value', async () => {
      const { validateValue } = await loadModule('static/js/form-validation.js');
      expect(validateValue('email', '')).toBe(null);
    });
    it('returns error for invalid email', async () => {
      const { validateValue } = await loadModule('static/js/form-validation.js');
      expect(validateValue('email', 'notemail')).toBe('invalid');
    });
    it('returns null for valid email', async () => {
      const { validateValue } = await loadModule('static/js/form-validation.js');
      expect(validateValue('email', 'test@example.com')).toBe(null);
    });
    it('returns error for invalid phone', async () => {
      const { validateValue } = await loadModule('static/js/form-validation.js');
      expect(validateValue('phone', 'abc')).toBe('bad phone');
    });
    it('returns null for valid phone', async () => {
      const { validateValue } = await loadModule('static/js/form-validation.js');
      expect(validateValue('phone', '+966501234567')).toBe(null);
    });
    it('returns error for min_length violation', async () => {
      const { validateValue } = await loadModule('static/js/form-validation.js');
      expect(validateValue('name', 'a')).toBe('bad name');
    });
    it('returns error for max_length violation', async () => {
      const { validateValue } = await loadModule('static/js/form-validation.js');
      expect(validateValue('name', 'a'.repeat(51))).toBe('bad name');
    });
    it('returns null for missing rule key', async () => {
      const { validateValue } = await loadModule('static/js/form-validation.js');
      expect(validateValue('nonexistent', 'value')).toBe(null);
    });
    it('returns pattern error for broken regex gracefully', async () => {
      const { validateValue } = await loadModule('static/js/form-validation.js');
      expect(validateValue('broken', 'anything')).toBe(null);
    });
  });

  describe('setFieldState', () => {
    it('sets error state with feedback', async () => {
      document.body.innerHTML = `<div class="form-group"><input name="f"><div class="invalid-feedback"></div></div>`;
      const { setFieldState } = await loadModule('static/js/form-validation.js');
      const input = document.querySelector('[name="f"]');
      const result = setFieldState(input, 'oops');
      expect(result).toBe(false);
      expect(input.classList.contains('is-invalid')).toBe(true);
      expect(document.querySelector('.invalid-feedback').textContent).toBe('oops');
    });

    it('clears error state', async () => {
      document.body.innerHTML = `<div class="form-group"><input name="f" class="is-invalid" aria-invalid="true"><div class="invalid-feedback">oops</div></div>`;
      const { setFieldState } = await loadModule('static/js/form-validation.js');
      const input = document.querySelector('[name="f"]');
      const result = setFieldState(input, null);
      expect(result).toBe(true);
      expect(input.classList.contains('is-invalid')).toBe(false);
      expect(document.querySelector('.invalid-feedback').textContent).toBe('');
    });

    it('finds feedback by data-error-for', async () => {
      document.body.innerHTML = `<div><input name="x"><div data-error-for="x"></div></div>`;
      const { setFieldState } = await loadModule('static/js/form-validation.js');
      const input = document.querySelector('[name="x"]');
      setFieldState(input, 'msg');
      expect(document.querySelector('[data-error-for="x"]').textContent).toBe('msg');
    });

    it('works when no feedback element present', async () => {
      document.body.innerHTML = `<div><input name="y"></div>`;
      const { setFieldState } = await loadModule('static/js/form-validation.js');
      const input = document.querySelector('[name="y"]');
      expect(setFieldState(input, 'err')).toBe(false);
      expect(setFieldState(input, null)).toBe(true);
    });
  });

  describe('validateInput', () => {
    it('returns true when field has no data-validate attr', async () => {
      document.body.innerHTML = `<input>`;
      const { validateInput } = await loadModule('static/js/form-validation.js');
      expect(validateInput(document.querySelector('input'))).toBe(true);
    });

    it('returns false for invalid input', async () => {
      document.body.innerHTML = `<input name="f" data-validate="email" value="not-an-email">`;
      const { validateInput } = await loadModule('static/js/form-validation.js');
      expect(validateInput(document.querySelector('input'))).toBe(false);
    });

    it('returns true for valid input', async () => {
      document.body.innerHTML = `<input name="f" data-validate="email" value="a@b.com">`;
      const { validateInput } = await loadModule('static/js/form-validation.js');
      expect(validateInput(document.querySelector('input'))).toBe(true);
    });
  });

  describe('preventDoubleSubmit', () => {
    it('blocks second submit and restores button on pageshow', async () => {
      document.body.innerHTML = `<form><button type="submit">Save</button></form>`;
      const { preventDoubleSubmit } = await loadModule('static/js/form-validation.js');
      const form = document.querySelector('form');
      preventDoubleSubmit(form);
      const btn = form.querySelector('button');
      form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      expect(btn.disabled).toBe(true);
      form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      expect(btn.disabled).toBe(true);
      window.dispatchEvent(new Event('pageshow'));
      expect(btn.disabled).toBe(false);
    });

    it('keeps original HTML on restore', async () => {
      document.body.innerHTML = `<form><button type="submit">Save</button></form>`;
      const { preventDoubleSubmit } = await loadModule('static/js/form-validation.js');
      const form = document.querySelector('form');
      preventDoubleSubmit(form);
      form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      window.dispatchEvent(new Event('pageshow'));
      expect(form.querySelector('button').innerHTML).toContain('Save');
    });
  });

  describe('DOMContentLoaded wiring', () => {
    it('attaches maxlength to phone and national_id', async () => {
      document.body.innerHTML = `
        <form method="POST"><input type="text" name="phone"><input type="text" name="national_id"></form>`;
      await loadModule('static/js/form-validation.js');
      document.dispatchEvent(new Event('DOMContentLoaded'));
      expect(document.querySelector('[name="phone"]').getAttribute('maxlength')).toBe('20');
      expect(document.querySelector('[name="national_id"]').getAttribute('maxlength')).toBe('32');
    });

    it('attaches dir=auto to text inputs without dir', async () => {
      document.body.innerHTML = `<input type="text" name="t"><textarea name="x"></textarea>`;
      await loadModule('static/js/form-validation.js');
      document.dispatchEvent(new Event('DOMContentLoaded'));
      expect(document.querySelector('[name="t"]').getAttribute('dir')).toBe('auto');
      expect(document.querySelector('[name="x"]').getAttribute('dir')).toBe('auto');
    });

    it('strips non-digits from national_id inputs', async () => {
      document.body.innerHTML = `<input type="tel" name="nid" data-validate="national_id">`;
      await loadModule('static/js/form-validation.js');
      document.dispatchEvent(new Event('DOMContentLoaded'));
      const input = document.querySelector('[name="nid"]');
      input.value = '1a2b3c4d5e67890';
      input.dispatchEvent(new Event('input'));
      expect(input.value).toBe('1234567890');
    });

    it('validates data-validate-form on submit and prevents invalid submission', async () => {
      document.body.innerHTML = `<form method="POST" data-validate-form><input name="email" data-validate="email" value="not-an-email"><button type="submit">Go</button></form>`;
      await loadModule('static/js/form-validation.js');
      document.dispatchEvent(new Event('DOMContentLoaded'));
      const form = document.querySelector('form');
      const dispatched = form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      expect(form.classList.contains('was-validated')).toBe(true);
    });

    it('DOMCONTENTLOADED calls preventDoubleSubmit on POST forms', async () => {
      document.body.innerHTML = `<form method="POST"><button type="submit">Go</button></form>`;
      await loadModule('static/js/form-validation.js');
      document.dispatchEvent(new Event('DOMContentLoaded'));
      const form = document.querySelector('form');
      form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      expect(form.querySelector('[type="submit"]').disabled).toBe(true);
    });
  });
});