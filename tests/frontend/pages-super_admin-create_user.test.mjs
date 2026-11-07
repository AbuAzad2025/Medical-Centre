import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <form id="createUserForm">
      <input type="password" id="password" value="abc">
      <button type="button" id="togglePw"><i class="fa fa-eye"></i></button>
      <input type="password" id="confirm_password" value="abc">
      <select id="role"><option value="user">user</option><option value="doctor">doctor</option></select>
      <div id="doctorPricingSection" style="display:none"></div>
      <button type="submit">Create</button>
    </form>
  `;
}

beforeEach(() => {
  baseDom();
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.escHtml = (s) => String(s || '');
  window.bootstrap = { Collapse: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn() })) }, Modal: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn(), hide: vi.fn() })) } };
});

afterEach(() => {
  vi.useRealTimers();
});

describe('super_admin/create_user.js', () => {
  it('togglePassword toggles field type and icon', async () => {
    const mod = await loadModule('static/js/pages/super_admin/create_user.js');
    const field = document.getElementById('password');
    const icon = document.querySelector('#togglePw i');
    expect(field.getAttribute('type')).toBe('password');
    mod.togglePassword('password');
    expect(field.getAttribute('type')).toBe('text');
    expect(icon.classList.contains('fa-eye-slash')).toBe(true);
    mod.togglePassword('password');
    expect(field.getAttribute('type')).toBe('password');
    expect(icon.classList.contains('fa-eye')).toBe(true);
  });

  it('checkPasswordStrength strong password', async () => {
    const mod = await loadModule('static/js/pages/super_admin/create_user.js');
    const out = mod.checkPasswordStrength('Abcdef1!');
    expect(out.percentage).toBe(100);
    expect(out.color).toBe('success');
  });

  it('checkPasswordStrength moderate password', async () => {
    const mod = await loadModule('static/js/pages/super_admin/create_user.js');
    const out = mod.checkPasswordStrength('abc123');
    expect(out.percentage).toBe(50);
    expect(out.color).toBe('warning');
  });

  it('checkPasswordStrength good password', async () => {
    const mod = await loadModule('static/js/pages/super_admin/create_user.js');
    const out = mod.checkPasswordStrength('Abcdefg1');
    expect(out.percentage).toBe(100);
    expect(out.color).toBe('success');
  });

  it('checkPasswordStrength weak password', async () => {
    const mod = await loadModule('static/js/pages/super_admin/create_user.js');
    const out = mod.checkPasswordStrength('a');
    expect(out.percentage).toBe(25);
    expect(out.color).toBe('danger');
  });

  it('confirm_password mismatch sets custom validity', async () => {
    await loadModule('static/js/pages/super_admin/create_user.js');
    const confirm = document.getElementById('confirm_password');
    confirm.value = 'different';
    confirm.dispatchEvent(new Event('input'));
    expect(confirm.validationMessage).toBe('كلمات المرور غير متطابقة');
  });

  it('confirm_password match clears validity', async () => {
    await loadModule('static/js/pages/super_admin/create_user.js');
    const confirm = document.getElementById('confirm_password');
    document.getElementById('password').value = 'abc';
    confirm.value = 'abc';
    confirm.dispatchEvent(new Event('input'));
    expect(confirm.validationMessage).toBe('');
  });

  it('password input creates strength indicator', async () => {
    await loadModule('static/js/pages/super_admin/create_user.js');
    const password = document.getElementById('password');
    password.value = 'abc';
    password.dispatchEvent(new Event('input'));
    expect(document.querySelector('#password-strength')).toBeTruthy();
    expect(password.parentNode.innerHTML).toContain('progress');
  });

  it('createUserForm submits valid match without preventing', async () => {
    await loadModule('static/js/pages/super_admin/create_user.js');
    const form = document.getElementById('createUserForm');
    document.getElementById('password').value = 'abc';
    document.getElementById('confirm_password').value = 'abc';
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    expect(window.Swal.fire).not.toHaveBeenCalled();
  });

  it('createUserForm with mismatch prevents and shows warning', async () => {
    await loadModule('static/js/pages/super_admin/create_user.js');
    const form = document.getElementById('createUserForm');
    document.getElementById('password').value = 'abc';
    document.getElementById('confirm_password').value = 'different';
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    expect(window.Swal.fire.mock.calls[0][0].title).toBe('تحذير');
  });

  it('toggleDoctorPricing shows section for doctor role', async () => {
    await loadModule('static/js/pages/super_admin/create_user.js');
    document.getElementById('role').value = 'doctor';
    document.getElementById('role').dispatchEvent(new Event('change'));
    expect(document.getElementById('doctorPricingSection').style.display).toBe('');
  });

  it('toggleDoctorPricing hides section for user role', async () => {
    await loadModule('static/js/pages/super_admin/create_user.js');
    document.getElementById('role').value = 'user';
    document.getElementById('role').dispatchEvent(new Event('change'));
    expect(document.getElementById('doctorPricingSection').style.display).toBe('none');
  });
});