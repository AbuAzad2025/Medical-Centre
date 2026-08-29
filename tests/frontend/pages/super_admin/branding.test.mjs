import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <div id="app"></div>
    <form id="brandingForm">
      <input name="primary_color" value="#0000ff" />
    </form>
    <input type="color" id="primary_color" value="#0000ff" />
    <input type="color" id="secondary_color" value="#ffffff" />
    <input type="color" id="accent_color" value="#ff0000" />
    <div id="primary-preview" style="background-color: #0000ff"></div>
    <div id="secondary-preview" style="background-color: #ffffff"></div>
    <div id="accent-preview" style="background-color: #ff0000"></div>
    <input type="file" id="logo_file" />
    <div class="logo-preview"></div>
    <div id="printPreviewFrame"></div>
    <div id="docTypeTabs">
      <a class="nav-link active" data-doc-type="invoice">Invoice</a>
      <a class="nav-link" data-doc-type="receipt">Receipt</a>
    </div>
    <div class="doc-fields" data-doc="invoice"></div>
    <div class="doc-fields" data-doc="receipt"></div>
    <div class="theme-card"></div>
    <meta name="csrf-token" content="test-token" />
  `;
  window.__M0__ = '/api/test/branding-save';
  window.__M1__ = '/api/test/preview';
  window.__M2__ = '/api/test/theme';
  window.__CSRF__ = 'test-token';
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
});

describe('super_admin/branding.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/super_admin/branding.js');
  });

  test('saveBranding is a function', async () => {
    await loadScript('static/js/pages/super_admin/branding.js');
    expect(typeof saveBranding).toBe('function');
  });

  test('resetBranding is a function', async () => {
    await loadScript('static/js/pages/super_admin/branding.js');
    expect(typeof resetBranding).toBe('function');
  });

  test('selectTheme is a function', async () => {
    await loadScript('static/js/pages/super_admin/branding.js');
    expect(typeof selectTheme).toBe('function');
  });

  test('showDocFields is a function', async () => {
    await loadScript('static/js/pages/super_admin/branding.js');
    expect(typeof showDocFields).toBe('function');
  });

  test('showDocFields toggles visibility', async () => {
    await loadScript('static/js/pages/super_admin/branding.js');
    showDocFields('invoice');
    const invoiceEl = document.querySelector('.doc-fields[data-doc="invoice"]');
    const receiptEl = document.querySelector('.doc-fields[data-doc="receipt"]');
    expect(invoiceEl.classList.contains('d-none')).toBe(false);
    expect(receiptEl.classList.contains('d-none')).toBe(true);
  });

  test('primary color preview updates on change', async () => {
    await loadScript('static/js/pages/super_admin/branding.js');
    const input = document.getElementById('primary_color');
    input.value = '#ff0000';
    input.dispatchEvent(new Event('change'));
    expect(document.getElementById('primary-preview').style.backgroundColor).toBe('rgb(255, 0, 0)');
  });
});
