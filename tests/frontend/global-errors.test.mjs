import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(() => {
  window.__ENV = 'testing';
  window.notify = { error: vi.fn(), warning: vi.fn() };
  window.fetch = vi.fn().mockResolvedValue({ ok: true });
  window.console.error = vi.fn();
  window.console.warn = vi.fn();
  window.API_ROUTES = { audit_log: '/super-admin/api/audit-log' };
  document.body.innerHTML = '';
  window.escHtml = (v) => {
    if (v === null || v === undefined) return '';
    return String(v).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  };
  vi.resetModules();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('global-errors.js', () => {
  it('reportError calls notify.error when available', async () => {
    const mod = await loadModule('static/js/global-errors.js');
    mod.reportError('oops', 'handler');
    expect(window.notify.error).toHaveBeenCalledWith('oops');
  });

  it('reportError logs to console.error when no notify', async () => {
    delete window.notify;
    const mod = await loadModule('static/js/global-errors.js');
    mod.reportError('oops', 'src');
    expect(window.console.error).toHaveBeenCalled();
  });

  it('reportError in production posts audit log', async () => {
    window.__ENV = 'production';
    document.body.innerHTML = '<meta name="csrf-token" content="abc">';
    const mod = await loadModule('static/js/global-errors.js');
    mod.reportError('boom', 'src');
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalledWith('/super-admin/api/audit-log', expect.objectContaining({ method: 'POST' }));
  });

  it('reportError in production tolerates fetch failure', async () => {
    window.__ENV = 'production';
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/global-errors.js');
    mod.reportError('boom', 'src');
    await new Promise(r => setTimeout(r, 30));
    expect(window.console.warn).toHaveBeenCalled();
  });

  it('window.onerror ignores source-map errors', async () => {
    const mod = await loadModule('static/js/global-errors.js');
    const out = window.onerror('msg', '/assets/file.js.map', 1, 1, new Error('oops'));
    expect(out).toBe(false);
    expect(window.notify.error).not.toHaveBeenCalled();
  });

  it('window.onerror reports generic error', async () => {
    const mod = await loadModule('static/js/global-errors.js');
    window.onerror('msg', '/file.js', 1, 1, new Error('oops'));
    expect(window.notify.error).toHaveBeenCalledWith('oops');
  });

  it('window.onunhandledrejection reports reason', async () => {
    const mod = await loadModule('static/js/global-errors.js');
    window.onunhandledrejection({ reason: new Error('rejected') });
    expect(window.notify.error).toHaveBeenCalledWith('rejected');
  });

  it('window.onunhandledrejection handles non-object reason', async () => {
    const mod = await loadModule('static/js/global-errors.js');
    window.onunhandledrejection({ reason: 'plain string' });
    expect(window.notify.error).toHaveBeenCalledWith('plain string');
  });

  it('showEntitlementLock adds overlay', async () => {
    const mod = await loadModule('static/js/global-errors.js');
    mod.showEntitlementLock({ title: 'Locked', message: 'Unavailable', capability_key: 'qr' });
    expect(document.querySelector('.entitlement-lock-overlay')).toBeTruthy();
    expect(document.querySelector('[data-capability="qr"]')).toBeTruthy();
  });

  it('showEntitlementLock ignores duplicates', async () => {
    const mod = await loadModule('static/js/global-errors.js');
    mod.showEntitlementLock({ title: 'Locked' });
    mod.showEntitlementLock({ title: 'Locked2' });
    expect(document.querySelectorAll('.entitlement-lock-overlay').length).toBe(1);
  });

  it('showEntitlementLock with upgrade URL renders link', async () => {
    const mod = await loadModule('static/js/global-errors.js');
    mod.showEntitlementLock({ title: 'Locked', message: 'msg', upgrade_url: '/upgrade' });
    expect(document.querySelector('.entitlement-lock-overlay a[href="/upgrade"]')).toBeTruthy();
  });

  it('showEntitlementLock dismiss button removes overlay', async () => {
    const mod = await loadModule('static/js/global-errors.js');
    mod.showEntitlementLock({ title: 'Locked', message: 'msg' });
    document.querySelector('[data-dismiss-lock]').click();
    expect(document.querySelector('.entitlement-lock-overlay')).toBeNull();
  });

  it('showEntitlementLock calls notify.warning', async () => {
    const mod = await loadModule('static/js/global-errors.js');
    mod.showEntitlementLock({ title: 'Locked', message: 'msg2' });
    expect(window.notify.warning).toHaveBeenCalledWith('msg2');
  });

  it('parseJsonSafe parses valid JSON', async () => {
    const mod = await loadModule('static/js/global-errors.js');
    const response = new Response(JSON.stringify({ ok: true }), { headers: { 'content-type': 'application/json' } });
    const out = await mod.parseJsonSafe(response);
    expect(out).toEqual({ ok: true });
  });

  it('parseJsonSafe returns {} for invalid JSON', async () => {
    const mod = await loadModule('static/js/global-errors.js');
    const response = new Response('not json');
    const out = await mod.parseJsonSafe(response);
    expect(out).toEqual({});
  });

  it('handleEntitlementStatus ignores non-402/403 status', async () => {
    const mod = await loadModule('static/js/global-errors.js');
    const response = new Response('{}', { status: 200 });
    mod.handleEntitlementStatus(response);
    expect(document.querySelector('.entitlement-lock-overlay')).toBeNull();
  });

  it('handleEntitlementStatus shows entitlement lock on 403', async () => {
    const mod = await loadModule('static/js/global-errors.js');
    const response = new Response(JSON.stringify({ title: 'Locked!', message: 'msg' }), { status: 403 });
    mod.handleEntitlementStatus(response);
    await new Promise(r => setTimeout(r, 20));
    expect(document.querySelector('.entitlement-lock-overlay')).toBeTruthy();
  });

  it('handleEntitlementStatus redirects when redirect_url is present', async () => {
    const mod = await loadModule('static/js/global-errors.js');
    window.location = { href: '' };
    const response = new Response(JSON.stringify({ redirect_url: '/upgrade' }), { status: 402 });
    mod.handleEntitlementStatus(response);
    await new Promise(r => setTimeout(r, 20));
    expect(window.location.href).toBe('/upgrade');
  });

  it('wrapFetchWithEntitlementHandling returns wrapped function', async () => {
    const mod = await loadModule('static/js/global-errors.js');
    const wrapped = mod.wrapFetchWithEntitlementHandling(() => Promise.resolve(new Response('{"ok":true}', { status: 200 })));
    const res = await wrapped('/x');
    expect(res.status).toBe(200);
  });

  it('wrapFetchWithEntitlementHandling calls handleEntitlementStatus', async () => {
    const mod = await loadModule('static/js/global-errors.js');
    window.location = { href: '' };
    const wrapped = mod.wrapFetchWithEntitlementHandling(() => Promise.resolve(new Response('{"redirect_url":"/upgrade"}', { status: 402 })));
    await wrapped('/x');
    await new Promise(r => setTimeout(r, 30));
    expect(window.location.href).toBe('/upgrade');
  });

  it('wrapFetchWithEntitlementHandling rethrows fetch errors', async () => {
    const mod = await loadModule('static/js/global-errors.js');
    const wrapped = mod.wrapFetchWithEntitlementHandling(() => Promise.reject(new Error('network')));
    await expect(wrapped('/x')).rejects.toThrow('network');
  });

  it('exposes window.__showEntitlementLock', async () => {
    await loadModule('static/js/global-errors.js');
    expect(typeof window.__showEntitlementLock).toBe('function');
  });

  it('exposes window.__wrapFetchEntitlement', async () => {
    await loadModule('static/js/global-errors.js');
    expect(typeof window.__wrapFetchEntitlement).toBe('function');
  });
});
describe('global-errors.js safeSameOriginUrl clamping', () => {
  it('allows root-relative URLs', async () => {
    const mod = await loadModule('static/js/global-errors.js');
    expect(mod.safeSameOriginUrl('/auth/login')).toBe('/auth/login');
    expect(mod.safeSameOriginUrl('/super-admin/upgrade')).toBe('/super-admin/upgrade');
  });

  it('rejects protocol-relative and absolute-external URLs', async () => {
    const mod = await loadModule('static/js/global-errors.js');
    expect(mod.safeSameOriginUrl('//evil.example.com/x')).toBe('');
    expect(mod.safeSameOriginUrl('https://evil.example.com/x')).toBe('');
  });

  it('rejects javascript:, data: and vbscript: URLs', async () => {
    const mod = await loadModule('static/js/global-errors.js');
    expect(mod.safeSameOriginUrl('javascript:alert(1)')).toBe('');
    expect(mod.safeSameOriginUrl('data:text/html,<script>alert(1)</script>')).toBe('');
    expect(mod.safeSameOriginUrl('vbscript:msgbox(1)')).toBe('');
  });

  it('allows same-origin absolute URLs', async () => {
    window.location = { origin: 'http://test.local', href: 'http://test.local/start' };
    const mod = await loadModule('static/js/global-errors.js');
    expect(mod.safeSameOriginUrl('http://test.local/upgrade')).toBe('http://test.local/upgrade');
    expect(mod.safeSameOriginUrl('http://evil.test.local/upgrade')).toBe('');
  });

  it('handleEntitlementStatus with unsafe redirect_url shows lock instead of navigating', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true });
    const mod = await loadModule('static/js/global-errors.js');
    const originalHref = window.location.href;
    const response = { status: 403, clone: () => response, json: () => Promise.resolve({ redirect_url: 'javascript:alert(1)', message: 'locked' }) };
    mod.handleEntitlementStatus(response);
    await new Promise(r => setTimeout(r, 30));
    expect(window.location.href).toBe(originalHref);
    expect(document.querySelector('.entitlement-lock-overlay')).not.toBeNull();
  });

  it('handleEntitlementStatus with same-origin redirect navigates', async () => {
    const mod = await loadModule('static/js/global-errors.js');
    const response = { status: 402, clone: () => response, json: () => Promise.resolve({ redirect_url: '/upgrade' }) };
    mod.handleEntitlementStatus(response);
    await new Promise(r => setTimeout(r, 30));
    expect(window.location.href).toContain('/upgrade');
  });

  it('entitlement lock with unsafe upgrade_url renders dismiss button, not a link', async () => {
    const mod = await loadModule('static/js/global-errors.js');
    mod.showEntitlementLock({ upgrade_url: 'javascript:alert(1)', message: 'msg' });
    expect(document.querySelector('.entitlement-lock-overlay a')).toBeNull();
    expect(document.querySelector('[data-dismiss-lock]')).not.toBeNull();
  });

  it('entitlement lock with same-origin upgrade_url renders a safe link', async () => {
    const mod = await loadModule('static/js/global-errors.js');
    mod.showEntitlementLock({ upgrade_url: '/upgrade-plan', message: 'msg' });
    const link = document.querySelector('.entitlement-lock-overlay a');
    expect(link).not.toBeNull();
    expect(link.getAttribute('href')).toBe('/upgrade-plan');
  });
});
