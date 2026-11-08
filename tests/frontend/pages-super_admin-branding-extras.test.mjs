import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <meta name="csrf-token" content="test-csrf">
    <form id="brandingForm" action="/branding/save">
      <input name="csrf_token" value="test-csrf">
      <input name="primary_color" id="primary_color" value="#000000">
      <input name="secondary_color" id="secondary_color" value="#111111">
      <input name="accent_color" id="accent_color" value="#222222">
      <input name="logo_file" id="logo_file" type="file">
    </form>
    <div id="primary-preview"></div>
    <div id="secondary-preview"></div>
    <div id="accent-preview"></div>
    <div id="printPreviewFrame" src="/old"></div>
    <div id="docTypeTabs">
      <a class="nav-link active" data-doc-type="invoice" href="#">Invoice</a>
      <a class="nav-link" data-doc-type="prescription" href="#">Prescription</a>
    </div>
    <div class="doc-fields" data-doc="invoice">Invoice fields</div>
    <div class="doc-fields" data-doc="prescription">Prescription fields</div>
    <div class="logo-preview"></div>
    <div class="theme-card"></div>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M = [];
  window.escHtml = (s) => String(s ?? '');
  window.__M0__ = '/api/branding/save';
  window.__M1__ = '/api/branding/print-preview';
  window.__M2__ = '/api/branding/theme';
  window.__CSRF__ = 'csrf-token-value';
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.bootstrap = { Collapse: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn() })) }, Modal: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn(), hide: vi.fn() })) } };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, colors: { primary_color: '#112233', secondary_color: '#445566', accent_color: '#778899' } }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('branding.js saveBranding fallback arms', () => {
  it('without any csrf elements the header is omitted', async () => {
    document.querySelector('#brandingForm input[name="csrf_token"]').remove();
    document.querySelector('meta[name="csrf-token"]').remove();
    const mod = await loadModule('static/js/pages/super_admin/branding.js');
    mod.saveBranding();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBeUndefined();
  });

  it('meta csrf is used when the form has none', async () => {
    document.querySelector('#brandingForm input[name="csrf_token"]').remove();
    const mod = await loadModule('static/js/pages/super_admin/branding.js');
    mod.saveBranding();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBe('test-csrf');
  });

  it('non-ok response triggers the catch fallback to form.submit', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/super_admin/branding.js');
    const form = document.getElementById('brandingForm');
    form.submit = vi.fn();
    mod.saveBranding();
    await new Promise(r => setTimeout(r, 30));
    expect(form.submit).toHaveBeenCalled();
  });

  it('server failure without an error key shows the default text', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    const mod = await loadModule('static/js/pages/super_admin/branding.js');
    mod.saveBranding();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].text).toBe('حدث خطأ في حفظ الإعدادات');
  });
});

describe('branding.js selectTheme fallback arms', () => {
  it('without __CSRF__ the body gets an empty token and no header', async () => {
    delete window.__CSRF__;
    const mod = await loadModule('static/js/pages/super_admin/branding.js');
    mod.selectTheme('9');
    await new Promise(r => setTimeout(r, 30));
    const call = global.fetch.mock.calls[0];
    expect(call[1].headers['X-CSRFToken']).toBeUndefined();
    const body = call[1].body;
    expect(body.get('csrf_token')).toBe('');
  });

  it('fetch !ok throws into the generic error branch', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/super_admin/branding.js');
    mod.selectTheme('9');
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].text).toBe('تعذر تطبيق الثيم');
  });

  it('server failure without an error key shows the default text', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    const mod = await loadModule('static/js/pages/super_admin/branding.js');
    mod.selectTheme('9');
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].text).toBe('تعذر تطبيق الثيم');
  });

  it('success with an empty colors object does not touch the inputs', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, colors: {} }) });
    const mod = await loadModule('static/js/pages/super_admin/branding.js');
    mod.selectTheme('9');
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('primary_color').value).toBe('#000000');
    expect(document.getElementById('primary-preview').style.backgroundColor).toBe('');
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('success');
  });

  it('success with partial colors updates only provided keys', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, colors: { secondary_color: '#abcdef' } }) });
    const mod = await loadModule('static/js/pages/super_admin/branding.js');
    mod.selectTheme('9');
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('secondary_color').value).toBe('#abcdef');
    expect(document.getElementById('primary_color').value).toBe('#000000');
  });

  it('success with missing preview elements does not crash', async () => {
    document.getElementById('primary-preview').remove();
    document.getElementById('secondary-preview').remove();
    document.getElementById('accent-preview').remove();
    const mod = await loadModule('static/js/pages/super_admin/branding.js');
    expect(() => mod.selectTheme('9')).not.toThrow();
    await new Promise(r => setTimeout(r, 30));
  });
});

describe('branding.js preview branches', () => {
  it('reloadPrintPreview without an active tab defaults to invoice', async () => {
    document.querySelector('#docTypeTabs .nav-link.active').classList.remove('active');
    const mod = await loadModule('static/js/pages/super_admin/branding.js');
    mod.reloadPrintPreview();
    expect(document.getElementById('printPreviewFrame').src).toContain('doc_type=invoice');
  });

  it('reloadPrintPreview does nothing with no print frame', async () => {
    document.getElementById('printPreviewFrame').remove();
    const mod = await loadModule('static/js/pages/super_admin/branding.js');
    expect(() => mod.reloadPrintPreview()).not.toThrow();
  });

  it('secondary_color change updates its preview', async () => {
    await loadModule('static/js/pages/super_admin/branding.js');
    const input = document.getElementById('secondary_color');
    input.value = '#123456';
    input.dispatchEvent(new Event('change'));
    expect(document.getElementById('secondary-preview').style.backgroundColor).toBe('rgb(18, 52, 86)');
  });

  it('color change with missing preview element does not crash', async () => {
    document.getElementById('secondary-preview').remove();
    await loadModule('static/js/pages/super_admin/branding.js');
    const input = document.getElementById('secondary_color');
    input.value = '#123456';
    expect(() => input.dispatchEvent(new Event('change'))).not.toThrow();
  });

  it('logo_file change without a file does nothing', async () => {
    await loadModule('static/js/pages/super_admin/branding.js');
    const input = document.getElementById('logo_file');
    input.dispatchEvent(new Event('change'));
    expect(document.querySelector('.logo-preview').innerHTML).toBe('');
  });
});
