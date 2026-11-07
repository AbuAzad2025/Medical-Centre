import { describe, it, expect, beforeEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = `
    <div id="queueContainer"></div>
    <table id="queueTable"><tbody></tbody></table>
    <button id="refreshQueue">Refresh</button>
    <select id="statusFilter"><option value="">All</option></select>
    <input id="searchQueue" />
  `;
  window.__M = [];
  window.API_ROUTES = { queue_list: '/api/queue', queue_update: '/api/queue/update' };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ queue: [] }) });
  await loadModule('static/js/pages/reception/queue_management.js');
});

describe('reception/queue_management.js', () => {
  it('loads without error', () => {
    expect(true).toBe(true);
  });
});