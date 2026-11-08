import { describe, it, expect, beforeEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = `<div id="usersContainer"></div><table id="usersTable"><tbody></tbody></table>`;
  window.__M = [];
  window.API_ROUTES = {};
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ users: [] }) });
  global.URL.createObjectURL = vi.fn(() => 'blob:x');
  global.URL.revokeObjectURL = vi.fn();
  await loadModule('static/js/pages/manager/user_management.js');
});

describe('manager/user_management.js', () => {
  it('loads without error', () => {
    expect(true).toBe(true);
  });
});
