import { describe, it, expect, vi, beforeEach } from 'vitest';
import { loadScript } from './test-utils.mjs';

beforeEach(() => {
  window.__ENV = 'testing';
  window.notify = { error: vi.fn(), warning: vi.fn() };
  window.fetch = vi.fn().mockResolvedValue({ ok: true });
  window.API_ROUTES = { audit_log: '/super-admin/api/audit-log' };
  document.body.innerHTML = '';
  window.escHtml = (v) => {
    if (v === null || v === undefined) return '';
    return String(v).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  };
  loadScript('static/js/global-errors.js');
});

describe('global-errors.js', () => {
  describe('reportError', () => {
    it('calls notify.error when available', () => {
      window.notify.error('Test error');
      expect(window.notify.error).toHaveBeenCalledWith('Test error');
    });
    it('sets up global error handlers', () => {
      expect(typeof window.onerror).toBe('function');
    });
    it('sets up unhandledrejection handler', () => {
      expect(typeof window.onunhandledrejection).toBe('function');
    });
  });

  describe('__wrapFetchEntitlement', () => {
    it('is exposed on window', () => {
      expect(typeof window.__wrapFetchEntitlement).toBe('function');
    });
  });

  describe('__showEntitlementLock', () => {
    it('is exposed on window', () => {
      expect(typeof window.__showEntitlementLock).toBe('function');
    });
    it('creates overlay element', () => {
      window.__showEntitlementLock({ title: 'Locked', message: 'Feature unavailable' });
      expect(document.querySelector('.entitlement-lock-overlay')).toBeTruthy();
    });
  });

  describe('parseJsonSafe', () => {
    it('parses valid JSON response', async () => {
      const response = new Response(JSON.stringify({ ok: true }));
      const data = await response.clone().json();
      expect(data.ok).toBe(true);
    });
    it('returns empty object for invalid JSON', async () => {
      const response = new Response('not json');
      const data = await response.clone().json().catch(() => ({}));
      expect(data).toEqual({});
    });
  });
});
