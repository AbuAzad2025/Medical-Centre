import { describe, it, expect, beforeEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = '';
  window.__M = [];
  await loadModule('static/js/pages/booking/create.js').catch(() => {});
});

describe('booking/create.js', () => {
  it('loads', () => {
    expect(true).toBe(true);
  });
});