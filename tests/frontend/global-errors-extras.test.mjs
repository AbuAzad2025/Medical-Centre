import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = '';
  document.head.innerHTML = '';
  delete window.__ENV;
  delete window.API_ROUTES;
  delete window.notify;
  delete window.escHtml;
  window.escHtml = (s) => String(s ?? '');
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('global-errors.js reportError arms', () => {
  it('reportError with no message falls back to the default detail', async () => {
    window.notify = { error: vi.fn() };
    const { reportError } = await loadModule('static/js/global-errors.js');
    reportError();
    expect(window.notify.error).toHaveBeenCalledWith('حدث خطأ غير متوقع');
  });

  it('console.error fallback includes the source argument', async () => {
    const err = vi.spyOn(console, 'error').mockImplementation(() => {});
    const { reportError } = await loadModule('static/js/global-errors.js');
    reportError('boom', 'unit-test');
    expect(err).toHaveBeenCalledWith('[global-errors]', 'unit-test', 'boom');
    err.mockRestore();
  });

  it('production audit log uses API_ROUTES.audit_log when set', async () => {
    window.__ENV = 'production';
    window.API_ROUTES = { audit_log: '/custom/audit' };
    window.notify = { error: vi.fn() };
    const { reportError } = await loadModule('static/js/global-errors.js');
    reportError('boom', 'unit-test');
    await new Promise(r => setTimeout(r, 20));
    expect(global.fetch.mock.calls[0][0]).toBe('/custom/audit');
  });

  it('production audit log without a csrf meta sends empty token', async () => {
    window.__ENV = 'production';
    window.notify = { error: vi.fn() };
    const { reportError } = await loadModule('static/js/global-errors.js');
    reportError('boom', 'unit-test');
    await new Promise(r => setTimeout(r, 20));
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBe('');
  });

  it('production audit log with a csrf meta forwards the token', async () => {
    window.__ENV = 'production';
    document.head.innerHTML = '<meta name="csrf-token" content="meta-tok">';
    window.notify = { error: vi.fn() };
    const { reportError } = await loadModule('static/js/global-errors.js');
    reportError('boom', 'unit-test');
    await new Promise(r => setTimeout(r, 20));
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBe('meta-tok');
  });
});

describe('global-errors.js onerror arms', () => {
  it('ignores errors whose source is a favicon reference', async () => {
    await loadModule('static/js/global-errors.js');
    expect(window.onerror('msg', 'http://x/favicon.ico', 1, 1, null)).toBe(false);
  });

  it('falls back to the generic detail when error and msg are both missing', async () => {
    window.notify = { error: vi.fn() };
    await loadModule('static/js/global-errors.js');
    window.onerror(undefined, undefined, 1, 1, null);
    expect(window.notify.error).toHaveBeenCalledWith('حدث خطأ غير متوقع');
  });

  it('error with message overrides the plain msg argument', async () => {
    window.notify = { error: vi.fn() };
    await loadModule('static/js/global-errors.js');
    window.onerror('plain', 'app.js', 1, 1, new Error('with-message'));
    expect(window.notify.error).toHaveBeenCalledWith('with-message');
  });
});

describe('global-errors.js unhandledrejection arms', () => {
  it('reason without a message is stringified', async () => {
    window.notify = { error: vi.fn() };
    await loadModule('static/js/global-errors.js');
    window.onunhandledrejection({ reason: 'plain-string-reason' });
    expect(window.notify.error).toHaveBeenCalledWith('plain-string-reason');
  });

  it('missing event reason falls back to the generic text', async () => {
    window.notify = { error: vi.fn() };
    await loadModule('static/js/global-errors.js');
    window.onunhandledrejection({});
    expect(window.notify.error).toHaveBeenCalled();
  });
});

describe('global-errors.js showEntitlementLock arms', () => {
  it('payload description is used when message is absent', async () => {
    const { showEntitlementLock } = await loadModule('static/js/global-errors.js');
    showEntitlementLock({ description: 'from-description', capability_key: 'lab' });
    const overlay = document.querySelector('.entitlement-lock-overlay');
    expect(overlay.innerHTML).toContain('from-description');
    expect(document.querySelector('.entitlement-lock-screen').getAttribute('data-capability')).toBe('lab');
  });

  it('payload error is used when description and message are absent', async () => {
    const { showEntitlementLock } = await loadModule('static/js/global-errors.js');
    showEntitlementLock({ error: 'from-error' });
    const overlay = document.querySelector('.entitlement-lock-overlay');
    expect(overlay.innerHTML).toContain('from-error');
  });

  it('payload with no message at all renders the generic default', async () => {
    const { showEntitlementLock } = await loadModule('static/js/global-errors.js');
    showEntitlementLock({});
    expect(document.querySelector('.entitlement-lock-overlay')).toBeTruthy();
  });

  it('dismiss button removes a second overlay instance safely', async () => {
    const { showEntitlementLock } = await loadModule('static/js/global-errors.js');
    showEntitlementLock({});
    const dismiss = document.querySelector('[data-dismiss-lock]');
    dismiss.click();
    expect(document.querySelector('.entitlement-lock-overlay')).toBeNull();
    // second call must not error with empty body
    showEntitlementLock({});
    expect(document.querySelector('.entitlement-lock-overlay')).toBeTruthy();
  });

  it('undefined payload renders the default lock screen', async () => {
    const { showEntitlementLock } = await loadModule('static/js/global-errors.js');
    showEntitlementLock(undefined);
    expect(document.querySelector('.entitlement-lock-overlay')).toBeTruthy();
  });
});
