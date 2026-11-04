import { describe, it, expect, beforeEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = `
    <button id="chargeBtn">Charge</button>
    <input id="amountInput" value="100" />
    <span id="statusEl"></span>
    <input name="csrf_token" value="tok" />
  `;
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ success: true, transaction_id: 'TX1', amount: 100 }),
  });
  await loadModule('static/js/components/pos-charge.js');
});

describe('pos-charge.js', () => {
  it('loads without error', () => {
    expect(typeof window.initPosCharge).toBe('function');
  });

  it('initPosCharge attaches click handler', () => {
    const btn = document.getElementById('chargeBtn');
    window.initPosCharge({ button: 'chargeBtn', amountInput: 'amountInput', statusElement: 'statusEl', chargeUrl: '/charge' });
    btn.click();
    expect(btn.disabled).toBe(true);
  });
});