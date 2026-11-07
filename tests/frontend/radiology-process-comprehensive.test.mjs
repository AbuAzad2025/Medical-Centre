import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = `
    <input id="test_name" value="X-Ray" />
    <input id="body_part" value="Chest" />
    <select id="report_template"><option value="1">Template 1</option></select>
    <button id="apply_template_btn">Apply</button>
    <textarea id="findings"></textarea>
    <textarea id="results"></textarea>
    <textarea id="recommendations"></textarea>
    <div id="radiologyTemplatesModal"></div>
    <div id="radiologyMacrosModal"></div>
    <form id="radiologyTemplateForm">
      <input id="tpl_id" />
      <input id="tpl_name" />
      <select id="tpl_modality"><option value="XRAY">X-Ray</option></select>
      <textarea id="tpl_findings"></textarea>
      <textarea id="tpl_impression"></textarea>
      <textarea id="tpl_recommendations"></textarea>
      <input id="tpl_active" type="checkbox" />
    </form>
    <tbody id="tpl_table_body"></tbody>
    <button id="tpl_refresh_btn">Refresh</button>
    <button id="tpl_reset_btn">Reset</button>
  `;
  window.__M = [];
  window.__M0__ = '/api/apply-template';
  window.__M1__ = '/api/templates';
  window.__M2__ = '/api/macros';
  window.__M3__ = '__BODY_PART__';
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ success: true, templates: [], findings: 'test findings', impression: 'test impression', recommendations: 'test recs' }),
  });
  await loadModule('static/js/pages/radiology/process.js');
});

describe('radiology/process.js', () => {
  it('loads without error', () => {
    expect(true).toBe(true);
  });
});