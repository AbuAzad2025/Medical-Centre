import { describe, it, expect, beforeEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(() => {
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.alert = vi.fn();
  window.confirm = vi.fn(() => true);
});

describe('api-feedback.js', () => {
  it('toast success uses Swal with success icon and timer', async () => {
    const mod = await loadModule('static/js/api-feedback.js');
    mod.toast('done', 'success');
    expect(window.Swal.fire).toHaveBeenCalled();
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('success');
    expect(window.Swal.fire.mock.calls[0][0].timer).toBe(2200);
  });

  it('toast error uses error icon and no timer', async () => {
    const mod = await loadModule('static/js/api-feedback.js');
    mod.toast('fail', 'error');
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
    expect(window.Swal.fire.mock.calls[0][0].timer).toBeUndefined();
  });

  it('toast warning and info set icons', async () => {
    const mod = await loadModule('static/js/api-feedback.js');
    mod.toast('warn', 'warning');
    mod.toast('info', 'info');
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('warning');
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('info');
  });

  it('toast with unknown type falls back to info', async () => {
    const mod = await loadModule('static/js/api-feedback.js');
    mod.toast('msg', 'weird');
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('info');
  });

  it('toast falls back to alert when Swal missing', async () => {
    delete window.Swal;
    const mod = await loadModule('static/js/api-feedback.js');
    mod.toast('plain', 'info');
    expect(window.alert).toHaveBeenCalledWith('plain');
  });

  it('toast uses provided title', async () => {
    const mod = await loadModule('static/js/api-feedback.js');
    mod.toast('msg', 'success', 'Custom');
    expect(window.Swal.fire.mock.calls[0][0].title).toBe('Custom');
  });

  it('confirmDialog fires onConfirm when resolved isConfirmed', async () => {
    const mod = await loadModule('static/js/api-feedback.js');
    const cb = vi.fn();
    mod.confirmDialog('sure?', cb);
    await new Promise(r => setTimeout(r, 20));
    expect(cb).toHaveBeenCalled();
  });

  it('confirmDialog not confirmed does not call onConfirm', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/api-feedback.js');
    const cb = vi.fn();
    mod.confirmDialog('sure?', cb);
    await new Promise(r => setTimeout(r, 20));
    expect(cb).not.toHaveBeenCalled();
  });

  it('confirmDialog falls back to window.confirm', async () => {
    delete window.Swal;
    const mod = await loadModule('static/js/api-feedback.js');
    const cb = vi.fn();
    mod.confirmDialog('sure?', cb);
    expect(cb).toHaveBeenCalled();
    expect(window.confirm).toHaveBeenCalled();
  });

  it('showApiSuccess with text uses text', async () => {
    const mod = await loadModule('static/js/api-feedback.js');
    mod.showApiSuccess('title', 'body');
    expect(window.Swal.fire.mock.calls[0][0].text).toBe('body');
  });

  it('showApiError with text uses text', async () => {
    const mod = await loadModule('static/js/api-feedback.js');
    mod.showApiError('title', 'body');
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('error');
  });

  it('showApiWarning shows warning', async () => {
    const mod = await loadModule('static/js/api-feedback.js');
    mod.showApiWarning('t', 'b');
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('warning');
  });

  it('showApiInfo shows info', async () => {
    const mod = await loadModule('static/js/api-feedback.js');
    mod.showApiInfo('t', 'b');
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('info');
  });

  it('showApiError with only title uses title', async () => {
    const mod = await loadModule('static/js/api-feedback.js');
    mod.showApiError('Only title');
    expect(window.Swal.fire.mock.calls[0][0].text).toBe('Only title');
  });

  it('notify helpers call toast', async () => {
    const mod = await loadModule('static/js/api-feedback.js');
    mod.notify.success('ok');
    mod.notify.error('bad');
    mod.notify.warning('warn');
    mod.notify.info('info');
    expect(window.Swal.fire.mock.calls.length).toBe(4);
  });

  it('default export exposes everything', async () => {
    const mod = await loadModule('static/js/api-feedback.js');
    expect(mod.default.toast).toBe(mod.toast);
    expect(mod.default.notify).toBeDefined();
  });
});