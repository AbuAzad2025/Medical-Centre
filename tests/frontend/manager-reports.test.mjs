import { describe, it, expect, beforeEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = `<div id="reportsContainer"></div>`;
  window.__M = [];
  window.API_ROUTES = {};
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
  await loadModule('static/js/pages/manager/reports.js');
});

describe('manager/reports.js', () => {
  it('loads without error', () => {
    expect(true).toBe(true);
  });
});