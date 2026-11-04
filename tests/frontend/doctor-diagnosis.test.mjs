import { describe, it, expect, beforeEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(async () => {
  vi.useFakeTimers();
  document.body.innerHTML = `
    <form action="/save">
      <input name="csrf_token" value="tok" />
      <textarea name="notes"></textarea>
    </form>
  `;
  window.showToast = vi.fn();
  global.fetch = vi.fn().mockResolvedValue({ ok: true });
  await loadModule('static/js/pages/doctor/diagnosis.js');
  // trigger DOMContentLoaded
  document.dispatchEvent(new Event('DOMContentLoaded'));
});

afterEach(() => {
  vi.useRealTimers();
});

describe('doctor/diagnosis.js', () => {
  it('loads without error', () => {
    expect(true).toBe(true);
  });
});