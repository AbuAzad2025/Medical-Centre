import { describe, it, expect, beforeEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = `
    <form id="triageForm" action="/save">
      <input name="csrf_token" value="tok" />
      <input name="blood_pressure" value="120/80" />
      <input name="heart_rate" value="72" />
      <input name="temperature" value="37" />
      <input name="oxygen_saturation" value="98" />
      <input name="respiratory_rate" value="16" />
      <input name="pain_level" value="3" />
      <button type="submit">Save</button>
    </form>
  `;
  window.Swal = { fire: vi.fn() };
  window.__M = [];
  window.__M0__ = '/api/triage';
  window.__M1__ = '/redirect';
  window.location = { href: '' };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
  await loadModule('static/js/pages/emergency/triage.js');
});

describe('emergency/triage.js', () => {
  it('loads without error', () => {
    expect(true).toBe(true);
  });
});