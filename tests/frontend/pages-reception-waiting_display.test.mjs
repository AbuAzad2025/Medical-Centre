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
    handlers,
  };
}

beforeEach(() => {
  baseDom();
  window.io = vi.fn(() => makeSocket());
  window.escHtml = (s) => String(s ?? '');
  window.__MOTION_ENABLED__ = () => true;
  window.__M0__ = '/api/queue/display';
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({
      success: true,
      current: [{ queue_number: 'A-1', department_name: 'Cardiology', doctor_name: 'Dr A', room_name: 'R1' }],
      called: [{ queue_number: 'A-2', department_name: 'Lab', doctor_name: 'Dr B' }],
      waiting: [{ queue_number: 'A-3', department_name: 'Radiology', doctor_name: 'Dr C' }],
    }),
  });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('reception/waiting_display.js', () => {
  it('creates socket on /queue namespace', async () => {
    await loadModule('static/js/pages/reception/waiting_display.js');
    expect(window.io).toHaveBeenCalledWith('/queue');
  });

  it('renders the clock at load', async () => {
    await loadModule('static/js/pages/reception/waiting_display.js');
    expect(document.getElementById('live-clock').textContent).toMatch(/\d{2}:\d{2}/);
  });

  it('refresh fetches and renders lists', async () => {
    await loadModule('static/js/pages/reception/waiting_display.js');
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
    expect(document.getElementById('current-list').innerHTML).toContain('A-1');
    expect(document.getElementById('called-list').innerHTML).toContain('A-2');
    expect(document.getElementById('waiting-list').innerHTML).toContain('A-3');
    expect(document.getElementById('current-list').hasAttribute('data-stale')).toBe(false);
  });

  it('refresh failure marks lists stale', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    await loadModule('static/js/pages/reception/waiting_display.js');
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('current-list').hasAttribute('data-stale')).toBe(true);
    expect(document.getElementById('called-list').hasAttribute('data-stale')).toBe(true);
  });

  it('refresh with unsuccessful payload does not throw and leaves stale marks', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    await loadModule('static/js/pages/reception/waiting_display.js');
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('current-list').hasAttribute('data-stale')).toBe(false);
  });

  it('empty lists render empty state text', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, current: [], called: [], waiting: [] }) });
    await loadModule('static/js/pages/reception/waiting_display.js');
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('current-list').innerHTML).toContain('لا يوجد');
  });

  it('room name rendered when present', async () => {
    await loadModule('static/js/pages/reception/waiting_display.js');
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('current-list').innerHTML).toContain('R1');
  });

  it('motion disabled removes queue-card-enter class', async () => {
    window.__MOTION_ENABLED__ = () => false;
    await loadModule('static/js/pages/reception/waiting_display.js');
    await new Promise(r => setTimeout(r, 30));
    const card = document.querySelector('#current-list .p-3');
    expect(card.classList.contains('queue-card-enter')).toBe(false);
  });

  it('socket queue_display_waiting re-renders lists', async () => {
    const socket = makeSocket();
    window.io = vi.fn(() => socket);
    await loadModule('static/js/pages/reception/waiting_display.js');
    await new Promise(r => setTimeout(r, 30));
    socket.trigger('queue_display_waiting', {
      current: [{ queue_number: 'Z-9', department_name: 'X-Ray', doctor_name: 'Dr Z' }],
      called: [],
      waiting: [],
    });
    expect(document.getElementById('current-list').innerHTML).toContain('Z-9');
  });

  it('socket queue_display_waiting ignores null payload', async () => {
    const socket = makeSocket();
    window.io = vi.fn(() => socket);
    await loadModule('static/js/pages/reception/waiting_display.js');
    await new Promise(r => setTimeout(r, 30));
    expect(() => socket.trigger('queue_display_waiting', null)).not.toThrow();
  });
});