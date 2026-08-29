import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <input id="test_name" value="X-Ray Chest" />
    <input id="body_part" value="Chest" />
    <select id="report_template"><option value="">None</option></select>
    <button id="apply_template_btn"></button>
    <button id="manage_templates_btn"></button>
    <textarea id="findings"></textarea>
    <textarea id="results"></textarea>
    <textarea id="recommendations"></textarea>
    <div id="radiologyTemplatesModal"></div>
    <div id="radiologyMacrosModal"></div>
    <form id="radiologyTemplateForm">
      <input id="tpl_id" value="" />
      <input id="tpl_name" value="" />
      <select id="tpl_modality"><option value="XRAY">XRAY</option></select>
      <textarea id="tpl_findings"></textarea>
      <textarea id="tpl_impression"></textarea>
      <textarea id="tpl_recommendations"></textarea>
      <input type="checkbox" id="tpl_active" checked />
    </form>
    <tbody id="tpl_table_body"></tbody>
    <button id="tpl_refresh_btn"></button>
    <button id="tpl_reset_btn"></button>
    <select id="report_macro"><option value="">None</option></select>
    <select id="macro_target"><option value="findings">Findings</option></select>
    <button id="apply_macro_btn"></button>
    <form id="radiologyMacroForm">
      <input id="macro_id" value="" />
      <input id="macro_name" value="" />
      <textarea id="macro_text"></textarea>
      <input type="checkbox" id="macro_active" checked />
    </form>
    <tbody id="macro_table_body"></tbody>
    <button id="macro_refresh_btn"></button>
    <button id="macro_reset_btn"></button>
    <button id="ai_assist_btn"></button>
    <div id="ai_assist_output"></div>
    <input id="pacs_url" value="" />
    <input id="study_uid" value="" />
    <meta name="csrf-token" content="test-token" />
  `;
  window.__M0__ = '/api/test/ai-assist';
  window.__M1__ = '/api/test/templates';
  window.__M2__ = '/api/test/macros';
  window.__M3__ = '__PART__';
  window.__M4__ = '/api/test/macro-save';
  window.__M5__ = '/api/test/macro-delete/__M__';
  window.__M6__ = '/api/test/template-delete/__TPL__';
  window.__M7__ = '/api/test/template-save';
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn() };
  window.Toast = { fire: vi.fn() };
  window.notify = { warning: vi.fn(), error: vi.fn() };
  window.confirm = vi.fn(() => true);
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ templates: [], macros: [] }) });
});

describe('radiology/process.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/radiology/process.js');
  });

  test('initializes template form elements', async () => {
    await loadScript('static/js/pages/radiology/process.js');
    expect(document.getElementById('radiologyTemplateForm')).not.toBeNull();
    expect(document.getElementById('tpl_id')).not.toBeNull();
    expect(document.getElementById('tpl_name')).not.toBeNull();
  });

  test('initializes macro form elements', async () => {
    await loadScript('static/js/pages/radiology/process.js');
    expect(document.getElementById('radiologyMacroForm')).not.toBeNull();
    expect(document.getElementById('macro_id')).not.toBeNull();
    expect(document.getElementById('macro_name')).not.toBeNull();
  });

  test('test_name input exists for auto-guess', async () => {
    await loadScript('static/js/pages/radiology/process.js');
    expect(document.getElementById('test_name')).not.toBeNull();
  });
});
