import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <meta name="csrf-token" content="test-csrf">
    <textarea id="medical_notes"></textarea>
    <select id="note_template_select"></select>
    <button id="apply_note_template_btn">Apply</button>
    <div id="doctorNoteTemplatesModal"></div>
    <form id="doctorNoteTemplateForm">
      <input id="dnt_id" value="">
      <input id="dnt_name" value="">
      <textarea id="dnt_text"></textarea>
      <input type="checkbox" id="dnt_active" checked>
    </form>
    <table><tbody id="dnt_table_body"></tbody></table>
    <button id="dnt_refresh_btn">Refresh</button>
    <button id="dnt_reset_btn">Reset</button>
    <form id="notesForm"></form>
  `;
}

const TEMPLATES = [
  { id: '1', name: 'Welcome', text: 'مرحبا بك', is_active: true },
];

beforeEach(() => {
  baseDom();
  window.__M0__ = '/api/note-templates';
  window.__M1__ = '/api/note-templates/save';
  window.__M2__ = '/api/note-templates/delete/__T__';
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.notify = { warning: vi.fn(), error: vi.fn(), success: vi.fn(), confirm: vi.fn((msg, cb) => cb()) };
  window.showToast = vi.fn();
  window.sessionStorage.clear();
  global.fetch = vi.fn((url) => {
    const u = String(url);
    if (u.includes('note-templates/save')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true }) });
    if (u.includes('note-templates/delete')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true }) });
    if (u.includes('note-templates')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: TEMPLATES }) });
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
  });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('doctor/notes.js', () => {
  it('autoResize sets height to scrollHeight', async () => {
    const mod = await loadModule('static/js/pages/doctor/notes.js');
    const el = document.getElementById('medical_notes');
    Object.defineProperty(el, 'scrollHeight', { value: 321, configurable: true });
    mod.autoResize();
    expect(el.style.height).toBe('321px');
  });

  it('fetchTemplates retrieves templates', async () => {
    const mod = await loadModule('static/js/pages/doctor/notes.js');
    const out = await mod.fetchTemplates();
    expect(out).toEqual(TEMPLATES);
  });

  it('fetchTemplates on failure shows toast', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/doctor/notes.js');
    await mod.fetchTemplates();
    expect(window.showToast).toHaveBeenCalled();
  });

  it('fillTemplateSelect renders active templates', async () => {
    const mod = await loadModule('static/js/pages/doctor/notes.js');
    mod.fillTemplateSelect(TEMPLATES);
    const sel = document.getElementById('note_template_select');
    expect(sel.innerHTML).toContain('Welcome');
  });

  it('fillTemplateSelect keeps prior selection', async () => {
    const mod = await loadModule('static/js/pages/doctor/notes.js');
    document.getElementById('note_template_select').innerHTML = '<option value="1" selected>Welcome</option>';
    document.getElementById('note_template_select').value = '1';
    mod.fillTemplateSelect(TEMPLATES);
    expect(document.getElementById('note_template_select').value).toBe('1');
  });

  it('resetTemplateForm clears inputs', async () => {
    const mod = await loadModule('static/js/pages/doctor/notes.js');
    document.getElementById('dnt_id').value = '5';
    document.getElementById('dnt_name').value = 'x';
    mod.resetTemplateForm();
    expect(document.getElementById('dnt_id').value).toBe('');
    expect(document.getElementById('dnt_active').checked).toBe(true);
  });

  it('renderTemplatesTable renders rows', async () => {
    const mod = await loadModule('static/js/pages/doctor/notes.js');
    document.getElementById('note_template_select').innerHTML = '';
    await mod.refreshTemplatesUI();
    expect(document.getElementById('dnt_table_body').innerHTML).toContain('Welcome');
  });

  it('apply button inserts template text into notes', async () => {
    await loadModule('static/js/pages/doctor/notes.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 30));
    document.getElementById('medical_notes').value = 'existing';
    document.getElementById('note_template_select').value = '1';
    document.getElementById('apply_note_template_btn').click();
    expect(document.getElementById('medical_notes').value).toContain('مرحبا بك');
  });

  it('apply button with no selection does nothing', async () => {
    await loadModule('static/js/pages/doctor/notes.js');
    document.getElementById('medical_notes').value = 'orig';
    document.getElementById('note_template_select').value = '';
    document.getElementById('apply_note_template_btn').click();
    expect(document.getElementById('medical_notes').value).toBe('orig');
  });

  it('DOMContentLoaded loads draft from sessionStorage', async () => {
    window.sessionStorage.setItem('medical_notes_draft', 'draft text');
    await loadModule('static/js/pages/doctor/notes.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(document.getElementById('medical_notes').value).toBe('draft text');
  });

  it('dntForm submit saves template and resets form', async () => {
    await loadModule('static/js/pages/doctor/notes.js');
    document.getElementById('dnt_name').value = 'NewT';
    document.getElementById('dnt_text').value = 'body';
    const form = document.getElementById('doctorNoteTemplateForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 50));
    expect(global.fetch).toHaveBeenCalledWith('/api/note-templates/save', expect.objectContaining({ method: 'POST' }));
  });

  it('dntForm submit failure shows notify error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    await loadModule('static/js/pages/doctor/notes.js');
    document.getElementById('dnt_name').value = 'NewT';
    document.getElementById('doctorNoteTemplateForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 50));
    expect(window.notify.error).toHaveBeenCalled();
  });

  it('dntTableBody edit button fills the form', async () => {
    await loadModule('static/js/pages/doctor/notes.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 30));
    const btn = document.querySelector('#dnt_table_body button[data-action="edit"]');
    expect(btn).toBeTruthy();
    btn.click();
    expect(document.getElementById('dnt_id').value).toBe('1');
  });

  it('dntTableBody delete button requests deletion', async () => {
    await loadModule('static/js/pages/doctor/notes.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 30));
    const btn = document.querySelector('#dnt_table_body button[data-action="delete"]');
    expect(btn).toBeTruthy();
    btn.click();
    await new Promise(r => setTimeout(r, 50));
    expect(global.fetch).toHaveBeenCalledWith('/api/note-templates/delete/1', expect.objectContaining({ method: 'POST' }));
  });

  it('dntResetBtn clears the form', async () => {
    await loadModule('static/js/pages/doctor/notes.js');
    document.getElementById('dnt_id').value = '3';
    document.getElementById('dnt_reset_btn').click();
    expect(document.getElementById('dnt_id').value).toBe('');
  });
});