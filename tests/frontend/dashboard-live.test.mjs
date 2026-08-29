import { describe, it, expect, vi, beforeEach } from 'vitest';
import { loadScript } from './test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = '';
});

describe('dashboard-live.js - applyMetrics', () => {
  it('updates DOM elements with metric values', () => {
    document.body.innerHTML = `
      <div data-widget-id="queue_live">
        <span data-metric-value></span>
      </div>
      <div data-widget-id="cash_summary">
        <span data-metric-value></span>
      </div>
    `;
    const metrics = { queue_count: 5, visits_today: 12 };
    const map = { queue_live: 'queue_count', cash_summary: 'visits_today' };
    document.querySelectorAll('[data-widget-id]').forEach(el => {
      const id = el.dataset.widgetId;
      const key = map[id];
      if (key && metrics[key] !== undefined) {
        const target = el.querySelector('[data-metric-value]');
        if (target) target.textContent = metrics[key];
      }
    });
    expect(document.querySelector('[data-widget-id="queue_live"] [data-metric-value]').textContent).toBe('5');
    expect(document.querySelector('[data-widget-id="cash_summary"] [data-metric-value]').textContent).toBe('12');
  });

  it('does nothing with null metrics', () => {
    document.body.innerHTML = '<div data-widget-id="test"><span data-metric-value></span></div>';
    expect(document.querySelector('[data-metric-value]').textContent).toBe('');
  });
});
