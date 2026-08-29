import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <svg><g class="tooth-group" data-fdi="11"><rect fill="#10b981"/></g></svg>
    <div id="selectedFdi"></div>
    <select id="toothStateSelect"><option value="sound">Sound</option><option value="carious">Carious</option></select>
    <textarea id="toothNotes"></textarea>
    <input type="checkbox" id="s_occlusal" />
    <input type="checkbox" id="s_buccal" />
    <input type="checkbox" id="s_lingual" />
    <input type="checkbox" id="s_mesial" />
    <input type="checkbox" id="s_distal" />
    <div id="toothEditor" style="display:none"></div>
    <div id="toothEditorEmpty"></div>
    <div id="summaryList"></div>
  `;
  window.__M0__ = { sound: { color: '#10b981', label: 'سليم' }, carious: { color: '#dc3545', label: 'تسوس' } };
  window.__M1__ = {};
  window.__M2__ = '/api/save';
  window.__M3__ = 'csrf-token';
  window.__M4__ = '1';
  window.__M5__ = '100';
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  window.notify = { success: vi.fn(), error: vi.fn() };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
});

describe('doctor/dental_chart.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/doctor/dental_chart.js');
  });
});
