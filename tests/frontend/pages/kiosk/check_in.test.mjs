import { describe, it, expect, beforeEach } from 'vitest';
import { loadModule } from '../test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = '';
  await loadModule('static/js/pages/kiosk/check_in.js');
});

describe('check_in.js', () => {
  it('loads without error', () => {
    expect(true).toBe(true);
  });
});
