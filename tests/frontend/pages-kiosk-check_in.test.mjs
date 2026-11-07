import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <input type="text" id="nationalId" value="">
    <div id="kioskKeypad"></div>
    <button id="kioskSubmit" data-api-url="/kiosk/api/check-in">Confirm</button>
    <div id="kioskResult" hidden></div>
  `;
}

beforeEach(() => {
  baseDom();
  window.navigator.vibrate = vi.fn();
  window.alert = vi.fn();
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, patient_name: 'Sara', message: 'welcome', queue_number: 'Q-10' }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('kiosk/check_in.js', () => {
  it('shows result when national id is empty', async () => {
    const mod = await loadModule('static/js/pages/kiosk/check_in.js');
    mod.doCheckIn();
    expect(document.getElementById('kioskResult').innerHTML).toBeTruthy();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('successful check-in shows queue number and clears input', async () => {
    const mod = await loadModule('static/js/pages/kiosk/check_in.js');
    document.getElementById('nationalId').value = '1234567890';
    mod.doCheckIn();
    await new Promise(r => setTimeout(r, 30));
    expect(window.navigator.vibrate).toHaveBeenCalledWith(10);
    expect(document.getElementById('kioskResult').innerHTML).toContain('Sara');
    expect(document.getElementById('kioskResult').innerHTML).toContain('Q-10');
    expect(document.getElementById('nationalId').value).toBe('');
    expect(document.getElementById('kioskSubmit').disabled).toBe(false);
  });

  it('successful check-in without queue number shows patient details', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, patient_name: 'Sara', message: 'ok' }) });
    const mod = await loadModule('static/js/pages/kiosk/check_in.js');
    document.getElementById('nationalId').value = '1';
    mod.doCheckIn();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('kioskResult').innerHTML).toContain('Sara');
  });

  it('failed check-in shows server message', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'not found' }) });
    const mod = await loadModule('static/js/pages/kiosk/check_in.js');
    document.getElementById('nationalId').value = '1';
    mod.doCheckIn();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('kioskResult').innerHTML).toContain('not found');
    expect(document.getElementById('kioskSubmit').disabled).toBe(false);
  });

  it('failed check-in without message shows generic message', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, json: () => Promise.resolve({}) });
    const mod = await loadModule('static/js/pages/kiosk/check_in.js');
    document.getElementById('nationalId').value = '1';
    mod.doCheckIn();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('kioskResult').innerHTML).toBeTruthy();
  });

  it('network failure shows generic error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/kiosk/check_in.js');
    document.getElementById('nationalId').value = '1';
    mod.doCheckIn();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('kioskResult').innerHTML).toBeTruthy();
    expect(document.getElementById('kioskSubmit').disabled).toBe(false);
  });

  it('kioskSubmit disabled during request', async () => {
    global.fetch = vi.fn().mockImplementation(() => new Promise(() => {}));
    const mod = await loadModule('static/js/pages/kiosk/check_in.js');
    document.getElementById('nationalId').value = '1';
    mod.doCheckIn();
    expect(document.getElementById('kioskSubmit').disabled).toBe(true);
  });

  it('showResult renders ok class for ok branch', async () => {
    const mod = await loadModule('static/js/pages/kiosk/check_in.js');
    mod.showResult(true, '<em>x</em>');
    const result = document.getElementById('kioskResult');
    expect(result.className).toContain('kiosk-result--ok');
    expect(result.hidden).toBe(false);
    expect(result.innerHTML).toBe('<em>x</em>');
  });

  it('showResult renders err class for failure', async () => {
    const mod = await loadModule('static/js/pages/kiosk/check_in.js');
    mod.showResult(false, '<em>y</em>');
    expect(document.getElementById('kioskResult').className).toContain('kiosk-result--err');
  });

  it('keypad renders 12 keys and typing digits appends', async () => {
    await loadModule('static/js/pages/kiosk/check_in.js');
    const keys = [...document.querySelectorAll('.kiosk-key')];
    expect(keys.length).toBe(12);
    const key3 = keys.find(k => k.textContent === '3');
    key3.click();
    expect(document.getElementById('nationalId').value).toBe('3');
  });

  it('backspace key removes last character', async () => {
    await loadModule('static/js/pages/kiosk/check_in.js');
    document.getElementById('nationalId').value = '123';
    const keys = [...document.querySelectorAll('.kiosk-key')];
    const back = keys.find(k => k.textContent === '⌫' || k.textContent.includes('⌫') || k.textContent === 'del' || k.textContent === '←');
    // find by not numeric: it's the 11th key (index 10: 'del')
    const target = back || keys[10];
    target.click();
    expect(document.getElementById('nationalId').value).toBe('12');
  });

  it('check (✓) key triggers submit', async () => {
    await loadModule('static/js/pages/kiosk/check_in.js');
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, patient_name: 'S', message: 'ok' }) });
    const keys = [...document.querySelectorAll('.kiosk-key')];
    const checkKey = keys[11]; // last key = checkmark
    document.getElementById('nationalId').value = '999';
    checkKey.click();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
  });

  it('kioskSubmit click triggers doCheckIn', async () => {
    await loadModule('static/js/pages/kiosk/check_in.js');
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
    document.getElementById('nationalId').value = '555';
    document.getElementById('kioskSubmit').click();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
  });

  it('without DOM elements nothing is wired', async () => {
    document.body.innerHTML = '';
    await loadModule('static/js/pages/kiosk/check_in.js');
    expect(typeof window.doCheckIn).toBe('function');
  });
});