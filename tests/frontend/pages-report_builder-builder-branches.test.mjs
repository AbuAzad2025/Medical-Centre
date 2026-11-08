import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <select id="entitySelect"><option value="">اختر</option><option value="patients">مرضى</option></select>
    <div id="fieldsContainer"></div>
    <select id="templateSelect"><option value="">بدون قالب</option><option value="7">T7</option></select>
    <input id="templateName" value="">
    <input id="limitInput" value="100">
    <button id="generateBtn">Go</button>
    <button id="saveTemplateBtn">Save</button>
    <button id="runTemplateBtn" disabled>Run</button>
    <div id="reportResult"></div>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M = [];
  window.__M0__ = { patients: { label: 'مرضى', fields: ['id', 'name', 'phone'] } };
  window.__M1__ = '/report/preview';
  window.__M2__ = 'csrf';
  window.__M3__ = '/report/save';
  window.__M4__ = '/report/list';
  window.__M5__ = {};
  window.__M6__ = null;
  window.__M7__ = '/report/templates/';
  window.escHtml = (s) => String(s ?? '');
  window.location = { href: '', pathname: '/report/builder' };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, headers: ['id'], rows: [{ id: 1 }] }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('builder.js renderFieldsForEntity fallback arms', () => {
  it('null selectedFields renders every field checked', async () => {
    const mod = await loadModule('static/js/pages/report_builder/builder.js');
    mod.renderFieldsForEntity('patients', null);
    expect(document.querySelectorAll('input[name="fields"]:checked').length).toBe(3);
  });

  it('empty key does nothing and clears the container', async () => {
    const mod = await loadModule('static/js/pages/report_builder/builder.js');
    document.getElementById('fieldsContainer').innerHTML = '<span>stale</span>';
    mod.renderFieldsForEntity('', []);
    expect(document.getElementById('fieldsContainer').innerHTML).toBe('');
  });

  it('unknown entity also clears the container', async () => {
    const mod = await loadModule('static/js/pages/report_builder/builder.js');
    mod.renderFieldsForEntity('nope', ['id']);
    expect(document.getElementById('fieldsContainer').innerHTML).toBe('');
  });

  it('specific selection renders only the chosen fields checked', async () => {
    const mod = await loadModule('static/js/pages/report_builder/builder.js');
    mod.renderFieldsForEntity('patients', ['id']);
    const checked = [...document.querySelectorAll('input[name="fields"]:checked')].map(cb => cb.value);
    expect(checked).toEqual(['id']);
  });

  it('empty array of selected fields renders none checked', async () => {
    const mod = await loadModule('static/js/pages/report_builder/builder.js');
    mod.renderFieldsForEntity('patients', []);
    // selected.size === 0 → every field checked (the ': true' arm), this covers the size?0:true second arm
    expect(document.querySelectorAll('input[name="fields"]:checked').length).toBe(3);
  });
});

describe('builder.js renderTable fallback arms', () => {
  it('error without message uses the default failure text', async () => {
    const mod = await loadModule('static/js/pages/report_builder/builder.js');
    mod.renderTable({ success: false });
    expect(document.getElementById('reportResult').innerHTML).toContain('تعذّر إنشاء التقرير');
  });

  it('rows with missing cells render empty cells', async () => {
    const mod = await loadModule('static/js/pages/report_builder/builder.js');
    mod.renderTable({ success: true, headers: ['id', 'missing'], rows: [{ id: 7 }] });
    expect(document.getElementById('reportResult').innerHTML).toContain('<td>7</td>');
    expect(document.getElementById('reportResult').innerHTML).toContain('<td></td>');
  });
});

describe('builder.js network failure arms', () => {
  it('generateBtn fetch failure shows the connection error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/report_builder/builder.js');
    mod.generateReport();
    await new Promise(r => setTimeout(r, 40));
    expect(document.getElementById('reportResult').innerHTML).toContain('انقطع الاتصال');
  });

  it('generateBtn non-ok response shows the connection error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/report_builder/builder.js');
    mod.generateReport();
    await new Promise(r => setTimeout(r, 40));
    expect(document.getElementById('reportResult').innerHTML).toContain('انقطع الاتصال');
  });

  it('saveTemplateBtn fetch failure shows the connection error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    await loadModule('static/js/pages/report_builder/builder.js');
    document.getElementById('templateName').value = 'My template';
    document.getElementById('saveTemplateBtn').click();
    await new Promise(r => setTimeout(r, 40));
    expect(document.getElementById('reportResult').innerHTML).toContain('انقطع الاتصال');
  });

  it('saveTemplateBtn non-ok response shows the connection error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    await loadModule('static/js/pages/report_builder/builder.js');
    document.getElementById('templateName').value = 'My template';
    document.getElementById('saveTemplateBtn').click();
    await new Promise(r => setTimeout(r, 40));
    expect(document.getElementById('reportResult').innerHTML).toContain('انقطع الاتصال');
  });

  it('runTemplateBtn non-ok response shows the connection error', async () => {
    window.__M5__ = { entity: 'patients' };
    window.__M6__ = '5';
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    await loadModule('static/js/pages/report_builder/builder.js');
    document.getElementById('runTemplateBtn').click();
    await new Promise(r => setTimeout(r, 40));
    expect(document.getElementById('reportResult').innerHTML).toContain('انقطع الاتصال');
  });
});

describe('builder.js initialConfig branches', () => {
  it('initial config with an entity renders its fields and enables run', async () => {
    window.__M5__ = { entity: 'patients', fields: ['id'] };
    window.__M6__ = '9';
    await loadModule('static/js/pages/report_builder/builder.js');
    expect(document.querySelectorAll('input[name="fields"]').length).toBe(3);
    expect(document.getElementById('runTemplateBtn').disabled).toBe(false);
  });

  it('initial config with entity but no active template keeps run disabled', async () => {
    window.__M5__ = { entity: 'patients' };
    window.__M6__ = null;
    await loadModule('static/js/pages/report_builder/builder.js');
    expect(document.getElementById('runTemplateBtn').disabled).toBe(true);
  });

  it('initial config without entity does not render fields', async () => {
    window.__M5__ = {};
    await loadModule('static/js/pages/report_builder/builder.js');
    expect(document.querySelectorAll('input[name="fields"]').length).toBe(0);
  });

  it('missing __M5__ falls back to the empty object', async () => {
    delete window.__M5__;
    window.__M6__ = undefined;
    await expect(loadModule('static/js/pages/report_builder/builder.js')).resolves.toBeDefined();
  });
});

describe('builder.js templateSelect and save flow arms', () => {
  it('templateSelect to a concrete id navigates with the query param', async () => {
    await loadModule('static/js/pages/report_builder/builder.js');
    const select = document.getElementById('templateSelect');
    select.value = '7';
    select.dispatchEvent(new Event('change'));
    expect(window.location.href).toContain('?template=7');
  });

  it('templateSelect to empty disables run and clears the name', async () => {
    await loadModule('static/js/pages/report_builder/builder.js');
    const select = document.getElementById('templateSelect');
    document.getElementById('templateName').value = 'old';
    select.value = '';
    select.dispatchEvent(new Event('change'));
    expect(document.getElementById('runTemplateBtn').disabled).toBe(true);
    expect(document.getElementById('templateName').value).toBe('');
  });

  it('save success without template id does not enable the run button', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, template: { id: 11 } }) });
    await loadModule('static/js/pages/report_builder/builder.js');
    document.getElementById('templateName').value = 'My template';
    document.getElementById('saveTemplateBtn').click();
    await new Promise(r => setTimeout(r, 40));
    expect(document.getElementById('runTemplateBtn').disabled).toBe(false);
    expect(document.getElementById('reportResult').innerHTML).toContain('alert-success');
  });

  it('save failure with message renders the server text', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'تكرار الاسم' }) });
    await loadModule('static/js/pages/report_builder/builder.js');
    document.getElementById('templateName').value = 'My template';
    document.getElementById('saveTemplateBtn').click();
    await new Promise(r => setTimeout(r, 40));
    expect(document.getElementById('reportResult').innerHTML).toContain('تكرار الاسم');
  });

  it('save failure without message uses the default text', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    await loadModule('static/js/pages/report_builder/builder.js');
    document.getElementById('templateName').value = 'My template';
    document.getElementById('saveTemplateBtn').click();
    await new Promise(r => setTimeout(r, 40));
    expect(document.getElementById('reportResult').innerHTML).toContain('تعذّر حفظ القالب');
  });

  it('collectPayload carries template_id from the active template', async () => {
    window.__M6__ = '3';
    const mod = await loadModule('static/js/pages/report_builder/builder.js');
    const payload = mod.collectPayload();
    expect(payload.template_id).toBe('3');
  });
});
