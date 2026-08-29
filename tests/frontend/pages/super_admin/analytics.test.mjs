import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <div id="app"></div>
    <canvas id="usageChart"></canvas>
    <canvas id="userDistributionChart"></canvas>
  `;
  window.__M0__ = [];
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn() };
  window.Chart = vi.fn(() => ({}));
  window.Chart.defaults = {
    plugins: { tooltip: {}, legend: { labels: {} } },
    font: { family: '' }
  };
});

describe('super_admin/analytics.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/super_admin/analytics.js');
  });

  test('exportAnalytics is a function', async () => {
    await loadScript('static/js/pages/super_admin/analytics.js');
    expect(typeof exportAnalytics).toBe('function');
  });

  test('refreshAnalytics is a function', async () => {
    await loadScript('static/js/pages/super_admin/analytics.js');
    expect(typeof refreshAnalytics).toBe('function');
  });
});
