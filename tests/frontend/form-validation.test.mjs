import { describe, it, expect, vi, beforeEach } from 'vitest';
import { loadScript } from './test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = '';
  window.__VALIDATION_RULES__ = {
    email: { pattern: '^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$', message_ar: 'البريد الإلكتروني غير صالح' },
    phone: { pattern: '^[\\+]?[1-9][\\d]{0,15}$', message_ar: 'رقم الهاتف غير صالح' },
    name: { min_length: 2, max_length: 50, message_ar: 'الاسم غير صالح' },
  };
  loadScript('static/js/form-validation.js');
});

describe('form-validation.js', () => {
  describe('validateValue', () => {
    it('returns null for empty value', () => {
      expect(window.FormValidation.validateValue('email', '')).toBe(null);
    });
    it('returns error for invalid email', () => {
      expect(window.FormValidation.validateValue('email', 'notemail')).toBe('البريد الإلكتروني غير صالح');
    });
    it('returns null for valid email', () => {
      expect(window.FormValidation.validateValue('email', 'test@example.com')).toBe(null);
    });
    it('returns error for invalid phone', () => {
      expect(window.FormValidation.validateValue('phone', 'abc')).toBe('رقم الهاتف غير صالح');
    });
    it('returns error for min_length violation', () => {
      expect(window.FormValidation.validateValue('name', 'a')).toBe('الاسم غير صالح');
    });
    it('returns error for max_length violation', () => {
      expect(window.FormValidation.validateValue('name', 'a'.repeat(51))).toBe('الاسم غير صالح');
    });
    it('returns null for missing rule key', () => {
      expect(window.FormValidation.validateValue('nonexistent', 'value')).toBe(null);
    });
  });

  describe('setFieldState', () => {
    it('sets error state', () => {
      document.body.innerHTML = `
        <div class="form-group">
          <input type="text" name="test">
          <div class="invalid-feedback"></div>
        </div>
      `;
      const input = document.querySelector('input[name="test"]');
      const result = window.FormValidation.setFieldState(input, 'Error message');
      expect(result).toBe(false);
      expect(input.classList.contains('is-invalid')).toBe(true);
      expect(input.getAttribute('aria-invalid')).toBe('true');
      expect(document.querySelector('.invalid-feedback').textContent).toBe('Error message');
    });
    it('clears error state', () => {
      document.body.innerHTML = `
        <div class="form-group">
          <input type="text" name="test" class="is-invalid" aria-invalid="true">
          <div class="invalid-feedback">Error</div>
        </div>
      `;
      const input = document.querySelector('input[name="test"]');
      const result = window.FormValidation.setFieldState(input, null);
      expect(result).toBe(true);
      expect(input.classList.contains('is-invalid')).toBe(false);
      expect(input.hasAttribute('aria-invalid')).toBe(false);
    });
  });
});
