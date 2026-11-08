import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <form id="loginForm">
      <button id="loginBtn" type="submit">
        <i class="fas fa-sign-in-alt btn-icon"></i>
        <span class="btn-text">دخول</span>
      </button>
      <span id="loginLoading" class="spinner"></span>
    </form>
    <div id="capsLock" style="display:none"></div>
    <div class="password-box">
      <input type="password" id="password">
      <button id="togglePassword" type="button" aria-label="إظهار كلمة المرور"><i class="fas fa-eye"></i></button>
    </div>
    <button data-action="forgot-password" id="forgotBtn">نسيت كلمة المرور؟</button>
  `;
}

beforeEach(() => {
  baseDom();
  window.alert = vi.fn();
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
});

afterEach(() => {
  vi.useRealTimers();
});

describe('login.js', () => {
  it('loginForm submit hides text+icon, shows loading, disables button', async () => {
    await loadModule('static/js/login.js');
    const form = document.getElementById('loginForm');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    expect(document.querySelector('.btn-text').style.display).toBe('none');
    expect(document.querySelector('.btn-icon').style.display).toBe('none');
    expect(document.getElementById('loginLoading').classList.contains('show')).toBe(true);
    expect(document.getElementById('loginBtn').disabled).toBe(true);
  });

  it('togglePassword swaps password type and icon', async () => {
    await loadModule('static/js/login.js');
    const pwd = document.getElementById('password');
    const toggle = document.getElementById('togglePassword');
    expect(pwd.getAttribute('type')).toBe('password');
    toggle.click();
    expect(pwd.getAttribute('type')).toBe('text');
    expect(toggle.getAttribute('aria-label')).toBe('إخفاء كلمة المرور');
    expect(toggle.innerHTML).toContain('fa-eye-slash');
    toggle.click();
    expect(pwd.getAttribute('type')).toBe('password');
    expect(toggle.innerHTML).toContain('fa-eye');
  });

  it('keyup with caps lock shows the indicator', async () => {
    await loadModule('static/js/login.js');
    const pwd = document.getElementById('password');
    const caps = document.getElementById('capsLock');
    const evt = new KeyboardEvent('keyup', { key: 'a' });
    Object.defineProperty(evt, 'getModifierState', { value: () => true });
    pwd.dispatchEvent(evt);
    expect(caps.style.display).toBe('block');
    const evtOff = new KeyboardEvent('keyup', { key: 'a' });
    Object.defineProperty(evtOff, 'getModifierState', { value: () => false });
    pwd.dispatchEvent(evtOff);
    expect(caps.style.display).toBe('none');
  });

  it('keyup without capsLock helper does not throw', async () => {
    document.getElementById('capsLock').remove();
    await loadModule('static/js/login.js');
    const pwd = document.getElementById('password');
    const evt = new KeyboardEvent('keyup', { key: 'a' });
    Object.defineProperty(evt, 'getModifierState', { value: () => true });
    expect(() => pwd.dispatchEvent(evt)).not.toThrow();
  });

  it('forgot-password click shows Swal info', async () => {
    await loadModule('static/js/login.js');
    document.getElementById('forgotBtn').click();
    expect(window.Swal.fire.mock.calls[0][0].icon).toBe('info');
  });

  it('forgot-password without Swal falls back to alert', async () => {
    delete window.Swal;
    await loadModule('static/js/login.js');
    document.getElementById('forgotBtn').click();
    expect(window.alert).toHaveBeenCalled();
  });

  it('no loginForm element does not throw', async () => {
    document.getElementById('loginForm').remove();
    await loadModule('static/js/login.js');
    expect(true).toBe(true);
  });

  it('no togglePassword element does not wire password toggle', async () => {
    document.getElementById('togglePassword').remove();
    await loadModule('static/js/login.js');
    expect(true).toBe(true);
  });
});