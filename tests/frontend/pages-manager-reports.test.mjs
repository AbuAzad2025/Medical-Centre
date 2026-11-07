import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <table id="reportsTable"><tbody><tr data-status="pending"><td>A</td></tr><tr data-status="favorite"><td>B</td></tr></tbody></table>
    <form id="customReportForm">
      <select name="report_type"><option value="">x</option><option value="sales">sales</option></select>
      <input name="date_from" type="date">
      <input name="date_to" type="date">
    </form>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M = [];
  window.escHtml = (s) => String(s || '');
  window.API_ROUTES = {};
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.bootstrap = { Collapse: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn() })) }, Modal: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn(), hide: vi.fn() })) } };
});

afterEach(() => {
  vi.useRealTimers();
});

describe('manager/reports.js', () => {
  it('generateReport shows info Swal', async () => {
    const mod = await loadModule('static/js/pages/manager/reports.js');
    mod.generateReport();
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('info');
  });

  it('exportAllReports shows info Swal', async () => {
    const mod = await loadModule('static/js/pages/manager/reports.js');
    mod.exportAllReports();
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('info');
  });

  it('viewPatientReports shows patient reports', async () => {
    const mod = await loadModule('static/js/pages/manager/reports.js');
    mod.viewPatientReports();
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('info');
  });

  it('viewFinancialReports shows financial reports', async () => {
    const mod = await loadModule('static/js/pages/manager/reports.js');
    mod.viewFinancialReports();
    expect(window.Swal.fire.mock.calls[0][0].text).toContain('التقارير المالية');
  });

  it('viewDoctorReports shows doctor reports', async () => {
    const mod = await loadModule('static/js/pages/manager/reports.js');
    mod.viewDoctorReports();
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('info');
  });

  it('viewAnalyticalReports shows analytics', async () => {
    const mod = await loadModule('static/js/pages/manager/reports.js');
    mod.viewAnalyticalReports();
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('info');
  });

  it('generateDailyReport creates daily report', async () => {
    const mod = await loadModule('static/js/pages/manager/reports.js');
    mod.generateDailyReport();
    expect(window.Swal.fire.mock.calls[0][0].text).toContain('يومي');
  });

  it('generateWeeklyReport creates weekly report', async () => {
    const mod = await loadModule('static/js/pages/manager/reports.js');
    mod.generateWeeklyReport();
    expect(window.Swal.fire.mock.calls[0][0].text).toContain('أسبوعي');
  });

  it('generateMonthlyReport creates monthly report', async () => {
    const mod = await loadModule('static/js/pages/manager/reports.js');
    mod.generateMonthlyReport();
    expect(window.Swal.fire.mock.calls[0][0].text).toContain('شهري');
  });

  it('generateCustomReport with missing fields shows warning', async () => {
    const mod = await loadModule('static/js/pages/manager/reports.js');
    document.querySelector('[name="report_type"]').value = '';
    mod.generateCustomReport();
    expect(window.Swal.fire.mock.calls[0][0].title).toBe('حقول مطلوبة');
  });

  it('generateCustomReport with complete fields shows info', async () => {
    const mod = await loadModule('static/js/pages/manager/reports.js');
    document.querySelector('[name="report_type"]').value = 'sales';
    document.querySelector('[name="date_from"]').value = '2026-01-01';
    document.querySelector('[name="date_to"]').value = '2026-12-31';
    mod.generateCustomReport();
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('info');
  });

  it('viewReport shows report details', async () => {
    const mod = await loadModule('static/js/pages/manager/reports.js');
    mod.viewReport('9');
    expect(window.Swal.fire.mock.calls[0][0].text).toContain('9');
  });

  it('downloadReport shows download info', async () => {
    const mod = await loadModule('static/js/pages/manager/reports.js');
    mod.downloadReport('9');
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('info');
  });

  it('shareReport shows share info', async () => {
    const mod = await loadModule('static/js/pages/manager/reports.js');
    mod.shareReport('9');
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('info');
  });

  it('deleteReport confirms then deletes', async () => {
    const mod = await loadModule('static/js/pages/manager/reports.js');
    await mod.deleteReport('9');
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('filterReports marks all rows visible', async () => {
    const mod = await loadModule('static/js/pages/manager/reports.js');
    mod.filterReports('all', null);
    const rows = document.querySelectorAll('#reportsTable tbody tr');
    expect(rows[0].style.display).toBe('');
    expect(rows[1].style.display).toBe('');
  });

  it('filterReports marks recent rows visible', async () => {
    const mod = await loadModule('static/js/pages/manager/reports.js');
    mod.filterReports('recent', null);
    const rows = document.querySelectorAll('#reportsTable tbody tr');
    expect(rows[0].style.display).toBe('');
  });

  it('filterReports marks favorite rows visible', async () => {
    const mod = await loadModule('static/js/pages/manager/reports.js');
    mod.filterReports('favorite', null);
    const rows = document.querySelectorAll('#reportsTable tbody tr');
    expect(rows[0].style.display).toBe('');
  });

  it('filterReports sets active class on the clicked button', async () => {
    const mod = await loadModule('static/js/pages/manager/reports.js');
    const btn = document.createElement('button');
    const event = { target: btn };
    mod.filterReports('all', event);
    expect(btn.classList.contains('active')).toBe(true);
  });

  it('DOMContentLoaded attaches hover handlers', async () => {
    await loadModule('static/js/pages/manager/reports.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const row = document.querySelector('#reportsTable tbody tr');
    row.dispatchEvent(new MouseEvent('mouseenter'));
    expect(row.style.backgroundColor).toBe('rgb(248, 249, 250)');
    row.dispatchEvent(new MouseEvent('mouseleave'));
    expect(row.style.backgroundColor).toBe('');
  });
});