import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <form id="convertForm" action="/test"></form>
  `;
  window.__M0__ = '/emergency/dashboard';
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
  delete window.location;
  window.location = { href: '', reload: vi.fn() };
});

describe('emergency/view.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/emergency/view.js');
  });
});
