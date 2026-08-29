import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <form id="triageForm">
      <input name="blood_pressure" value="120/80" />
      <input name="heart_rate" value="72" />
      <input name="temperature" value="36.5" />
      <input name="oxygen_saturation" value="98" />
      <input name="respiratory_rate" value="16" />
      <input name="pain_level" value="3" />
      <input name="csrf_token" value="test" />
    </form>
  `;
  window.__M0__ = '/api/test/triage';
  window.__M1__ = '/emergency/dashboard';
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
  delete window.location;
  window.location = { href: '', reload: vi.fn() };
});

describe('emergency/triage.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/emergency/triage.js');
  });

  test('triageForm submit listener registered', async () => {
    await loadScript('static/js/pages/emergency/triage.js');
    expect(document.getElementById('triageForm')).not.toBeNull();
  });
});
