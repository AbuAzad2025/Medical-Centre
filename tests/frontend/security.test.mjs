import { describe, it, expect, vi, beforeEach } from 'vitest';
import { loadModule } from './test-utils.mjs';

/**
 * These cases used to define the logic they asserted on:
 *
 *   const InputValidator = window.inputValidator?.constructor || class InputValidator {
 *     validateEmail(email) { return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email); }
 *   };
 *
 * The fallback meant the suite passed whether or not static/js/security.js
 * existed, worked, or was the file under test at all - 465 lines of production
 * code with no coverage and no way to fail. The script is loaded here instead,
 * and the assertions run against it.
 */
beforeEach(async () => {
  document.body.innerHTML = '';
  vi.clearAllMocks();
  await loadModule('static/js/security.js');
});

describe('security.js', () => {
  describe('InputValidator', () => {
    it('is exposed', () => {
      expect(typeof window.InputValidator).toBe('function');
    });

    it('validateEmail accepts a valid email', () => {
      const v = new window.InputValidator();
      expect(v.validateEmail('test@example.com')).toBe(true);
    });

    it('validateEmail rejects an invalid email', () => {
      const v = new window.InputValidator();
      expect(v.validateEmail('notanemail')).toBe(false);
    });

    it('validateEmail rejects an email with a space', () => {
      const v = new window.InputValidator();
      expect(v.validateEmail('a b@example.com')).toBe(false);
    });

    it('validatePhone accepts an international phone', () => {
      const v = new window.InputValidator();
      expect(v.validatePhone('+966501234567')).toBe(true);
    });

    it('validatePhone rejects letters', () => {
      const v = new window.InputValidator();
      expect(v.validatePhone('abc')).toBe(false);
    });

    it('validateDate accepts a YYYY-MM-DD date', () => {
      const v = new window.InputValidator();
      expect(v.validateDate('2026-11-30')).toBe(true);
    });

    it('validateDate rejects an impossible date', () => {
      const v = new window.InputValidator();
      expect(v.validateDate('2026-13-45')).toBe(false);
    });

    it('validateTime accepts a 24-hour time', () => {
      const v = new window.InputValidator();
      expect(v.validateTime('23:59')).toBe(true);
    });

    it('validateTime rejects minutes above 59', () => {
      const v = new window.InputValidator();
      expect(v.validateTime('12:75')).toBe(false);
    });

    it('sanitizeString escapes the characters that break out of markup', () => {
      const v = new window.InputValidator();
      const out = v.sanitizeString('<script>"x"&\'y\'</script>');
      expect(out).not.toContain('<');
      expect(out).not.toContain('>');
      expect(out).not.toContain('"');
      expect(out).toContain('&lt;');
      expect(out).toContain('&amp;');
    });
  });

  describe('the other classes are exposed', () => {
    it('SecurityManager', () => {
      expect(typeof window.SecurityManager).toBe('function');
    });

    it('SecureFileUpload', () => {
      expect(typeof window.SecureFileUpload).toBe('function');
    });

    it('SessionManager', () => {
      expect(typeof window.SessionManager).toBe('function');
    });

    it('AuditLogger', () => {
      expect(typeof window.AuditLogger).toBe('function');
    });
  });
});
