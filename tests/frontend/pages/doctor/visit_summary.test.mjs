import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <form id="visitSummaryForm">
      <input name="csrf_token" value="test" />
    </form>
  `;
  window.__M0__ = '/api/test/visit-summary';
  window.__M1__ = '/doctor/dashboard';
  window.API_ROUTES = {};
  window.notify = { success: vi.fn(), error: vi.fn() };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
});

describe('doctor/visit_summary.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/doctor/visit_summary.js');
  });
});
