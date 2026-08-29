import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = '<div id="app"></div>';
  window.API_ROUTES = {};
});

describe('emergency/list.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/emergency/list.js');
  });
});
