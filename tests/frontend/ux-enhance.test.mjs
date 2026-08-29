import { describe, it, expect, vi, beforeEach } from 'vitest';
import { loadScript } from './test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = '';
  loadScript('static/js/ux-enhance.js');
});

describe('ux-enhance.js', () => {
  describe('showFieldErrors', () => {
    it('displays errors on correct fields', () => {
      document.body.innerHTML = `
        <form id="testForm">
          <div class="form-group">
            <input type="text" name="email">
            <div class="invalid-feedback"></div>
          </div>
          <div class="form-group">
            <input type="text" name="phone">
            <div class="invalid-feedback"></div>
          </div>
        </form>
      `;
      const form = document.getElementById('testForm');
      const result = window.UXEnhance.showFieldErrors(form, { email: 'Invalid email' });
      expect(result).toBe(true);
      const emailInput = form.querySelector('[name="email"]');
      expect(emailInput.classList.contains('is-invalid')).toBe(true);
      expect(emailInput.getAttribute('aria-invalid')).toBe('true');
      expect(form.querySelector('.invalid-feedback').textContent).toBe('Invalid email');
    });

    it('returns false for null errors', () => {
      document.body.innerHTML = '<form id="testForm"></form>';
      const form = document.getElementById('testForm');
      const result = window.UXEnhance.showFieldErrors(form, null);
      expect(result).toBe(false);
    });

    it('handles array error messages', () => {
      document.body.innerHTML = `
        <form id="testForm">
          <input type="text" name="name">
        </form>
      `;
      const form = document.getElementById('testForm');
      const result = window.UXEnhance.showFieldErrors(form, { name: ['Error 1', 'Error 2'] });
      expect(result).toBe(true);
    });
  });
});
