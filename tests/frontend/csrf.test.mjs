import { describe, it, expect, beforeEach } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = '';
  await loadModule('static/js/csrf.js');
});

describe('csrf.js', () => {
  it('loads without error', () => {
    expect(true).toBe(true);
  });
});
