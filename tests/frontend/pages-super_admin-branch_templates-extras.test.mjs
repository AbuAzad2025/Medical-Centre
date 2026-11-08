import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <meta name="csrf-token" content="test-csrf">
    <textarea id="templatesJson">[]</textarea>
    <button id="saveTemplates">Save</button>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M = ['preset'];
  window.__M0__ = '/api/branch-templates';
  window.escHtml = (s) => String(s ?? '');
  window.alert = vi.fn();
  window.showToast = vi.fn();
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('branch_templates.js fallback arms', () => {
  it('empty textarea JSON parses as empty array', async () => {
    document.getElementById('templatesJson').value = '';
    await loadModule('static/js/pages/super_admin/branch_templates.js');
    document.getElementById('saveTemplates').click();
    await new Promise(r => setTimeout(r, 30));
    expect(JSON.parse(global.fetch.mock.calls[0][1].body).items).toEqual([]);
  });

  it('save without csrf meta sends no token header', async () => {
    document.querySelector('meta[name="csrf-token"]').remove();
    await loadModule('static/js/pages/super_admin/branch_templates.js');
    document.getElementById('saveTemplates').click();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBeUndefined();
  });

  it('json parse failure in the response still alerts success path gracefully', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.reject(new Error('bad json')) });
    await loadModule('static/js/pages/super_admin/branch_templates.js');
    document.getElementById('saveTemplates').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.alert).toHaveBeenCalled();
  });

  it('module loads with no __M preset as well', async () => {
    delete window.__M;
    await expect(loadModule('static/js/pages/super_admin/branch_templates.js')).resolves.toBeDefined();
  });
});
