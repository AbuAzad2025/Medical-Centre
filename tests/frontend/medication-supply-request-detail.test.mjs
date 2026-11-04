import { describe, it, expect, beforeEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = `
    <button id="approveBtn">Approve</button>
  `;
  window.__M = [];
  window.__M0__ = 'csrf-token';
  window.__M1__ = '/api/approve';
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
  await loadModule('static/js/pages/medication/supply_request_detail.js');
});

describe('medication/supply_request_detail.js', () => {
  it('loads without error', () => {
    expect(true).toBe(true);
  });
});