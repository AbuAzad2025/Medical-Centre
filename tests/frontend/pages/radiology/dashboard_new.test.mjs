import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <div id="rad-chart-data">{"spark":[10,20,5,3],"mainData":[1,2,3,4,5],"equipment":[3,1]}</div>
    <canvas id="sparkToday"></canvas>
    <canvas id="sparkCompleted"></canvas>
    <canvas id="sparkTime"></canvas>
    <canvas id="sparkQuality"></canvas>
    <canvas id="radMainChart"></canvas>
    <canvas id="equipmentChart"></canvas>
  `;
  const MockChart = function() { return { toBase64Image: vi.fn(), destroy: vi.fn() }; };
  MockChart.defaults = {
    plugins: { tooltip: {}, legend: { labels: {} } },
    font: { family: '' }
  };
  window.Chart = MockChart;
});

describe('radiology/dashboard_new.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/radiology/dashboard_new.js');
  });
});
