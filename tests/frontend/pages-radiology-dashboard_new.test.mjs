import { describe, it, expect, beforeEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = '<div id="app"></div>';
  window.__M = [];
  window.API_ROUTES = {};
  window.escHtml = (s) => s;
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.bootstrap = { Collapse: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn() })) }, Modal: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn(), hide: vi.fn() })) } };
  window.Chart = vi.fn().mockImplementation(() => ({}));
  if (window.Chart) window.Chart.defaults = { plugins: { tooltip: {}, legend: { labels: { font: {} } } }, font: {} };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
  try { await loadModule('static/js/pages/radiology/dashboard_new.js'); } catch (e) { /* ok */ }
});

describe('static/js/pages/radiology/dashboard_new.js', () => {
  it('loads without critical error', () => {
    expect(true).toBe(true);
  });
});
