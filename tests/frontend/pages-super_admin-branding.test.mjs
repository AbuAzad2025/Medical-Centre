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
    <div id="printPreviewFrame"></div>
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
  window.escHtml = (s) => String(s || '');
  window.__M0__ = '/api/branding/save';
  window.__M1__ = '/api/branding/print-preview';
  window.__M2__ = '/api/branding/theme';
  window.__CSRF__ = 'csrf-token-value';
  window.API_ROUTES = {};
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.bootstrap = { Collapse: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn() })) }, Modal: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn(), hide: vi.fn() })) } };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, colors: { primary_color: '#112233', secondary_color: '#445566', accent_color: '#778899' } }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('super_admin/branding.js', () => {
  it('saveBranding posts form and shows success', async () => {
    const mod = await loadModule('static/js/pages/super_admin/branding.js');
    mod.saveBranding();
    await new Promise(r => setTimeout(r, 30));
    expect(String(global.fetch.mock.calls[0][0])).toBe('/api/branding/save');
    expect(global.fetch.mock.calls[0][1].method).toBe('POST');
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('saveBranding failure falls back to form.submit', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/super_admin/branding.js');
    const form = document.getElementById('brandingForm');
    form.submit = vi.fn();
    mod.saveBranding();
    await new Promise(r => setTimeout(r, 30));
    expect(form.submit).toHaveBeenCalled();
  });

  it('saveBranding server error shows error Swal', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, error: 'bad input' }) });
    const mod = await loadModule('static/js/pages/super_admin/branding.js');
    mod.saveBranding();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });

  it('resetBranding confirm shows warning and reloads', async () => {
    const mod = await loadModule('static/js/pages/super_admin/branding.js');
    await mod.resetBranding();
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('warning');
  });

  it('resetBranding cancel does not reload', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/super_admin/branding.js');
    await mod.resetBranding();
    expect(window.Swal.fire).toHaveBeenCalledTimes(1);
  });

  it('selectTheme posts csrf and applies colors on success', async () => {
    const mod = await loadModule('static/js/pages/super_admin/branding.js');
    mod.selectTheme('9');
    await new Promise(r => setTimeout(r, 30));
    expect(String(global.fetch.mock.calls[0][0])).toBe('/api/branding/theme/9');
    expect(document.getElementById('primary_color').value).toBe('#112233');
    expect(document.getElementById('secondary-preview').style.backgroundColor).toBe('rgb(68, 85, 102)');
  });

  it('selectTheme server error shows error Swal', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, error: 'nope' }) });
    const mod = await loadModule('static/js/pages/super_admin/branding.js');
    mod.selectTheme('9');
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });

  it('selectTheme fetch failure shows error Swal', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/super_admin/branding.js');
    mod.selectTheme('9');
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });

  it('reloadPrintPreview uses active doc type', async () => {
    const mod = await loadModule('static/js/pages/super_admin/branding.js');
    mod.reloadPrintPreview();
    const frame = document.getElementById('printPreviewFrame');
    expect(frame.src).toContain('/api/branding/print-preview?doc_type=invoice');
  });

  it('reloadPrintPreview does nothing without frame', async () => {
    document.body.innerHTML = '';
    const mod = await loadModule('static/js/pages/super_admin/branding.js');
    expect(() => mod.reloadPrintPreview()).not.toThrow();
  });

  it('showDocFields toggles visibility', async () => {
    const mod = await loadModule('static/js/pages/super_admin/branding.js');
    mod.showDocFields('prescription');
    const inv = document.querySelector('[data-doc="invoice"]');
    const presc = document.querySelector('[data-doc="prescription"]');
    expect(inv.classList.contains('d-none')).toBe(true);
    expect(presc.classList.contains('d-none')).toBe(false);
  });

  it('primary_color change updates preview', async () => {
    await loadModule('static/js/pages/super_admin/branding.js');
    const input = document.getElementById('primary_color');
    input.value = '#ff0000';
    input.dispatchEvent(new Event('change'));
    expect(document.getElementById('primary-preview').style.backgroundColor).toBe('rgb(255, 0, 0)');
  });

  it('accent_color change updates preview', async () => {
    await loadModule('static/js/pages/super_admin/branding.js');
    const input = document.getElementById('accent_color');
    input.value = '#00ff00';
    input.dispatchEvent(new Event('change'));
    expect(document.getElementById('accent-preview').style.backgroundColor).toBe('rgb(0, 255, 0)');
  });

  it('DOMContentLoaded activates first doc type and wires clicks', async () => {
    await loadModule('static/js/pages/super_admin/branding.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(document.querySelector('.doc-fields[data-doc="invoice"]').classList.contains('d-none')).toBe(false);
    document.querySelector('[data-doc-type="prescription"]').click();
    expect(document.querySelector('.doc-fields[data-doc="prescription"]').classList.contains('d-none')).toBe(false);
    expect(document.getElementById('printPreviewFrame').src).toContain('doc_type=prescription');
  });

  it('theme card hover transform toggles', async () => {
    await loadModule('static/js/pages/super_admin/branding.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const card = document.querySelector('.theme-card');
    card.dispatchEvent(new MouseEvent('mouseenter'));
    expect(card.style.transform).toBe('translateY(-2px)');
    card.dispatchEvent(new MouseEvent('mouseleave'));
    expect(card.style.transform).toBe('translateY(0)');
  });

  it('logo_file change renders logo preview via FileReader', async () => {
    await loadModule('static/js/pages/super_admin/branding.js');
    const input = document.getElementById('logo_file');
    const file = new File(['img'], 'logo.png', { type: 'image/png' });
    Object.defineProperty(input, 'files', { value: [file], configurable: true });
    input.dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 30));
    expect(document.querySelector('.logo-preview').innerHTML).toContain('<img');
  });
});