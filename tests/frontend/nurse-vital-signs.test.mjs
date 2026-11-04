import { describe, it, expect, beforeEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = `
    <form id="vitalSignsForm" action="/save">
      <input name="csrf_token" value="tok" />
      <button type="submit">Save</button>
    </form>
  `;
  window.location = { reload: vi.fn() };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
  await loadModule('static/js/pages/nurse/vital_signs.js');
  document.dispatchEvent(new Event('DOMContentLoaded'));
});

describe('nurse/vital_signs.js', () => {
  it('loads without error', () => {
    expect(true).toBe(true);
  });
});