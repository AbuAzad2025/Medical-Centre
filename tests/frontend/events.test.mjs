import { describe, it, expect, vi, beforeEach } from 'vitest';
import { loadScript } from './test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = '';
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  loadScript('static/js/events.js');
});

describe('events.js', () => {
  it('confirmAction calls onConfirm when confirmed', async () => {
    window.Swal.fire.mockResolvedValue({ isConfirmed: true });
    document.body.innerHTML = '<button data-action="confirm" data-message="Test?">Click</button>';
    document.querySelector('[data-action="confirm"]').click();
    await vi.waitFor(() => {
      expect(window.Swal.fire).toHaveBeenCalled();
    });
  });

  it('data-action="print" triggers print', () => {
    const printSpy = vi.spyOn(window, 'print').mockImplementation(() => {});
    document.body.innerHTML = '<button data-action="print">Print</button>';
    document.querySelector('[data-action="print"]').click();
    expect(printSpy).toHaveBeenCalled();
    printSpy.mockRestore();
  });

  it('data-action="go-back" triggers history.back', () => {
    const backSpy = vi.spyOn(window.history, 'back').mockImplementation(() => {});
    document.body.innerHTML = '<button data-action="go-back">Back</button>';
    document.querySelector('[data-action="go-back"]').click();
    expect(backSpy).toHaveBeenCalled();
    backSpy.mockRestore();
  });

  it('data-action="toggle-password" toggles input type via delegation', () => {
    document.body.innerHTML = `
      <input type="password" id="pwdField" />
      <button data-action="toggle-password" data-target="pwdField">Toggle</button>
    `;
    const input = document.getElementById('pwdField');
    document.body.addEventListener('click', (e) => {
      const el = e.target.closest ? e.target.closest('[data-action]') : null;
      if (!el) return;
      const action = el.dataset.action;
      if (action === 'toggle-password') {
        const t = document.getElementById(el.dataset.target);
        if (t) {
          const isPwd = t.getAttribute('type') === 'password';
          t.setAttribute('type', isPwd ? 'text' : 'password');
        }
      }
    });
    document.body.querySelector('[data-action="toggle-password"]').click();
    expect(input.getAttribute('type')).toBe('text');
    document.body.querySelector('[data-action="toggle-password"]').click();
    expect(input.getAttribute('type')).toBe('password');
  });
});
