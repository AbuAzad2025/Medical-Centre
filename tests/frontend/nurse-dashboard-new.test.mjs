import { describe, it, expect, beforeEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(async () => {
  window.Chart = vi.fn().mockImplementation(() => ({}));
  window.Chart.defaults = { plugins: { tooltip: {}, legend: { labels: { font: {} } } }, font: {} };
  document.body.innerHTML = `
    <script type="application/json" id="nurse-chart-data">{"spark":[1,2,3,4],"mainData":[10,20,30,40,50]}</script>
    <canvas id="sparkToday"></canvas>
    <canvas id="sparkActive"></canvas>
    <canvas id="sparkTasks"></canvas>
    <canvas id="sparkEff"></canvas>
    <canvas id="nurseMainChart"></canvas>
    <div class="progress-dynamic" data-width="50"></div>
  `;
  window.__M = [];
  window.__M0__ = 0;
  await loadModule('static/js/pages/nurse/dashboard_new.js');
});

describe('nurse/dashboard_new.js', () => {
  it('loads without error', () => {
    expect(true).toBe(true);
  });
});