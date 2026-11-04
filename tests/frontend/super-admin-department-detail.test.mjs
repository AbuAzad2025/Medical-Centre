import { describe, it, expect, beforeEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = `<meta name="csrf-token" content="tok" />`;
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.API_ROUTES = {};
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
  await loadModule('static/js/pages/super_admin/department_detail.js');
});

describe('super_admin/department_detail.js', () => {
  it('loads without error', () => {
    expect(true).toBe(true);
  });
});