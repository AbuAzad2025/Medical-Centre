import { describe, it, expect, beforeEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = '<form></form>';
  await loadModule('static/js/app.js');
  document.dispatchEvent(new Event('DOMContentLoaded'));
  // wait for async imports
  await new Promise(r => setTimeout(r, 50));
});

describe('app.js', () => {
  it('loads without error', () => {
    expect(true).toBe(true);
  });
});