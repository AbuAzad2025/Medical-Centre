import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <div id="cartItems"><div id="emptyCart">Empty</div></div>
    <div id="cartTotal">0.00 ₪</div>
    <button id="checkoutBtn" disabled></button>
    <span id="checkoutBtnLabel">Checkout</span>
    <button id="clearCart"></button>
    <input id="medSearch" type="text" />
    <tbody id="medResults"></tbody>
    <div id="noResults" class="d-none"></div>
    <input name="paymentMethod" type="radio" value="cash" checked />
    <input name="paymentMethod" type="radio" value="card" />
    <div id="cardChargeBlock" class="d-none"></div>
    <input id="customerName" value="" />
    <input id="pharmacyTransactionId" value="" />
    <input id="pharmacyCardLastDigits" value="" />
    <meta name="csrf-token" content="test-token" />
  `;
  window.__PHARMACY_POS__ = { posEnabled: false, sellUrl: '/api/sell', searchUrl: '/api/search', receiptUrl: '/receipt/0' };
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.showApiWarning = vi.fn();
  window.showApiError = vi.fn();
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve([]) });
});

describe('pharmacy/pos.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/pharmacy/pos.js');
  });

  test('checkout button starts disabled', async () => {
    await loadScript('static/js/pages/pharmacy/pos.js');
    expect(document.getElementById('checkoutBtn').disabled).toBe(true);
  });

  test('empty cart message shown initially', async () => {
    await loadScript('static/js/pages/pharmacy/pos.js');
    expect(document.getElementById('emptyCart')).not.toBeNull();
  });

  test('medSearch input exists', async () => {
    await loadScript('static/js/pages/pharmacy/pos.js');
    expect(document.getElementById('medSearch')).not.toBeNull();
  });

  test('card charge block is hidden by default', async () => {
    await loadScript('static/js/pages/pharmacy/pos.js');
    expect(document.getElementById('cardChargeBlock').classList.contains('d-none')).toBe(true);
  });
});
