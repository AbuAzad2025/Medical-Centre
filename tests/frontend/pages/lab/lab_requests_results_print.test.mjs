import { describe, it, expect, beforeEach } from 'vitest';
import { loadModule } from '../../test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = '';
  await loadModule('static/js/pages/lab/lab_requests_results_print.js');
});

describe('lab_requests_results_print.js', () => {
  it('loads without error', () => {
    expect(true).toBe(true);
  });
});
