import { describe, it, expect, beforeEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = `
    <input id="barcodeInput" value="12345" />
    <select id="scanAction"><option value="lookup">lookup</option></select>
    <div id="scanResult"></div>
  `;
  window.__M = [];
  window.__M0__ = '/api/scan';
  window.__M1__ = 'csrf-token';
  global.fetch = vi.fn().mockResolvedValue({
    json: () => Promise.resolve({ success: true, entity_type: 'Patient', entity_id: 1 }),
  });
  await loadModule('static/js/pages/barcode/scan.js');
});

describe('barcode/scan.js', () => {
  it('loads without error', () => {
    expect(true).toBe(true);
  });
});