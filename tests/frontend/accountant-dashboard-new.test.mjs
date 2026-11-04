import { describe, it, expect, beforeEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(async () => {
  window.Chart = vi.fn().mockImplementation(() => ({}));
  window.Chart.defaults = { plugins: { tooltip: {}, legend: { labels: { font: {} } } }, font: {} };
  document.body.innerHTML = `
    <script type="application/json" id="acc-chart-data">{"spark":[1,2,3,4],"mainData":[10,20,30,40,50]}</script>
    <canvas id="sparkToday"></canvas>
    <canvas id="sparkMonth"></canvas>
    <canvas id="sparkPending"></canvas>
    <canvas id="sparkHealth"></canvas>
    <canvas id="accMainChart"></canvas>
    <div class="progress-dynamic" data-width="50"></div>
  `;
  window.__M = [];
  window.__M0__ = 0;
  await loadModule('static/js/pages/accountant/dashboard_new.js');
});

describe('accountant/dashboard_new.js', () => {
  it('loads without error', () => {
    expect(true).toBe(true);
  });
});