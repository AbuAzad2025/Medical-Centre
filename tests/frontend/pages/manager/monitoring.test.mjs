import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <div id="app"></div>
  `;
  window.__M0__ = [];
  window.__M1__ = 5;
  window.__M2__ = 3;
  window.__M3__ = 2;
  window.__M4__ = 4;
  window.__M5__ = 1;
  window.__M6__ = 6;
  window.__M7__ = '/api/test/monitoring';
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, units_status: {} }) });
  delete window.location;
  window.location = { href: '', reload: vi.fn() };
});

describe('manager/monitoring.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/manager/monitoring.js');
  });

  test('exportMonitoringReport is a function', async () => {
    await loadScript('static/js/pages/manager/monitoring.js');
    expect(typeof exportMonitoringReport).toBe('function');
  });

  test('updateUnitStatus is a function', async () => {
    await loadScript('static/js/pages/manager/monitoring.js');
    expect(typeof updateUnitStatus).toBe('function');
  });

  test('viewUnitDetails is a function', async () => {
    await loadScript('static/js/pages/manager/monitoring.js');
    expect(typeof viewUnitDetails).toBe('function');
  });
});
