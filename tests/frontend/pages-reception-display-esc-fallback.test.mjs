import { describe, test, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

// Standalone queue kiosk pages deliberately do NOT load base.js, so the
// browser-side escHtml helper may be absent. The scripts carry their own
// fallback. These tests prove:
//  - the fallback exists and HTML-escapes the dangerous characters, and
//  - when window.escHtml IS present, it is preferred over the fallback, and
//  - a fetch failure marks the lists stale instead of crashing the kiosk.

const ROOT = 'static/js/pages/reception';

const ESC_CHECK = `<b>&"'</b>`;
// The element text after an innerHTML roundtrip: quotes decode back, tags do not.
const ESC_TEXT = ESC_CHECK;

function jsonResponse(payload) {
  return Promise.resolve({
    ok: true,
    json: () => Promise.resolve(payload),
  });
}

describe('reception display pages escHtml fallback', () => {
  const ORIGINAL_ESC = window.escHtml;
  const ORIGINAL_FETCH = global.fetch;

  beforeEach(() => {
    document.body.innerHTML = `
      <div id="calls-grid"></div>
      <span id="live-clock"></span>
      <div id="current-list"></div>
      <div id="called-list"></div>
      <div id="waiting-list"></div>
    `;
    window.__M0__ = '/api/test/calls';
    delete window.escHtml;
    window.io = undefined;
    global.fetch = vi.fn(() =>
      jsonResponse({
        success: true,
        items: [{ queue_number: ESC_CHECK, department_name: ESC_CHECK, doctor_name: ESC_CHECK, status: ESC_CHECK }],
        current: [{ queue_number: ESC_CHECK, department_name: ESC_CHECK, doctor_name: ESC_CHECK, room_name: ESC_CHECK }],
        called: [{ queue_number: ESC_CHECK, department_name: ESC_CHECK, doctor_name: ESC_CHECK }],
        waiting: [{ queue_number: ESC_CHECK, department_name: ESC_CHECK, doctor_name: ESC_CHECK, room_name: ESC_CHECK }],
      }),
    );
  });

  afterEach(() => {
    if (ORIGINAL_ESC === undefined) {
      delete window.escHtml;
    } else {
      window.escHtml = ORIGINAL_ESC;
    }
    global.fetch = ORIGINAL_FETCH;
    document.body.innerHTML = '';
  });

  test('calls_display renders the queue escaped: text stays text, tags never become elements', async () => {
    await loadModule(`${ROOT}/calls_display.js`);
    await vi.waitFor(() => {
      expect(document.querySelectorAll('.call-card').length).toBe(1);
    });
    expect(document.querySelector('.queue-number').textContent).toBe(ESC_TEXT);
    // No injected <b> element may exist — the payload was escaped, not parsed.
    expect(document.querySelector('.queue-number b')).toBeNull();
    expect(document.getElementById('calls-grid').querySelectorAll('b').length).toBe(0);
  });

  test('waiting_display renders all three lists escaped', async () => {
    await loadModule(`${ROOT}/waiting_display.js`);
    await vi.waitFor(() => {
      expect(document.getElementById('current-list').querySelectorAll('.queue-number').length).toBe(1);
    });
    expect(document.querySelector('#current-list .queue-number').textContent).toBe(ESC_TEXT);
    expect(document.querySelector('#current-list b')).toBeNull();
    expect(document.querySelector('#called-list b')).toBeNull();
    expect(document.querySelector('#waiting-list b')).toBeNull();
    expect(document.querySelector('#waiting-list .queue-number').textContent).toBe(ESC_TEXT);
  });

  test('calls_display prefers window.escHtml when present', async () => {
    const esc = vi.fn((v) => `ESC[${v}]`);
    window.escHtml = esc;
    await loadModule(`${ROOT}/calls_display.js`);
    await vi.waitFor(() => {
      expect(esc).toHaveBeenCalled();
    });
  });

  test('calls_display fetch !ok sets stale marker instead of throwing', async () => {
    global.fetch = vi.fn(() => Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) }));
    await loadModule(`${ROOT}/calls_display.js`);
    await vi.waitFor(() => {
      expect(document.getElementById('calls-grid').hasAttribute('data-stale')).toBe(true);
    });
  });

  test('waiting_display fetch !ok sets data-stale on all three lists', async () => {
    global.fetch = vi.fn(() => Promise.resolve({ ok: false, status: 503, json: () => Promise.resolve({}) }));
    await loadModule(`${ROOT}/waiting_display.js`);
    await vi.waitFor(() => {
      expect(document.getElementById('current-list').hasAttribute('data-stale')).toBe(true);
      expect(document.getElementById('called-list').hasAttribute('data-stale')).toBe(true);
      expect(document.getElementById('waiting-list').hasAttribute('data-stale')).toBe(true);
    });
  });

  test('waiting_display success:false is a silent no-op, not a crash', async () => {
    global.fetch = vi.fn(() => jsonResponse({ success: false }));
    await loadModule(`${ROOT}/waiting_display.js`);
    await vi.waitFor(() => {
      expect(global.fetch).toHaveBeenCalled();
    });
    expect(document.getElementById('current-list').innerHTML).toBe('');
  });
});
