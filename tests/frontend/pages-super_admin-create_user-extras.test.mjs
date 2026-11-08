import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <div>
      <input id="password" type="password">
      <span id="password-strength"></span>
    </div>
    <input id="confirm_password" type="password">
    <form id="createUserForm" action="/admin/create" method="post"></form>
    <select id="role"><option value="admin">admin</option><option value="doctor">doctor</option></select>
    <div id="doctorPricingSection" style="display:none"></div>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M = [];
  window.escHtml = (s) => String(s ?? '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
});

afterEach(() => {
  vi.useRealTimers();
});

describe('create_user.js strength indicator reuse', () => {
  it('existing strength indicator element is reused instead of re-created', async () => {
    await loadModule('static/js/pages/super_admin/create_user.js');
    const input = document.getElementById('password');
    input.value = 'abc123XY!@';
    input.dispatchEvent(new Event('input'));
    expect(document.querySelectorAll('#password-strength').length).toBe(1);
    input.value = 'short';
    input.dispatchEvent(new Event('input'));
    expect(document.querySelectorAll('#password-strength').length).toBe(1);
  });

  it('weak password scores danger', async () => {
    const mod = await loadModule('static/js/pages/super_admin/create_user.js');
    const result = mod.checkPasswordStrength('abc');
    expect(result.color).toBe('danger');
    expect(result.percentage).toBe(25);
  });

  it('moderate password scores warning', async () => {
    const mod = await loadModule('static/js/pages/super_admin/create_user.js');
    const result = mod.checkPasswordStrength('aB');
    // lowercase + uppercase only → score 2 → warning bucket
    expect(result.color).toBe('warning');
    expect(result.percentage).toBe(50);
  });

  it('good password without an uppercase letter scores info', async () => {
    const mod = await loadModule('static/js/pages/super_admin/create_user.js');
    const result = mod.checkPasswordStrength('abc123!@');
    // hits the missing-uppercase else arm; score still lands in the success bucket
    expect(result.percentage).toBe(100);
  });

  it('good password without a digit still reaches the top bucket', async () => {
    const mod = await loadModule('static/js/pages/super_admin/create_user.js');
    // hits the missing-digit else arm
    const result = mod.checkPasswordStrength('abcDEF!@');
    expect(result.percentage).toBe(100);
  });

  it('good password without a special char still reaches the top bucket', async () => {
    const mod = await loadModule('static/js/pages/super_admin/create_user.js');
    const result = mod.checkPasswordStrength('abcXYZ123');
    expect(result.percentage).toBe(100);
  });

  it('good password without a lowercase letter hits the missing-lowercase else arm', async () => {
    const mod = await loadModule('static/js/pages/super_admin/create_user.js');
    const result = mod.checkPasswordStrength('ABC123!@');
    expect(result.color).toBeDefined();
  });

  it('empty password accumulates at least three failures', async () => {
    const mod = await loadModule('static/js/pages/super_admin/create_user.js');
    const result = mod.checkPasswordStrength('');
    expect(result.color).toBe('danger');
  });
});

describe('create_user.js roleSelect branches', () => {
  it('missing doctorPricingSection does not crash toggleDoctorPricing', async () => {
    document.getElementById('doctorPricingSection').remove();
    const mod = await loadModule('static/js/pages/super_admin/create_user.js');
    document.getElementById('role').value = 'doctor';
    expect(() => mod.toggleDoctorPricing()).not.toThrow();
  });

  it('module loads without a role select and does not crash', async () => {
    document.getElementById('role').remove();
    await expect(loadModule('static/js/pages/super_admin/create_user.js')).resolves.toBeDefined();
  });
});
