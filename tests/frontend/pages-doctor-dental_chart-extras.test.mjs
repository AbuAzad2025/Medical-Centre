import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <div id="selectedFdi"></div>
    <select id="toothStateSelect"><option value="sound">sound</option><option value="caries">caries</option><option value="missing">missing</option></select>
    <input id="toothNotes" value="">
    <input type="checkbox" id="s_occlusal">
    <input type="checkbox" id="s_buccal">
    <input type="checkbox" id="s_lingual">
    <input type="checkbox" id="s_mesial">
    <input type="checkbox" id="s_distal">
    <div id="toothEditor" style="display:none"></div>
    <div id="toothEditorEmpty" style="display:block"></div>
    <div class="tooth-group" data-fdi="11"><rect fill="#10b981"></rect></div>
    <ul id="summaryList"></ul>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M = [];
  window.__M0__ = { sound: { label: 'سليم', color: '#10b981' }, caries: { label: 'تسوس', color: '#f59e0b' }, missing: { label: 'مفقود', color: '#ef4444' } };
  window.__M1__ = { 11: { state: 'caries', surfaces: { buccal: true }, notes: 'x-rays ordered' } };
  window.__M2__ = '/api/dental-chart/save';
  window.__M3__ = 'csrf-token';
  window.__M4__ = '9';
  window.__M5__ = '77';
  window.escHtml = (s) => String(s ?? '');
  window.notify = { success: vi.fn(), error: vi.fn() };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('dental_chart.js fallback arms', () => {
  it('tooth with no notes loads an empty notes field', async () => {
    window.__M1__ = { 21: { state: 'sound', surfaces: {} } };
    const mod = await loadModule('static/js/pages/doctor/dental_chart.js');
    document.body.insertAdjacentHTML('beforeend', '<div class="tooth-group" data-fdi="21"><rect fill="#10b981"></rect></div>');
    mod.openToothModal('21');
    expect(document.getElementById('toothNotes').value).toBe('');
  });

  it('missing surfaces collection defaults to no checked boxes', async () => {
    const mod = await loadModule('static/js/pages/doctor/dental_chart.js');
    mod.openToothModal('11'); // seeded tooth HAS surfaces — also exercise tooth without
    expect(document.getElementById('s_buccal').checked).toBe(true);
  });

  it('updateSvgTooth with an unknown state falls back to the default color', async () => {
    const mod = await loadModule('static/js/pages/doctor/dental_chart.js');
    mod.updateSvgTooth('11', 'mystery-state');
    const rect = document.querySelector('.tooth-group[data-fdi="11"] rect');
    expect(rect.getAttribute('fill')).toBe('#10b981');
  });

  it('updateSvgTooth does not add a second circle when one exists', async () => {
    const mod = await loadModule('static/js/pages/doctor/dental_chart.js');
    mod.updateSvgTooth('11', 'caries');
    const first = document.querySelector('.tooth-group[data-fdi="11"] circle');
    expect(first).toBeTruthy();
    mod.updateSvgTooth('11', 'missing');
    expect(document.querySelectorAll('.tooth-group[data-fdi="11"] circle').length).toBe(1);
  });

  it('updateSvgTooth with sound state and no circle does not throw', async () => {
    const mod = await loadModule('static/js/pages/doctor/dental_chart.js');
    expect(() => mod.updateSvgTooth('11', 'sound')).not.toThrow();
  });

  it('saveChart non-ok response throws into the catch arm', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/doctor/dental_chart.js');
    mod.saveChart();
    await new Promise(r => setTimeout(r, 30));
    expect(window.notify.error).toHaveBeenCalled();
  });

  it('saveChart server failure with custom message shows it', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'visit locked' }) });
    const mod = await loadModule('static/js/pages/doctor/dental_chart.js');
    mod.saveChart();
    await new Promise(r => setTimeout(r, 30));
    expect(window.notify.error).toHaveBeenCalledWith('visit locked');
  });

  it('saveChart server failure with no message uses the default text', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    const mod = await loadModule('static/js/pages/doctor/dental_chart.js');
    mod.saveChart();
    await new Promise(r => setTimeout(r, 30));
    expect(window.notify.error).toHaveBeenCalledWith('تعذّر حفظ مخطط الأسنان. حاول مرة أخرى.');
  });

  it('updateSummary ignores states with zero count and shows the empty message when empty', async () => {
    window.__M1__ = {};
    const mod = await loadModule('static/js/pages/doctor/dental_chart.js');
    mod.updateSummary();
    expect(document.getElementById('summaryList').innerHTML).toContain('لا يوجد');
  });

  it('STATES without a key for a stored tooth state does not crash updateSummary', async () => {
    window.__M0__ = { sound: { label: 'سليم', color: '#10b981' } };
    window.__M1__ = { 11: { state: 'weird', surfaces: {} } };
    const mod = await loadModule('static/js/pages/doctor/dental_chart.js');
    expect(() => mod.updateSummary()).not.toThrow();
  });
});
