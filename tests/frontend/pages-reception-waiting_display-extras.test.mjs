import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <div id="live-clock">--:--</div>
    <div id="current-list"></div>
    <div id="called-list"></div>
    <div id="waiting-list"></div>
  `;
}

function makeSocket() {
  const handlers = {};
  return {
    on: vi.fn((event, cb) => { handlers[event] = cb; }),
    trigger(event, data) { if (handlers[event]) handlers[event](data); },
  };
}

beforeEach(() => {
  baseDom();
  window.__M = ['preset'];
  window.__M0__ = '/api/queue/waiting';
  window.io = vi.fn(() => makeSocket());
  window.escHtml = (s) => String(s ?? '');
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, current: [{ queue_number: 'A-1', department_name: 'ENT', doctor_name: 'Dr X' }], called: [{ queue_number: 'B-2', department_name: 'Lab', doctor_name: 'Dr Y', room_name: 'Lab1' }], waiting: [{ queue_number: 'C-3', department_name: 'Cardio', doctor_name: 'Dr Z' }] }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('waiting_display.js fallback arms', () => {
  it('missing queue_number renders dash', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, current: [{ department_name: 'ENT' }], called: [], waiting: [] }) });
    await loadModule('static/js/pages/reception/waiting_display.js');
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('current-list').innerHTML).toContain('>-<');
  });

  it('missing room name renders empty room text', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, current: [], called: [{ queue_number: 'B-9', department_name: 'Lab', doctor_name: 'Dr Y' }], waiting: [] }) });
    await loadModule('static/js/pages/reception/waiting_display.js');
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('called-list').innerHTML).toContain('B-9');
  });

  it('success refresh clears previously stale lists', async () => {
    document.getElementById('current-list').setAttribute('data-stale', '');
    document.getElementById('called-list').setAttribute('data-stale', '');
    document.getElementById('waiting-list').setAttribute('data-stale', '');
    await loadModule('static/js/pages/reception/waiting_display.js');
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('current-list').hasAttribute('data-stale')).toBe(false);
    expect(document.getElementById('called-list').hasAttribute('data-stale')).toBe(false);
    expect(document.getElementById('waiting-list').hasAttribute('data-stale')).toBe(false);
  });

  it('missing one of the three lists does not crash refresh', async () => {
    document.getElementById('current-list').remove();
    await loadModule('static/js/pages/reception/waiting_display.js');
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('called-list').textContent).toContain('B-2');
  });

  it('missing one of the three lists does not crash markStale on failure', async () => {
    document.getElementById('called-list').remove();
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    await loadModule('static/js/pages/reception/waiting_display.js');
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('current-list').hasAttribute('data-stale')).toBe(true);
  });

  it('socket with missing list element does not crash', async () => {
    document.getElementById('waiting-list').remove();
    await loadModule('static/js/pages/reception/waiting_display.js');
    const socket = window.io.mock.results[0].value;
    expect(() => socket.trigger('queue_display_waiting', { current: [], called: [], waiting: [{ queue_number: 'W-1', department_name: 'ENT', doctor_name: 'Dr X' }] })).not.toThrow();
  });

  it('motion enabled keeps the enter-animation class', async () => {
    window.__MOTION_ENABLED__ = () => true;
    await loadModule('static/js/pages/reception/waiting_display.js');
    await new Promise(r => setTimeout(r, 30));
    expect(document.querySelector('.queue-card-enter')).toBeTruthy();
    delete window.__MOTION_ENABLED__;
  });
});
