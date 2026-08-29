import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = '<div id="app"></div>';
  window.__M0__ = '/api/test/emergency-visits';
  window.__M1__ = '/api/test/complete-visit';
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true, value: '' }) };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
  delete window.location;
  window.location = { href: '', reload: vi.fn() };
});

describe('emergency/emergency_visits.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/emergency/emergency_visits.js');
  });

  test('startTreatment is a function', async () => {
    await loadScript('static/js/pages/emergency/emergency_visits.js');
    expect(typeof startTreatment).toBe('function');
  });

  test('completeVisit is a function', async () => {
    await loadScript('static/js/pages/emergency/emergency_visits.js');
    expect(typeof completeVisit).toBe('function');
  });
});
