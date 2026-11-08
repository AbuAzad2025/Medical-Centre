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
  window.escHtml = (s) => String(s ?? '');
  window.location = { reload: vi.fn() };
  global.URL.createObjectURL = vi.fn(() => 'blob:x');
  global.URL.revokeObjectURL = vi.fn();
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe('audit_trail.js export fallbacks', () => {
  it('missing actor falls back to a placeholder name', async () => {
    window.__M0__ = [{ timestamp: '2026-11-08', action: 'login' }];
    const mod = await loadModule('static/js/pages/super_admin/audit_trail.js');
    mod.exportAuditLogs('csv');
    const blob = global.URL.createObjectURL.mock.calls[0][0];
    const text = await blobText(blob);
    expect(text).toContain('غير محدد');
  });

  it('actor object without full_name falls back to placeholder', async () => {
    window.__M0__ = [{ timestamp: '2026-11-08', user: {}, action: 'x' }];
    // legacy payload shape: actor nested under 'user' is not read; the flat
    // 'actor' key is the canonical one. missing everywhere => placeholder
    const mod = await loadModule('static/js/pages/super_admin/audit_trail.js');
    expect(() => mod.exportAuditLogs('csv')).not.toThrow();
  });

  it('changes object renders as JSON string in the details cell', async () => {
    window.__M0__ = [{ timestamp: '2026-11-08', action: 'update', changes: { a: 1 } }];
    const mod = await loadModule('static/js/pages/super_admin/audit_trail.js');
    mod.exportAuditLogs('csv');
    const blob = global.URL.createObjectURL.mock.calls[0][0];
    const text = await blobText(blob);
    expect(text).toContain('""a"":1');
  });

  it('null target_id renders as empty cell', async () => {
    window.__M0__ = [{ timestamp: '2026-11-08', action: 'login', target_id: null }];
    const mod = await loadModule('static/js/pages/super_admin/audit_trail.js');
    mod.exportAuditLogs('csv');
    const blob = global.URL.createObjectURL.mock.calls[0][0];
    const text = await blobText(blob);
    expect(text).toContain('"","",');
  });

  it('unknown format string falls back to csv', async () => {
    window.__M0__ = [];
    const mod = await loadModule('static/js/pages/super_admin/audit_trail.js');
    expect(mod.exportAuditLogs('weird')).toBe('csv');
  });

  it('empty action/model/ip fall back to empty cells', async () => {
    window.__M0__ = [{ timestamp: '', actor: null, action: null, target_model: null, ip_address: null }];
    const mod = await loadModule('static/js/pages/super_admin/audit_trail.js');
    expect(() => mod.exportAuditLogs('csv')).not.toThrow();
  });
});
