import { describe, it, expect, beforeEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(async () => {
  window.Chart = vi.fn().mockImplementation(() => ({}));
  window.Chart.defaults = { plugins: { tooltip: {}, legend: { labels: { font: {} } } }, font: {} };
  document.body.innerHTML = `
    <script type="application/json" id="chart-data">{"months":["Jan","Feb"],"tenantGrowth":[1,2],"mrrTrend":[3,4],"statusLabels":["A"],"statusData":[5],"ticketLabels":["T"],"ticketData":[6],"churnSpark":[1,2],"userSpark":[3,4]}</script>
    <canvas id="mainChart"></canvas>
    <canvas id="statusChart"></canvas>
    <canvas id="ticketChart"></canvas>
    <canvas id="sparkTenants"></canvas>
    <canvas id="sparkMRR"></canvas>
    <canvas id="sparkChurn"></canvas>
    <canvas id="sparkUsers"></canvas>
  `;
  window.__M = [];
  window.__M0__ = 0;
  await loadModule('static/js/pages/owner/dashboard.js');
});

describe('owner/dashboard.js', () => {
  it('loads without error', () => {
    expect(true).toBe(true);
  });
});