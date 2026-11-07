import { describe, it, expect, beforeEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = `<div id="auditContainer"></div><table id="auditTable"><tbody></tbody></table>`;
  window.__M = [];
  window.API_ROUTES = {};
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ logs: [] }) });
  await loadModule('static/js/pages/super_admin/audit_trail.js');
});

describe('super_admin/audit_trail.js', () => {
  it('loads without error', () => {
    expect(true).toBe(true);
  });
});