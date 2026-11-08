import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <meta name="csrf-token" content="csrf-detail">
    <button id="approveBtn">Approve</button>
  `;
  window.__M0__ = 'csrf-detail-token';
  window.__M1__ = '/api/supply/approve/7';
  window.location = { reload: vi.fn() };
  window.alert = vi.fn();
  window.showToast = vi.fn();
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
  vi.useFakeTimers();
  window.print = vi.fn();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('medication/supply_request_detail.js', () => {
  it('approve click posts and reloads', async () => {
    await loadModule('static/js/pages/medication/supply_request_detail.js');
    document.getElementById('approveBtn').click();
    await vi.advanceTimersByTimeAsync(10);
    expect(global.fetch).toHaveBeenCalledWith('/api/supply/approve/7', expect.objectContaining({ method: 'POST' }));
    expect(window.location.reload).toHaveBeenCalled();
  });

  it('approve network failure shows toast', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    await loadModule('static/js/pages/medication/supply_request_detail.js');
    document.getElementById('approveBtn').click();
    await vi.advanceTimersByTimeAsync(10);
    expect(window.showToast).toHaveBeenCalled();
    expect(window.location.reload).not.toHaveBeenCalled();
  });

  it('approve non-ok response shows toast', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    await loadModule('static/js/pages/medication/supply_request_detail.js');
    document.getElementById('approveBtn').click();
    await vi.advanceTimersByTimeAsync(10);
    expect(window.showToast).toHaveBeenCalled();
  });

  it('approve network failure without showToast falls back to alert', async () => {
    delete window.showToast;
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    await loadModule('static/js/pages/medication/supply_request_detail.js');
    document.getElementById('approveBtn').click();
    await vi.advanceTimersByTimeAsync(10);
    expect(window.alert).toHaveBeenCalled();
  });

  it('missing approveBtn does not throw', async () => {
    document.getElementById('approveBtn').remove();
    await loadModule('static/js/pages/medication/supply_request_detail.js');
    expect(true).toBe(true);
  });
});

describe('lab/lab_requests_results_print.js', () => {
  it('load + 1000ms triggers print', async () => {
    await loadModule('static/js/pages/lab/lab_requests_results_print.js');
    window.dispatchEvent(new Event('load'));
    expect(window.print).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1000);
    expect(window.print).toHaveBeenCalledTimes(1);
  });
});