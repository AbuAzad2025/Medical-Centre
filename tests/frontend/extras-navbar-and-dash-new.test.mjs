import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function makeChart() {
  window.Chart = vi.fn().mockImplementation(() => ({}));
  window.Chart.defaults = { plugins: { tooltip: {}, legend: { labels: {} } }, font: {} };
}

beforeEach(() => {
  document.body.innerHTML = `
    <div id="currentDate"></div>
    <div id="currentTime"></div>
  `;
  makeChart();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('_navbar.js', () => {
  it('writes date and time on load', async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-11-08T09:30:00'));
    await loadModule('static/js/pages/partials/_navbar.js');
    expect(document.getElementById('currentDate').textContent.length).toBeGreaterThan(0);
    expect(document.getElementById('currentTime').textContent).toMatch(/[\d٠-٩]{1,2}:[\d٠-٩]{2}/);
    vi.useRealTimers();
  });

  it('setInterval updates clock periodically', async () => {
    vi.useFakeTimers();
    await loadModule('static/js/pages/partials/_navbar.js');
    const before = document.getElementById('currentTime').textContent;
    vi.advanceTimersByTime(1000);
    expect(before).toBeDefined();
    vi.useRealTimers();
  });

  it('missing clock elements do not throw', async () => {
    document.body.innerHTML = '';
    vi.useFakeTimers();
    await loadModule('static/js/pages/partials/_navbar.js');
    expect(document.getElementById('currentTime')).toBeNull();
    vi.useRealTimers();
  });

  it('exposes window.updateClock', async () => {
    await loadModule('static/js/pages/partials/_navbar.js');
    expect(typeof window.updateClock).toBe('function');
  });
});

describe('accountant/dashboard_new.js', () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <script type="application/json" id="acc-chart-data">{"spark":[10,20,30,40],"mainData":[5,10,15,20,25]}</script>
      <canvas id="sparkToday"></canvas>
      <canvas id="sparkMonth"></canvas>
      <canvas id="sparkPending"></canvas>
      <canvas id="sparkHealth"></canvas>
      <canvas id="accMainChart"></canvas>
      <div class="progress-dynamic" data-width="55"></div>
    `;
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({});
  });

  it('renders charts when data element present', async () => {
    await loadModule('static/js/pages/accountant/dashboard_new.js');
    expect(window.Chart).toHaveBeenCalled();
    expect(document.querySelector('.progress-dynamic').style.width).toBe('55%');
  });

  it('skips chart rendering when data element missing', async () => {
    document.body.innerHTML = '';
    await loadModule('static/js/pages/accountant/dashboard_new.js');
    expect(window.Chart).not.toHaveBeenCalled();
  });
});

describe('nurse/dashboard_new.js', () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <script type="application/json" id="nurse-chart-data">{"spark":[7,11,5,9],"mainData":[3,6,9,12,15]}</script>
      <canvas id="sparkToday"></canvas>
      <canvas id="sparkActive"></canvas>
      <canvas id="sparkTasks"></canvas>
      <canvas id="sparkEff"></canvas>
      <canvas id="nurseMainChart"></canvas>
      <div class="progress-dynamic" data-width="80"></div>
    `;
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({});
  });

  it('renders charts and progress when data present', async () => {
    await loadModule('static/js/pages/nurse/dashboard_new.js');
    expect(window.Chart).toHaveBeenCalled();
    expect(document.querySelector('.progress-dynamic').style.width).toBe('80%');
  });

  it('skips rendering when data missing', async () => {
    document.body.innerHTML = '';
    await loadModule('static/js/pages/nurse/dashboard_new.js');
    expect(window.Chart).not.toHaveBeenCalled();
  });
});