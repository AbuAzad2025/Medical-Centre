import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';


function blobText(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(blob);
  });
}

beforeEach(() => {
  document.body.innerHTML = `
    <div class="modal" id="changesModal"><pre id="changes-content"></pre></div>
    <div class="modal" id="detailsModal"><pre id="details-content"></pre></div>
  `;
  window.__M = [];
  window.escHtml = (s) => String(s || '');
  window.__M0__ = [
    { timestamp: '2026-11-01T09:00', user: { full_name: 'admin' }, action: 'login', entity_type: 'user', description: 'login', status: 'SUCCESS', target_model: 'User', target_id: 7, ip_address: '10.0.0.1', request_id: 'req-1' },
  ];
  window.API_ROUTES = {};
  window.location = { reload: vi.fn() };
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.bootstrap = {
    Modal: vi.fn().mockImplementation(() => ({ show: vi.fn(), hide: vi.fn() })),
  };
  global.URL.createObjectURL = vi.fn(() => 'blob:x');
  global.URL.revokeObjectURL = vi.fn();
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe('super_admin/audit_trail.js', () => {
  it('refreshAuditLogs reloads the page', async () => {
    const mod = await loadModule('static/js/pages/super_admin/audit_trail.js');
    mod.refreshAuditLogs();
    expect(window.location.reload).toHaveBeenCalled();
  });

  it('exportAuditLogs() exports the real __M0__ array as CSV', async () => {
    const mod = await loadModule('static/js/pages/super_admin/audit_trail.js');
    expect(mod.exportAuditLogs()).toBe('csv');
    expect(global.URL.createObjectURL).toHaveBeenCalled();
    const blob = global.URL.createObjectURL.mock.calls[0][0];
    expect(blob.type).toContain('text/csv');
  });

  it('exportAuditLogs(json) exports real JSON payload', async () => {
    const mod = await loadModule('static/js/pages/super_admin/audit_trail.js');
    expect(mod.exportAuditLogs('json')).toBe('json');
    const blob = global.URL.createObjectURL.mock.calls[0][0];
    expect(blob.type).toContain('application/json');
  });

  it('exportAuditLogs with empty payload still produces a file', async () => {
    window.__M0__ = undefined;
    const mod = await loadModule('static/js/pages/super_admin/audit_trail.js');
    expect(() => mod.exportAuditLogs('csv')).not.toThrow();
  });

  it('CSV cells with quotes and commas are escaped', async () => {
    window.__M0__ = [{ timestamp: '2026-11-08', actor: { full_name: 'Ali, "The Boss"' }, action: 'update', entity_type: 'Patient' }];
    const mod = await loadModule('static/js/pages/super_admin/audit_trail.js');
    mod.exportAuditLogs('csv');
    const blob = global.URL.createObjectURL.mock.calls[0][0];
    const text = await blobText(blob);
    expect(text).toContain('"Ali, ""The Boss"""');
  });

  it('CSV formula injection is neutralised with a leading quote', async () => {
    window.__M0__ = [{ timestamp: '=1+1', user: { full_name: 'x' }, action: 'login' }];
    const mod = await loadModule('static/js/pages/super_admin/audit_trail.js');
    mod.exportAuditLogs('csv');
    const blob = global.URL.createObjectURL.mock.calls[0][0];
    const text = await blobText(blob);
    expect(text).toContain('"\u0027=1+1"');
  });

  it('showChangesModal renders the payload into the changes pre element', async () => {
    const mod = await loadModule('static/js/pages/super_admin/audit_trail.js');
    mod.showChangesModal({ before: 1, after: 2 });
    expect(document.getElementById('changes-content').textContent).toContain('"before": 1');
    expect(window.bootstrap.Modal).toHaveBeenCalled();
  });

  it('showChangesModal with a string payload passes it through', async () => {
    const mod = await loadModule('static/js/pages/super_admin/audit_trail.js');
    mod.showChangesModal('raw text');
    expect(document.getElementById('changes-content').textContent).toBe('raw text');
  });

  it('showLogDetails renders the log JSON into the details pre element', async () => {
    const mod = await loadModule('static/js/pages/super_admin/audit_trail.js');
    mod.showLogDetails({ id: 5, action: 'login' });
    expect(document.getElementById('details-content').textContent).toContain('"id": 5');
  });

  it('exportAllLogs delegates to exportAuditLogs with csv format', async () => {
    const mod = await loadModule('static/js/pages/super_admin/audit_trail.js');
    expect(mod.exportAllLogs()).toBe('csv');
  });

  it('missing modal elements do not crash the modal helpers', async () => {
    document.body.innerHTML = '';
    const mod = await loadModule('static/js/pages/super_admin/audit_trail.js');
    expect(() => mod.showChangesModal({ a: 1 })).not.toThrow();
    expect(() => mod.showLogDetails({ b: 2 })).not.toThrow();
  });
});
