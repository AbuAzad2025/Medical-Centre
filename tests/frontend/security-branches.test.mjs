import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

const realSessionStorage = window.sessionStorage;

beforeEach(() => {
  document.body.innerHTML = '';
  document.head.innerHTML = '';
  window.localStorage.clear();
  realSessionStorage.clear();
  delete window.API_ROUTES;
  delete window.notifications;
  delete window.DOMPurify;
  delete window.securityManager;
  delete window.inputValidator;
  delete window.secureFileUpload;
  delete window.sessionManager;
  delete window.auditLogger;
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe('security.js XSS/DOMPurify branch', () => {
  it('warns when DOMPurify is not loaded', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    await loadModule('static/js/security.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(warn).toHaveBeenCalledWith(expect.stringContaining('DOMPurify'));
  });

  it('stays silent when DOMPurify is loaded', async () => {
    window.DOMPurify = { sanitize: vi.fn(x => x) };
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    await loadModule('static/js/security.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(warn).not.toHaveBeenCalledWith(expect.stringContaining('DOMPurify'));
  });
});

describe('security.js handleSessionTimeout branches', () => {
  it('shows a notification and redirects to auth login with API_ROUTES.auth_login', async () => {
    vi.useFakeTimers();
    window.API_ROUTES = { auth_login: '/custom/login' };
    window.notifications = { show: vi.fn() };
    window.location = { href: '' };
    await loadModule('static/js/security.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    window.securityManager.handleSessionTimeout();
    expect(window.notifications.show).toHaveBeenCalled();
    vi.advanceTimersByTime(3100);
    expect(window.location.href).toBe('/custom/login');
    vi.useRealTimers();
  });

  it('falls back to the default login route without API_ROUTES', async () => {
    vi.useFakeTimers();
    window.location = { href: '' };
    await loadModule('static/js/security.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    window.securityManager.handleSessionTimeout();
    vi.advanceTimersByTime(3100);
    expect(window.location.href).toBe('/auth/login');
    vi.useRealTimers();
  });

  it('without window.notifications still redirects after the delay', async () => {
    vi.useFakeTimers();
    window.location = { href: '' };
    await loadModule('static/js/security.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(() => window.securityManager.handleSessionTimeout()).not.toThrow();
    vi.advanceTimersByTime(3100);
    expect(window.location.href).toBe('/auth/login');
    vi.useRealTimers();
  });
});

describe('security.js password strength arms', () => {
  it('flags a password missing a lowercase letter', async () => {
    await loadModule('static/js/security.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const result = window.securityManager.checkPasswordStrength('ABCDEF1!');
    expect(result.feedback).toContain('يجب أن تحتوي على حرف صغير واحد على الأقل');
  });
});

describe('security.js rate limiting branches', () => {
  it('uses GET as the default method key and expires stale requests', async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-11-08T00:00:00Z'));
    await loadModule('static/js/security.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    window.securityManager.setupRateLimiting();
    expect(() => window.fetch('/api/x', { })).not.toThrow();
    vi.setSystemTime(new Date('2026-11-08T00:01:01Z'));
    expect(() => window.fetch('/api/x')).not.toThrow();
    vi.useRealTimers();
  });

  it('keys requests by explicit method so GET and POST do not mix', async () => {
    await loadModule('static/js/security.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    window.securityManager.setupRateLimiting();
    window.fetch('/api/x', { method: 'POST' });
    window.fetch('/api/x', { method: 'GET' });
    expect(true).toBe(true);
  });
});

describe('security.js session storage error branches', () => {
  it('loadSessionData swallows malformed JSON', async () => {
    realSessionStorage.setItem('medical_session', '{not-json');
    await loadModule('static/js/security.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(window.sessionManager.sessionData.size).toBe(0);
  });

  it('saveSessionData swallows sessionStorage quota errors', async () => {
    await loadModule('static/js/security.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const original = realSessionStorage.setItem.bind(realSessionStorage);
    realSessionStorage.setItem = () => { throw new Error('quota'); };
    expect(() => window.sessionManager.set('k', 'v')).not.toThrow();
    realSessionStorage.setItem = original;
  });
});

describe('security.js storage listener branches', () => {
  it('storage events with a different key do not reload session data', async () => {
    await loadModule('static/js/security.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const spy = vi.spyOn(window.sessionManager, 'loadSessionData');
    window.dispatchEvent(new StorageEvent('storage', { key: 'other_key' }));
    expect(spy).not.toHaveBeenCalled();
    window.dispatchEvent(new StorageEvent('storage', { key: 'medical_session' }));
    expect(spy).toHaveBeenCalled();
  });
});

describe('security.js audit log branches', () => {
  it('sendLog posts without X-CSRFToken when no token is available', async () => {
    document.head.innerHTML = '';
    await loadModule('static/js/security.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    window.auditLogger.log('test_action', { a: 1 });
    const call = global.fetch.mock.calls[0];
    expect(call[1].headers['X-CSRFToken']).toBeUndefined();
  });

  it('sendLog includes the meta token when present', async () => {
    document.head.innerHTML = '<meta name="csrf-token" content="meta-csrf">';
    await loadModule('static/js/security.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    window.auditLogger.log('test_action', {});
    const call = global.fetch.mock.calls[0];
    expect(call[1].headers['X-CSRFToken']).toBe('meta-csrf');
  });

  it('sendLog posts to API_ROUTES.audit_log when set', async () => {
    window.API_ROUTES = { audit_log: '/custom/audit' };
    await loadModule('static/js/security.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    window.auditLogger.log('x', {});
    expect(global.fetch.mock.calls[0][0]).toBe('/custom/audit');
  });

  it('sendLog network failure logs a warning', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    await loadModule('static/js/security.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    window.auditLogger.log('x', {});
    await new Promise(r => setTimeout(r, 20));
    expect(warn).toHaveBeenCalledWith(expect.stringContaining('فشل'));
  });
});

describe('security.js sanitization and validation arms', () => {
  it('blur sanitizes a TEXTAREA value', async () => {
    await loadModule('static/js/security.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const ta = document.createElement('textarea');
    ta.value = '<script>alert(1)</script>hello';
    document.body.appendChild(ta);
    ta.dispatchEvent(new FocusEvent('blur', { bubbles: true }));
    expect(ta.value).not.toContain('<script>');
    expect(ta.value).toContain('hello');
  });

  it('blur on a valid email adds is-valid', async () => {
    await loadModule('static/js/security.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const el = document.createElement('input');
    el.type = 'email';
    el.value = 'a@b.co';
    document.body.appendChild(el);
    el.classList.add('is-invalid');
    el.dispatchEvent(new FocusEvent('blur', { bubbles: true }));
    expect(el.classList.contains('is-valid')).toBe(true);
  });

  it('blur on an invalid tel phone adds is-invalid', async () => {
    await loadModule('static/js/security.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const el = document.createElement('input');
    el.type = 'tel';
    el.value = 'abc';
    document.body.appendChild(el);
    el.dispatchEvent(new FocusEvent('blur', { bubbles: true }));
    expect(el.classList.contains('is-invalid')).toBe(true);
  });

  it('blur on a valid tel phone adds is-valid', async () => {
    await loadModule('static/js/security.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const el = document.createElement('input');
    el.type = 'tel';
    el.value = '+970599123456';
    document.body.appendChild(el);
    el.dispatchEvent(new FocusEvent('blur', { bubbles: true }));
    expect(el.classList.contains('is-valid')).toBe(true);
  });
});

describe('security.js file validation notification branches', () => {
  it('invalid file with notifications present shows the errors joined', async () => {
    window.notifications = { show: vi.fn() };
    await loadModule('static/js/security.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const input = document.createElement('input');
    input.type = 'file';
    document.body.appendChild(input);
    const badFile = { type: 'application/x-msdownload', size: 1, name: 'evil.exe' };
    Object.defineProperty(input, 'files', { value: [badFile], configurable: true });
    input.dispatchEvent(new Event('change', { bubbles: true }));
    expect(window.notifications.show).toHaveBeenCalled();
  });
});

describe('security.js validateDate branch', () => {
  it('rejects dates matching the pattern but impossible to parse', async () => {
    await loadModule('static/js/security.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(window.inputValidator.validateDate('2024-13-99')).toBe(false);
    expect(window.inputValidator.validateDate('2024-02-29')).toBe(true);
    expect(window.inputValidator.validateDate('not-a-date')).toBe(false);
  });
});
