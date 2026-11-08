import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <meta name="csrf-token" content="csrf-charge">
    <input type="number" id="amountField" value="50">
    <input type="text" id="fallbackAmount" value="999">
    <input type="text" id="cardDigits" value="">
    <input type="text" id="cardHolder" value="">
    <button id="payBtn" data-charge-url="/pos/charge">Pay</button>
    <span id="chargeStatus"></span>
  `;
}

beforeEach(() => {
  baseDom();
  window.showApiWarning = vi.fn();
  window.showApiError = vi.fn();
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({
      success: true,
      transaction_id: 'TXN-1',
      card_last_digits: '1234',
      card_holder_name: 'SARA',
      amount: '50',
    }),
  });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('components/pos-charge.js', () => {
  it('does nothing when button not found', async () => {
    const mod = await loadModule('static/js/components/pos-charge.js');
    expect(() => mod.initPosCharge({ button: 'nonexistentBtn' })).not.toThrow();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('warns when amount is zero and returns', async () => {
    document.getElementById('amountField').value = '0';
    document.getElementById('fallbackAmount').value = '0';
    const mod = await loadModule('static/js/components/pos-charge.js');
    mod.initPosCharge({ button: 'payBtn', amountInput: 'amountField', statusElement: 'chargeStatus', chargeUrl: '/pos/charge', amountFallback: 'fallbackAmount' });
    document.getElementById('payBtn').click();
    await new Promise(r => setTimeout(r, 20));
    expect(window.showApiWarning).toHaveBeenCalled();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('uses amountFallback when amount is zero', async () => {
    document.getElementById('amountField').value = '0';
    const mod = await loadModule('static/js/components/pos-charge.js');
    mod.initPosCharge({ button: 'payBtn', amountInput: 'amountField', chargeUrl: '/pos/charge', amountFallback: 'fallbackAmount' });
    document.getElementById('payBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
    expect(global.fetch.mock.calls[0][1].body.toString()).toContain('amount=999');
  });

  it('uses getAmount function when provided', async () => {
    const mod = await loadModule('static/js/components/pos-charge.js');
    mod.initPosCharge({ button: 'payBtn', getAmount: () => '75.5', chargeUrl: '/pos/charge', statusElement: 'chargeStatus' });
    document.getElementById('payBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch.mock.calls[0][1].body.toString()).toContain('amount=75.5');
  });

  it('successful charge sets status text and fills card fields', async () => {
    const mod = await loadModule('static/js/components/pos-charge.js');
    mod.initPosCharge({ button: 'payBtn', amountInput: 'amountField', statusElement: 'chargeStatus', chargeUrl: '/pos/charge', cardLastDigitsId: 'cardDigits', cardHolderId: 'cardHolder' });
    document.getElementById('payBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('chargeStatus').textContent).toContain('TXN-1');
    expect(document.getElementById('cardDigits').value).toBe('1234');
    expect(document.getElementById('cardHolder').value).toBe('SARA');
    expect(document.getElementById('amountField').value).toBe('50');
    expect(document.getElementById('payBtn').disabled).toBe(false);
  });

  it('server failure shows error status and calls showApiError', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'card declined' }) });
    const mod = await loadModule('static/js/components/pos-charge.js');
    mod.initPosCharge({ button: 'payBtn', amountInput: 'amountField', statusElement: 'chargeStatus', chargeUrl: '/pos/charge' });
    document.getElementById('payBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('chargeStatus').textContent).toBe('card declined');
    expect(document.getElementById('chargeStatus').className).toContain('text-danger');
    expect(window.showApiError).toHaveBeenCalled();
    expect(document.getElementById('payBtn').disabled).toBe(false);
  });

  it('network failure shows generic error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/components/pos-charge.js');
    mod.initPosCharge({ button: 'payBtn', amountInput: 'amountField', statusElement: 'chargeStatus', chargeUrl: '/pos/charge' });
    document.getElementById('payBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('chargeStatus').className).toContain('text-danger');
    expect(window.showApiError).toHaveBeenCalled();
    expect(document.getElementById('payBtn').disabled).toBe(false);
  });

  it('onSuccess callback fires with payload', async () => {
    const onSuccess = vi.fn();
    const mod = await loadModule('static/js/components/pos-charge.js');
    mod.initPosCharge({ button: 'payBtn', amountInput: 'amountField', chargeUrl: '/pos/charge', onSuccess });
    document.getElementById('payBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(onSuccess).toHaveBeenCalledWith(expect.objectContaining({ transaction_id: 'TXN-1' }));
  });

  it('chargeUrl from btn.dataset.chargeUrl is used when opts.chargeUrl missing', async () => {
    const mod = await loadModule('static/js/components/pos-charge.js');
    mod.initPosCharge({ button: 'payBtn', amountInput: 'amountField', statusElement: 'chargeStatus' });
    document.getElementById('payBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(String(global.fetch.mock.calls[0][0])).toContain('/pos/charge');
  });

  it('success without status element still calls onSuccess', async () => {
    const onSuccess = vi.fn();
    const mod = await loadModule('static/js/components/pos-charge.js');
    mod.initPosCharge({ button: 'payBtn', amountInput: 'amountField', chargeUrl: '/pos/charge', onSuccess });
    document.getElementById('payBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(onSuccess).toHaveBeenCalled();
  });

  it('failure without status element still calls showApiError', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    const mod = await loadModule('static/js/components/pos-charge.js');
    mod.initPosCharge({ button: 'payBtn', amountInput: 'amountField', chargeUrl: '/pos/charge' });
    document.getElementById('payBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.showApiError).toHaveBeenCalled();
  });

  it('resolves button element when passed directly', async () => {
    const btn = document.getElementById('payBtn');
    const mod = await loadModule('static/js/components/pos-charge.js');
    mod.initPosCharge({ button: btn, amountInput: 'amountField', chargeUrl: '/pos/charge' });
    btn.click();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
  });

  it('exposes window.initPosCharge', async () => {
    await loadModule('static/js/components/pos-charge.js');
    expect(typeof window.initPosCharge).toBe('function');
  });
});