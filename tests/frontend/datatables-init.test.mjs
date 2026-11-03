import { describe, it, expect, beforeEach } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = '';
  await loadModule('static/js/datatables-init.js');
});

describe('datatables-init.js', () => {
  it('loads without error', () => {
    expect(true).toBe(true);
  });
});
