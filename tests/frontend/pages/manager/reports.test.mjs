import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <div id="app"></div>
    <table id="reportsTable"><tbody>
      <tr data-type="recent"><td>Report 1</td></tr>
      <tr data-type="favorite"><td>Report 2</td></tr>
    </tbody></table>
    <button class="btn-outline-primary">All</button>
    <button class="btn-outline-success">Recent</button>
    <form id="customReportForm">
      <input name="report_type" value="" />
      <input name="date_from" value="" />
      <input name="date_to" value="" />
    </form>
  `;
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
});

describe('manager/reports.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/manager/reports.js');
  });

  test('filterReports is a function', async () => {
    await loadScript('static/js/pages/manager/reports.js');
    expect(typeof filterReports).toBe('function');
  });

  test('generateReport is a function', async () => {
    await loadScript('static/js/pages/manager/reports.js');
    expect(typeof generateReport).toBe('function');
  });

  test('filterReports with event parameter', async () => {
    await loadScript('static/js/pages/manager/reports.js');
    const btn = document.querySelector('.btn-outline-primary');
    const event = { target: btn };
    filterReports('all', event);
    expect(btn.classList.contains('active')).toBe(true);
  });
});
