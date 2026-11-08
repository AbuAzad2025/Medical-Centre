import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadModule } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <div class="modal" id="changesModal"><pre id="changes-content"></pre></div>
    <div class="modal" id="detailsModal"><pre id="details-content"></pre></div>
  `;
  window.__M0__ = [{ timestamp: '2026-01-01', user: { full_name: 'Admin' }, action: 'login', entity_type: 'user', description: 'Login', status: 'success' }];
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  global.URL.createObjectURL = vi.fn(() => 'blob:x');
  global.URL.revokeObjectURL = vi.fn();
});

describe('super_admin/audit_trail.js', () => {
  test('loads without critical errors', async () => {
    await loadModule('static/js/pages/super_admin/audit_trail.js');
  });

  test('showChangesModal is a function', async () => {
    await loadModule('static/js/pages/super_admin/audit_trail.js');
    expect(typeof showChangesModal).toBe('function');
  });

  test('exportAuditLogs is a function', async () => {
    await loadModule('static/js/pages/super_admin/audit_trail.js');
    expect(typeof exportAuditLogs).toBe('function');
  });

  test('showChangesModal accepts an inline-passed object like the row buttons do', async () => {
    await loadModule('static/js/pages/super_admin/audit_trail.js');
    showChangesModal({ before: 1, after: 2 });
    expect(document.getElementById('changes-content').textContent).toContain('"before": 1');
  });

  test('showLogDetails renders JSON for an inline-passed object', async () => {
    await loadModule('static/js/pages/super_admin/audit_trail.js');
    showLogDetails({ id: 9, action: 'login' });
    expect(document.getElementById('details-content').textContent).toContain('"id": 9');
  });
});
