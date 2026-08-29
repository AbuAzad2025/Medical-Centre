import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <select id="paymentCurrencySelect">
      <option value="ILS">ILS</option>
      <option value="USD">USD</option>
    </select>
    <div id="exchangeRateInfo" class="d-none"></div>
    <div id="remainingDisplay"></div>
    <span id="baseCurrencyLabel">ILS</span>
    <select id="paymentMethodSelect">
      <option value="CASH">Cash</option>
      <option value="INSURANCE">Insurance</option>
      <option value="CARD">Card</option>
    </select>
    <div id="insuranceFieldsRow" class="d-none"></div>
    <div id="cardFieldsRow" class="d-none"></div>
  `;
  window.__M0__ = 'ILS';
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ available: true, rate: 3.5 }) });
});

describe('accountant/process_payment.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/accountant/process_payment.js');
  });
});
