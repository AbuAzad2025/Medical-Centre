import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <div id="app"></div>
    <canvas id="qcMainChart"></canvas>
  `;
  window.__M0__ = '/api/test/qc-data';
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  window.Chart = vi.fn(() => ({}));
  window.Chart.defaults = {
    plugins: { tooltip: {}, legend: { labels: {} } },
    font: { family: '' }
  };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ labels: [], lab: [], radiology: [], visits: [] }) });
});

describe('quality_compliance/dashboard.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/quality_compliance/dashboard.js');
  });

  test('r.ok check exists in fetch call', async () => {
    const code = await import('fs').then(fs => fs.default.readFileSync('static/js/pages/quality_compliance/dashboard.js', 'utf-8'));
    expect(code).toContain('r.ok');
  });
});
