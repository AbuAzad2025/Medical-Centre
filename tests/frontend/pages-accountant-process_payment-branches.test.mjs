import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <meta name="csrf-token" content="test-csrf">
    <select id="paymentCurrencySelect"><option value="NIS">NIS</option><option value="USD">USD</option></select>
    <div id="exchangeRateInfo" class="d-none"></div>
    <div id="remainingDisplay">0.00</div>
    <span id="baseCurrencyLabel">NIS</span>
    <select id="paymentMethodSelect"><option value="CASH">CASH</option><option value="INSURANCE">INSURANCE</option><option value="CARD">CARD</option></select>
    <div id="insuranceFieldsRow" class="d-none"></div>
    <div id="cardFieldsRow" class="d-none"></div>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M = [];
  window.__M0__ = 'NIS';
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s ?? '');
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ available: true, rate: 3.7 }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('process_payment.js rate branches', () => {
  it('base currency hides the rate info and sets the label', async () => {
    await loadModule('static/js/pages/accountant/process_payment.js');
    document.getElementById('paymentCurrencySelect').value = 'NIS';
    document.getElementById('paymentCurrencySelect').dispatchEvent(new Event('change'));
    expect(document.getElementById('exchangeRateInfo').classList.contains('d-none')).toBe(true);
    expect(document.getElementById('baseCurrencyLabel').textContent).toBe('NIS');
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('available rate shows the rate and clears the hidden flag', async () => {
    await loadModule('static/js/pages/accountant/process_payment.js');
    document.getElementById('paymentCurrencySelect').value = 'USD';
    document.getElementById('paymentCurrencySelect').dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('exchangeRateInfo').classList.contains('d-none')).toBe(false);
    expect(document.getElementById('exchangeRateInfo').innerHTML).toContain('3.7');
  });

  it('unavailable rate shows the warning message without rate', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ available: false }) });
    await loadModule('static/js/pages/accountant/process_payment.js');
    document.getElementById('paymentCurrencySelect').value = 'USD';
    document.getElementById('paymentCurrencySelect').dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('exchangeRateInfo').innerHTML).toContain('fas fa-exclamation-triangle');
  });

  it('non-ok rate check hides the rate info via the catch branch', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    await loadModule('static/js/pages/accountant/process_payment.js');
    document.getElementById('paymentCurrencySelect').value = 'USD';
    document.getElementById('paymentCurrencySelect').dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('exchangeRateInfo').classList.contains('d-none')).toBe(true);
  });

  it('network failure hides the rate info via the catch branch', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    await loadModule('static/js/pages/accountant/process_payment.js');
    document.getElementById('paymentCurrencySelect').value = 'USD';
    document.getElementById('paymentCurrencySelect').dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('exchangeRateInfo').classList.contains('d-none')).toBe(true);
  });

  it('uses API_ROUTES.check_rate when set', async () => {
    window.API_ROUTES = { check_rate: '/custom/rate' };
    await loadModule('static/js/pages/accountant/process_payment.js');
    document.getElementById('paymentCurrencySelect').value = 'USD';
    document.getElementById('paymentCurrencySelect').dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch.mock.calls[0][0]).toContain('/custom/rate');
  });

  it('falls back to the default rate endpoint when API_ROUTES is unset', async () => {
    delete window.API_ROUTES;
    await loadModule('static/js/pages/accountant/process_payment.js');
    document.getElementById('paymentCurrencySelect').value = 'USD';
    document.getElementById('paymentCurrencySelect').dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch.mock.calls[0][0]).toContain('/reception/api/check-rate');
  });
});

describe('process_payment.js payment method branches', () => {
  it('INSURANCE method shows the insurance row and hides card', async () => {
    await loadModule('static/js/pages/accountant/process_payment.js');
    document.getElementById('paymentMethodSelect').value = 'INSURANCE';
    document.getElementById('paymentMethodSelect').dispatchEvent(new Event('change'));
    expect(document.getElementById('insuranceFieldsRow').classList.contains('d-none')).toBe(false);
    expect(document.getElementById('cardFieldsRow').classList.contains('d-none')).toBe(true);
  });

  it('CARD method shows the card row and hides insurance', async () => {
    await loadModule('static/js/pages/accountant/process_payment.js');
    document.getElementById('paymentMethodSelect').value = 'CARD';
    document.getElementById('paymentMethodSelect').dispatchEvent(new Event('change'));
    expect(document.getElementById('cardFieldsRow').classList.contains('d-none')).toBe(false);
    expect(document.getElementById('insuranceFieldsRow').classList.contains('d-none')).toBe(true);
  });

  it('CASH method hides both rows', async () => {
    await loadModule('static/js/pages/accountant/process_payment.js');
    document.getElementById('paymentMethodSelect').value = 'CARD';
    document.getElementById('paymentMethodSelect').dispatchEvent(new Event('change'));
    document.getElementById('paymentMethodSelect').value = 'CASH';
    document.getElementById('paymentMethodSelect').dispatchEvent(new Event('change'));
    expect(document.getElementById('insuranceFieldsRow').classList.contains('d-none')).toBe(true);
    expect(document.getElementById('cardFieldsRow').classList.contains('d-none')).toBe(true);
  });

  it('missing method select does not crash', async () => {
    document.getElementById('paymentMethodSelect').remove();
    await expect(loadModule('static/js/pages/accountant/process_payment.js')).resolves.toBeDefined();
  });

  it('missing insurance and card rows do not crash on change', async () => {
    document.getElementById('insuranceFieldsRow').remove();
    document.getElementById('cardFieldsRow').remove();
    await loadModule('static/js/pages/accountant/process_payment.js');
    document.getElementById('paymentMethodSelect').value = 'CARD';
    expect(() => document.getElementById('paymentMethodSelect').dispatchEvent(new Event('change'))).not.toThrow();
  });
});
