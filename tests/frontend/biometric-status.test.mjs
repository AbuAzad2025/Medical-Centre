import { describe, it, expect, beforeEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = `
    <button id="registerBtn">Register</button>
    <div id="registerResult"></div>
  `;
  window.__M = [];
  window.__M0__ = '/api/biometric/register';
  global.fetch = vi.fn().mockResolvedValue({
    json: () => Promise.resolve({ success: true }),
  });
  await loadModule('static/js/pages/biometric/status.js');
});

describe('biometric/status.js', () => {
  it('loads without error', () => {
    expect(true).toBe(true);
  });
});