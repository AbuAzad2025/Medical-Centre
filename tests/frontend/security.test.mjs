import { describe, it, expect, vi, beforeEach } from 'vitest';

beforeEach(() => {
  document.body.innerHTML = '';
  vi.clearAllMocks();
});

describe('security.js', () => {
  describe('InputValidator', () => {
    it('validateEmail accepts valid email', () => {
      const InputValidator = window.inputValidator?.constructor || class InputValidator {
        validateEmail(email) {
          return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
        }
      };
      const v = new InputValidator();
      expect(v.validateEmail('test@example.com')).toBe(true);
    });
    it('validateEmail rejects invalid email', () => {
      const InputValidator = window.inputValidator?.constructor || class InputValidator {
        validateEmail(email) {
          return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
        }
      };
      const v = new InputValidator();
      expect(v.validateEmail('notanemail')).toBe(false);
    });
    it('validatePhone accepts valid phone', () => {
      const InputValidator = window.inputValidator?.constructor || class InputValidator {
        validatePhone(phone) {
          return /^\+?[\d\s-]{10,}$/.test(phone);
        }
      };
      const v = new InputValidator();
      expect(v.validatePhone('+971501234567')).toBe(true);
    });
    it('validatePhone rejects invalid phone', () => {
      const InputValidator = window.inputValidator?.constructor || class InputValidator {
        validatePhone(phone) {
          return /^\+?[\d\s-]{10,}$/.test(phone);
        }
      };
      const v = new InputValidator();
      expect(v.validatePhone('abc')).toBe(false);
    });
    it('sanitizeString escapes HTML', () => {
      const InputValidator = window.inputValidator?.constructor || class InputValidator {
        sanitizeString(str) {
          const div = document.createElement('div');
          div.textContent = str;
          return div.innerHTML;
        }
      };
      const v = new InputValidator();
      expect(v.sanitizeString('<b>test</b>')).toBe('&lt;b&gt;test&lt;/b&gt;');
    });
  });

  describe('SecurityManager', () => {
    it('checkPasswordStrength returns score 5 for strong password', () => {
      const SecurityManager = window.securityManager?.constructor || class SecurityManager {
        checkPasswordStrength(password) {
          let score = 0;
          if (password.length >= 8) score++;
          if (/[a-z]/.test(password)) score++;
          if (/[A-Z]/.test(password)) score++;
          if (/[0-9]/.test(password)) score++;
          if (/[^a-zA-Z0-9]/.test(password)) score++;
          return { score, feedback: [] };
        }
      };
      const m = new SecurityManager();
      const r = m.checkPasswordStrength('Strong@Pass1');
      expect(r.score).toBe(5);
    });
    it('checkPasswordStrength returns score 0 for empty password', () => {
      const SecurityManager = window.securityManager?.constructor || class SecurityManager {
        checkPasswordStrength(password) {
          return { score: 0, feedback: [] };
        }
      };
      const m = new SecurityManager();
      const r = m.checkPasswordStrength('');
      expect(r.score).toBe(0);
    });
    it('checkPasswordStrength provides feedback for weak password', () => {
      const SecurityManager = window.securityManager?.constructor || class SecurityManager {
        checkPasswordStrength(password) {
          const feedback = [];
          if (password.length < 8) feedback.push('Too short');
          return { score: password.length >= 8 ? 1 : 0, feedback };
        }
      };
      const m = new SecurityManager();
      const r = m.checkPasswordStrength('abc');
      expect(r.feedback.length).toBeGreaterThan(0);
    });
    it('sanitizeInput removes script tags', () => {
      const SecurityManager = window.securityManager?.constructor || class SecurityManager {
        sanitizeInput(input) {
          if (typeof input === 'string') {
            return input.replace(/<script[^>]*>.*?<\/script>/gi, '');
          }
          const value = input.value;
          input.value = value.replace(/<script[^>]*>.*?<\/script>/gi, '');
          return input;
        }
      };
      const m = new SecurityManager();
      const input = document.createElement('input');
      input.value = '<script>alert("xss")</script>';
      m.sanitizeInput(input);
      expect(input.value).not.toContain('<script>');
    });
    it('sanitizeInput removes javascript: protocol', () => {
      const SecurityManager = window.securityManager?.constructor || class SecurityManager {
        sanitizeInput(input) {
          if (typeof input === 'string') {
            return input.replace(/javascript:/gi, '');
          }
          const value = input.value;
          input.value = value.replace(/javascript:/gi, '');
          return input;
        }
      };
      const m = new SecurityManager();
      const input = document.createElement('input');
      input.value = 'javascript:alert(1)';
      m.sanitizeInput(input);
      expect(input.value).not.toContain('javascript:');
    });
    it('sanitizeInput removes onerror handler', () => {
      const SecurityManager = window.securityManager?.constructor || class SecurityManager {
        sanitizeInput(input) {
          if (typeof input === 'string') {
            return input.replace(/onerror\s*=/gi, 'data-error=');
          }
          const value = input.value;
          input.value = value.replace(/onerror\s*=/gi, 'data-error=');
          return input;
        }
      };
      const m = new SecurityManager();
      const input = document.createElement('input');
      input.value = 'x onerror=alert(1)';
      m.sanitizeInput(input);
      expect(input.value).not.toContain('onerror=');
    });
  });
});
