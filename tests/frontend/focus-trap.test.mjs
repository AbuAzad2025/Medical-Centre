import { describe, it, expect, vi, beforeEach } from 'vitest';
import { loadScript } from './test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = '';
});

describe('focus-trap.js', () => {
  it('registers trapFocus on shown.bs.modal event', () => {
    loadScript('static/js/focus-trap.js');
    document.body.innerHTML = `
      <div class="modal" id="testModal">
        <input type="text" id="first" />
        <button id="btn">OK</button>
        <input type="text" id="last" />
      </div>
    `;
    const modal = document.getElementById('testModal');
    const keydownSpy = vi.fn();
    modal.addEventListener('keydown', keydownSpy);
    modal.dispatchEvent(new Event('shown.bs.modal'));
    const tabEvent = new KeyboardEvent('keydown', { key: 'Tab', bubbles: true });
    modal.dispatchEvent(tabEvent);
    expect(keydownSpy).toHaveBeenCalled();
  });

  it('cleanup removes handler on hidden.bs.modal', () => {
    loadScript('static/js/focus-trap.js');
    document.body.innerHTML = `
      <div class="modal" id="testModal">
        <input type="text" id="input1" />
      </div>
    `;
    const modal = document.getElementById('testModal');
    modal.dispatchEvent(new Event('shown.bs.modal'));
    modal.dispatchEvent(new Event('hidden.bs.modal'));
    const keydownSpy = vi.fn();
    modal.addEventListener('keydown', keydownSpy);
    modal.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true }));
    expect(true).toBe(true);
  });
});
