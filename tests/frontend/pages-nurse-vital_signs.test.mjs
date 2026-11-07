import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <form id="vitalSignsForm" action="/nurse/vital-signs">
      <input name="csrf_token" value="test-csrf">
      <input name="blood_pressure" value="120/80">
      <input name="heart_rate" value="80">
      <input name="temperature" value="37.0">
      <input name="oxygen_saturation" value="98">
      <input name="respiratory_rate" value="18">
      <button type="submit">Save</button>
    </form>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M = [];
  window.escHtml = (s) => String(s || '');
  window.API_ROUTES = {};
  window.alert = vi.fn();
  window.location = { reload: vi.fn() };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('nurse/vital_signs.js', () => {
  it('submit success reloads the page', async () => {
    await loadModule('static/js/pages/nurse/vital_signs.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const form = document.getElementById('vitalSignsForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/nurse/vital-signs'), expect.objectContaining({ method: 'POST' }));
    expect(window.location.reload).toHaveBeenCalled();
  });

  it('submit failure shows alert and re-enables button', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'invalid value' }) });
    await loadModule('static/js/pages/nurse/vital_signs.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const btn = document.querySelector('button[type="submit"]');
    const form = document.getElementById('vitalSignsForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(window.alert).toHaveBeenCalledWith('invalid value');
    expect(btn.disabled).toBe(false);
  });

  it('submit with missing message shows fallback alert', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    await loadModule('static/js/pages/nurse/vital_signs.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const form = document.getElementById('vitalSignsForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(window.alert).toHaveBeenCalled();
  });

  it('submit fetch failure shows generic alert and re-enables', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    await loadModule('static/js/pages/nurse/vital_signs.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const btn = document.querySelector('button[type="submit"]');
    const form = document.getElementById('vitalSignsForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(window.alert).toHaveBeenCalled();
    expect(btn.disabled).toBe(false);
  });

  it('submit with non-ok response throws and shows alert', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    await loadModule('static/js/pages/nurse/vital_signs.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const form = document.getElementById('vitalSignsForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(window.alert).toHaveBeenCalled();
  });

  it('submit disables the button during request', async () => {
    global.fetch = vi.fn().mockImplementation(() => new Promise(() => {}));
    await loadModule('static/js/pages/nurse/vital_signs.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const btn = document.querySelector('button[type="submit"]');
    const form = document.getElementById('vitalSignsForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    expect(btn.disabled).toBe(true);
  });

  it('DOMContentLoaded with no form does nothing', async () => {
    document.body.innerHTML = '';
    await loadModule('static/js/pages/nurse/vital_signs.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(document.getElementById('vitalSignsForm')).toBeNull();
  });
});