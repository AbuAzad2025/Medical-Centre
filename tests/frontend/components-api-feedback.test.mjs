import { describe, it, expect, beforeEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(() => {
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.alert = vi.fn();
  window.confirm = vi.fn(() => true);
});

describe('components/api-feedback.js', () => {
  it('swal returns the Swal object when available', async () => {
    const mod = await loadModule('static/js/components/api-feedback.js');
    expect(mod.swal()).toBe(window.Swal);
  });

  it('swal returns null when Swal missing', async () => {
    delete window.Swal;
    const mod = await loadModule('static/js/components/api-feedback.js');
    expect(mod.swal()).toBeNull();
  });

  it('toast success uses Swal with timer', async () => {
    const mod = await loadModule('static/js/components/api-feedback.js');
    mod.toast('done', 'success');
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('success');
    expect(window.Swal.fire.mock.calls[0][0].timer).toBe(2200);
  });

  it('toast error uses error icon', async () => {
    const mod = await loadModule('static/js/components/api-feedback.js');
    mod.toast('fail', 'error');
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });

  it('toast unknown type falls back to info icon', async () => {
    const mod = await loadModule('static/js/components/api-feedback.js');
    mod.toast('msg', 'bogus');
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('info');
  });

  it('toast with missing Swal falls back to alert', async () => {
    delete window.Swal;
    const mod = await loadModule('static/js/components/api-feedback.js');
    mod.toast('plain', 'info');
    expect(window.alert).toHaveBeenCalledWith('plain');
  });

  it('toast uses provided title', async () => {
    const mod = await loadModule('static/js/components/api-feedback.js');
    mod.toast('msg', 'success', 'My title');
    expect(window.Swal.fire.mock.calls[0][0].title).toBe('My title');
  });

  it('confirmDialog with Swal confirmed calls onConfirm', async () => {
    const mod = await loadModule('static/js/components/api-feedback.js');
    const cb = vi.fn();
    mod.confirmDialog('sure?', cb);
    await new Promise(r => setTimeout(r, 20));
    expect(cb).toHaveBeenCalled();
  });

  it('confirmDialog with cancelled does not call onConfirm', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/components/api-feedback.js');
    const cb = vi.fn();
    mod.confirmDialog('sure?', cb);
    await new Promise(r => setTimeout(r, 20));
    expect(cb).not.toHaveBeenCalled();
  });

  it('confirmDialog falls back to window.confirm', async () => {
    delete window.Swal;
    const mod = await loadModule('static/js/components/api-feedback.js');
    const cb = vi.fn();
    mod.confirmDialog('sure?', cb);
    expect(window.confirm).toHaveBeenCalled();
    expect(cb).toHaveBeenCalled();
  });

  it('showApiSuccess/showApiError/showApiWarning call toast', async () => {
    const mod = await loadModule('static/js/components/api-feedback.js');
    mod.showApiSuccess('ok', 'body');
    mod.showApiError('bad', 'body');
    mod.showApiWarning('warn', 'body');
    expect(window.Swal.fire.mock.calls.length).toBe(3);
  });

  it('showApiSuccess with only title uses title text', async () => {
    const mod = await loadModule('static/js/components/api-feedback.js');
    mod.showApiSuccess('Only title');
    expect(window.Swal.fire.mock.calls[0][0].text).toBe('Only title');
  });

  it('exposes notify and helper set functions globally', async () => {
    await loadModule('static/js/components/api-feedback.js');
    expect(typeof window.notify).toBe('object');
    expect(typeof window.showApiSuccess).toBe('function');
    expect(typeof window.showApiError).toBe('function');
    expect(typeof window.showApiWarning).toBe('function');
  });
});