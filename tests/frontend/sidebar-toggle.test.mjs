import { describe, it, expect, beforeEach } from 'vitest';
import { loadModule } from '../test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = '';
  await loadModule('static/js/sidebar-toggle.js');
});

describe('sidebar-toggle.js', () => {
  it('loads without error', () => {
    expect(true).toBe(true);
  });
});
