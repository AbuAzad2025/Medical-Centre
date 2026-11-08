import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(() => {
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.alert = vi.fn();
  window.confirm = vi.fn(() => true);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('api-feedback.js fallback arms', () => {
  it('Swal with non-function fire falls back to alert', async () => {
    window.Swal = { fire: 'not-a-function' };
    const mod = await loadModule('static/js/api-feedback.js');
    mod.toast('plain', 'info');
    expect(window.alert).toHaveBeenCalledWith('plain');
  });

  it('Swal with non-function fire falls back to window.confirm', async () => {
    window.Swal = { fire: 42 };
    const mod = await loadModule('static/js/api-feedback.js');
    const cb = vi.fn();
    mod.confirmDialog('sure?', cb);
    expect(cb).toHaveBeenCalled();
    expect(window.confirm).toHaveBeenCalledWith('sure?');
  });

  it('confirmDialog with empty message uses the default question', async () => {
    const mod = await loadModule('static/js/api-feedback.js');
    const cb = vi.fn();
    mod.confirmDialog('', cb);
    await new Promise(r => setTimeout(r, 10));
    expect(window.Swal.fire.mock.calls[0][0].text).toContain('متأكد');
  });

  it('confirmDialog with non-function onConfirm does not crash', async () => {
    const mod = await loadModule('static/js/api-feedback.js');
    expect(() => mod.confirmDialog('sure?', null)).not.toThrow();
    await new Promise(r => setTimeout(r, 10));
  });

  it('window.confirm returning false does not call onConfirm', async () => {
    window.Swal = { fire: null };
    window.confirm = vi.fn(() => false);
    const mod = await loadModule('static/js/api-feedback.js');
    const cb = vi.fn();
    mod.confirmDialog('sure?', cb);
    expect(cb).not.toHaveBeenCalled();
  });

  it('showApiSuccess with no arguments falls back to the default text', async () => {
    const mod = await loadModule('static/js/api-feedback.js');
    mod.showApiSuccess();
    expect(window.Swal.fire.mock.calls[0][0].text).toBeDefined();
  });

  it('showApiWarning with only a title uses the title as text', async () => {
    const mod = await loadModule('static/js/api-feedback.js');
    mod.showApiWarning('Just title');
    expect(window.Swal.fire.mock.calls[0][0].text).toBe('Just title');
  });

  it('showApiInfo with no arguments falls back to the default text', async () => {
    const mod = await loadModule('static/js/api-feedback.js');
    mod.showApiInfo();
    expect(window.Swal.fire.mock.calls[0][0].text).toBeDefined();
  });

  it('showApiSuccess with only a title uses the title as text', async () => {
    const mod = await loadModule('static/js/api-feedback.js');
    mod.showApiSuccess('Only title');
    expect(window.Swal.fire.mock.calls[0][0].text).toBe('Only title');
  });
});
