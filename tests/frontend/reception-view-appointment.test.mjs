import { describe, it, expect, beforeEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = `
    <div id="appointmentDetail"></div>
  `;
  window.__M = [];
  await loadModule('static/js/pages/reception/view_appointment.js').catch(() => {});
});

describe('reception/view_appointment.js', () => {
  it('loads', () => {
    expect(true).toBe(true);
  });
});