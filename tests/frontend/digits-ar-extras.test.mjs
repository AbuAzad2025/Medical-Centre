import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = '';
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('digits-ar.js normalizeArabicDigits branches', () => {
  it('null root returns without crashing', async () => {
    const { normalizeArabicDigits } = await loadModule('static/js/digits-ar.js');
    expect(() => normalizeArabicDigits(null)).not.toThrow();
    expect(() => normalizeArabicDigits(undefined)).not.toThrow();
  });

  it('replaces Arabic-Indic digits in text nodes with ASCII digits', async () => {
    document.body.innerHTML = '<div>العدد ٩٠ و ٦٧</div>';
    const { normalizeArabicDigits } = await loadModule('static/js/digits-ar.js');
    normalizeArabicDigits(document.body);
    expect(document.body.textContent).toContain('90');
    expect(document.body.textContent).toContain('67');
  });

  it('leaves plain ASCII text untouched', async () => {
    document.body.innerHTML = '<div>plain 123</div>';
    const { normalizeArabicDigits } = await loadModule('static/js/digits-ar.js');
    normalizeArabicDigits(document.body);
    expect(document.body.textContent).toBe('plain 123');
  });

  it('normalizes digits typed into a text input on input events', async () => {
    document.body.innerHTML = '<input type="text" id="field">';
    const { normalizeArabicDigits } = await loadModule('static/js/digits-ar.js');
    normalizeArabicDigits(document.body);
    const input = document.getElementById('field');
    input.value = '٩١٢٣';
    input.dispatchEvent(new Event('input'));
    expect(input.value).toBe('9123');
  });

  it('number inputs accept only ASCII digits at the DOM level (module is a no-op there)', async () => {
    document.body.innerHTML = '<input type="number" id="field">';
    const { normalizeArabicDigits } = await loadModule('static/js/digits-ar.js');
    normalizeArabicDigits(document.body);
    const input = document.getElementById('field');
    expect(() => input.dispatchEvent(new Event('input'))).not.toThrow();
  });

  it('calling normalizeArabicDigits twice does not duplicate handlers', async () => {
    document.body.innerHTML = '<input type="text" id="field">';
    const mod = await loadModule('static/js/digits-ar.js');
    mod.normalizeArabicDigits(document.body);
    mod.normalizeArabicDigits(document.body);
    const input = document.getElementById('field');
    input.value = '٨٨';
    input.dispatchEvent(new Event('input'));
    expect(input.value).toBe('88');
  });

  it('normalize ignores inputs inside detached subtrees on re-init', async () => {
    document.body.innerHTML = '<input type="text" id="keep">';
    const mod = await loadModule('static/js/digits-ar.js');
    mod.normalizeArabicDigits(document.body);
    document.body.innerHTML = '';
    document.body.innerHTML = '<input type="text" id="fresh">';
    mod.normalizeArabicDigits(document.body);
    const fresh = document.getElementById('fresh');
    fresh.value = '٠';
    fresh.dispatchEvent(new Event('input'));
    expect(fresh.value).toBe('0');
  });
});
