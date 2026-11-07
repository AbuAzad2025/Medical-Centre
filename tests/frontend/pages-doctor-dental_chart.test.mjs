import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <meta name="csrf-token" content="test-csrf">
    <svg viewBox="0 0 160 90" xmlns="http://www.w3.org/2000/svg">
      <g class="tooth-group" data-fdi="11"><rect width="40" height="40" fill="#10b981"></rect></g>
      <g class="tooth-group" data-fdi="12"><rect width="40" height="40" fill="#10b981"></rect><circle cx="15" cy="10" r="3"></circle></g>
    </svg>
    <div id="selectedFdi"></div>
    <select id="toothStateSelect"><option value="sound">sound</option><option value="caries">caries</option><option value="restored">restored</option></select>
    <textarea id="toothNotes"></textarea>
    <input type="checkbox" id="s_occlusal">
    <input type="checkbox" id="s_buccal">
    <input type="checkbox" id="s_lingual">
    <input type="checkbox" id="s_mesial">
    <input type="checkbox" id="s_distal">
    <div id="toothEditor" style="display:none"></div>
    <div id="toothEditorEmpty" style="display:block"></div>
    <ul id="summaryList"></ul>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M0__ = { sound: { color: '#10b981', label: 'سليم' }, caries: { color: '#ef4444', label: 'تسوس' }, restored: { color: '#3b82f6', label: 'مرمم' } };
  window.__M1__ = { '11': { state: 'sound', surfaces: {}, notes: '' }, '12': { state: 'caries', surfaces: { buccal: 'caries' }, notes: 'bad' } };
  window.__M2__ = '/api/dental/save';
  window.__M3__ = 'csrf-token-value';
  window.__M4__ = '9';
  window.__M5__ = '3';
  window.escHtml = (s) => String(s || '');
  window.notify = { success: vi.fn(), error: vi.fn() };
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.bootstrap = { Collapse: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn() })) }, Modal: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn(), hide: vi.fn() })) } };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('doctor/dental_chart.js', () => {
  it('openToothModal populates the editor with tooth state', async () => {
    const mod = await loadModule('static/js/pages/doctor/dental_chart.js');
    mod.openToothModal('11');
    expect(document.getElementById('selectedFdi').textContent).toBe('11');
    expect(document.getElementById('toothStateSelect').value).toBe('sound');
    expect(document.getElementById('toothEditor').style.display).toBe('block');
    expect(document.getElementById('toothEditorEmpty').style.display).toBe('none');
  });

  it('openToothModal with unknown tooth loads defaults', async () => {
    const mod = await loadModule('static/js/pages/doctor/dental_chart.js');
    mod.openToothModal('99');
    expect(document.getElementById('toothStateSelect').value).toBe('sound');
    expect(document.getElementById('toothNotes').value).toBe('');
  });

  it('applyToothState persists state, surfaces and notes', async () => {
    const mod = await loadModule('static/js/pages/doctor/dental_chart.js');
    mod.openToothModal('11');
    document.getElementById('toothStateSelect').value = 'caries';
    document.getElementById('toothNotes').value = 'deep cavity';
    document.getElementById('s_occlusal').checked = true;
    document.getElementById('s_buccal').checked = true;
    mod.applyToothState();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('applyToothState without selection does nothing', async () => {
    const mod = await loadModule('static/js/pages/doctor/dental_chart.js');
    expect(() => mod.applyToothState()).not.toThrow();
  });

  it('updateSvgTooth updates color for restored state', async () => {
    const mod = await loadModule('static/js/pages/doctor/dental_chart.js');
    mod.updateSvgTooth('11', 'restored');
    expect(document.querySelector('[data-fdi="11"] rect').getAttribute('fill')).toBe('#3b82f6');
    expect(document.querySelector('[data-fdi="11"] circle')).toBeTruthy();
  });

  it('updateSvgTooth removes circle when state is sound', async () => {
    const mod = await loadModule('static/js/pages/doctor/dental_chart.js');
    mod.updateSvgTooth('12', 'sound');
    expect(document.querySelector('[data-fdi="12"] circle')).toBeNull();
  });

  it('updateSvgTooth with missing group does nothing', async () => {
    const mod = await loadModule('static/js/pages/doctor/dental_chart.js');
    expect(() => mod.updateSvgTooth('99', 'caries')).not.toThrow();
  });

  it('updateSummary renders counts and empty state', async () => {
    const mod = await loadModule('static/js/pages/doctor/dental_chart.js');
    mod.updateSummary();
    expect(document.getElementById('summaryList').innerHTML).toContain('تسوس');
    expect(document.getElementById('summaryList').innerHTML).toContain('سليم');
  });

  it('saveChart posts payload on success', async () => {
    const mod = await loadModule('static/js/pages/doctor/dental_chart.js');
    mod.saveChart();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalledWith('/api/dental/save', expect.objectContaining({ method: 'POST' }));
    expect(window.notify.success).toHaveBeenCalledWith('تم حفظ مخطط الأسنان');
  });

  it('saveChart server failure shows error notify', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'dup' }) });
    const mod = await loadModule('static/js/pages/doctor/dental_chart.js');
    mod.saveChart();
    await new Promise(r => setTimeout(r, 30));
    expect(window.notify.error).toHaveBeenCalled();
  });

  it('saveChart network failure shows generic error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/doctor/dental_chart.js');
    mod.saveChart();
    await new Promise(r => setTimeout(r, 30));
    expect(window.notify.error).toHaveBeenCalled();
  });
});