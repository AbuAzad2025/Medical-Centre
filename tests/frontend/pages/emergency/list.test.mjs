import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadModule } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = '<div id="app"></div>';
  window.API_ROUTES = {};
});

describe('emergency/list.js', () => {
  test('loads without critical errors', async () => {
    await loadModule('static/js/pages/emergency/list.js');
  });
});
