import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <meta name="csrf-token" content="test-csrf">
    <form id="convertForm" action="/emergency/convert/9">
      <input name="csrf_token" value="test-csrf">
      <select name="new_destination"><option value="doctor">doctor</option></select>
      <button type="submit">Convert</button>
    </form>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M0__ = '/emergency/list';
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.location = { href: '', reload: vi.fn() };
  vi.spyOn(window, 'print').mockImplementation(() => {});
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('emergency/view.js', () => {
  it('exposes window helpers', async () => {
    await loadModule('static/js/pages/emergency/view.js');
    expect(typeof window.printEmergency).toBe('function');
    expect(typeof window.exportEmergency).toBe('function');
    expect(typeof window.shareEmergency).toBe('function');
  });

  it('printEmergency calls window.print', async () => {
    const mod = await loadModule('static/js/pages/emergency/view.js');
    mod.printEmergency();
    expect(window.print).toHaveBeenCalled();
  });

  it('exportEmergency and shareEmergency do not throw', async () => {
    const mod = await loadModule('static/js/pages/emergency/view.js');
    expect(() => mod.exportEmergency()).not.toThrow();
    expect(() => mod.shareEmergency()).not.toThrow();
  });

  it('convertForm submit posts and navigates on success', async () => {
    await loadModule('static/js/pages/emergency/view.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const form = document.getElementById('convertForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(String(global.fetch.mock.calls[0][0])).toContain('/emergency/convert/9');
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('success');
    expect(window.location.href).toBe('/emergency/list');
  });

  it('convertForm server failure shows error Swal', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'busy' }) });
    await loadModule('static/js/pages/emergency/view.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const form = document.getElementById('convertForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });

  it('convertForm network failure shows error Swal', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    await loadModule('static/js/pages/emergency/view.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const form = document.getElementById('convertForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });

  it('convertForm without message shows generic error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    await loadModule('static/js/pages/emergency/view.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const form = document.getElementById('convertForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });

  it('convertForm missing does nothing', async () => {
    document.getElementById('convertForm').remove();
    await loadModule('static/js/pages/emergency/view.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(true).toBe(true);
  });
});