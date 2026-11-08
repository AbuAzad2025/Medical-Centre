import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from '../../test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <meta name="csrf-token" content="test-token">
    <input id="test_name" value="X-Ray Chest" />
    <input id="body_part" value="Chest" />
    <select id="report_template">
      <option value="1">XRAY - CXR</option>
      <option value="2">CT - Head</option>
      <option value="3">MRI - Knee</option>
    </select>
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
  { id: '2', name: 'CT Head', modality: 'CT', findings: 'CT normal', impression: 'Nothing acute', recommendations: 'none', is_active: true },
  { id: '3', name: 'MRI Knee', modality: 'MRI', findings: 'MRI normal', impression: 'No tear', recommendations: 'none', is_active: true },
];
const MACROS = [
  { id: '9', name: 'Heart', text: 'Heart size is normal', is_active: true },
];

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
  global.fetch = vi.fn((url, _opts) => {
    const u = String(url);
    if (u.includes('ai-assist')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, data: { suggestions: ['follow up'], disclaimer: 'consult', external_ref: 'ACR-01' } }) });
    }
    if (u.includes('templates')) {
      if (u.includes('delete') || u.includes('__TPL__') || u.includes('save')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: TEMPLATES }) });
    }
    if (u.includes('macro')) {
      if (u.includes('delete') || u.includes('save') || u.includes('macro-save')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ macros: MACROS }) });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
  });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('radiology/process.js extra branches', () => {
  it('test_name change auto-syncs CT template', async () => {
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    const input = document.getElementById('test_name');
    input.value = 'CT Brain';
    input.dispatchEvent(new Event('change'));
    expect(document.getElementById('report_template').value).toBe('2');
  });

  it('test_name change auto-syncs MRI template', async () => {
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    const input = document.getElementById('test_name');
    input.value = 'MRI Knee';
    input.dispatchEvent(new Event('change'));
    expect(document.getElementById('report_template').value).toBe('3');
  });

  it('test_name change falls back to empty selection for unknown modality', async () => {
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    const input = document.getElementById('test_name');
    input.value = 'angiography';
    input.dispatchEvent(new Event('change'));
    expect(document.getElementById('report_template').value).toBe('');
  });

  it('test_name change with ultrasound text selects US-like template fallback', async () => {
    const TEMPLATES2 = [...TEMPLATES, { id: '4', name: 'US Abdo', modality: 'US', findings: 'US normal', impression: '', recommendations: '', is_active: true }];
    global.fetch = vi.fn((url) => {
      if (String(url).includes('templates')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: TEMPLATES2 }) });
      if (String(url).includes('macro')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ macros: MACROS }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });
    document.getElementById('report_template').innerHTML = '<option value="">None</option><option value="4">US - Abdo</option>';
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    const input = document.getElementById('test_name');
    input.value = ' ultrasound ';
    input.dispatchEvent(new Event('change'));
    expect(document.getElementById('report_template').value).toBe('4');
  });

  it('AI assist with empty suggestions shows just disclaimer and ref', async () => {
    global.fetch = vi.fn((url) => {
      if (String(url).includes('ai-assist')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, data: { suggestions: [], disclaimer: 'consult', external_ref: 'ACR' } }) });
      if (String(url).includes('templates')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: TEMPLATES }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ macros: MACROS }) });
    });
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 10));
    document.getElementById('ai_assist_btn').click();
    await new Promise(r => setTimeout(r, 50));
    const out = document.getElementById('ai_assist_output').textContent;
    expect(out).toContain('consult');
    expect(out).toContain('ACR');
  });

  it('AI assist with missing disclaimer and ref still renders suggestions', async () => {
    global.fetch = vi.fn((url) => {
      if (String(url).includes('ai-assist')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, data: { suggestions: ['follow up'] } }) });
      if (String(url).includes('templates')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: TEMPLATES }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ macros: MACROS }) });
    });
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 10));
    document.getElementById('ai_assist_btn').click();
    await new Promise(r => setTimeout(r, 50));
    const out = document.getElementById('ai_assist_output').textContent;
    expect(out).toContain('follow up');
  });

  it('AI assist with undefined data falls back to default message', async () => {
    global.fetch = vi.fn((url) => {
      if (String(url).includes('ai-assist')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: false }) });
      if (String(url).includes('templates')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: TEMPLATES }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ macros: MACROS }) });
    });
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 10));
    document.getElementById('ai_assist_btn').click();
    await new Promise(r => setTimeout(r, 50));
    expect(document.getElementById('ai_assist_output').textContent).toContain('تعذر');
  });

  it('AI assist non-ok response shows error toast', async () => {
    global.fetch = vi.fn((url) => {
      if (String(url).includes('ai-assist')) return Promise.resolve({ ok: false, status: 500 });
      if (String(url).includes('templates')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: TEMPLATES }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ macros: MACROS }) });
    });
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 10));
    document.getElementById('ai_assist_btn').click();
    await new Promise(r => setTimeout(r, 50));
    expect(window.showToast).toHaveBeenCalled();
  });

  it('template form submit with non-ok response triggers notify error', async () => {
    global.fetch = vi.fn((url) => {
      if (String(url).includes('template-save')) return Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) });
      if (String(url).includes('templates')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: TEMPLATES }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ macros: MACROS }) });
    });
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 10));
    document.getElementById('tpl_name').value = 'T';
    document.getElementById('radiologyTemplateForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 50));
    expect(window.notify.error).toHaveBeenCalled();
  });

  it('macro form submit with non-ok response triggers notify error', async () => {
    global.fetch = vi.fn((url) => {
      if (String(url).includes('macro-save')) return Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) });
      if (String(url).includes('macros')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ macros: MACROS }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: TEMPLATES }) });
    });
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 10));
    document.getElementById('macro_name').value = 'M';
    document.getElementById('radiologyMacroForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 50));
    expect(window.notify.error).toHaveBeenCalled();
  });

  it('template delete with non-ok response shows notify error', async () => {
    global.fetch = vi.fn((url) => {
      if (String(url).includes('template-delete')) return Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) });
      if (String(url).includes('templates')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: TEMPLATES }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ macros: MACROS }) });
    });
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 10));
    const tr = document.querySelector('#tpl_table_body tr');
    tr.querySelector('button[data-action="delete"]').click();
    await new Promise(r => setTimeout(r, 50));
    expect(window.notify.error).toHaveBeenCalled();
  });

  it('macro delete with non-ok response shows notify error', async () => {
    global.fetch = vi.fn((url) => {
      if (String(url).includes('macro-delete')) return Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) });
      if (String(url).includes('macros')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ macros: MACROS }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: TEMPLATES }) });
    });
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 10));
    const tr = document.querySelector('#macro_table_body tr');
    tr.querySelector('button[data-action="delete"]').click();
    await new Promise(r => setTimeout(r, 50));
    expect(window.notify.error).toHaveBeenCalled();
  });

  it('macro delete with success refreshes the macros table', async () => {
    global.fetch = vi.fn((url) => {
      if (String(url).includes('macro-delete')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true }) });
      if (String(url).includes('macro')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ macros: MACROS }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: TEMPLATES }) });
    });
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    const tr = document.querySelector('#macro_table_body tr');
    tr.querySelector('button[data-action="delete"]').click();
    await new Promise(r => setTimeout(r, 50));
    expect(global.fetch).toHaveBeenCalled();
  });

  it('template delete with network failure shows fallback toast', async () => {
    global.fetch = vi.fn((url) => {
      if (String(url).includes('template-delete')) return Promise.reject(new Error('network'));
      if (String(url).includes('templates')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: TEMPLATES }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ macros: MACROS }) });
    });
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    const tr = document.querySelector('#tpl_table_body tr');
    tr.querySelector('button[data-action="delete"]').click();
    await new Promise(r => setTimeout(r, 50));
    expect(window.showToast).toHaveBeenCalled();
  });

  it('macro delete with network failure shows fallback toast', async () => {
    global.fetch = vi.fn((url) => {
      if (String(url).includes('macro-delete')) return Promise.reject(new Error('network'));
      if (String(url).includes('macros')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ macros: MACROS }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: TEMPLATES }) });
    });
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    const tr = document.querySelector('#macro_table_body tr');
    tr.querySelector('button[data-action="delete"]').click();
    await new Promise(r => setTimeout(r, 50));
    expect(window.showToast).toHaveBeenCalled();
  });

  it('AI assist without pacs and study uid renders with empty values', async () => {
    document.getElementById('pacs_url').remove();
    document.getElementById('study_uid').remove();
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 10));
    document.getElementById('ai_assist_btn').click();
    await new Promise(r => setTimeout(r, 50));
    expect(global.fetch).toHaveBeenCalled();
    const body = JSON.parse(global.fetch.mock.calls.find(c => String(c[0]).includes('ai-assist'))[1].body);
    expect(body.pacs_url).toBe('');
    expect(body.study_uid).toBe('');
  });

  it('empty impression renders empty impression in AI payload', async () => {
    document.getElementById('results').value = '';
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 10));
    document.getElementById('ai_assist_btn').click();
    await new Promise(r => setTimeout(r, 50));
    const body = JSON.parse(global.fetch.mock.calls.find(c => String(c[0]).includes('ai-assist'))[1].body);
    expect(body.impression).toBe('');
  });

  it('macro edit button fills the form when macros cache is populated', async () => {
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    const tr = document.querySelector('#macro_table_body tr');
    tr.querySelector('button[data-action="edit"]').click();
    expect(document.getElementById('macro_id').value).toBe('9');
  });

  it('macro table cell click on non-button does nothing', async () => {
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    const tr = document.querySelector('#macro_table_body tr');
    tr.querySelector('td').click();
    expect(document.getElementById('macro_id').value).toBe('');
  });

  it('template table cell click on non-button does nothing', async () => {
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    const tr = document.querySelector('#tpl_table_body tr');
    tr.querySelector('td').click();
    expect(document.getElementById('tpl_id').value).toBe('');
  });

  it('macro refresh button refreshes macros', async () => {
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 10));
    global.fetch.mockClear();
    document.getElementById('macro_refresh_btn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
  });

  it('template refresh button refreshes templates', async () => {
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 10));
    global.fetch.mockClear();
    document.getElementById('tpl_refresh_btn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
  });
});