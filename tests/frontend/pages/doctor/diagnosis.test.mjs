import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <form action="/test" method="POST">
      <input name="csrf_token" value="test" />
      <input name="field1" value="" />
      <textarea name="notes"></textarea>
    </form>
  `;
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  window.Toast = { fire: vi.fn() };
  global.fetch = vi.fn().mockResolvedValue({ ok: true });
});

describe('doctor/diagnosis.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/doctor/diagnosis.js');
  });
});
