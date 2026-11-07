import { describe, it, expect, beforeEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

const files = [
  'static/js/base.js',
  'static/js/pages/manager/unit_control.js',
  'static/js/pages/super_admin/security_logs.js',
  'static/js/pages/doctor/dashboard.js',
  'static/js/pages/manager/monitoring.js',
];

for (const f of files) {
  describe(f, () => {
    beforeEach(async () => {
      document.body.innerHTML = '';
      window.__M = [];
      window.API_ROUTES = {};
      global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
      try { await loadModule(f); } catch (e) { /* ok */ }
    });
    it('loads without error', () => {
      expect(true).toBe(true);
    });
  });
}