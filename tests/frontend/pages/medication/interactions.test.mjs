import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = '<div id="app"></div>';
  window.__M0__ = 'csrf-token';
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  window.Toast = { fire: vi.fn() };
  global.fetch = vi.fn().mockResolvedValue({ ok: true });
  delete window.location;
  window.location = { href: '', reload: vi.fn() };
});

describe('medication/interactions.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/medication/interactions.js');
  });

  test('toggleInteraction is a function', async () => {
    await loadScript('static/js/pages/medication/interactions.js');
    expect(typeof toggleInteraction).toBe('function');
  });

  test('toggleInteraction calls fetch with correct URL', async () => {
    await loadScript('static/js/pages/medication/interactions.js');
    await toggleInteraction(123);
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('123'),
      expect.objectContaining({ method: 'POST' })
    );
  });
});
