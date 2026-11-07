import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from '../../test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <meta name="csrf-token" content="test-token">
    <input id="test_name" value="X-Ray Chest" />
    <input id="body_part" value="Chest" />
    <select id="report_template"><option value="">None</option><option value="1">XRAY - CXR</option></select>
    <button id="apply_template_btn">Apply</button>
    <button id="manage_templates_btn">Manage</button>
    <textarea id="findings"></textarea>
    <textarea id="results"></textarea>
    <textarea id="recommendations"></textarea>
    <div id="radiologyTemplatesModal"></div>
    <div id="radiologyMacrosModal"></div>
    <form id="radiologyTemplateForm">
      <input id="tpl_id" value="" />
      <input id="tpl_name" value="" />
      <select id="tpl_modality"><option value="XRAY">XRAY</option><option value="CT">CT</option></select>
      <textarea id="tpl_findings"></textarea>
      <textarea id="tpl_impression"></textarea>
      <textarea id="tpl_recommendations"></textarea>
      <input type="checkbox" id="tpl_active" checked />
    </form>
    <table><tbody id="tpl_table_body"></tbody></table>
    <button id="tpl_refresh_btn">Refresh</button>
    <button id="tpl_reset_btn">Reset</button>
    <select id="report_macro"><option value="">None</option><option value="9">Heart</option></select>
    <select id="macro_target"><option value="findings">Findings</option><option value="recommendations">Recommendations</option></select>
    <button id="apply_macro_btn">Apply macro</button>
    <form id="radiologyMacroForm">
      <input id="macro_id" value="" />
      <input id="macro_name" value="" />
      <textarea id="macro_text"></textarea>
      <input type="checkbox" id="macro_active" checked />
    </form>
    <table><tbody id="macro_table_body"></tbody></table>
    <button id="macro_refresh_btn">Refresh</button>
    <button id="macro_reset_btn">Reset</button>
    <button id="ai_assist_btn">AI</button>
    <div id="ai_assist_output"></div>
    <input id="pacs_url" value="/pacs/study1" />
    <input id="study_uid" value="1.2.3" />
  `;
}

const TEMPLATES = [
  { id: '1', name: 'CXR', modality: 'XRAY', findings: '__BODY_PART__ normal', impression: 'Normal CXR', recommendations: 'none', is_active: true },
];
const MACROS = [
  { id: '9', name: 'Heart', text: 'Heart size is normal', is_active: true },
];

function setupFetch({ templates = TEMPLATES, macros = MACROS } = {}) {
  global.fetch = vi.fn((url, _opts) => {
    const u = String(url);
    if (u.includes('templates')) {
      if (u.includes('delete') || u.includes('__TPL__') || u.includes('save')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates }) });
    }
    if (u.includes('macro')) {
      if (u.includes('delete') || u.includes('__M__') || u.includes('save') || u.includes('macro-save')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ macros }) });
    }
    if (u.includes('ai-assist')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, data: { suggestions: ['follow up'], disclaimer: 'consult radiologist', external_ref: 'ACR' } }) });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
  });
}

beforeEach(() => {
  baseDom();
  window.__M0__ = '/api/ai-assist';
  window.__M1__ = '/api/templates';
  window.__M2__ = '/api/macros';
  window.__M3__ = '__BODY_PART__';
  window.__M4__ = '/api/macro-save';
  window.__M5__ = '/api/macro-delete/__M__';
  window.__M6__ = '/api/template-delete/__TPL__';
  window.__M7__ = '/api/template-save';
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.confirm = vi.fn(() => true);
  window.notify = { warning: vi.fn(), error: vi.fn(), success: vi.fn() };
  window.showToast = vi.fn();
  setupFetch();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('radiology/process.js', () => {
  it('loads and initializes templates/macros via fetch', async () => {
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    expect(global.fetch).toHaveBeenCalled();
    expect(document.getElementById('tpl_table_body').innerHTML).toContain('CXR');
    expect(document.getElementById('macro_table_body').innerHTML).toContain('Heart');
  });

  it('apply button with no template selected warns', async () => {
    document.getElementById('test_name').value = '';
    document.getElementById('report_template').value = '';
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 10));
    document.getElementById('apply_template_btn').click();
    expect(window.notify.warning).toHaveBeenCalled();
  });

  it('apply button applies template with body-part substitution', async () => {
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    document.getElementById('report_template').value = '1';
    document.getElementById('findings').value = 'existing text';
    document.getElementById('apply_template_btn').click();
    expect(window.confirm).toHaveBeenCalled();
    expect(document.getElementById('findings').value).toBe('Chest normal');
    expect(document.getElementById('results').value).toBe('Normal CXR');
    expect(document.getElementById('recommendations').value).toBe('none');
  });

  it('apply button cancel keeps existing content', async () => {
    window.confirm = vi.fn(() => false);
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    document.getElementById('report_template').value = '1';
    document.getElementById('findings').value = 'existing text';
    document.getElementById('apply_template_btn').click();
    expect(document.getElementById('findings').value).toBe('existing text');
  });

  it('test_name change syncs template selection by modality', async () => {
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    const input = document.getElementById('test_name');
    input.value = 'MRI spine';
    input.dispatchEvent(new Event('change'));
    expect(document.getElementById('report_template').value).toBe('');
  });

  it('ai_assist_btn calls fetch and renders output', async () => {
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 10));
    document.getElementById('ai_assist_btn').click();
    await new Promise(r => setTimeout(r, 50));
    expect(document.getElementById('ai_assist_output').textContent).toContain('follow up');
  });

  it('ai_assist_btn failure shows toast', async () => {
    global.fetch = vi.fn((url) => {
      if (String(url).includes('ai-assist')) return Promise.reject(new Error('network'));
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: TEMPLATES, macros: MACROS }) });
    });
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    document.getElementById('ai_assist_btn').click();
    await new Promise(r => setTimeout(r, 50));
    expect(window.showToast).toHaveBeenCalled();
  });

  it('apply_macro_btn appends macro text to findings', async () => {
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 10));
    document.getElementById('report_macro').value = '9';
    document.getElementById('findings').value = 'prev';
    document.getElementById('apply_macro_btn').click();
    expect(document.getElementById('findings').value).toContain('Heart size is normal');
  });

  it('apply_macro_btn inserts into the chosen target field', async () => {
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 10));
    document.getElementById('report_macro').value = '9';
    document.getElementById('macro_target').value = 'recommendations';
    document.getElementById('recommendations').value = 'prev';
    document.getElementById('apply_macro_btn').click();
    expect(document.getElementById('recommendations').value).toContain('Heart size is normal');
  });

  it('macro form submit posts payload and reloads', async () => {
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 10));
    document.getElementById('macro_name').value = 'NewMacro';
    document.getElementById('macro_text').value = 'body';
    document.getElementById('radiologyMacroForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 50));
    expect(global.fetch).toHaveBeenCalledWith('/api/macro-save', expect.objectContaining({ method: 'POST' }));
  });

  it('macro form submit failure shows toast', async () => {
    global.fetch = vi.fn((url) => {
      if (String(url).includes('macro-save')) return Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ macros: MACROS }) });
    });
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    document.getElementById('macro_name').value = 'NewMacro';
    document.getElementById('radiologyMacroForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 50));
    expect(window.notify.error).toHaveBeenCalled();
  });

  it('macro edit button fills the form', async () => {
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    const tr = document.querySelector('#macro_table_body tr');
    tr.querySelector('button[data-action="edit"]').click();
    expect(document.getElementById('macro_id').value).toBe('9');
    expect(document.getElementById('macro_name').value).toBe('Heart');
  });

  it('macro delete button issues delete request', async () => {
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    const tr = document.querySelector('#macro_table_body tr');
    tr.querySelector('button[data-action="delete"]').click();
    await new Promise(r => setTimeout(r, 50));
    expect(global.fetch).toHaveBeenCalledWith('/api/macro-delete/9', expect.objectContaining({ method: 'POST' }));
  });

  it('template form submit posts payload', async () => {
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 10));
    document.getElementById('tpl_name').value = 'T';
    document.getElementById('tpl_findings').value = 'findings';
    document.getElementById('radiologyTemplateForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 50));
    expect(global.fetch).toHaveBeenCalledWith('/api/template-save', expect.objectContaining({ method: 'POST' }));
  });

  it('template form submit response non-ok shows error toast alternative', async () => {
    global.fetch = vi.fn((url) => {
      if (String(url).includes('template-save')) return Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: TEMPLATES, macros: MACROS }) });
    });
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    document.getElementById('tpl_name').value = 'T';
    document.getElementById('radiologyTemplateForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 20));
    expect(window.notify.error).toHaveBeenCalled();
  });

  it('template edit button fills the form', async () => {
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    const tr = document.querySelector('#tpl_table_body tr');
    tr.querySelector('button[data-action="edit"]').click();
    expect(document.getElementById('tpl_name').value).toBe('CXR');
  });

  it('template delete button issues delete request', async () => {
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    const tr = document.querySelector('#tpl_table_body tr');
    tr.querySelector('button[data-action="delete"]').click();
    await new Promise(r => setTimeout(r, 50));
    expect(global.fetch).toHaveBeenCalledWith('/api/template-delete/1', expect.objectContaining({ method: 'POST' }));
  });

  it('macro refresh and reset buttons trigger refresh and clear', async () => {
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 10));
    document.getElementById('macro_refresh_btn').click();
    await new Promise(r => setTimeout(r, 20));
    document.getElementById('macro_reset_btn').click();
    expect(document.getElementById('macro_id').value).toBe('');
    expect(document.getElementById('macro_active').checked).toBe(true);
  });

  it('template refresh and reset buttons trigger refresh and clear', async () => {
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 10));
    document.getElementById('tpl_refresh_btn').click();
    await new Promise(r => setTimeout(r, 20));
    document.getElementById('tpl_reset_btn').click();
    expect(document.getElementById('tpl_id').value).toBe('');
    expect(document.getElementById('tpl_active').checked).toBe(true);
  });

  it('ai_assist renders suggestions with disclaimer and ref', async () => {
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 10));
    document.getElementById('ai_assist_btn').click();
    await new Promise(r => setTimeout(r, 50));
    const out = document.getElementById('ai_assist_output').textContent;
    expect(out).toContain('• follow up');
    expect(out).toContain('consult radiologist');
    expect(out).toContain('ACR');
  });
});