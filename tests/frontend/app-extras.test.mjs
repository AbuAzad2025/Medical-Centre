import { describe, it, expect, beforeEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

const { csrfInit, csrfInitDefault, flashInit, flashInitDefault, digitsNormalize, digitsNormalizeDefault, datatablesInit, datatablesInitDefault } = vi.hoisted(() => ({
  csrfInit: vi.fn(),
  csrfInitDefault: vi.fn(),
  flashInit: vi.fn(),
  flashInitDefault: vi.fn(),
  digitsNormalize: vi.fn(),
  digitsNormalizeDefault: vi.fn(),
  datatablesInit: vi.fn(),
  datatablesInitDefault: vi.fn(),
}));

vi.mock('../../static/js/csrf.js', () => ({
  initCsrf: csrfInit,
  default: { initCsrf: csrfInitDefault },
}));
vi.mock('../../static/js/flash.js', () => ({
  initFlashAutoHide: flashInit,
  default: { initFlashAutoHide: flashInitDefault },
}));
vi.mock('../../static/js/digits-ar.js', () => ({
  normalizeArabicDigits: digitsNormalize,
  default: { normalizeArabicDigits: digitsNormalizeDefault },
}));
vi.mock('../../static/js/datatables-init.js', () => ({
  initDataTables: datatablesInit,
  default: { initDataTables: datatablesInitDefault },
}));

beforeEach(() => {
  document.body.innerHTML = '';
  document.head.innerHTML = '';
  delete window.csrfToken;
  delete window.__csrfInitialized;
  for (const fn of [csrfInit, csrfInitDefault, flashInit, flashInitDefault, digitsNormalize, digitsNormalizeDefault, datatablesInit, datatablesInitDefault]) {
    fn.mockClear();
  }
});

describe('app.js initCsrfManual', () => {
  it('uses window.csrfToken fallback when meta is missing and token preset', async () => {
    window.csrfToken = 'preset-token';
    const mod = await loadModule('static/js/app.js');
    mod.initCsrfManual();
    expect(window.csrfToken).toBe('preset-token');
  });

  it('falls back to empty string when no meta and no preset token', async () => {
    const mod = await loadModule('static/js/app.js');
    mod.initCsrfManual();
    expect(window.csrfToken).toBe('');
  });

  it('uses meta token when present', async () => {
    document.head.innerHTML = '<meta name="csrf-token" content="meta-tok">';
    const mod = await loadModule('static/js/app.js');
    mod.initCsrfManual();
    expect(window.csrfToken).toBe('meta-tok');
    expect(window.__csrfInitialized).toBe(true);
  });

  it('does not duplicate csrf_token input when form already has one', async () => {
    document.head.innerHTML = '<meta name="csrf-token" content="meta-tok">';
    document.body.innerHTML = '<form id="f1"><input type="hidden" name="csrf_token" value="existing"></form>';
    const mod = await loadModule('static/js/app.js');
    mod.initCsrfManual();
    expect(document.querySelectorAll('#f1 input[name="csrf_token"]').length).toBe(1);
  });

  it('adds csrf_token input to forms missing one', async () => {
    document.head.innerHTML = '<meta name="csrf-token" content="meta-tok">';
    document.body.innerHTML = '<form id="f2"></form>';
    const mod = await loadModule('static/js/app.js');
    mod.initCsrfManual();
    const input = document.querySelector('#f2 input[name="csrf_token"]');
    expect(input).not.toBeNull();
    expect(input.value).toBe('meta-tok');
  });
});

describe('app.js DOMContentLoaded named export path', () => {
  it('prefers named csrf export when present', async () => {
    await loadModule('static/js/app.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 30));
    expect(csrfInit).toHaveBeenCalled();
    expect(csrfInitDefault).not.toHaveBeenCalled();
  });

  it('flash and digits named exports are both called', async () => {
    await loadModule('static/js/app.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 30));
    expect(flashInit).toHaveBeenCalled();
    expect(digitsNormalize).toHaveBeenCalledWith(document.body);
    expect(datatablesInit).toHaveBeenCalled();
  });
});
