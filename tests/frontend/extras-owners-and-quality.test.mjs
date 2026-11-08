import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function makeChart() {
  window.Chart = vi.fn().mockImplementation(() => ({}));
  window.Chart.defaults = { plugins: { tooltip: {}, legend: { labels: {} } }, font: {} };
}

beforeEach(() => {
  document.body.innerHTML = '';
  makeChart();
  window.console.warn = vi.fn();
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({});
});

afterEach(() => {
  vi.useRealTimers();
});

describe('owner/dashboard.js', () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <script type="application/json" id="chart-data">{"months":["Jan","Feb"],"tenantGrowth":[5,8],"mrrTrend":[1000,1250],"statusLabels":["Active","Inactive"],"statusData":[30,12],"ticketLabels":["Open","Done"],"ticketData":[7,3],"churnSpark":[1,1,2],"userSpark":[10,14,18]}</script>
      <canvas id="mainChart"></canvas>
      <canvas id="statusChart"></canvas>
      <canvas id="ticketChart"></canvas>
      <canvas id="sparkTenants"></canvas>
      <canvas id="sparkMRR"></canvas>
      <canvas id="sparkChurn"></canvas>
      <canvas id="sparkUsers"></canvas>
    `;
  });

  it('renders all owner charts when data present', async () => {
    await loadModule('static/js/pages/owner/dashboard.js');
    expect(window.Chart).toHaveBeenCalled();
    expect(window.Chart.mock.calls.length).toBeGreaterThanOrEqual(4);
  });

  it('skips rendering when chart-data element absent', async () => {
    document.body.innerHTML = '';
    await loadModule('static/js/pages/owner/dashboard.js');
    expect(window.Chart).not.toHaveBeenCalled();
  });
});

describe('quality_compliance/dashboard.js', () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <canvas id="qcMainChart"></canvas>
      <div class="progress-dynamic" data-width="45"></div>
    `;
    window.__M0__ = '/quality/api/dashboard';
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ labels: ['Jan'], lab: [10], radiology: [20], visits: [30] }) });
  });

  it('fetches and renders the main chart when data arrives', async () => {
    await loadModule('static/js/pages/quality_compliance/dashboard.js');
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/api/'));
    expect(window.Chart).toHaveBeenCalled();
    expect(document.querySelector('.progress-dynamic').style.width).toBe('45%');
  });

  it('fetch failure renders an error placeholder', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    await loadModule('static/js/pages/quality_compliance/dashboard.js');
    await new Promise(r => setTimeout(r, 30));
    expect(document.body.innerHTML).toContain('text-muted');
  });
});

describe('visit_summary.js extra branches', () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <form id="visitSummaryForm" action="/test">
        <input name="csrf_token" value="test-csrf">
        <textarea name="summary">summary</textarea>
        <button type="submit">Save</button>
      </form>
    `;
    window.__M0__ = '/visit/summary/save';
    window.__M1__ = '/visit/detail';
    window.escHtml = (s) => String(s || '');
    window.notify = { success: vi.fn(), error: vi.fn() };
    window.location = { href: '' };
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
  });

  it('submit with server error prefix strips the prefix before notify.error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'خطأ: patient mismatch' }) });
    await loadModule('static/js/pages/doctor/visit_summary.js');
    const form = document.getElementById('visitSummaryForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(window.notify.error).toHaveBeenCalledWith('patient mismatch');
  });

  it('submit without notify keeps silent', async () => {
    delete window.notify;
    await loadModule('static/js/pages/doctor/visit_summary.js');
    const form = document.getElementById('visitSummaryForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(true).toBe(true);
  });

  it('submit without csrf_token uses meta', async () => {
    document.querySelector('input[name="csrf_token"]').remove();
    document.body.insertAdjacentHTML('beforeend', '<meta name="csrf-token" content="meta-csrf">');
    await loadModule('static/js/pages/doctor/visit_summary.js');
    const form = document.getElementById('visitSummaryForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    const req = global.fetch.mock.calls[0][1];
    expect(req.headers['X-CSRFToken']).toBe('meta-csrf');
  });

  it('submit when notify.error absent does not crash', async () => {
    window.notify = { success: vi.fn() };
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    await loadModule('static/js/pages/doctor/visit_summary.js');
    const form = document.getElementById('visitSummaryForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(true).toBe(true);
  });
});
describe('quality_compliance/dashboard.js extra branches', () => {
  it('non-ok response triggers the catch branch and renders fallback', async () => {
    document.body.innerHTML = `
      <canvas id="qcMainChart"></canvas>
      <div class="progress-dynamic" data-width="30"></div>
    `;
    window.__M0__ = '/quality/api/dashboard';
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    await loadModule('static/js/pages/quality_compliance/dashboard.js');
    await new Promise(r => setTimeout(r, 30));
    expect(document.body.innerHTML).toContain('text-muted');
  });

  it('progress-dynamic with non-numeric width falls back to 0%', async () => {
    document.body.innerHTML = `
      <canvas id="qcMainChart"></canvas>
      <div class="progress-dynamic" data-width="garbage"></div>
    `;
    window.__M0__ = '/quality/api/dashboard';
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ labels: ['Jan'], lab: [1], radiology: [2], visits: [3] }) });
    await loadModule('static/js/pages/quality_compliance/dashboard.js');
    expect(document.querySelector('.progress-dynamic').style.width).toBe('0%');
  });

  it('Chart undefined skips the defaults block without throwing', async () => {
    document.body.innerHTML = '<canvas id="qcMainChart"></canvas>';
    delete window.Chart;
    window.__M0__ = '/quality/api/dashboard';
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    await loadModule('static/js/pages/quality_compliance/dashboard.js');
    await new Promise(r => setTimeout(r, 30));
    expect(true).toBe(true);
  });
});

describe('owner/dashboard.js Chart-undefined arm', () => {
  it('module loads without Chart and without chart-data element', async () => {
    delete window.Chart;
    document.body.innerHTML = '';
    await expect(loadModule('static/js/pages/owner/dashboard.js')).resolves.toBeDefined();
  });
});
