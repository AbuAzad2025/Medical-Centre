import { describe, it, expect, beforeEach } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = `
    <span id="cpu-usage"></span>
    <span id="memory-usage"></span>
    <span id="disk-usage"></span>
    <span id="uptime"></span>
  `;
  window.__M = [];
  await loadModule('static/js/pages/super_admin/performance.js');
});

describe('super_admin/performance.js', () => {
  it('loads without error', () => {
    expect(true).toBe(true);
  });
});