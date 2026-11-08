import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { initPosCharge } from '../../static/js/components/pos-charge.js';

function baseDom() {
  document.body.innerHTML = `
    <meta name="csrf-token" content="test-csrf">
    <button id="chargeBtn">Charge</button>
    <input id="amountInput" value="50">
    <div id="statusEl"></div>
    <input id="cardDigits">
    <input id="cardHolder">
  `;
}

beforeEach(() => {
  baseDom();
  window.showApiWarning = vi.fn();
  window.showApiError = vi.fn();
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, transaction_id: 'T-1', card_last_digits: '4444', card_holder_name: 'Sara A', amount: 75 }) });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('pos-charge.js element resolution arms', () => {
  it('statusElement passed as a string resolves by id', async () => {
    initPosCharge({ button: 'chargeBtn', amountInput: 'amountInput', statusElement: 'statusEl', chargeUrl: '/pos/charge', cardLastDigitsId: 'cardDigits', cardHolderId: 'cardHolder' });
    document.getElementById('chargeBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('statusEl').textContent).toContain('T-1');
  });

  it('amountInput passed as an element is respected', async () => {
    const amountEl = document.getElementById('amountInput');
    initPosCharge({ button: 'chargeBtn', amountInput: amountEl, statusElement: 'statusEl', chargeUrl: '/pos/charge' });
    amountEl.value = '80';
    document.getElementById('chargeBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch.mock.calls[0][1].body.toString()).toBe('amount=80');
  });

  it('NaN amount with no fallback warns and returns without fetching', async () => {
    document.getElementById('amountInput').value = 'not-a-number';
    initPosCharge({ button: 'chargeBtn', amountInput: 'amountInput', statusElement: 'statusEl', chargeUrl: '/pos/charge' });
    document.getElementById('chargeBtn').click();
    await new Promise(r => setTimeout(r, 20));
    expect(window.showApiWarning).toHaveBeenCalled();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('zero amount without showApiWarning does not crash', async () => {
    document.getElementById('amountInput').value = '0';
    delete window.showApiWarning;
    initPosCharge({ button: 'chargeBtn', amountInput: 'amountInput', statusElement: 'statusEl', chargeUrl: '/pos/charge' });
    expect(() => document.getElementById('chargeBtn').click()).not.toThrow();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('charge with a missing csrf meta sends no token header', async () => {
    document.querySelector('meta[name="csrf-token"]').remove();
    initPosCharge({ button: 'chargeBtn', amountInput: 'amountInput', chargeUrl: '/pos/charge' });
    document.getElementById('chargeBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBeUndefined();
  });
});

describe('pos-charge.js success payload arms', () => {
  it('amount element is overridden with the server-returned amount', async () => {
    initPosCharge({ button: 'chargeBtn', amountInput: 'amountInput', chargeUrl: '/pos/charge' });
    document.getElementById('chargeBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('amountInput').value).toBe('75');
  });

  it('card field elements missing from DOM are skipped silently', async () => {
    document.getElementById('cardDigits').remove();
    document.getElementById('cardHolder').remove();
    initPosCharge({ button: 'chargeBtn', amountInput: 'amountInput', chargeUrl: '/pos/charge', cardLastDigitsId: 'cardDigits', cardHolderId: 'cardHolder' });
    expect(() => document.getElementById('chargeBtn').click()).not.toThrow();
    await new Promise(r => setTimeout(r, 30));
  });

  it('payload without card fields does not set them', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, transaction_id: 'T-9' }) });
    initPosCharge({ button: 'chargeBtn', amountInput: 'amountInput', chargeUrl: '/pos/charge', cardLastDigitsId: 'cardDigits', cardHolderId: 'cardHolder' });
    document.getElementById('chargeBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('cardDigits').value).toBe('');
    expect(document.getElementById('cardHolder').value).toBe('');
  });

  it('payload without amount keeps the local value', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
    initPosCharge({ button: 'chargeBtn', amountInput: 'amountInput', chargeUrl: '/pos/charge' });
    document.getElementById('chargeBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('amountInput').value).toBe('50');
  });

  it('failure with no message and missing statusEl still calls showApiError with default', async () => {
    document.getElementById('statusEl').remove();
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    initPosCharge({ button: 'chargeBtn', amountInput: 'amountInput', chargeUrl: '/pos/charge' });
    document.getElementById('chargeBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.showApiError).toHaveBeenCalled();
  });

  it('failure without window.showApiError does not crash', async () => {
    delete window.showApiError;
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'nope' }) });
    initPosCharge({ button: 'chargeBtn', amountInput: 'amountInput', statusElement: 'statusEl', chargeUrl: '/pos/charge' });
    expect(() => document.getElementById('chargeBtn').click()).not.toThrow();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('statusEl').textContent).toBe('nope');
  });

  it('network failure without window.showApiError does not crash', async () => {
    delete window.showApiError;
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    initPosCharge({ button: 'chargeBtn', amountInput: 'amountInput', statusElement: 'statusEl', chargeUrl: '/pos/charge' });
    expect(() => document.getElementById('chargeBtn').click()).not.toThrow();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('statusEl').textContent).toContain('الاتصال');
  });
});
