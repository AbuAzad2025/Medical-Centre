import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { loadModule } from './test-utils.mjs';

/**
 * These cases used to re-implement applyMetrics in the test and assert on
 * that copy. The production script was never loaded, so
 * static/js/dashboard-live.js had no coverage and the cases could not fail
 * however the real script behaved.
 *
 * The script polls the snapshot endpoint on DOMContentLoaded, so it is loaded
 * here and the event dispatched - the assertions then run against the real
 * behaviour, including the mapping from a metric name to a widget.
 */
beforeEach(async () => {
  document.body.innerHTML = '';
  window.API_ROUTES = {};
  window.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ metrics: { queue_count: 5, visits_today: 12 } }),
  });

  document.body.innerHTML = `
    <div class="command-center">
      <div data-widget-id="queue_live"><span data-metric-value></span></div>
      <div data-widget-id="cash_summary"><span data-metric-value></span></div>
    </div>
  `;

  await loadModule('static/js/dashboard-live.js');
  document.dispatchEvent(new Event('DOMContentLoaded'));
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe('dashboard-live.js', () => {
  it('fetches the snapshot endpoint', async () => {
    await vi.waitFor(() => {
      expect(window.fetch).toHaveBeenCalled();
    });
    expect(window.fetch.mock.calls[0][0]).toBe('/api/dashboard/snapshot');
  });

  it('writes a mapped metric into its widget', async () => {
    await vi.waitFor(() => {
      expect(
        document.querySelector('[data-widget-id="queue_live"] [data-metric-value]').textContent,
      ).toBe('5');
    });
  });

  it('maps a second widget to its own metric', async () => {
    await vi.waitFor(() => {
      expect(
        document.querySelector('[data-widget-id="cash_summary"] [data-metric-value]').textContent,
      ).toBe('12');
    });
  });

  it('leaves a widget with no metric alone', async () => {
    document.body.insertAdjacentHTML(
      'beforeend',
      '<div data-widget-id="triage_board"><span data-metric-value></span></div>',
    );

    await vi.waitFor(() => {
      expect(window.fetch).toHaveBeenCalled();
    });

    expect(
      document.querySelector('[data-widget-id="triage_board"] [data-metric-value]').textContent,
    ).toBe('');
  });
});
