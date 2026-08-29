import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = '<div id="app"></div>';
  window.__M0__ = '/api/test/visits';
  window.__M1__ = true;
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.Toast = { fire: vi.fn() };
  window.bootstrap = { Modal: { getOrCreateInstance: () => ({ show: vi.fn(), hide: vi.fn() }) } };
  delete window.location;
  window.location = { href: '', reload: vi.fn(), search: '' };
});

describe('reception/visits.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/reception/visits.js');
  });
});
