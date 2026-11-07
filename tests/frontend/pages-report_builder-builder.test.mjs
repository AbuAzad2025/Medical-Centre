import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <meta name="csrf-token" content="test-csrf">
    <select id="entitySelect"><option value="">--</option><option value="patients">Patients</option><option value="visits">Visits</option></select>
    <div id="fieldsContainer"></div>
    <select id="templateSelect"><option value="">--</option><option value="7">Template</option></select>
    <input id="limitInput" type="number" value="50">
    <input id="templateName" value="">
    <div id="reportResult"></div>
    <button id="generateBtn">Generate</button>
    <button id="saveTemplateBtn">Save</button>
    <button id="runTemplateBtn" disabled>Run</button>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M = [];
  window.escHtml = (s) => String(s || '');
  window.__M0__ = { patients: { fields: ['id', 'full_name', 'phone'] }, visits: { fields: ['id', 'visit_date'] } };
  window.__M1__ = '/api/report/preview';
  window.__M2__ = 'csrf';
  window.__M3__ = '/api/report/save';
  window.__M4__ = '/api/report/list';
  window.__M5__ = { entity: 'patients', fields: ['id'] };
  window.__M6__ = 7;
  window.__M7__ = '/api/report/';
  window.location = { href: '', pathname: '/report_builder' };
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, headers: ['id'], rows: [{ id: 1 }], template: { id: 7 } }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('report_builder/builder.js', () => {
  it('renderFieldsForEntity renders fields with checked state', async () => {
    const mod = await loadModule('static/js/pages/report_builder/builder.js');
    mod.renderFieldsForEntity('patients', ['full_name']);
    const checkboxes = document.querySelectorAll('#fieldsContainer input[name="fields"]');
    expect(checkboxes.length).toBe(3);
    expect(checkboxes[0].checked).toBe(false);
    expect(checkboxes[1].checked).toBe(true);
  });

  it('renderFieldsForEntity unknown entity clears container', async () => {
    const mod = await loadModule('static/js/pages/report_builder/builder.js');
    document.getElementById('fieldsContainer').innerHTML = '<span>x</span>';
    mod.renderFieldsForEntity('nope');
    expect(document.getElementById('fieldsContainer').innerHTML).toBe('');
  });

  it('entity change updates fields', async () => {
    await loadModule('static/js/pages/report_builder/builder.js');
    const sel = document.getElementById('entitySelect');
    sel.value = 'visits';
    sel.dispatchEvent(new Event('change'));
    expect(document.getElementById('fieldsContainer').innerHTML).toContain('visit_date');
  });

  it('template change to empty resets active template', async () => {
    await loadModule('static/js/pages/report_builder/builder.js');
    const sel = document.getElementById('templateSelect');
    sel.value = '';
    sel.dispatchEvent(new Event('change'));
    expect(document.getElementById('templateName').value).toBe('');
    expect(document.getElementById('runTemplateBtn').disabled).toBe(true);
  });

  it('template change to id navigates', async () => {
    await loadModule('static/js/pages/report_builder/builder.js');
    const sel = document.getElementById('templateSelect');
    sel.value = '7';
    sel.dispatchEvent(new Event('change'));
    expect(window.location.href).toContain('?template=7');
  });

  it('collectPayload gathers entity, fields and limit', async () => {
    const mod = await loadModule('static/js/pages/report_builder/builder.js');
    document.getElementById('entitySelect').value = 'patients';
    document.getElementById('templateName').value = 'Q4';
    mod.renderFieldsForEntity('patients', []);
    const payload = mod.collectPayload();
    expect(payload.entity).toBe('patients');
    expect(payload.name).toBe('Q4');
    expect(payload.limit).toBe('50');
    expect(payload.template_id).toBe(7);
  });

  it('renderTable renders error alert on failure', async () => {
    const mod = await loadModule('static/js/pages/report_builder/builder.js');
    mod.renderTable({ success: false, message: 'boom' });
    expect(document.getElementById('reportResult').innerHTML).toContain('boom');
  });

  it('renderTable renders table on success', async () => {
    const mod = await loadModule('static/js/pages/report_builder/builder.js');
    mod.renderTable({ success: true, headers: ['h1'], rows: [{ h1: 'v' }] });
    expect(document.getElementById('reportResult').innerHTML).toContain('<th>');
    expect(document.getElementById('reportResult').innerHTML).toContain('h1');
  });

  it('generateBtn posts preview and renders result', async () => {
    await loadModule('static/js/pages/report_builder/builder.js');
    document.getElementById('generateBtn').click();
    await new Promise(r => setTimeout(r, 40));
    expect(global.fetch).toHaveBeenCalled();
    expect(global.fetch.mock.calls[0][0]).toBe('/api/report/preview');
  });

  it('runTemplateBtn does nothing without active template', async () => {
    window.__M6__ = null;
    window.__M5__ = {};
    await loadModule('static/js/pages/report_builder/builder.js');
    document.getElementById('runTemplateBtn').disabled = false;
    document.getElementById('runTemplateBtn').click();
    await new Promise(r => setTimeout(r, 20));
    expect(global.fetch.mock.calls.filter(c => String(c[0]).includes('/run')).length).toBe(0);
  });

  it('saveTemplateBtn without name shows warning', async () => {
    await loadModule('static/js/pages/report_builder/builder.js');
    document.getElementById('templateName').value = '';
    document.getElementById('saveTemplateBtn').click();
    await new Promise(r => setTimeout(r, 10));
    expect(document.getElementById('reportResult').innerHTML).toContain('أدخل اسماً');
  });

  it('saveTemplateBtn posts and shows success', async () => {
    await loadModule('static/js/pages/report_builder/builder.js');
    document.getElementById('templateName').value = 'T';
    document.getElementById('saveTemplateBtn').click();
    await new Promise(r => setTimeout(r, 40));
    expect(global.fetch).toHaveBeenCalledWith('/api/report/save', expect.objectContaining({ method: 'POST' }));
    expect(document.getElementById('reportResult').innerHTML).toContain('تم حفظ القالب');
  });

  it('saveTemplateBtn shows error on success:false', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'dup' }) });
    await loadModule('static/js/pages/report_builder/builder.js');
    document.getElementById('templateName').value = 'T';
    document.getElementById('saveTemplateBtn').click();
    await new Promise(r => setTimeout(r, 40));
    expect(document.getElementById('reportResult').innerHTML).toContain('dup');
  });

  it('runTemplateBtn click posts to run endpoint and renders', async () => {
    await loadModule('static/js/pages/report_builder/builder.js');
    document.getElementById('runTemplateBtn').disabled = false;
    document.getElementById('runTemplateBtn').click();
    await new Promise(r => setTimeout(r, 40));
    expect(global.fetch.mock.calls.some(c => String(c[0]).includes('/7/run'))).toBe(true);
  });

  it('runTemplateBtn fetch failure shows error alert', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    await loadModule('static/js/pages/report_builder/builder.js');
    document.getElementById('runTemplateBtn').disabled = false;
    document.getElementById('runTemplateBtn').click();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('reportResult').innerHTML).toContain('انقطع');
  });

  it('initial config sets entity and enables run button', async () => {
    await loadModule('static/js/pages/report_builder/builder.js');
    expect(document.getElementById('fieldsContainer').innerHTML).toContain('id');
    expect(document.getElementById('runTemplateBtn').disabled).toBe(false);
  });
});