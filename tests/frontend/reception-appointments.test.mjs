import { describe, it, expect, beforeEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = `
    <div id="appointmentsContainer"></div>
    <table id="appointmentsTable"><tbody></tbody></table>
    <input id="appointmentSearch" />
  `;
  window.__M = [];
  window.API_ROUTES = { appointments_list: '/api/appointments' };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ appointments: [] }) });
  await loadModule('static/js/pages/reception/appointments.js');
});

describe('reception/appointments.js', () => {
  it('loads without error', () => {
    expect(true).toBe(true);
  });
});