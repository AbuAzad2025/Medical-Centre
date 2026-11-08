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
    <button id="checkoutBtn" disabled><span id="checkoutBtnLabel">إتمام البيع (نقداً)</span></button>
    <button id="clearCart">مسح</button>
    <input id="medSearch">
    <div id="medResults"></div>
    <div id="noResults" class="d-none"></div>
  `;
}

beforeEach(() => {
  setupDom();
  window.__M = [];
  window.escHtml = (s) => String(s ?? '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.initPosCharge = vi.fn();
  window.showApiWarning = vi.fn();
  window.showApiError = vi.fn();
  window.location = { href: '', reload: vi.fn() };
  window.__PHARMACY_POS__ = { posEnabled: false, sellUrl: '/api/sell', searchUrl: '/api/search', chargeUrl: '/pos/charge', receiptUrl: '/receipt/0' };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('pos.js config and label branches', () => {
  it('module loads with no __PHARMACY_POS__ config at all', async () => {
    delete window.__PHARMACY_POS__;
    await expect(loadModule('static/js/pages/pharmacy/pos.js')).resolves.toBeDefined();
    expect(window.initPosCharge).not.toHaveBeenCalled();
  });

  it('updateCheckoutLabel without the label element is a no-op', async () => {
    document.getElementById('checkoutBtnLabel').remove();
    const mod = await loadModule('static/js/pages/pharmacy/pos.js');
    expect(() => mod.updateCheckoutLabel()).not.toThrow();
  });

  it('toggleCardBlock without the card block is a no-op', async () => {
    document.getElementById('cardChargeBlock').remove();
    const mod = await loadModule('static/js/pages/pharmacy/pos.js');
    expect(() => mod.toggleCardBlock()).not.toThrow();
  });

  it('switching to cash clears the pos charge data and txn fields', async () => {
    document.body.insertAdjacentHTML('beforeend', '<input id="pharmacyTransactionId" value="TX-1"><input id="pharmacyCardLastDigits" value="4242">');
    window.__PHARMACY_POS__ = { posEnabled: true, sellUrl: '/api/sell', searchUrl: '/api/search', chargeUrl: '/pos/charge', receiptUrl: '/receipt/0' };
    let captured = null;
    window.initPosCharge = vi.fn((opts) => { captured = opts; });
    const mod = await loadModule('static/js/pages/pharmacy/pos.js');
    captured.onSuccess({ transaction_id: 'T9', card_last_digits: '1234' });
    document.getElementById('pmCard').checked = true;
    document.getElementById('pmCard').dispatchEvent(new Event('change', { bubbles: true }));
    expect(document.getElementById('pharmacyTransactionId').value).toBe('T9');
    document.getElementById('pmCash').checked = true;
    document.getElementById('pmCash').dispatchEvent(new Event('change', { bubbles: true }));
    expect(document.getElementById('pharmacyTransactionId').value).toBe('');
    expect(document.getElementById('pharmacyCardLastDigits').value).toBe('');
  });

  it('cash toggle with missing txn/digits elements does not crash', async () => {
    const mod = await loadModule('static/js/pages/pharmacy/pos.js');
    expect(() => mod.toggleCardBlock()).not.toThrow();
  });
});

describe('pos.js card checkout branches', () => {
  function cartWithOne() {
    return null; // cart setup done via exports instead
  }

  it('card method with posEnabled and no transaction id shows the warning and aborts', async () => {
    document.body.insertAdjacentHTML('beforeend', '<input id="pharmacyTransactionId" value="">');
    window.__PHARMACY_POS__ = { posEnabled: true, sellUrl: '/api/sell', searchUrl: '/api/search', chargeUrl: '/pos/charge', receiptUrl: '/receipt/0' };
    const mod = await loadModule('static/js/pages/pharmacy/pos.js');
    mod.addToCart('m1', 'Aspirin', 10, 50);
    document.getElementById('pmCard').checked = true;
    document.getElementById('checkoutBtn').disabled = false;
    document.getElementById('checkoutBtn').click();
    expect(window.showApiWarning).toHaveBeenCalled();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('card method with posEnabled but missing txn element shows the warning', async () => {
    window.__PHARMACY_POS__ = { posEnabled: true, sellUrl: '/api/sell', searchUrl: '/api/search', chargeUrl: '/pos/charge', receiptUrl: '/receipt/0' };
    const mod = await loadModule('static/js/pages/pharmacy/pos.js');
    mod.addToCart('m1', 'Aspirin', 10, 50);
    document.getElementById('pmCard').checked = true;
    document.getElementById('checkoutBtn').disabled = false;
    document.getElementById('checkoutBtn').click();
    expect(window.showApiWarning).toHaveBeenCalled();
  });

  it('card method without posEnabled proceeds to the sale without txn validation', async () => {
    const mod = await loadModule('static/js/pages/pharmacy/pos.js');
    mod.addToCart('m1', 'Aspirin', 10, 50);
    document.getElementById('pmCard').checked = true;
    document.getElementById('checkoutBtn').disabled = false;
    document.getElementById('checkoutBtn').click();
    await new Promise(r => setTimeout(r, 40));
    const call = global.fetch.mock.calls[0];
    const body = JSON.parse(call[1].body);
    expect(body.payment_method).toBe('card');
  });

  it('checkout includes posChargeData with approval_code fallback', async () => {
    document.body.insertAdjacentHTML('beforeend', '<input id="pharmacyTransactionId" value=""><input id="pharmacyCardLastDigits" value="">');
    window.__PHARMACY_POS__ = { posEnabled: true, sellUrl: '/api/sell', searchUrl: '/api/search', chargeUrl: '/pos/charge', receiptUrl: '/receipt/0' };
    let captured = null;
    window.initPosCharge = vi.fn((opts) => { captured = opts; });
    const mod = await loadModule('static/js/pages/pharmacy/pos.js');
    captured.onSuccess({ approval_code: 'AP-7', card_last_digits: '9999' });
    mod.addToCart('m1', 'Aspirin', 10, 50);
    document.getElementById('pmCard').checked = true;
    document.getElementById('pharmacyTransactionId').value = 'AP-7';
    document.getElementById('checkoutBtn').disabled = false;
    document.getElementById('checkoutBtn').click();
    await new Promise(r => setTimeout(r, 40));
    const body = JSON.parse(global.fetch.mock.calls[0][1].body);
    expect(body.transaction_id).toBe('AP-7');
    expect(body.card_last_digits).toBe('9999');
  });

  it('pos charge onSuccess without transaction_id or approval_code leaves txn blank', async () => {
    document.body.insertAdjacentHTML('beforeend', '<input id="pharmacyTransactionId" value="KEEP">');
    window.__PHARMACY_POS__ = { posEnabled: true, sellUrl: '/api/sell', searchUrl: '/api/search', chargeUrl: '/pos/charge', receiptUrl: '/receipt/0' };
    let captured = null;
    window.initPosCharge = vi.fn((opts) => { captured = opts; });
    await loadModule('static/js/pages/pharmacy/pos.js');
    captured.onSuccess({});
    expect(document.getElementById('pharmacyTransactionId').value).toBe('');
  });

  it('pos charge onSuccess with missing digits element skips the digits write', async () => {
    window.__PHARMACY_POS__ = { posEnabled: true, sellUrl: '/api/sell', searchUrl: '/api/search', chargeUrl: '/pos/charge', receiptUrl: '/receipt/0' };
    let captured = null;
    window.initPosCharge = vi.fn((opts) => { captured = opts; });
    await loadModule('static/js/pages/pharmacy/pos.js');
    expect(() => captured.onSuccess({ transaction_id: 'T5', card_last_digits: '1111' })).not.toThrow();
  });

  it('sale success navigates to the receipt url with the sale id', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, sale_id: 123 }) });
    const mod = await loadModule('static/js/pages/pharmacy/pos.js');
    mod.addToCart('m1', 'Aspirin', 10, 50);
    document.getElementById('checkoutBtn').disabled = false;
    document.getElementById('checkoutBtn').click();
    await new Promise(r => setTimeout(r, 40));
    expect(window.location.href).toBe('/receipt/123');
  });

  it('sale failure with a server message shows it', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'out of stock' }) });
    const mod = await loadModule('static/js/pages/pharmacy/pos.js');
    mod.addToCart('m1', 'Aspirin', 10, 50);
    document.getElementById('checkoutBtn').disabled = false;
    document.getElementById('checkoutBtn').click();
    await new Promise(r => setTimeout(r, 40));
    expect(window.showApiError.mock.calls[0][1]).toBe('out of stock');
  });

  it('sale failure without server message shows the default error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    const mod = await loadModule('static/js/pages/pharmacy/pos.js');
    mod.addToCart('m1', 'Aspirin', 10, 50);
    document.getElementById('checkoutBtn').disabled = false;
    document.getElementById('checkoutBtn').click();
    await new Promise(r => setTimeout(r, 40));
    expect(window.showApiError.mock.calls[0][1]).toBe('تعذّر إتمام البيع');
  });

  it('failed sale restores the card checkout label for card method', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'no' }) });
    document.body.insertAdjacentHTML('beforeend', '<input id="pharmacyTransactionId" value="T9"><input id="pharmacyCardLastDigits" value="1">');
    window.__PHARMACY_POS__ = { posEnabled: true, sellUrl: '/api/sell', searchUrl: '/api/search', chargeUrl: '/pos/charge', receiptUrl: '/receipt/card-0' };
    let captured = null;
    window.initPosCharge = vi.fn((opts) => { captured = opts; });
    const mod = await loadModule('static/js/pages/pharmacy/pos.js');
    captured.onSuccess({ transaction_id: 'T9' });
    mod.addToCart('m1', 'Aspirin', 10, 50);
    document.getElementById('pmCard').checked = true;
    document.getElementById('checkoutBtn').disabled = false;
    document.getElementById('checkoutBtn').click();
    await new Promise(r => setTimeout(r, 40));
    expect(document.getElementById('checkoutBtn').innerHTML).toContain('إتمام البيع (بطاقة)');
    expect(document.getElementById('checkoutBtn').disabled).toBe(false);
  });
});

describe('pos.js qty-input guard branches', () => {
  it('change on a qty input with no cart entry is ignored', async () => {
    const mod = await loadModule('static/js/pages/pharmacy/pos.js');
    const input = document.createElement('input');
    input.classList.add('qty-input');
    input.dataset.index = '5';
    input.value = '3';
    document.body.appendChild(input);
    expect(() => input.dispatchEvent(new Event('change', { bubbles: true }))).not.toThrow();
    expect(mod.cartTotal()).toBe(0);
  });

  it('whitespace-only search query clears the results', async () => {
    await loadModule('static/js/pages/pharmacy/pos.js');
    const input = document.getElementById('medSearch');
    document.getElementById('medResults').innerHTML = '<tr><td>old</td></tr>';
    input.value = '   ';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    expect(document.getElementById('medResults').innerHTML).toBe('');
  });

  it('search results with missing price/stock render zero fallbacks', async () => {
    vi.useFakeTimers();
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve([{ id: 'm9', trade_name: 'TestDrug', price: null, stock: null }]) });
    await loadModule('static/js/pages/pharmacy/pos.js');
    const input = document.getElementById('medSearch');
    input.value = 'test';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    await vi.advanceTimersByTimeAsync(400);
    expect(document.getElementById('medResults').innerHTML).toContain('0.00');
    vi.useRealTimers();
  });

  it('remove-item click on an unknown index does not crash', async () => {
    await loadModule('static/js/pages/pharmacy/pos.js');
    const btn = document.createElement('button');
    btn.className = 'remove-item';
    btn.dataset.index = '9';
    document.body.appendChild(btn);
    expect(() => btn.click()).not.toThrow();
  });
});
