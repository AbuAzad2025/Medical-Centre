import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <meta name="csrf-token" content="csrf-status">
    <input id="barcodeInput" value="1234567890">
    <select id="scanAction"><option value="REGISTER">REGISTER</option></select>
    <div id="scanResult"></div>
    <button id="registerBtn">Register device</button>
    <div id="registerResult"></div>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M0__ = '/biometric/api/register';
  window.__M1__ = 'csrf-status';
  window.escHtml = (s) => String(s ?? '');
  window.showToast = vi.fn();
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, entity_type: 'patient', entity_id: 42 }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('barcode/scan.js', () => {
  it('submitScan success renders success alert with entity', async () => {
    const mod = await loadModule('static/js/pages/barcode/scan.js');
    mod.submitScan();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
    expect(document.getElementById('scanResult').innerHTML).toContain('patient #42');
  });

  it('submitScan failure renders danger alert with message', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'barcode not found' }) });
    const mod = await loadModule('static/js/pages/barcode/scan.js');
    mod.submitScan();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('scanResult').innerHTML).toContain('barcode not found');
  });

  it('submitScan fetch failure resolves without crashing', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/barcode/scan.js');
    expect(() => mod.submitScan()).not.toThrow();
    await new Promise(r => setTimeout(r, 30));
  });

  it('barcodeInput Enter keydown submits the scan', async () => {
    await loadModule('static/js/pages/barcode/scan.js');
    document.getElementById('barcodeInput').dispatchEvent(new KeyboardEvent('keypress', { key: 'Enter', bubbles: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
  });

  it('barcodeInput non-Enter key does not submit', async () => {
    await loadModule('static/js/pages/barcode/scan.js');
    document.getElementById('barcodeInput').dispatchEvent(new KeyboardEvent('keypress', { key: 'a', bubbles: true }));
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('exposes window.submitScan', async () => {
    await loadModule('static/js/pages/barcode/scan.js');
    expect(typeof window.submitScan).toBe('function');
  });
});

describe('biometric/status.js', () => {
  it('register click posts and shows success', async () => {
    await loadModule('static/js/pages/biometric/status.js');
    document.getElementById('registerBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(String(global.fetch.mock.calls[0][0])).toContain('/biometric/api/register');
    expect(global.fetch.mock.calls[0][1].method).toBe('POST');
    expect(document.getElementById('registerResult').innerHTML).toContain('alert-success');
  });

  it('register failure shows error and restores button', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('boom'));
    await loadModule('static/js/pages/biometric/status.js');
    const btn = document.getElementById('registerBtn');
    btn.click();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('registerResult').innerHTML).toContain('alert-danger');
    expect(btn.disabled).toBe(false);
  });

  it('register does not double-fire while disabled', async () => {
    global.fetch = vi.fn().mockImplementation(() => new Promise(() => {}));
    await loadModule('static/js/pages/biometric/status.js');
    const btn = document.getElementById('registerBtn');
    btn.click();
    btn.click();
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  it('register without showToast still completes without crashing', async () => {
    delete window.showToast;
    await loadModule('static/js/pages/biometric/status.js');
    document.getElementById('registerBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('registerResult').innerHTML).toContain('alert-success');
  });
});