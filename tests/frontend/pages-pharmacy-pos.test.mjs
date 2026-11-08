import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function setupDom() {
  document.body.innerHTML = `
    <meta name="csrf-token" content="test-csrf">
    <input type="radio" name="paymentMethod" value="cash" checked id="pmCash">
    <input type="radio" name="paymentMethod" value="card" id="pmCard">
    <div id="cardChargeBlock" class="d-none"></div>
    <div id="cartItems"></div>
    <div id="cartTotal">0.00</div>
    <input id="customerName" value="Walk-in">
    <button id="checkoutBtn" disabled>إتمام البيع</button>
    <span id="checkoutBtnLabel">إتمام البيع (نقداً)</span>
    <button id="clearCart">مسح</button>
    <input id="medSearch">
    <div id="medResults"></div>
    <div id="noResults" class="d-none"></div>
  `;
}

beforeEach(() => {
  setupDom();
  document.body.innerHTML = '';
  setupDom();
  window.__M = [];
  window.API_ROUTES = {};
  window.__M0__ = '/api/sell';
  window.__PHARMACY_POS__ = { posEnabled: false, sellUrl: '/api/sell', searchUrl: '/api/search', chargeUrl: '/pos/charge', receiptUrl: '/receipt/0' };
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.bootstrap = { Collapse: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn() })) }, Modal: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn(), hide: vi.fn() })) } };
  window.initPosCharge = vi.fn();
  window.showApiWarning = vi.fn();
  window.showApiError = vi.fn();
  window.location = { href: '', reload: vi.fn() };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
  vi.resetModules();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('pharmacy/pos.js', () => {
  it('cartTotal returns zero for empty cart', async () => {
    const mod = await loadModule('static/js/pages/pharmacy/pos.js');
    expect(mod.cartTotal()).toBe(0);
  });

  it('addToCart adds an item and renders it', async () => {
    const mod = await loadModule('static/js/pages/pharmacy/pos.js');
    mod.addToCart('1', 'Aspirin', '5.5', '100');
    expect(mod.cartTotal()).toBe(5.5);
    expect(document.getElementById('cartItems').innerHTML).toContain('Aspirin');
    expect(document.getElementById('checkoutBtn').disabled).toBe(false);
  });

  it('addToCart increments quantity of same item', async () => {
    const mod = await loadModule('static/js/pages/pharmacy/pos.js');
    mod.addToCart('1', 'Aspirin', '5.5', '100');
    mod.addToCart('1', 'Aspirin', '5.5', '100');
    expect(mod.cartTotal()).toBe(11);
  });

  it('cartTotal matches the sum across multiple items', async () => {
    const mod = await loadModule('static/js/pages/pharmacy/pos.js');
    mod.addToCart('1', 'Aspirin', '10', '100');
    mod.addToCart('2', 'Vitamin D', '20', '100');
    mod.addToCart('1', 'Aspirin', '10', '100');
    expect(mod.cartTotal()).toBe(40);
  });

  it('renderCart with empty cart shows empty state', async () => {
    const mod = await loadModule('static/js/pages/pharmacy/pos.js');
    mod.renderCart();
    expect(document.getElementById('cartItems').innerHTML).toContain('السلة فارغة');
    expect(document.getElementById('checkoutBtn').disabled).toBe(true);
  });

  it('selectedPaymentMethod defaults to cash', async () => {
    const mod = await loadModule('static/js/pages/pharmacy/pos.js');
    expect(mod.selectedPaymentMethod()).toBe('cash');
  });

  it('selectedPaymentMethod reads checked radio', async () => {
    const mod = await loadModule('static/js/pages/pharmacy/pos.js');
    document.getElementById('pmCard').checked = true;
    expect(mod.selectedPaymentMethod()).toBe('card');
  });

  it('updateCheckoutLabel reflects card method', async () => {
    const mod = await loadModule('static/js/pages/pharmacy/pos.js');
    document.getElementById('pmCard').checked = true;
    mod.updateCheckoutLabel();
    expect(document.getElementById('checkoutBtnLabel').textContent).toBe('إتمام البيع (بطاقة)');
  });

  it('toggleCardBlock hides card block for cash', async () => {
    const mod = await loadModule('static/js/pages/pharmacy/pos.js');
    document.getElementById('pmCash').checked = true;
    mod.toggleCardBlock();
    expect(document.getElementById('cardChargeBlock').classList.contains('d-none')).toBe(true);
  });

  it('toggleCardBlock shows card block for card', async () => {
    const mod = await loadModule('static/js/pages/pharmacy/pos.js');
    document.getElementById('pmCard').checked = true;
    mod.toggleCardBlock();
    expect(document.getElementById('cardChargeBlock').classList.contains('d-none')).toBe(false);
  });

  it('quick-add click event adds to cart', async () => {
    await loadModule('static/js/pages/pharmacy/pos.js');
    const btn = document.createElement('button');
    btn.className = 'quick-add';
    btn.dataset.id = '3';
    btn.dataset.name = 'Paracetamol';
    btn.dataset.price = '3.5';
    btn.dataset.stock = '50';
    document.body.appendChild(btn);
    btn.click();
    expect(document.getElementById('cartItems').innerHTML).toContain('Paracetamol');
  });

  it('remove-item click event removes from cart', async () => {
    const mod = await loadModule('static/js/pages/pharmacy/pos.js');
    mod.addToCart('9', 'Ventoline', '12', '100');
    document.querySelector('[data-index="0"].remove-item') || null;
    const removeBtn = document.querySelector('.remove-item');
    removeBtn.click();
    expect(document.getElementById('cartTotal').textContent).toBe('0.00 ₪');
  });

  it('DOMContentLoaded wires clearCart to empty the cart', async () => {
    const mod = await loadModule('static/js/pages/pharmacy/pos.js');
    mod.addToCart('1', 'Test', '5', '10');
    document.getElementById('clearCart').click();
    expect(document.getElementById('cartTotal').textContent).toBe('0.00 ₪');
  });

  it('search input loads results', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve([{ id: 7, trade_name: 'Vitamin D', price: 9, stock: 30 }]) });
    await loadModule('static/js/pages/pharmacy/pos.js');
    const search = document.getElementById('medSearch');
    search.value = 'vitam';
    search.dispatchEvent(new Event('input', { bubbles: true }));
    await new Promise(r => setTimeout(r, 450));
    expect(document.getElementById('medResults').innerHTML).toContain('Vitamin D');
  });

  it('search with empty results shows noResults', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve([]) });
    await loadModule('static/js/pages/pharmacy/pos.js');
    const search = document.getElementById('medSearch');
    search.value = 'zzz';
    search.dispatchEvent(new Event('input', { bubbles: true }));
    await new Promise(r => setTimeout(r, 450));
    expect(document.getElementById('noResults').classList.contains('d-none')).toBe(false);
  });

  it('search short input clears results', async () => {
    await loadModule('static/js/pages/pharmacy/pos.js');
    const search = document.getElementById('medSearch');
    search.value = '';
    search.dispatchEvent(new Event('input', { bubbles: true }));
    expect(document.getElementById('medResults').innerHTML).toBe('');
  });

  it('checkout without items does nothing', async () => {
    await loadModule('static/js/pages/pharmacy/pos.js');
    document.getElementById('checkoutBtn').click();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('checkout with cash item server failure shows error and restores button', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'Insufficient stock' }) });
    const mod = await loadModule('static/js/pages/pharmacy/pos.js');
    mod.addToCart('1', 'Aspirin', '5', '100');
    document.getElementById('checkoutBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('checkoutBtn').disabled).toBe(false);
    expect(window.showApiError).toHaveBeenCalled();
  });

  it('qty-input change updates stored quantity with bounds', async () => {
    const mod = await loadModule('static/js/pages/pharmacy/pos.js');
    mod.addToCart('1', 'Aspirin', '5', '100');
    mod.addToCart('2', 'Vitamin D', '10', '100');
    const qtyInput = document.querySelector('.qty-input');
    qtyInput.value = '3';
    qtyInput.dispatchEvent(new Event('change', { bubbles: true }));
    expect(mod.cartTotal()).toBe(25);
    const qtyInput2 = document.querySelectorAll('.qty-input')[1];
    qtyInput2.value = '0';
    qtyInput2.dispatchEvent(new Event('change', { bubbles: true }));
    expect(mod.cartTotal()).toBe(25 - 10 + 10); // first item qty 3 x5 = 15; second qty min 1 -> 10 => 25
  });

  it('paymentMethod change toggles card block', async () => {
    await loadModule('static/js/pages/pharmacy/pos.js');
    const pm = document.getElementById('pmCard');
    pm.checked = true;
    pm.dispatchEvent(new Event('change', { bubbles: true }));
    expect(document.getElementById('cardChargeBlock').classList.contains('d-none')).toBe(false);
  });

  it('posEnabled wiring calls initPosCharge', async () => {
    window.__PHARMACY_POS__ = { posEnabled: true, sellUrl: '/api/sell', searchUrl: '/api/search', chargeUrl: '/pos/charge', receiptUrl: '/receipt/0' };
    window.initPosCharge = vi.fn();
    await loadModule('static/js/pages/pharmacy/pos.js');
    expect(window.initPosCharge).toHaveBeenCalled();
    expect(window.initPosCharge.mock.calls[0][0].button).toBe('pharmacyPosChargeBtn');
  });

  it('posEnabled charge success fills transaction id and card digits', async () => {
    window.__PHARMACY_POS__ = { posEnabled: true, sellUrl: '/api/sell', searchUrl: '/api/search', chargeUrl: '/pos/charge', receiptUrl: '/receipt/0' };
    let onSuccessCb = null;
    window.initPosCharge = vi.fn().mockImplementation((opts) => { onSuccessCb = opts.onSuccess; });
    document.body.innerHTML += '<input id="pharmacyTransactionId"><input id="pharmacyCardLastDigits"><div id="pharmacyPosStatus"></div><button id="pharmacyPosChargeBtn">Pay</button>';
    await loadModule('static/js/pages/pharmacy/pos.js');
    onSuccessCb({ transaction_id: 'TXN-777', card_last_digits: '4040' });
    expect(document.getElementById('pharmacyTransactionId').value).toBe('TXN-777');
    expect(document.getElementById('pharmacyCardLastDigits').value).toBe('4040');
  });

  it('posEnabled charge success with only approval_code fills pharmacyTransactionId', async () => {
    window.__PHARMACY_POS__ = { posEnabled: true, sellUrl: '/api/sell', searchUrl: '/api/search', chargeUrl: '/pos/charge', receiptUrl: '/receipt/0' };
    let onSuccessCb = null;
    window.initPosCharge = vi.fn().mockImplementation((opts) => { onSuccessCb = opts.onSuccess; });
    document.body.innerHTML += '<input id="pharmacyTransactionId"><input id="pharmacyCardLastDigits"><div id="pharmacyPosStatus"></div><button id="pharmacyPosChargeBtn">Pay</button>';
    await loadModule('static/js/pages/pharmacy/pos.js');
    onSuccessCb({ approval_code: 'APP-9', card_last_digits: '1111' });
    expect(document.getElementById('pharmacyTransactionId').value).toBe('APP-9');
  });

  it('card checkout with pharmacyTransactionId posts transaction_id', async () => {
    window.__PHARMACY_POS__ = { posEnabled: true, sellUrl: '/api/sell', searchUrl: '/api/search', chargeUrl: '/pos/charge', receiptUrl: '/receipt/0' };
    let onSuccessCb = null;
    window.initPosCharge = vi.fn().mockImplementation((opts) => { onSuccessCb = opts.onSuccess; });
    document.body.innerHTML += '<input id="pharmacyTransactionId" value="TXN-777"><input id="pharmacyCardLastDigits" value="4040"><div id="pharmacyPosStatus"></div><button id="pharmacyPosChargeBtn">Pay</button>';
    window.showApiWarning = vi.fn();
    const mod = await loadModule('static/js/pages/pharmacy/pos.js');
    onSuccessCb({ transaction_id: 'TXN-777', card_last_digits: '4040' });
    document.getElementById('pmCard').checked = true;
    mod.addToCart('1', 'Aspirin', '5', '100');
    document.getElementById('checkoutBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.showApiWarning).not.toHaveBeenCalled();
    expect(global.fetch).toHaveBeenCalled();
    const body = JSON.parse(global.fetch.mock.calls[global.fetch.mock.calls.length - 1][1].body);
    expect(body.transaction_id).toBe('TXN-777');
    expect(body.card_last_digits).toBe('4040');
  });

  it('checkout network failure shows error and restores button', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/pharmacy/pos.js');
    mod.addToCart('1', 'Aspirin', '5', '100');
    document.getElementById('checkoutBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('checkoutBtn').disabled).toBe(false);
    expect(window.showApiError).toHaveBeenCalled();
  });

  it('checkout with cash item completes the sale', async () => {
    const mod = await loadModule('static/js/pages/pharmacy/pos.js');
    mod.addToCart('1', 'Aspirin', '5', '100');
    document.getElementById('checkoutBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
  });
});