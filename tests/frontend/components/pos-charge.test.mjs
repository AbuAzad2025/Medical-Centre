import { describe, it, expect, beforeEach } from 'vitest';
import { loadModule } from '../test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = '';
  await loadModule('static/js/components/pos-charge.js');
});

describe('pos-charge.js', () => {
  it('loads without error', () => {
    expect(true).toBe(true);
  });
});
