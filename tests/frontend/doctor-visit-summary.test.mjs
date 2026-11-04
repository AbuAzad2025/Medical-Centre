import { describe, it, expect, beforeEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = `
    <form id="visitSummaryForm" action="/save">
      <input name="csrf_token" value="tok" />
      <button type="submit">Save</button>
    </form>
  `;
  window.__M = [];
  window.__M0__ = '/api/save';
  window.__M1__ = '/redirect';
  window.notify = { success: vi.fn(), error: vi.fn() };
  window.location = { href: '' };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
  await loadModule('static/js/pages/doctor/visit_summary.js');
});

describe('doctor/visit_summary.js', () => {
  it('loads without error', () => {
    expect(true).toBe(true);
  });
});