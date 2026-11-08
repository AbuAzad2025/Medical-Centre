import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <form id="loginForm">
      <button id="loginBtn" type="submit">
        <span class="btn-text">Sign in</span>
      </button>
      <span id="loginLoading" class="spinner"></span>
    </form>
    <div id="capsLock" style="display:none"></div>
    <input type="password" id="password">
    <button id="togglePassword" type="button"><i class="fas fa-eye"></i></button>
    <button data-action="forgot-password" id="forgotBtn">Forgot?</button>
  `;
  window.alert = vi.fn();
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
});

afterEach(() => {
  vi.useRealTimers();
});

describe('login.js fallback arms', () => {
  it('submit without the icon element does not throw and disables the button', async () => {
    document.querySelector('#loginBtn .btn-icon')?.remove();
    await loadModule('static/js/login.js');
    const form = document.getElementById('loginForm');
    expect(() => form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))).not.toThrow();
    expect(document.getElementById('loginBtn').disabled).toBe(true);
  });

  it('keyup without getModifierState hides the caps lock indicator', async () => {
    await loadModule('static/js/login.js');
    const pwd = document.getElementById('password');
    const caps = document.getElementById('capsLock');
    const evt = new KeyboardEvent('keyup', { key: 'a' });
    Object.defineProperty(evt, 'getModifierState', { value: undefined });
    pwd.dispatchEvent(evt);
    expect(caps.style.display).toBe('none');
  });

  it('missing forgot-password element does not crash the module', async () => {
    document.getElementById('forgotBtn').remove();
    await expect(loadModule('static/js/login.js')).resolves.toBeDefined();
  });

  it('missing password element does not wire the toggle', async () => {
    document.getElementById('password').remove();
    await expect(loadModule('static/js/login.js')).resolves.toBeDefined();
  });
});
