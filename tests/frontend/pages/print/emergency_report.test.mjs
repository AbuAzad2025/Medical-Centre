import { describe, it, expect, beforeEach } from 'vitest';
import { loadModule } from '../test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = '';
  await loadModule('static/js/pages/print/emergency_report.js');
});

describe('emergency_report.js', () => {
  it('loads without error', () => {
    expect(true).toBe(true);
  });
});
