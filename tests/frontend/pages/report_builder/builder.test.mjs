import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <div id="app"></div>
    <select id="entitySelect"><option value="patients">Patients</option></select>
    <select id="templateSelect"><option value="">None</option></select>
    <div id="fieldsContainer"></div>
    <input id="limitInput" value="100" />
    <input id="templateName" value="" />
    <button id="generateBtn"></button>
    <button id="saveTemplateBtn"></button>
    <button id="runTemplateBtn" disabled></button>
    <div id="reportResult"></div>
  `;
  window.__M0__ = { patients: { fields: ['id', 'name', 'phone'] } };
  window.__M1__ = '/api/test/preview';
  window.__M2__ = 'csrf-token';
  window.__M3__ = '/api/test/save';
  window.__M4__ = '/api/test/list';
  window.__M5__ = {};
  window.__M6__ = null;
  window.__M7__ = '/api/test/template/';
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ success: true, headers: ['id', 'name'], rows: [{ id: 1, name: 'Test' }] })
  });
});

describe('report_builder/builder.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/report_builder/builder.js');
  });

  test('renderFieldsForEntity is a function', async () => {
    await loadScript('static/js/pages/report_builder/builder.js');
    expect(typeof renderFieldsForEntity).toBe('function');
  });

  test('collectPayload is a function', async () => {
    await loadScript('static/js/pages/report_builder/builder.js');
    expect(typeof collectPayload).toBe('function');
  });

  test('generateReport is a function', async () => {
    await loadScript('static/js/pages/report_builder/builder.js');
    expect(typeof generateReport).toBe('function');
  });

  test('renderFieldsForEntity renders checkboxes', async () => {
    await loadScript('static/js/pages/report_builder/builder.js');
    renderFieldsForEntity('patients', ['id']);
    const container = document.getElementById('fieldsContainer');
    expect(container.innerHTML).toContain('id');
    expect(container.innerHTML).toContain('name');
  });

  test('collectPayload returns expected structure', async () => {
    await loadScript('static/js/pages/report_builder/builder.js');
    const payload = collectPayload();
    expect(payload).toHaveProperty('entity');
    expect(payload).toHaveProperty('fields');
    expect(payload).toHaveProperty('limit');
    expect(payload).toHaveProperty('name');
  });
});
