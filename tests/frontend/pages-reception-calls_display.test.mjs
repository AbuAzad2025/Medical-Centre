import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <div id="live-clock">--:--</div>
    <div id="calls-grid"></div>
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
  window.__M0__ = '/api/queue/calls';
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({
      success: true,
      items: [{ queue_number: 'B-1', department_name: 'Cardiology', doctor_name: 'Dr A', room_name: 'R1', status: 'called' }],
    }),
  });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('reception/calls_display.js', () => {
  it('creates socket on /queue namespace', async () => {
    await loadModule('static/js/pages/reception/calls_display.js');
    expect(window.io).toHaveBeenCalledWith('/queue');
  });

  it('renders the clock at load', async () => {
    await loadModule('static/js/pages/reception/calls_display.js');
    expect(document.getElementById('live-clock').textContent).toMatch(/\d{2}:\d{2}/);
  });

  it('refresh fetches and renders the calls grid', async () => {
    await loadModule('static/js/pages/reception/calls_display.js');
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
    expect(document.getElementById('calls-grid').innerHTML).toContain('B-1');
    expect(document.getElementById('calls-grid').innerHTML).toContain('Cardiology');
    expect(document.getElementById('calls-grid').hasAttribute('data-stale')).toBe(false);
  });

  it('refresh failure marks the grid stale', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    await loadModule('static/js/pages/reception/calls_display.js');
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('calls-grid').hasAttribute('data-stale')).toBe(true);
  });

  it('refresh with unsuccessful payload does not throw and keeps grid empty', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    await loadModule('static/js/pages/reception/calls_display.js');
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('calls-grid').hasAttribute('data-stale')).toBe(false);
  });

  it('empty items shows empty-state text', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, items: [] }) });
    await loadModule('static/js/pages/reception/calls_display.js');
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('calls-grid').innerHTML).toContain('لا يوجد');
  });

  it('room name rendered when present', async () => {
    await loadModule('static/js/pages/reception/calls_display.js');
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('calls-grid').innerHTML).toContain('R1');
  });

  it('status text rendered', async () => {
    await loadModule('static/js/pages/reception/calls_display.js');
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('calls-grid').innerHTML).toContain('called');
  });

  it('socket queue_display_calls re-renders the grid', async () => {
    const socket = makeSocket();
    window.io = vi.fn(() => socket);
    await loadModule('static/js/pages/reception/calls_display.js');
    await new Promise(r => setTimeout(r, 30));
    socket.trigger('queue_display_calls', { items: [{ queue_number: 'Z-9', department_name: 'X-Ray', doctor_name: 'Dr Z', status: 'now' }] });
    expect(document.getElementById('calls-grid').innerHTML).toContain('Z-9');
  });

  it('socket with null payload leaves grid intact', async () => {
    const socket = makeSocket();
    window.io = vi.fn(() => socket);
    await loadModule('static/js/pages/reception/calls_display.js');
    await new Promise(r => setTimeout(r, 30));
    document.getElementById('calls-grid').innerHTML = '<span>existing</span>';
    socket.trigger('queue_display_calls', null);
    expect(document.getElementById('calls-grid').innerHTML).toContain('existing');
  });
});