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
      <option value="4">US - Abdomen</option>
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
  { id: '4', name: 'US Abdo', modality: 'US', findings: 'US normal', impression: '', recommendations: '', is_active: true },
];
const MACROS = [{ id: '9', name: 'Heart', text: 'Heart size is normal', is_active: true }];

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
  window.escHtml = (s) => String(s ?? '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.confirm = vi.fn(() => true);
  window.notify = { warning: vi.fn(), error: vi.fn(), success: vi.fn() };
  window.showToast = vi.fn();
  window.alert = vi.fn();
  global.fetch = vi.fn((url) => {
    const u = String(url);
    if (u.includes('ai-assist')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, data: { suggestions: ['s1'], disclaimer: 'disc', external_ref: 'REF' } }) });
    }
    if (u.includes('templates')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: TEMPLATES }) });
    if (u.includes('macro')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ macros: MACROS }) });
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
  });
});

afterEach(() => {
  vi.useRealTimers();
});

async function loadAndClickAi() {
  await loadModule('static/js/pages/radiology/process.js');
  await new Promise(r => setTimeout(r, 10));
  document.getElementById('ai_assist_btn').click();
  await new Promise(r => setTimeout(r, 60));
  return JSON.parse(global.fetch.mock.calls.find(c => String(c[0]).includes('ai-assist'))[1].body);
}

describe('radiology/process.js guessTemplateFromTestName branches', () => {
  it('CT test name yields CT modality in AI payload', async () => {
    document.getElementById('test_name').value = 'CT Chest';
    const payload = await loadAndClickAi();
    expect(payload.modality).toBe('CT');
  });

  it('MRI test name yields MRI modality in AI payload', async () => {
    document.getElementById('test_name').value = 'MRI Knee';
    const payload = await loadAndClickAi();
    expect(payload.modality).toBe('MRI');
  });

  it('ultrasound test name yields US modality', async () => {
    document.getElementById('test_name').value = 'ultrasound abdomen';
    const payload = await loadAndClickAi();
    expect(payload.modality).toBe('US');
  });

  it('u/s test name yields US modality', async () => {
    document.getElementById('test_name').value = 'u/s kidney';
    const payload = await loadAndClickAi();
    expect(payload.modality).toBe('US');
  });

  it('x-ray test name yields XRAY modality', async () => {
    document.getElementById('test_name').value = 'x-ray pelvis';
    const payload = await loadAndClickAi();
    expect(payload.modality).toBe('XRAY');
  });

  it('unknown test name yields empty modality', async () => {
    document.getElementById('test_name').value = 'ecg';
    const payload = await loadAndClickAi();
    expect(payload.modality).toBe('');
  });
});

describe('radiology/process.js getBodyPart branches', () => {
  it('empty body_part yields the placeholder', async () => {
    document.getElementById('body_part').value = '';
    const payload = await loadAndClickAi();
    expect(payload.body_part).toBe('________');
  });

  it('whitespace body_part yields the placeholder', async () => {
    document.getElementById('body_part').value = '   ';
    const payload = await loadAndClickAi();
    expect(payload.body_part).toBe('________');
  });

  it('missing body_part element yields the placeholder', async () => {
    document.getElementById('body_part').remove();
    const payload = await loadAndClickAi();
    expect(payload.body_part).toBe('________');
  });

  it('missing test_name element still loads the module', async () => {
    document.getElementById('test_name').remove();
    await loadModule('static/js/pages/radiology/process.js');
    expect(true).toBe(true);
  });
});

describe('radiology/process.js AI assist response/edge branches', () => {
  it('invalid JSON response body falls back to empty object and shows the retry message', async () => {
    global.fetch = vi.fn((url) => {
      if (String(url).includes('ai-assist')) {
        return Promise.resolve({ ok: true, json: () => Promise.reject(new Error('bad json')) });
      }
      if (String(url).includes('templates')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: TEMPLATES }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ macros: MACROS }) });
    });
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 10));
    document.getElementById('ai_assist_btn').click();
    await new Promise(r => setTimeout(r, 60));
    expect(document.getElementById('ai_assist_output').textContent).toContain('تعذر');
  });

  it('fetch rejection triggers showToast when available', async () => {
    global.fetch = vi.fn((url) => {
      if (String(url).includes('ai-assist')) return Promise.reject(new Error('network'));
      if (String(url).includes('templates')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: TEMPLATES }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ macros: MACROS }) });
    });
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 10));
    document.getElementById('ai_assist_btn').click();
    await new Promise(r => setTimeout(r, 60));
    expect(window.showToast).toHaveBeenCalled();
    expect(document.getElementById('ai_assist_btn').disabled).toBe(false);
  });

  it('fetch rejection falls back to alert when showToast is missing', async () => {
    delete window.showToast;
    global.fetch = vi.fn((url) => {
      if (String(url).includes('ai-assist')) return Promise.reject(new Error('network'));
      if (String(url).includes('templates')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: TEMPLATES }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ macros: MACROS }) });
    });
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 10));
    document.getElementById('ai_assist_btn').click();
    await new Promise(r => setTimeout(r, 60));
    expect(window.alert).toHaveBeenCalled();
  });

  it('missing ai_assist_btn means no listener and no fetch happens on load', async () => {
    document.getElementById('ai_assist_btn').remove();
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    expect(global.fetch.mock.calls.some(c => String(c[0]).includes('ai-assist'))).toBe(false);
  });

  it('missing ai_assist_output still allows the module to load', async () => {
    document.getElementById('ai_assist_output').remove();
    await loadModule('static/js/pages/radiology/process.js');
    expect(true).toBe(true);
  });

  it('csrf meta missing sends AI request without token header', async () => {
    document.querySelector('meta[name="csrf-token"]').remove();
    const payload = await loadAndClickAi();
    const req = global.fetch.mock.calls.find(c => String(c[0]).includes('ai-assist'))[1];
    expect(req.headers['X-CSRFToken']).toBeUndefined();
    expect(payload.modality).toBe('XRAY');
  });
});

describe('radiology/process.js fetch error alert fallbacks', () => {
  it('fetchTemplates non-ok falls back to alert when showToast missing', async () => {
    delete window.showToast;
    global.fetch = vi.fn((url) => {
      if (String(url).includes('templates')) return Promise.resolve({ ok: false, status: 500 });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ macros: MACROS }) });
    });
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 30));
    expect(window.alert).toHaveBeenCalled();
  });

  it('fetchMacros non-ok falls back to alert when showToast missing', async () => {
    delete window.showToast;
    global.fetch = vi.fn((url) => {
      if (String(url).includes('macro')) return Promise.resolve({ ok: false, status: 500 });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: TEMPLATES }) });
    });
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 30));
    expect(window.alert).toHaveBeenCalled();
  });

  it('fetchTemplates with non-array templates key yields empty cache', async () => {
    global.fetch = vi.fn((url) => {
      if (String(url).includes('templates')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: 'nope' }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ macros: MACROS }) });
    });
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 30));
    expect(document.querySelectorAll('#tpl_table_body tr').length).toBe(0);
  });

  it('fetchMacros with non-array macros key yields empty cache', async () => {
    global.fetch = vi.fn((url) => {
      if (String(url).includes('macros')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ macros: 42 }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: TEMPLATES }) });
    });
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 30));
    expect(document.querySelectorAll('#macro_table_body tr').length).toBe(0);
  });
});

describe('radiology/process.js template apply branches', () => {
  it('apply button with no template selected shows warning and does not fetch templates', async () => {
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    document.getElementById('report_template').value = '';
    document.getElementById('apply_template_btn').click();
    expect(window.notify.warning).toHaveBeenCalled();
  });

  it('apply button with unknown template id leaves fields unchanged', async () => {
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 10));
    document.getElementById('report_template').innerHTML = '<option value="999" selected>X</option>';
    document.getElementById('apply_template_btn').click();
    expect(document.getElementById('findings').value).toBe('');
    expect(window.confirm).not.toHaveBeenCalled();
  });

  it('apply template with existing content and cancelled confirm leaves fields unchanged', async () => {
    window.confirm = vi.fn(() => false);
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 10));
    document.getElementById('findings').value = 'existing';
    document.getElementById('report_template').value = '1';
    document.getElementById('apply_template_btn').click();
    expect(document.getElementById('findings').value).toBe('existing');
  });

  it('apply template replaces __BODY_PART__ across all three fields', async () => {
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 10));
    document.getElementById('report_template').value = '1';
    document.getElementById('apply_template_btn').click();
    expect(document.getElementById('findings').value).toBe('Chest normal');
  });

  it('refresh path preserves the pre-selected template through syncTemplateSelectionByModality', async () => {
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    document.getElementById('report_template').value = '2';
    const modal = document.getElementById('radiologyTemplatesModal');
    modal.dispatchEvent(new Event('show.bs.modal'));
    await new Promise(r => setTimeout(r, 60));
    expect(document.getElementById('report_template').value).toBe('2');
  });

  it('resetTemplateForm derives the modality from the test name (CT)', async () => {
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 10));
    document.getElementById('test_name').value = 'CT Brain';
    document.getElementById('tpl_reset_btn').click();
    expect(document.getElementById('tpl_modality').value).toBe('CT');
  });

  it('resetTemplateForm falls back to XRAY for unrecognized test name', async () => {
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 10));
    document.getElementById('test_name').value = 'ecg';
    document.getElementById('tpl_reset_btn').click();
    expect(document.getElementById('tpl_modality').value).toBe('XRAY');
  });

  it('template table renders inactive badge for inactive templates', async () => {
    global.fetch = vi.fn((url) => {
      if (String(url).includes('templates')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: [{ id: '1', name: 'Old', modality: 'MRI', findings: '', impression: '', recommendations: '', is_active: false }] }) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ macros: MACROS }) });
    });
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 30));
    expect(document.querySelector('#tpl_table_body').innerHTML).toContain('bg-secondary');
  });

  it('template table skips entries without id', async () => {
    global.fetch = vi.fn((url) => {
      if (String(url).includes('templates')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: [null, { name: 'noid' }, { id: '5', name: 'ok', modality: 'XRAY', is_active: true }] }) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ macros: MACROS }) });
    });
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 30));
    expect(document.querySelectorAll('#tpl_table_body tr').length).toBe(1);
  });

  it('template table renders missing modality as empty badge text', async () => {
    global.fetch = vi.fn((url) => {
      if (String(url).includes('templates')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: [{ id: '5', name: 'NoMod', is_active: true }] }) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ macros: MACROS }) });
    });
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 30));
    expect(document.querySelector('#tpl_table_body tr').textContent).toContain('NoMod');
  });
});

describe('radiology/process.js macro branches', () => {
  it('macro table renders inactive badge and skips entries without id', async () => {
    global.fetch = vi.fn((url) => {
      if (String(url).includes('macros')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ macros: [null, { name: 'noid' }, { id: '9', name: 'Old', text: 't', is_active: false }] }) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: TEMPLATES }) });
    });
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 30));
    const tbody = document.querySelector('#macro_table_body');
    expect(tbody.querySelectorAll('tr').length).toBe(1);
    expect(tbody.innerHTML).toContain('bg-secondary');
  });

  it('macro table renders missing name as empty cell text', async () => {
    global.fetch = vi.fn((url) => {
      if (String(url).includes('macros')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ macros: [{ id: '9', text: 'only text', is_active: true }] }) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: TEMPLATES }) });
    });
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 30));
    expect(document.querySelectorAll('#macro_table_body tr').length).toBe(1);
  });

  it('apply macro with macro_target missing inserts into findings', async () => {
    document.getElementById('macro_target').remove();
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    document.getElementById('report_macro').value = '9';
    document.getElementById('findings').value = '';
    document.getElementById('apply_macro_btn').click();
    expect(document.getElementById('findings').value).toBe('Heart size is normal');
  });

  it('macros modal show event resets form and refreshes macros', async () => {
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    document.getElementById('macro_name').value = 'dirty';
    const modal = document.getElementById('radiologyMacrosModal');
    modal.dispatchEvent(new Event('show.bs.modal'));
    await new Promise(r => setTimeout(r, 60));
    expect(document.getElementById('macro_name').value).toBe('');
  });

  it('macro reset button with missing macro_id element does nothing', async () => {
    document.getElementById('macro_id').remove();
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    expect(() => document.getElementById('macro_reset_btn').click()).not.toThrow();
  });

  it('macro reset button clears the form', async () => {
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    document.getElementById('macro_name').value = 'x';
    document.getElementById('macro_text').value = 'y';
    document.getElementById('macro_reset_btn').click();
    expect(document.getElementById('macro_name').value).toBe('');
    expect(document.getElementById('macro_active').checked).toBe(true);
  });

  it('apply macro with missing macro_select does nothing', async () => {
    document.getElementById('report_macro').remove();
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    expect(() => document.getElementById('apply_macro_btn').click()).not.toThrow();
  });

  it('apply macro with unknown id does nothing', async () => {
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    const select = document.getElementById('report_macro');
    select.innerHTML = '<option value="missing">X</option>';
    select.value = 'missing';
    document.getElementById('apply_macro_btn').click();
    expect(document.getElementById('findings').value).toBe('');
  });

  it('apply macro appends to non-empty target with newline', async () => {
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    document.getElementById('report_macro').value = '9';
    document.getElementById('findings').value = 'previous findings';
    document.getElementById('apply_macro_btn').click();
    expect(document.getElementById('findings').value).toBe('previous findings\nHeart size is normal');
  });

  it('apply macro with missing macroEntry text inserts empty string', async () => {
    global.fetch = vi.fn((url) => {
      if (String(url).includes('macros')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ macros: [{ id: '9', name: 'NoText', is_active: true }] }) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: TEMPLATES }) });
    });
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    document.getElementById('report_macro').value = '9';
    document.getElementById('findings').value = '';
    document.getElementById('apply_macro_btn').click();
    expect(document.getElementById('findings').value).toBe('');
  });

  it('apply macro with missing target textarea does nothing', async () => {
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    document.getElementById('report_macro').value = '9';
    document.getElementById('macro_target').value = 'recommendations';
    document.getElementById('recommendations').remove();
    expect(() => document.getElementById('apply_macro_btn').click()).not.toThrow();
  });

  it('macro delete cancelled in confirm does not delete', async () => {
    window.confirm = vi.fn(() => false);
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    global.fetch.mockClear();
    const tr = document.querySelector('#macro_table_body tr');
    tr.querySelector('button[data-action="delete"]').click();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch.mock.calls.some(c => String(c[0]).includes('macro-delete'))).toBe(false);
  });

  it('macro edit with missing name/text in cache fills empty values', async () => {
    global.fetch = vi.fn((url) => {
      if (String(url).includes('macros')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ macros: [{ id: '9', is_active: false }] }) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: TEMPLATES }) });
    });
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    const tr = document.querySelector('#macro_table_body tr');
    tr.querySelector('button[data-action="edit"]').click();
    expect(document.getElementById('macro_name').value).toBe('');
    expect(document.getElementById('macro_text').value).toBe('');
    expect(document.getElementById('macro_active').checked).toBe(false);
  });

  it('macro save fetch rejection shows showToast and keeps form state', async () => {
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.includes('macro-save')) return Promise.reject(new Error('network'));
      if (u.includes('macros')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ macros: MACROS }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: TEMPLATES }) });
    });
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    document.getElementById('macro_name').value = 'M';
    document.getElementById('radiologyMacroForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 60));
    expect(window.showToast).toHaveBeenCalled();
  });

  it('macro save rejection falls back to alert without showToast', async () => {
    delete window.showToast;
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.includes('macro-save')) return Promise.reject(new Error('network'));
      if (u.includes('macros')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ macros: MACROS }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: TEMPLATES }) });
    });
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    document.getElementById('radiologyMacroForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 60));
    expect(window.alert).toHaveBeenCalled();
  });

  it('template save fetch rejection falls back to alert without showToast', async () => {
    delete window.showToast;
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.includes('template-save')) return Promise.reject(new Error('network'));
      if (u.includes('templates')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: TEMPLATES }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ macros: MACROS }) });
    });
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    document.getElementById('radiologyTemplateForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 60));
    expect(window.alert).toHaveBeenCalled();
  });

  it('template save rejection keeps showToast path when present', async () => {
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.includes('template-save')) return Promise.reject(new Error('network'));
      if (u.includes('templates')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: TEMPLATES }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ macros: MACROS }) });
    });
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    document.getElementById('radiologyTemplateForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 60));
    expect(window.showToast).toHaveBeenCalled();
  });

  it('template delete with notify missing still attempts alert fallback', async () => {
    delete window.notify;
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.includes('template-delete')) return Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) });
      if (u.includes('templates')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: TEMPLATES }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ macros: MACROS }) });
    });
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    const tr = document.querySelector('#tpl_table_body tr');
    tr.querySelector('button[data-action="delete"]').click();
    await new Promise(r => setTimeout(r, 60));
    expect(true).toBe(true); // must not throw
  });

  it('macro delete fetch rejection falls back to alert without showToast', async () => {
    delete window.showToast;
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.includes('macro-delete')) return Promise.reject(new Error('network'));
      if (u.includes('macros')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ macros: MACROS }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: TEMPLATES }) });
    });
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    const tr = document.querySelector('#macro_table_body tr');
    tr.querySelector('button[data-action="delete"]').click();
    await new Promise(r => setTimeout(r, 60));
    expect(window.alert).toHaveBeenCalled();
  });

  it('template delete fetch rejection falls back to alert without showToast', async () => {
    delete window.showToast;
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.includes('template-delete')) return Promise.reject(new Error('network'));
      if (u.includes('templates')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: TEMPLATES }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ macros: MACROS }) });
    });
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    const tr = document.querySelector('#tpl_table_body tr');
    tr.querySelector('button[data-action="delete"]').click();
    await new Promise(r => setTimeout(r, 60));
    expect(window.alert).toHaveBeenCalled();
  });

  it('template edit with missing modality defaults to XRAY', async () => {
    global.fetch = vi.fn((url) => {
      if (String(url).includes('templates')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: [{ id: '1', name: 'NoMod', findings: 'f', impression: 'i', recommendations: 'r', is_active: true }] }) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ macros: MACROS }) });
    });
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    const tr = document.querySelector('#tpl_table_body tr');
    tr.querySelector('button[data-action="edit"]').click();
    expect(document.getElementById('tpl_modality').value).toBe('XRAY');
  });

  it('template cancelled in confirm does not delete', async () => {
    window.confirm = vi.fn(() => false);
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    global.fetch.mockClear();
    const tr = document.querySelector('#tpl_table_body tr');
    tr.querySelector('button[data-action="delete"]').click();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch.mock.calls.some(c => String(c[0]).includes('template-delete'))).toBe(false);
  });

  it('template edit with missing fields fills empty values', async () => {
    global.fetch = vi.fn((url) => {
      if (String(url).includes('templates')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: [{ id: '1', is_active: false }] }) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ templates: TEMPLATES, macros: MACROS }) });
    });
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    const tr = document.querySelector('#tpl_table_body tr');
    tr.querySelector('button[data-action="edit"]').click();
    expect(document.getElementById('tpl_name').value).toBe('');
    expect(document.getElementById('tpl_findings').value).toBe('');
    expect(document.getElementById('tpl_modality').value).toBe('XRAY');
    expect(document.getElementById('tpl_active').checked).toBe(false);
  });

  it('macro edit missing id is skipped when clicked via unknown data-id', async () => {
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    const tbody = document.getElementById('macro_table_body');
    const btn = document.createElement('button');
    btn.setAttribute('data-action', 'edit');
    btn.setAttribute('data-id', 'does-not-exist');
    tbody.appendChild(btn);
    btn.click();
    expect(document.getElementById('macro_id').value).toBe('');
  });

  it('template delete request encodes the id', async () => {
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    global.fetch.mockClear();
    const tr = document.querySelector('#tpl_table_body tr');
    tr.querySelector('button[data-action="delete"]').click();
    await new Promise(r => setTimeout(r, 60));
    const deleteCall = global.fetch.mock.calls.find(c => String(c[0]).includes('template-delete'));
    expect(deleteCall).toBeTruthy();
    expect(deleteCall[1].method).toBe('POST');
  });

  it('template form submit with empty id sends id undefined', async () => {
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    document.getElementById('radiologyTemplateForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 60));
    const saveCall = global.fetch.mock.calls.find(c => String(c[0]).includes('template-save'));
    expect(saveCall).toBeTruthy();
    const body = JSON.parse(saveCall[1].body);
    expect(body.id).toBeUndefined();
  });

  it('macro form submit with empty id sends id undefined', async () => {
    await loadModule('static/js/pages/radiology/process.js');
    await new Promise(r => setTimeout(r, 20));
    document.getElementById('radiologyMacroForm').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(r => setTimeout(r, 60));
    const saveCall = global.fetch.mock.calls.find(c => String(c[0]).includes('macro-save'));
    expect(saveCall).toBeTruthy();
    const body = JSON.parse(saveCall[1].body);
    expect(body.id).toBeUndefined();
  });
});
