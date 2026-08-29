import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <button id="runWhatIf"></button>
    <input id="what_if_staff" value="2" />
    <input id="what_if_rooms" value="1" />
    <span id="whatIfThroughput"></span>
    <span id="whatIfWait"></span>
    <span id="whatIfRevenue"></span>
    <meta name="csrf-token" content="test-token" />
  `;
  window.__M0__ = '/api/test/what-if';
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn() };
  window.Toast = { fire: vi.fn() };
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ predicted_throughput: 100, predicted_wait_minutes: 5, predicted_revenue: 5000 })
  });
});

describe('manager/dashboard.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/manager/dashboard.js');
  });

  test('runWhatIf button exists', async () => {
    await loadScript('static/js/pages/manager/dashboard.js');
    expect(document.getElementById('runWhatIf')).not.toBeNull();
  });
});
