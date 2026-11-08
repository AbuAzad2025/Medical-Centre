import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function makeChartMock(withLabelsFont = true) {
  window.Chart = vi.fn().mockImplementation(() => ({}));
  window.Chart.defaults = { plugins: { tooltip: {}, legend: { labels: withLabelsFont ? { font: {} } : {} } }, font: {} };
}

function emergencyDom() {
  document.body.innerHTML = `
    <canvas id="sparkToday"></canvas>
    <canvas id="sparkCompleted"></canvas>
    <canvas id="sparkCritical"></canvas>
    <canvas id="sparkRx"></canvas>
    <canvas id="emgMainChart"></canvas>
    <script type="application/json" id="emg-chart-data">{"spark":[7,11,5,9],"mainData":[3,6,9,12,15]}</script>
  `;
}
function labDom() {
  document.body.innerHTML = `
    <canvas id="sparkToday"></canvas>
    <canvas id="sparkCompleted"></canvas>
    <canvas id="sparkTime"></canvas>
    <canvas id="sparkQuality"></canvas>
    <canvas id="labMainChart"></canvas>
    <canvas id="equipmentChart"></canvas>
    <div class="progress-dynamic" data-width="45"></div>
    <script type="application/json" id="lab-chart-data">{"spark":[7,11,5,9],"mainData":[3,6,9,12,15],"equipment":[12,3]}</script>
  `;
}
function radiologyDom() {
  document.body.innerHTML = `
    <canvas id="sparkToday"></canvas>
    <canvas id="sparkCompleted"></canvas>
    <canvas id="sparkTime"></canvas>
    <canvas id="sparkQuality"></canvas>
    <canvas id="radMainChart"></canvas>
    <canvas id="equipmentChart"></canvas>
    <div class="progress-dynamic" data-width="65"></div>
    <script type="application/json" id="rad-chart-data">{"spark":[7,11,5,9],"mainData":[3,6,9,12,15],"equipment":[12,3]}</script>
  `;
}

const CASES = [
  ['static/js/pages/emergency/dashboard_new.js', emergencyDom, ['sparkToday', 'sparkCompleted', 'sparkCritical', 'sparkRx', 'emgMainChart'], 5, 'emg-chart-data'],
  ['static/js/pages/lab/dashboard_new.js', labDom, ['sparkToday', 'sparkCompleted', 'sparkTime', 'sparkQuality', 'labMainChart', 'equipmentChart'], 6, 'lab-chart-data'],
  ['static/js/pages/radiology/dashboard_new.js', radiologyDom, ['sparkToday', 'sparkCompleted', 'sparkTime', 'sparkQuality', 'radMainChart', 'equipmentChart'], 6, 'rad-chart-data'],
];

beforeEach(() => {
  window.__M = [];
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({});
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('dashboard_new fallback arms', () => {
  it('accountant and nurse dashboards tolerate missing chart data elements', async () => {
    makeChartMock(true);
    document.body.innerHTML = '';
    await loadModule('static/js/pages/accountant/dashboard_new.js');
    await loadModule('static/js/pages/nurse/dashboard_new.js');
    expect(window.Chart).not.toHaveBeenCalled();
  });

  it('Chart defaults labels.font fallback works when font is absent', async () => {
    makeChartMock(false);
    document.body.innerHTML = '';
    await loadModule('static/js/pages/accountant/dashboard_new.js');
    expect(window.Chart.defaults.plugins.legend.labels.font).toEqual({});
  });

  it('window.__M preset is respected without crashing', async () => {
    makeChartMock(true);
    window.__M = ['preset'];
    document.body.innerHTML = '';
    await loadModule('static/js/pages/accountant/dashboard_new.js');
    expect(window.__M).toEqual(['preset']);
  });

  for (const [modulePath, dom, chartIds, expectedCalls, dataId] of CASES) {
    it(`${modulePath}: renders all charts when data is present`, async () => {
      makeChartMock(true);
      dom();
      await loadModule(modulePath);
      expect(window.Chart).toHaveBeenCalledTimes(expectedCalls);
    });

    it(`${modulePath}: no chart data element means no charts`, async () => {
      makeChartMock(true);
      dom();
      document.getElementById(dataId).remove();
      await loadModule(modulePath);
      expect(window.Chart).not.toHaveBeenCalled();
    });
  }

  it('lab and radiology progress-dynamic bars render their width', async () => {
    makeChartMock(true);
    labDom();
    await loadModule('static/js/pages/lab/dashboard_new.js');
    expect(document.querySelector('.progress-dynamic').style.width).toBe('45%');
    document.body.innerHTML = '';
    radiologyDom();
    await loadModule('static/js/pages/radiology/dashboard_new.js');
    expect(document.querySelector('.progress-dynamic').style.width).toBe('65%');
  });

  it('progress-dynamic with garbage width falls back to 0%', async () => {
    makeChartMock(true);
    labDom();
    document.querySelector('.progress-dynamic').setAttribute('data-width', 'garbage');
    await loadModule('static/js/pages/lab/dashboard_new.js');
    expect(document.querySelector('.progress-dynamic').style.width).toBe('0%');
  });
});

describe('dashboard_new preset-arm coverage for emergency/lab/radiology', () => {
  for (const modulePath of [
    'static/js/pages/emergency/dashboard_new.js',
    'static/js/pages/lab/dashboard_new.js',
    'static/js/pages/radiology/dashboard_new.js',
    'static/js/pages/nurse/dashboard_new.js',
  ]) {
    it(`${modulePath}: preset font and preset __M are respected`, async () => {
      makeChartMock(true);
      window.Chart.defaults.plugins.legend.labels.font = { size: 16 };
      window.__M = ['preset'];
      document.body.innerHTML = '';
      await loadModule(modulePath);
      expect(window.Chart.defaults.plugins.legend.labels.font).toEqual({ size: 16 });
      expect(window.__M).toEqual(['preset']);
      delete window.__M;
    });
  }
});
