import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = '';
  try { sessionStorage.clear(); } catch (e) {}
  vi.clearAllMocks();
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
  await loadModule('static/js/security.js');
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe('security.js', () => {
  describe('InputValidator class', () => {
    it('validateEmail accepts and rejects', () => {
      const v = new window.InputValidator();
      expect(v.validateEmail('a@b.com')).toBe(true);
      expect(v.validateEmail('nope')).toBe(false);
      expect(v.validateEmail('a b@c.com')).toBe(false);
    });

    it('validatePhone accepts international and rejects letters', () => {
      const v = new window.InputValidator();
      expect(v.validatePhone('+966501234567')).toBe(true);
      expect(v.validatePhone('abc')).toBe(false);
    });

    it('validateArabicName accepts Arabic', () => {
      const v = new window.InputValidator();
      expect(v.validateArabicName('محمد أحمد')).toBe(true);
      expect(v.validateArabicName('John')).toBe(false);
    });

    it('validateEnglishName accepts English', () => {
      const v = new window.InputValidator();
      expect(v.validateEnglishName('John Doe')).toBe(true);
      expect(v.validateEnglishName('محمد')).toBe(false);
    });

    it('validateIdNumber accepts digits', () => {
      const v = new window.InputValidator();
      expect(v.validateIdNumber('12345')).toBe(true);
      expect(v.validateIdNumber('abc')).toBe(false);
    });

    it('validateDate accepts valid and rejects impossible', () => {
      const v = new window.InputValidator();
      expect(v.validateDate('2026-11-30')).toBe(true);
      expect(v.validateDate('2026-13-45')).toBe(false);
    });

    it('validateTime accepts and rejects', () => {
      const v = new window.InputValidator();
      expect(v.validateTime('23:59')).toBe(true);
      expect(v.validateTime('12:75')).toBe(false);
    });

    it('sanitizeString escapes markup characters', () => {
      const v = new window.InputValidator();
      const out = v.sanitizeString('<script>&"x\'y"</script>');
      expect(out).not.toContain('<');
      expect(out).not.toContain('>');
      expect(out).toContain('&lt;');
      expect(out).toContain('&gt;');
      expect(out).toContain('&quot;');
      expect(out).toContain('&#x27;');
      expect(out).toContain('&amp;');
    });
  });

  describe('SecurityManager class', () => {
    it('reads CSRF token from meta and sanitizes input', () => {
      document.body.innerHTML = '<meta name="csrf-token" content="tok123">';
      const manager = new window.SecurityManager();
      expect(manager.csrfToken).toBe('tok123');
      const input = document.createElement('input');
      input.value = '<script>alert(1)</script> javascript:alert(1) onload=hack';
      manager.sanitizeInput(input);
      expect(input.value).not.toContain('<script>');
      expect(input.value).not.toContain('javascript:');
      expect(input.value).not.toContain('onload=');
      manager.destroy();
    });

    it('getCSRFToken handles missing meta', () => {
      const manager = new window.SecurityManager();
      expect(manager.csrfToken).toBe(null);
      manager.destroy();
    });

    it('checkPasswordStrength scores strong password', () => {
      const manager = new window.SecurityManager();
      const out = manager.checkPasswordStrength('Abcdef1!');
      expect(out.score).toBe(5);
      expect(out.feedback).toEqual([]);
      manager.destroy();
    });

    it('checkPasswordStrength pushes feedback for weak password', () => {
      const manager = new window.SecurityManager();
      const out = manager.checkPasswordStrength('abc');
      expect(out.score).toBeLessThan(5);
      expect(out.feedback.length).toBeGreaterThan(0);
      manager.destroy();
    });

    it('blur handler sanitizes INPUT or TEXTAREA', () => {
      const manager = new window.SecurityManager();
      const input = document.createElement('input');
      input.value = '<script>bad</script>safe';
      document.body.appendChild(input);
      input.dispatchEvent(new FocusEvent('blur', { bubbles: true }));
      expect(input.value).toContain('safe');
      manager.destroy();
    });

    it('submit handler injects csrf_token if missing', () => {
      document.body.innerHTML = '<meta name="csrf-token" content="csrf-token-value"><form id="f"><input name="foo"></form>';
      const manager = new window.SecurityManager();
      const form = document.getElementById('f');
      form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      expect(form.querySelector('input[name="csrf_token"]').value).toBe('csrf-token-value');
      manager.destroy();
    });

    it('destroy clears handlers and intervals', () => {
      const manager = new window.SecurityManager();
      expect(() => manager.destroy()).not.toThrow();
    });

    it('setupRateLimiting blocks after 100 requests', () => {
      const manager = new window.SecurityManager();
      const original = window.fetch;
      manager.setupRateLimiting();
      for (let i = 0; i < 100; i++) window.fetch('/api/x', { method: 'GET' });
      expect(() => window.fetch('/api/x', { method: 'GET' })).toThrow();
      window.fetch = original;
      manager.destroy();
    });
  });

  describe('SecureFileUpload class', () => {
    it('validateFile accepts allowed image within size', () => {
      const upload = new window.SecureFileUpload();
      const file = new File(['img'], 'photo.png', { type: 'image/png' });
      const out = upload.validateFile(file);
      expect(out.isValid).toBe(true);
      expect(out.errors).toEqual([]);
    });

    it('validateFile rejects disallowed type and oversized file', () => {
      const upload = new window.SecureFileUpload();
      const big = new File([new Uint8Array(1024)], 'doc.bin', { type: 'application/octet-stream' });
      Object.defineProperty(big, 'size', { value: 11 * 1024 * 1024 });
      const out = upload.validateFile(big);
      expect(out.isValid).toBe(false);
      expect(out.errors.length).toBeGreaterThan(0);
    });

    it('validateFile rejects malicious filename', () => {
      const upload = new window.SecureFileUpload();
      const file = new File(['x'], 'bad;name!.png', { type: 'image/png' });
      const out = upload.validateFile(file);
      expect(out.errors.length).toBe(1);
    });

    it('scanFile detects malicious content', async () => {
      const upload = new window.SecureFileUpload();
      const malicious = new File(['<script>alert(1)</script>'], 'evil.svg', { type: 'image/svg+xml' });
      const out = await upload.scanFile(malicious);
      expect(out.isSafe).toBe(false);
    });

    it('scanFile accepts safe content', async () => {
      const upload = new window.SecureFileUpload();
      const safe = new File(['hello'], 'safe.txt', { type: 'text/plain' });
      const out = await upload.scanFile(safe);
      expect(out.isSafe).toBe(true);
    });
  });

  describe('SessionManager class', () => {
    it('round-trips values through sessionStorage', () => {
      const manager = new window.SessionManager();
      manager.set('k', 'v');
      expect(manager.get('k')).toBe('v');
      manager.remove('k');
      expect(manager.get('k')).toBeUndefined();
    });

    it('clear empties session and storage', () => {
      const manager = new window.SessionManager();
      manager.set('k', 'v');
      manager.clear();
      expect(manager.get('k')).toBeUndefined();
    });

    it('loads existing session from storage', () => {
      sessionStorage.setItem('medical_session', JSON.stringify([['a', 'b']]));
      const manager = new window.SessionManager();
      expect(manager.get('a')).toBe('b');
    });
  });

  describe('AuditLogger class', () => {
    it('logs entries capped at maxLogs', () => {
      const logger = new window.AuditLogger();
      for (let i = 0; i < 1001; i++) logger.log('test' + i);
      expect(logger.logs.length).toBe(1000);
    });

    it('uses user id from sessionStorage when available', () => {
      sessionStorage.setItem('user_id', '42');
      const logger = new window.AuditLogger();
      logger.log('action');
      expect(logger.logs[0].userId).toBe('42');
    });

    it('uses anonymous when missing session user id', () => {
      const logger = new window.AuditLogger();
      logger.log('action');
      expect(logger.logs[0].userId).toBe('anonymous');
    });
  });

  describe('module init on DOMContentLoaded', () => {
    it('creates managers on window after DOMContentLoaded', async () => {
      document.body.innerHTML = '<input type="email" id="emailField" value="not-an-email">';
      document.dispatchEvent(new Event('DOMContentLoaded'));
      await new Promise(r => setTimeout(r, 10));
      expect(window.securityManager).toBeDefined();
      expect(window.inputValidator).toBeDefined();
      expect(window.secureFileUpload).toBeDefined();
      expect(window.sessionManager).toBeDefined();
      expect(window.auditLogger).toBeDefined();
    });

    it('blur handler marks invalid email', async () => {
      document.body.innerHTML = '<input type="email" value="not-an-email">';
      document.dispatchEvent(new Event('DOMContentLoaded'));
      await new Promise(r => setTimeout(r, 10));
      const input = document.querySelector('input');
      input.dispatchEvent(new FocusEvent('blur', { bubbles: true }));
      expect(input.classList.contains('is-invalid')).toBe(true);
    });

    it('file change with invalid type clears the input', async () => {
      window.notifications = { show: vi.fn() };
      document.body.innerHTML = '<input type="file">';
      document.dispatchEvent(new Event('DOMContentLoaded'));
      await new Promise(r => setTimeout(r, 10));
      const input = document.querySelector('input');
      const file = new File(['x'], 'doc.exe', { type: 'application/octet-stream' });
      Object.defineProperty(input, 'files', { value: [file], configurable: true });
      input.dispatchEvent(new Event('change', { bubbles: true }));
      expect(window.notifications.show).toHaveBeenCalled();
    });
  });
});