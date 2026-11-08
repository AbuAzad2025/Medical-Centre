import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <meta name="csrf-token" content="csrf-pp">
    <select id="paymentCurrencySelect"><option value="ILS">ILS</option><option value="USD">USD</option><option value="EGP">EGP</option></select>
    <div id="exchangeRateInfo" class="d-none"></div>
    <div id="remainingDisplay"></div>
    <span id="baseCurrencyLabel"></span>
    <select id="paymentMethodSelect"><option value="CASH">CASH</option><option value="CARD">CARD</option><option value="INSURANCE">INSURANCE</option></select>
    <div id="insuranceFieldsRow" class="d-none"></div>
    <div id="cardFieldsRow" class="d-none"></div>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M0__ = 'ILS';
  window.escHtml = (s) => String(s ?? '');
  window.API_ROUTES = { check_rate: '/reception/api/check-rate' };
  window.location = { reload: vi.fn() };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ available: true, rate: 3.25 }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('accountant/process_payment.js', () => {
  it('base currency load hides rate info and sets label', async () => {
    await loadModule('static/js/pages/accountant/process_payment.js');
    expect(document.getElementById('exchangeRateInfo').classList.contains('d-none')).toBe(true);
    expect(document.getElementById('baseCurrencyLabel').textContent).toBe('ILS');
  });

  it('currency change to different currency fetches rate', async () => {
    await loadModule('static/js/pages/accountant/process_payment.js');
    const sel = document.getElementById('paymentCurrencySelect');
    sel.value = 'USD';
    sel.dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 30));
    expect(String(global.fetch.mock.calls[0][0])).toContain('from=USD&to=ILS');
    expect(document.getElementById('exchangeRateInfo').classList.contains('d-none')).toBe(false);
  });

  it('unavailable rate shows warning branch', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ available: false }) });
    await loadModule('static/js/pages/accountant/process_payment.js');
    const sel = document.getElementById('paymentCurrencySelect');
    sel.value = 'EGP';
    sel.dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('exchangeRateInfo').innerHTML).toContain('fa-exclamation-triangle');
  });

  it('fetch failure hides rate info', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    await loadModule('static/js/pages/accountant/process_payment.js');
    const sel = document.getElementById('paymentCurrencySelect');
    sel.value = 'USD';
    sel.dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('exchangeRateInfo').classList.contains('d-none')).toBe(true);
  });

  it('rate endpoint non-ok throws and hides rate info', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    await loadModule('static/js/pages/accountant/process_payment.js');
    const sel = document.getElementById('paymentCurrencySelect');
    sel.value = 'USD';
    sel.dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('exchangeRateInfo').classList.contains('d-none')).toBe(true);
  });

  it('insurance method shows insurance row only', async () => {
    await loadModule('static/js/pages/accountant/process_payment.js');
    const sel = document.getElementById('paymentMethodSelect');
    sel.value = 'INSURANCE';
    sel.dispatchEvent(new Event('change'));
    expect(document.getElementById('insuranceFieldsRow').classList.contains('d-none')).toBe(false);
    expect(document.getElementById('cardFieldsRow').classList.contains('d-none')).toBe(true);
  });

  it('card method shows card row only', async () => {
    await loadModule('static/js/pages/accountant/process_payment.js');
    const sel = document.getElementById('paymentMethodSelect');
    sel.value = 'CARD';
    sel.dispatchEvent(new Event('change'));
    expect(document.getElementById('cardFieldsRow').classList.contains('d-none')).toBe(false);
    expect(document.getElementById('insuranceFieldsRow').classList.contains('d-none')).toBe(true);
  });

  it('CASH method hides both rows', async () => {
    await loadModule('static/js/pages/accountant/process_payment.js');
    const sel = document.getElementById('paymentMethodSelect');
    sel.value = 'CARD';
    sel.dispatchEvent(new Event('change'));
    sel.value = 'CASH';
    sel.dispatchEvent(new Event('change'));
    expect(document.getElementById('cardFieldsRow').classList.contains('d-none')).toBe(true);
    expect(document.getElementById('insuranceFieldsRow').classList.contains('d-none')).toBe(true);
  });
});

describe('accountant/pending_payments.js', () => {
  it('refreshPage calls location.reload', async () => {
    const mod = await loadModule('static/js/pages/accountant/pending_payments.js');
    mod.refreshPage();
    expect(window.location.reload).toHaveBeenCalled();
  });

  it('setInterval is registered without throwing', async () => {
    vi.useFakeTimers();
    await loadModule('static/js/pages/accountant/pending_payments.js');
    expect(() => vi.advanceTimersByTime(60000)).not.toThrow();
    vi.useRealTimers();
  });

  it('exposes window.refreshPage', async () => {
    await loadModule('static/js/pages/accountant/pending_payments.js');
    expect(typeof window.refreshPage).toBe('function');
  });
});