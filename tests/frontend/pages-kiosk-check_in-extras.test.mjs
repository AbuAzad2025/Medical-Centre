import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom(withKeypad = true) {
  document.body.innerHTML = `
    <input id="nationalId">
    ${withKeypad ? '<div id="kioskKeypad"></div>' : ''}
    <button id="kioskSubmit" data-api-url="/custom/check-in">Submit</button>
    <div id="kioskResult" hidden></div>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M = [];
  window.escHtml = (s) => String(s ?? '');
  Object.defineProperty(navigator, 'vibrate', { value: vi.fn(), configurable: true });
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, queue_number: 'B-7', patient_name: 'سارة', message: 'تم تسجيل الدخول' }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('kiosk/check_in.js fallback arms', () => {
  it('uses the data-api-url endpoint when set', async () => {
    const mod = await loadModule('static/js/pages/kiosk/check_in.js');
    document.getElementById('nationalId').value = '12345';
    mod.doCheckIn();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch.mock.calls[0][0]).toBe('/custom/check-in');
  });

  it('falls back to the default endpoint when data-api-url is unset', async () => {
    document.getElementById('kioskSubmit').removeAttribute('data-api-url');
    const mod = await loadModule('static/js/pages/kiosk/check_in.js');
    document.getElementById('nationalId').value = '12345';
    mod.doCheckIn();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch.mock.calls[0][0]).toBe('/kiosk/api/check-in');
  });

  it('success with no message or name renders empty placeholders without crashing', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
    const mod = await loadModule('static/js/pages/kiosk/check_in.js');
    document.getElementById('nationalId').value = '12345';
    mod.doCheckIn();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('kioskResult').hidden).toBe(false);
  });

  it('success hides the result banner after 8 seconds', async () => {
    vi.useFakeTimers();
    const mod = await loadModule('static/js/pages/kiosk/check_in.js');
    document.getElementById('nationalId').value = '12345';
    mod.doCheckIn();
    await vi.advanceTimersByTimeAsync(30);
    expect(document.getElementById('kioskResult').hidden).toBe(false);
    await vi.advanceTimersByTimeAsync(8100);
    expect(document.getElementById('kioskResult').hidden).toBe(true);
    vi.useRealTimers();
  });

  it('navigator.vibrate absent does not throw on success', async () => {
    delete navigator.vibrate;
    const mod = await loadModule('static/js/pages/kiosk/check_in.js');
    document.getElementById('nationalId').value = '12345';
    expect(() => mod.doCheckIn()).not.toThrow();
    await new Promise(r => setTimeout(r, 30));
  });

  it('module loads without keypad elements', async () => {
    document.getElementById('kioskKeypad').remove();
    await expect(loadModule('static/js/pages/kiosk/check_in.js')).resolves.toBeDefined();
    expect(document.getElementById('kioskSubmit')).not.toBeNull();
  });

  it('response with non-JSON body falls into the catch branch', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.reject(new Error('bad json')) });
    const mod = await loadModule('static/js/pages/kiosk/check_in.js');
    document.getElementById('nationalId').value = '12345';
    mod.doCheckIn();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('kioskResult').className).toContain('kiosk-result--err');
  });
});
