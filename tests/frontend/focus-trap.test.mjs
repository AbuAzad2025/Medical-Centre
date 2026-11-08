import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `<div class="modal" id="modal" tabindex="-1"><input id="first"><button id="last">x</button></div>`;
});

afterEach(() => {
  vi.useRealTimers();
});

describe('focus-trap.js', () => {
  it('exposes trapFocus on window', async () => {
    await loadModule('static/js/focus-trap.js');
    expect(typeof window.trapFocus).toBe('function');
  });

  it('trapFocus with no focusables does nothing', async () => {
    document.body.innerHTML = '<div class="modal" id="m"><p>no focusables</p></div>';
    const mod = await loadModule('static/js/focus-trap.js');
    expect(() => mod.trapFocus(document.getElementById('m'))).not.toThrow();
  });

  it('Tab on last element wraps focus to first', async () => {
    const mod = await loadModule('static/js/focus-trap.js');
    const m = document.getElementById('modal');
    mod.trapFocus(m);
    document.getElementById('last').focus();
    m.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true }));
    expect(document.activeElement.id).toBe('first');
  });

  it('Shift+Tab on first element wraps focus to last', async () => {
    const mod = await loadModule('static/js/focus-trap.js');
    const m = document.getElementById('modal');
    mod.trapFocus(m);
    document.getElementById('first').focus();
    m.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true }));
    expect(document.activeElement.id).toBe('last');
  });

  it('Tab on non-last element does not wrap', async () => {
    const mod = await loadModule('static/js/focus-trap.js');
    const m = document.getElementById('modal');
    mod.trapFocus(m);
    document.getElementById('first').focus();
    m.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true }));
    expect(document.activeElement.id).toBe('first');
  });

  it('Tab with focus outside modal wraps to first on Tab key', async () => {
    const mod = await loadModule('static/js/focus-trap.js');
    const m = document.getElementById('modal');
    mod.trapFocus(m);
    document.body.focus();
    m.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true }));
    expect(document.activeElement.id).toBe('first');
  });

  it('Shift+Tab with focus outside modal wraps to last', async () => {
    const mod = await loadModule('static/js/focus-trap.js');
    const m = document.getElementById('modal');
    mod.trapFocus(m);
    document.body.focus();
    m.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true }));
    expect(document.activeElement.id).toBe('last');
  });

  it('non-Tab key is ignored', async () => {
    const mod = await loadModule('static/js/focus-trap.js');
    const m = document.getElementById('modal');
    mod.trapFocus(m);
    document.getElementById('last').focus();
    m.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    expect(document.activeElement.id).toBe('last');
  });

  it('hidden.bs.modal removes the keydown handler', async () => {
    const mod = await loadModule('static/js/focus-trap.js');
    const m = document.getElementById('modal');
    mod.trapFocus(m);
    m.dispatchEvent(new Event('hidden.bs.modal'));
    document.getElementById('last').focus();
    m.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true }));
    expect(document.activeElement.id).toBe('last');
  });

  it('DOMContentLoaded wires existing modals', async () => {
    await loadModule('static/js/focus-trap.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const m = document.getElementById('modal');
    m.dispatchEvent(new Event('shown.bs.modal'));
    document.getElementById('last').focus();
    m.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true }));
    expect(document.activeElement.id).toBe('first');
  });

  it('MutationObserver wires dynamically added modals', async () => {
    vi.useRealTimers();
    await loadModule('static/js/focus-trap.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const sheet = document.createElement('div');
    sheet.className = 'modal';
    sheet.innerHTML = '<button id="dynFirst">a</button><button id="dynLast">b</button>';
    document.body.appendChild(sheet);
    await new Promise(r => setTimeout(r, 50));
    sheet.dispatchEvent(new Event('shown.bs.modal'));
    const last = document.getElementById('dynLast');
    last.focus();
    sheet.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true }));
    expect(document.activeElement.id).toBe('dynFirst');
  });
});