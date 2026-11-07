import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = '<span id="systemStatusIndicator"></span>';
  window.location = { reload: vi.fn() };
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.API_ROUTES = { health: '/health' };
  window.console.warn = vi.fn();
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ status: 'healthy', database: 'connected', redis: 'connected', version: '3.5.0' }),
  });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('system_maintenance.js', () => {
  it('optimizeDatabase confirms then shows info', async () => {
    const mod = await loadModule('static/js/pages/super_admin/system_maintenance.js');
    mod.optimizeDatabase();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire).toHaveBeenCalledTimes(2);
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('info');
  });

  it('optimizeDatabase cancel shows no second Swal', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/super_admin/system_maintenance.js');
    mod.optimizeDatabase();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire).toHaveBeenCalledTimes(1);
  });

  it('forceLogoutAll confirms then shows success', async () => {
    const mod = await loadModule('static/js/pages/super_admin/system_maintenance.js');
    mod.forceLogoutAll();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire).toHaveBeenCalledTimes(2);
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('success');
  });

  it('forceLogoutAll cancel shows no second Swal', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/super_admin/system_maintenance.js');
    mod.forceLogoutAll();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire).toHaveBeenCalledTimes(1);
  });

  it('refreshLogs calls location.reload', async () => {
    const mod = await loadModule('static/js/pages/super_admin/system_maintenance.js');
    mod.refreshLogs();
    expect(window.location.reload).toHaveBeenCalled();
  });

  it('clearLogs confirms then shows success', async () => {
    const mod = await loadModule('static/js/pages/super_admin/system_maintenance.js');
    mod.clearLogs();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire).toHaveBeenCalledTimes(2);
    expect(window.Swal.fire.mock.calls[1][0].icon).toBe('success');
  });

  it('clearLogs cancel shows no second Swal', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/super_admin/system_maintenance.js');
    mod.clearLogs();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire).toHaveBeenCalledTimes(1);
  });

  it('loadSystemStatus marks healthy system as bg-success', async () => {
    const mod = await loadModule('static/js/pages/super_admin/system_maintenance.js');
    mod.loadSystemStatus();
    await new Promise(r => setTimeout(r, 30));
    const el = document.getElementById('systemStatusIndicator');
    expect(el.className).toContain('bg-success');
    expect(el.title).toContain('v3.5.0');
  });

  it('loadSystemStatus marks unhealthy as bg-danger', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ status: 'degraded', database: 'down', redis: 'connected', version: '3.5.0' }) });
    const mod = await loadModule('static/js/pages/super_admin/system_maintenance.js');
    mod.loadSystemStatus();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('systemStatusIndicator').className).toContain('bg-danger');
  });

  it('loadSystemStatus with redis unavailable is still healthy', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ status: 'healthy', database: 'connected', redis: 'unavailable' }) });
    const mod = await loadModule('static/js/pages/super_admin/system_maintenance.js');
    mod.loadSystemStatus();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('systemStatusIndicator').className).toContain('bg-success');
  });

  it('loadSystemStatus does not throw when indicator missing', async () => {
    document.body.innerHTML = '';
    const mod = await loadModule('static/js/pages/super_admin/system_maintenance.js');
    expect(() => mod.loadSystemStatus()).not.toThrow();
    await new Promise(r => setTimeout(r, 30));
  });

  it('fetch failure logs a warning', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/super_admin/system_maintenance.js');
    mod.loadSystemStatus();
    await new Promise(r => setTimeout(r, 30));
    expect(window.console.warn).toHaveBeenCalled();
  });

  it('DOMContentLoaded triggers loadSystemStatus', async () => {
    await loadModule('static/js/pages/super_admin/system_maintenance.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
  });
});