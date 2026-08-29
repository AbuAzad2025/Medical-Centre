import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <textarea id="medical_notes"></textarea>
    <select id="note_template_select"></select>
    <button id="apply_note_template_btn"></button>
    <div id="doctorNoteTemplatesModal"></div>
    <form id="doctorNoteTemplateForm">
      <input id="dnt_id" value="" />
      <input id="dnt_name" value="" />
      <textarea id="dnt_text"></textarea>
      <input type="checkbox" id="dnt_active" checked />
    </form>
    <tbody id="dnt_table_body"></tbody>
    <button id="dnt_refresh_btn"></button>
    <button id="dnt_reset_btn"></button>
    <form>
      <input name="csrf_token" value="test" />
    </form>
  `;
  window.__M0__ = '/api/test/templates';
  window.__M1__ = '/api/test/template-save';
  window.__M2__ = '/api/test/template-delete/__T__';
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.Toast = { fire: vi.fn() };
  window.notify = { success: vi.fn(), error: vi.fn(), confirm: vi.fn((msg, cb) => cb()) };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ templates: [] }) });
});

describe('doctor/notes.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/doctor/notes.js');
  });
});
