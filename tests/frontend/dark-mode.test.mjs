import { describe, it, expect, beforeEach } from 'vitest';
import { loadModule } from '../test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = '';
  await loadModule('static/js/dark-mode.js');
});

describe('dark-mode.js', () => {
  it('loads without error', () => {
    expect(true).toBe(true);
  });
});
