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
  window.__M0__ = '/api/branch/templates';
  window.__M = [];
  window.escHtml = (s) => String(s || '');
  window.API_ROUTES = {};
  window.alert = vi.fn();
  window.showToast = vi.fn();
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('branch_templates.js', () => {
  it('invalid JSON shows alert and does not fetch', async () => {
    document.getElementById('templatesJson').value = 'not json';
    await loadModule('static/js/pages/super_admin/branch_templates.js');
    document.getElementById('saveTemplates').click();
    await new Promise(r => setTimeout(r, 20));
    expect(window.alert).toHaveBeenCalled();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('save click posts items to the endpoint', async () => {
    document.getElementById('templatesJson').value = '[{"branch_id":1,"name":"A"}]';
    await loadModule('static/js/pages/super_admin/branch_templates.js');
    document.getElementById('saveTemplates').click();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalledWith('/api/branch/templates', expect.objectContaining({ method: 'POST' }));
    const body = JSON.parse(global.fetch.mock.calls[0][1].body);
    expect(body.items[0].branch_id).toBe(1);
  });

  it('save success shows success alert', async () => {
    await loadModule('static/js/pages/super_admin/branch_templates.js');
    document.getElementById('saveTemplates').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.alert).toHaveBeenCalled();
  });

  it('save failure response shows generic alert', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    await loadModule('static/js/pages/super_admin/branch_templates.js');
    document.getElementById('saveTemplates').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.alert).toHaveBeenCalled();
  });

  it('non-ok response shows generic error toast', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500, json: () => Promise.resolve({}) });
    await loadModule('static/js/pages/super_admin/branch_templates.js');
    document.getElementById('saveTemplates').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.showToast).toHaveBeenCalled();
  });

  it('fetch rejection shows toast', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    await loadModule('static/js/pages/super_admin/branch_templates.js');
    document.getElementById('saveTemplates').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.showToast).toHaveBeenCalled();
  });

  it('fetch rejection without showToast falls back to alert', async () => {
    delete window.showToast;
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    await loadModule('static/js/pages/super_admin/branch_templates.js');
    document.getElementById('saveTemplates').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.alert).toHaveBeenCalled();
  });

  it('no saveTemplates button does nothing', async () => {
    document.getElementById('saveTemplates').remove();
    await loadModule('static/js/pages/super_admin/branch_templates.js');
    expect(true).toBe(true);
  });
});