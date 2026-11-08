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

let socket;

beforeEach(() => {
  baseDom();
  socket = makeSocket();
  window.io = vi.fn(() => socket);
  window.escHtml = (s) => String(s ?? '');
  window.__M0__ = '/api/queue/calls';
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, items: [] }) });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('calls_display.js render arms', () => {
  it('renders the no-calls notice for an empty list', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, items: [] }) });
    await loadModule('static/js/pages/reception/calls_display.js');
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('calls-grid').textContent).toContain('لا يوجد');
  });

  it('renders the no-calls notice for a missing items key', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
    await loadModule('static/js/pages/reception/calls_display.js');
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('calls-grid').textContent).toContain('لا يوجد');
  });

  it('renders item with missing queue number as dash and without room', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, items: [{ department_name: 'Lab', doctor_name: 'Dr X', status: 'called' }] }) });
    await loadModule('static/js/pages/reception/calls_display.js');
    await new Promise(r => setTimeout(r, 30));
    const grid = document.getElementById('calls-grid');
    expect(grid.innerHTML).toContain('>-<');
    expect(grid.innerHTML).toContain('Lab');
  });

  it('refresh leaves the grid untouched on success:false', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false }) });
    document.getElementById('calls-grid').textContent = 'keep';
    await loadModule('static/js/pages/reception/calls_display.js');
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('calls-grid').textContent).toBe('keep');
  });

  it('refresh leaves the grid untouched on null data', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(null) });
    document.getElementById('calls-grid').textContent = 'keep';
    await loadModule('static/js/pages/reception/calls_display.js');
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('calls-grid').textContent).toBe('keep');
  });

  it('non-ok response marks the grid as stale', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    await loadModule('static/js/pages/reception/calls_display.js');
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('calls-grid').hasAttribute('data-stale')).toBe(true);
  });

  it('network failure marks the grid as stale', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    await loadModule('static/js/pages/reception/calls_display.js');
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('calls-grid').hasAttribute('data-stale')).toBe(true);
  });

  it('successful refresh clears a previously stale marker', async () => {
    let calls = 0;
    global.fetch = vi.fn(() => {
      calls += 1;
      if (calls === 1) return Promise.resolve({ ok: false, status: 500 });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, items: [] }) });
    });
    vi.useFakeTimers();
    await loadModule('static/js/pages/reception/calls_display.js');
    await vi.advanceTimersByTimeAsync(30);
    expect(document.getElementById('calls-grid').hasAttribute('data-stale')).toBe(true);
    vi.advanceTimersByTime(6000);
    await vi.advanceTimersByTimeAsync(30);
    expect(document.getElementById('calls-grid').hasAttribute('data-stale')).toBe(false);
    vi.useRealTimers();
  });

  it('socket event with falsy data is ignored', async () => {
    await loadModule('static/js/pages/reception/calls_display.js');
    document.getElementById('calls-grid').textContent = 'keep';
    socket.trigger('queue_display_calls', null);
    expect(document.getElementById('calls-grid').textContent).toBe('keep');
  });

  it('socket event with an items payload re-renders the grid', async () => {
    await loadModule('static/js/pages/reception/calls_display.js');
    socket.trigger('queue_display_calls', { items: [{ queue_number: 'C-9', department_name: 'ENT', doctor_name: 'Dr Y', room_name: 'E1', status: 'called' }] });
    expect(document.getElementById('calls-grid').innerHTML).toContain('C-9');
    expect(document.getElementById('calls-grid').innerHTML).toContain('E1');
  });
});
