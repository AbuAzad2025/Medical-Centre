import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <meta name="csrf-token" content="csrf-notes">
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
  { id: '1', name: 'Welcome', text: 'مرحباً', is_active: true },
  { id: '2', name: 'Inactive', text: 'قديمة', is_active: false },
  { id: '3', name: 'NoName', is_active: true },
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
  window.console.warn = vi.fn();
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

describe('doctor/notes.js extra branches', () => {
  it('autoResize with missing noteTextEl does nothing', async () => {
    document.getElementById('medical_notes').remove();
    const mod = await loadModule('static/js/pages/doctor/notes.js');
    expect(() => mod.autoResize()).not.toThrow();
  });

  it('fetchTemplates non-ok response shows toast', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/doctor/notes.js');
    const out = await mod.fetchTemplates();
    expect(out).toBeUndefined();
    expect(window.showToast).toHaveBeenCalled();
  });

  it('fetchTemplates without templates key returns []', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
    const mod = await loadModule('static/js/pages/doctor/notes.js');
    expect(await mod.fetchTemplates()).toEqual([]);
  });

  it('fetchTemplates with non-array templates returns []', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ templates: 'nope' }) });
    const mod = await loadModule('static/js/pages/doctor/notes.js');
    expect(await mod.fetchTemplates()).toEqual([]);
  });

  it('fetchTemplates without showToast falls back to console.warn', async () => {
    delete window.showToast;
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/doctor/notes.js');
    await mod.fetchTemplates();
    expect(window.console.warn).toHaveBeenCalled();
  });

  it('fillTemplateSelect filters inactive templates', async () => {
    const mod = await loadModule('static/js/pages/doctor/notes.js');
    mod.fillTemplateSelect(TEMPLATES);
    const options = document.getElementById('note_template_select').querySelectorAll('option');
    expect(options.length).toBe(3); // default + active (2)
    expect([...options].map(o => o.value)).toContain('3');
    expect([...options].map(o => o.value)).not.toContain('2');
  });

  it('fillTemplateSelect without tplSelectEl returns', async () => {
    document.getElementById('note_template_select').remove();
    const mod = await loadModule('static/js/pages/doctor/notes.js');
    expect(() => mod.fillTemplateSelect(TEMPLATES)).not.toThrow();
  });

  it('renderTemplatesTable renders inactive badge', async () => {
    const mod = await loadModule('static/js/pages/doctor/notes.js');
    mod.renderTemplatesTable.__call = null;
    // seed cache via refreshTemplatesUI
    await mod.refreshTemplatesUI();
    expect(document.querySelector('#dnt_table_body').innerHTML).toContain('Inactive');
    expect(document.querySelector('#dnt_table_body').innerHTML).toContain('bg-secondary');
  });

  it('renderTemplatesTable skips entries missing id', async () => {
    const mod = await loadModule('static/js/pages/doctor/notes.js');
    window.__M0__ = '/api/x';
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ templates: [null, {}, { id: '9', name: 'Good', is_active: true }] }) });
    await mod.refreshTemplatesUI();
    expect(document.querySelector('#dnt_table_body').innerHTML).toContain('Good');
  });

  it('renderTemplatesTable without table body returns', async () => {
    document.getElementById('dnt_table_body').closest('table').remove();
    const mod = await loadModule('static/js/pages/doctor/notes.js');
    expect(() => mod.renderTemplatesTable()).not.toThrow();
  });

  it('applyTplBtn inserts on empty notes field', async () => {
    await loadModule('static/js/pages/doctor/notes.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 30));
    document.getElementById('medical_notes').value = '';
    document.getElementById('note_template_select').value = '1';
    document.getElementById('apply_note_template_btn').click();
    expect(document.getElementById('medical_notes').value).toBe('مرحباً');
  });

  it('applyTplBtn without selection does nothing', async () => {
    await loadModule('static/js/pages/doctor/notes.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 30));
    document.getElementById('note_template_select').value = '';
    document.getElementById('apply_note_template_btn').click();
    expect(document.getElementById('medical_notes').value).toBe('');
  });

  it('applyTplBtn with unknown template id does nothing', async () => {
    await loadModule('static/js/pages/doctor/notes.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 30));
    document.getElementById('medical_notes').value = 'keep';
    document.getElementById('note_template_select').innerHTML = '<option value="999" selected>X</option>';
    document.getElementById('apply_note_template_btn').click();
    expect(document.getElementById('medical_notes').value).toBe('keep');
  });

  it('DOMContentLoaded with draft fills the textarea', async () => {
    window.sessionStorage.setItem('medical_notes_draft', 'draft text');
    await loadModule('static/js/pages/doctor/notes.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(document.getElementById('medical_notes').value).toBe('draft text');
    expect(window.sessionStorage.getItem('medical_notes_draft')).toBe('draft text');
  });

  it('DOMContentLoaded without drafts leaves textarea empty', async () => {
    await loadModule('static/js/pages/doctor/notes.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(document.getElementById('medical_notes').value).toBe('');
  });

  it('submitting the first form removes the draft key', async () => {
    window.sessionStorage.setItem('medical_notes_draft', 'draft text');
    await loadModule('static/js/pages/doctor/notes.js');
    const form = document.querySelector('form'); // notes.js targets the first form
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    expect(window.sessionStorage.getItem('medical_notes_draft')).toBeNull();
  });

  it('doctorNoteTemplateForm submit with non-ok response shows notify error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    await loadModule('static/js/pages/doctor/notes.js');
    document.getElementById('dnt_name').value = 'T';
    const form = document.getElementById('doctorNoteTemplateForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(window.notify.error).toHaveBeenCalled();
  });

  it('doctorNoteTemplateForm submit without csrfToken sends no token header', async () => {
    document.querySelector('meta[name="csrf-token"]').remove();
    const mod = await loadModule('static/js/pages/doctor/notes.js');
    document.getElementById('dnt_name').value = 'T';
    const form = document.getElementById('doctorNoteTemplateForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 30));
    const req = global.fetch.mock.calls[0][1];
    expect(req.headers['X-CSRFToken']).toBeUndefined();
  });

  it('dntTableBody delete requests r.ok failure shows notify error', async () => {
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.includes('note-templates/delete')) return Promise.resolve({ ok: false, status: 500 });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: TEMPLATES }) });
    });
    await loadModule('static/js/pages/doctor/notes.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 30));
    const btn = document.querySelector('#dnt_table_body button[data-action="delete"]');
    btn.click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.notify.error).toHaveBeenCalled();
  });

  it('dntTableBody delete with missing template in cache does nothing', async () => {
    await loadModule('static/js/pages/doctor/notes.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 30));
    const btn = document.createElement('button');
    btn.dataset.action = 'delete';
    btn.dataset.id = 'missing';
    document.getElementById('dnt_table_body').appendChild(btn);
    btn.click();
    expect(window.notify.confirm).not.toHaveBeenCalled();
  });

  it('dntTableBody click with no closest button does nothing', async () => {
    await loadModule('static/js/pages/doctor/notes.js');
    document.getElementById('dnt_table_body').dispatchEvent(new MouseEvent('click', { bubbles: true }));
    expect(window.notify.confirm).not.toHaveBeenCalled();
  });

  it('dntTableBody edit fills form with missing name/text', async () => {
    window.__M0__ = '/api/x';
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ templates: [{ id: '9', text: '', is_active: false }] }) });
    await loadModule('static/js/pages/doctor/notes.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 30));
    const btn = document.querySelector('#dnt_table_body button[data-action="edit"]');
    btn.click();
    expect(document.getElementById('dnt_name').value).toBe('');
    expect(document.getElementById('dnt_text').value).toBe('');
    expect(document.getElementById('dnt_active').checked).toBe(false);
  });

  it('modal show event resets and refreshes templates', async () => {
    await loadModule('static/js/pages/doctor/notes.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 30));
    const modal = document.getElementById('doctorNoteTemplatesModal');
    document.getElementById('dnt_name').value = 'x';
    modal.dispatchEvent(new Event('show.bs.modal'));
    expect(document.getElementById('dnt_name').value).toBe('');
  });

  it('not checking showToast warning path calls console.warn in notifyErr fallback', async () => {
    delete window.showToast;
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/doctor/notes.js');
    await mod.fetchTemplates();
    expect(window.console.warn).toHaveBeenCalled();
  });
});
describe('doctor/notes.js remaining branch arms', () => {
  it('applyTplBtn with missing template select element is a no-op', async () => {
    document.getElementById('note_template_select').remove();
    await loadModule('static/js/pages/doctor/notes.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 20));
    expect(() => document.getElementById('apply_note_template_btn').click()).not.toThrow();
  });

  it('applyTplBtn with missing notes textarea is a no-op', async () => {
    document.getElementById('medical_notes').remove();
    await loadModule('static/js/pages/doctor/notes.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 20));
    expect(() => document.getElementById('apply_note_template_btn').click()).not.toThrow();
  });

  it('apply template without text inserts the empty string', async () => {
    global.fetch = vi.fn((url) => {
      if (String(url).includes('note-templates')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: [{ id: '3', name: 'NoText', is_active: true }] }) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true }) });
    });
    await loadModule('static/js/pages/doctor/notes.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 30));
    document.getElementById('note_template_select').value = '3';
    document.getElementById('apply_note_template_btn').click();
    expect(document.getElementById('medical_notes').value).toBe('');
  });

  it('click directly on the table body (no target) is a no-op', async () => {
    await loadModule('static/js/pages/doctor/notes.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 30));
    const tbody = document.getElementById('dnt_table_body');
    tbody.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    expect(window.notify.confirm).not.toHaveBeenCalled();
  });

  it('template delete without csrf meta sends no token header', async () => {
    document.querySelector('meta[name="csrf-token"]').remove();
    await loadModule('static/js/pages/doctor/notes.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 30));
    const btn = document.querySelector('#dnt_table_body button[data-action="delete"]');
    btn.click();
    await new Promise(r => setTimeout(r, 30));
    const deleteCall = global.fetch.mock.calls.find(c => String(c[0]).includes('note-templates/delete'));
    expect(deleteCall).toBeTruthy();
    expect(deleteCall[1].headers['X-CSRFToken']).toBeUndefined();
  });

  it('template delete network failure shows the connection error', async () => {
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.includes('note-templates/delete')) return Promise.reject(new Error('network'));
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: TEMPLATES }) });
    });
    await loadModule('static/js/pages/doctor/notes.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 30));
    const btn = document.querySelector('#dnt_table_body button[data-action="delete"]');
    btn.click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.notify.error).toHaveBeenCalledWith('انقطع الاتصال. تحقق من الشبكة وحاول مرة أخرى.');
  });

  it('template save fetch failure shows the connection error', async () => {
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.includes('note-templates/save')) return Promise.reject(new Error('network'));
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: TEMPLATES }) });
    });
    await loadModule('static/js/pages/doctor/notes.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 30));
    document.getElementById('doctorNoteTemplateForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    expect(window.notify.error).toHaveBeenCalledWith('انقطع الاتصال. تحقق من الشبكة وحاول مرة أخرى.');
  });

  it('template save non-ok shows the retry message', async () => {
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.includes('note-templates/save')) return Promise.resolve({ ok: false, status: 500 });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: TEMPLATES }) });
    });
    await loadModule('static/js/pages/doctor/notes.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 30));
    document.getElementById('doctorNoteTemplateForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 40));
    expect(window.notify.error).toHaveBeenCalledWith('تعذّر حفظ القالب. حاول مرة أخرى.');
  });

  it('applyTplBtn appends template text to existing notes', async () => {
    await loadModule('static/js/pages/doctor/notes.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 30));
    document.getElementById('medical_notes').value = 'previous';
    document.getElementById('note_template_select').value = '1';
    document.getElementById('apply_note_template_btn').click();
    expect(document.getElementById('medical_notes').value).toBe('previous\nمرحباً');
  });
});

describe('doctor/notes.js delegation edge arms', () => {
  it('click dispatched on a text node does nothing', async () => {
    await loadModule('static/js/pages/doctor/notes.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 30));
    const tbody = document.getElementById('dnt_table_body');
    const textNode = document.createTextNode('plain text');
    tbody.appendChild(textNode);
    expect(() => textNode.dispatchEvent(new MouseEvent('click', { bubbles: true }))).not.toThrow();
    expect(window.notify.confirm).not.toHaveBeenCalled();
  });
});
