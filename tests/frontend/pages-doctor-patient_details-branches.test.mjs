import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <div id="diagnosis-tab"></div>
    <div id="prescriptions-tab"></div>
    <div id="lab-tab"></div>
    <div id="radiology-tab"></div>
    <div id="history-tab"></div>
    <input id="field1">
    <textarea id="field2"></textarea>
    <select id="field3"><option>x</option></select>
  `;
  for (const id of ['diagnosis-tab', 'prescriptions-tab', 'lab-tab', 'radiology-tab', 'history-tab']) {
    window['clickCount_' + id] = 0;
    document.getElementById(id).addEventListener('click', () => { window['clickCount_' + id]++; });
  }
}

beforeEach(() => {
  baseDom();
  window.__M = [];
  window.__M0__ = '/d';
  window.__M1__ = '/r';
  window.location = { href: '' };
});

afterEach(() => {
  vi.useRealTimers();
});

describe('patient_details.js keyboard shortcut branches', () => {
  it('alt+1 through alt+5 click the matching tabs', async () => {
    await loadModule('static/js/pages/doctor/patient_details.js');
    const tabs = ['diagnosis-tab', 'prescriptions-tab', 'lab-tab', 'radiology-tab', 'history-tab'];
    for (const [index, id] of tabs.entries()) {
      document.dispatchEvent(new KeyboardEvent('keydown', { key: String(index + 1), altKey: true, bubbles: true }));
      expect(window['clickCount_' + id]).toBe(1);
    }
  });

  it('alt+d navigates to __M0__ and alt+r navigates to __M1__ (case insensitive)', async () => {
    await loadModule('static/js/pages/doctor/patient_details.js');
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'd', altKey: true, bubbles: true }));
    expect(window.location.href).toBe('/d');
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'R', altKey: true, bubbles: true }));
    expect(window.location.href).toBe('/r');
  });

  it('keydown inside an input field is ignored', async () => {
    await loadModule('static/js/pages/doctor/patient_details.js');
    for (const id of ['field1', 'field2', 'field3']) {
      const el = document.getElementById(id);
      el.dispatchEvent(new KeyboardEvent('keydown', { key: '1', altKey: true, bubbles: true }));
    }
    expect(window['clickCount_diagnosis-tab']).toBe(0);
  });

  it('keydown without the Alt modifier does nothing', async () => {
    await loadModule('static/js/pages/doctor/patient_details.js');
    document.dispatchEvent(new KeyboardEvent('keydown', { key: '1', bubbles: true }));
    expect(window['clickCount_diagnosis-tab']).toBe(0);
  });

  it('unrelated Alt combos do nothing', async () => {
    await loadModule('static/js/pages/doctor/patient_details.js');
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'x', altKey: true, bubbles: true }));
    expect(window['clickCount_diagnosis-tab']).toBe(0);
    expect(window.location.href).toBe('');
  });

  it('missing tab elements do not crash', async () => {
    document.getElementById('diagnosis-tab').remove();
    await loadModule('static/js/pages/doctor/patient_details.js');
    expect(() => document.dispatchEvent(new KeyboardEvent('keydown', { key: '1', altKey: true, bubbles: true }))).not.toThrow();
  });
});
