import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <div id="doctorPanels">
      <div class="dashboard-panel" data-panel="panel1"></div>
      <div class="dashboard-panel" data-panel="panel2"></div>
    </div>
    <div id="dashboardSettingsList"></div>
    <button id="saveDashboardSettings"></button>
    <div data-stat="today-visits"></div>
    <div data-stat="waiting"></div>
  `;
  window.__M0__ = '/api/test/layout';
  window.__M1__ = 'csrf-token';
  window.__M2__ = '/doctor/queue';
  window.__M3__ = '/doctor/prescriptions';
  window.__M4__ = '/doctor/lab-results';
  window.__M5__ = '/doctor/appointments';
  window.API_ROUTES = { doctor_dashboard_stats: '/api/stats' };
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn() };
  window.Toast = { fire: vi.fn() };
  window.notify = { warning: vi.fn(), error: vi.fn() };
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ items: [{ id: 'panel1', order: 1, enabled: true }, { id: 'panel2', order: 2, enabled: false }], success: true, stats: { today_visits: 5, waiting_patients: 3, in_progress: 1, completed_today: 10, prescriptions_today: 8, appointments_today: 6, pending_lab: 2, pending_radiology: 1 } })
  });
});

describe('doctor/dashboard.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/doctor/dashboard.js');
  });
});
