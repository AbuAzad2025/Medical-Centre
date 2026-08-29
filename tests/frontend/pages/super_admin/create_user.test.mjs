import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <div id="app"></div>
    <input id="password" type="password" value="Test123!" />
    <button class="btn-outline-secondary"><i class="fas fa-eye"></i></button>
    <input id="confirm_password" type="password" value="Test123!" />
    <form id="createUserForm"></form>
    <select id="role"><option value="reception">Reception</option><option value="doctor">Doctor</option></select>
    <div id="doctorPricingSection" style="display:none"></div>
  `;
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
});

describe('super_admin/create_user.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/super_admin/create_user.js');
  });

  test('togglePassword is a function', async () => {
    await loadScript('static/js/pages/super_admin/create_user.js');
    expect(typeof togglePassword).toBe('function');
  });

  test('checkPasswordStrength is a function', async () => {
    await loadScript('static/js/pages/super_admin/create_user.js');
    expect(typeof checkPasswordStrength).toBe('function');
  });

  test('toggleDoctorPricing is a function', async () => {
    await loadScript('static/js/pages/super_admin/create_user.js');
    expect(typeof toggleDoctorPricing).toBe('function');
  });

  test('checkPasswordStrength rates strong password', async () => {
    await loadScript('static/js/pages/super_admin/create_user.js');
    const result = checkPasswordStrength('StrongP@ss1');
    expect(result.percentage).toBe(100);
    expect(result.color).toBe('success');
  });

  test('checkPasswordStrength rates weak password', async () => {
    await loadScript('static/js/pages/super_admin/create_user.js');
    const result = checkPasswordStrength('abc');
    expect(result.percentage).toBe(25);
    expect(result.color).toBe('danger');
  });

  test('toggleDoctorPricing shows section for doctor role', async () => {
    await loadScript('static/js/pages/super_admin/create_user.js');
    document.getElementById('role').value = 'doctor';
    toggleDoctorPricing();
    expect(document.getElementById('doctorPricingSection').style.display).toBe('');
  });

  test('toggleDoctorPricing hides section for non-doctor role', async () => {
    await loadScript('static/js/pages/super_admin/create_user.js');
    document.getElementById('role').value = 'reception';
    toggleDoctorPricing();
    expect(document.getElementById('doctorPricingSection').style.display).toBe('none');
  });
});
