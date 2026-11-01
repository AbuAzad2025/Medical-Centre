/* CSRF token handling - TypeScript */
(function(): void {
  'use strict';

  function getCsrfToken(): string {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta) return meta.getAttribute('content') || '';
    const input = document.querySelector('input[name="csrf_token"]') as HTMLInputElement | null;
    if (input) return input.value;
    return '';
  }

  function addCsrfToForm(form: HTMLFormElement): void {
    const token = getCsrfToken();
    if (!token) return;
    let input = form.querySelector('input[name="csrf_token"]') as HTMLInputElement | null;
    if (!input) {
      input = document.createElement('input');
      input.type = 'hidden';
      input.name = 'csrf_token';
      form.appendChild(input);
    }
    input.value = token;
  }

  // Auto-add CSRF to all forms
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('form').forEach((form) => {
      addCsrfToForm(form as HTMLFormElement);
    });
  });

  (window as any).getCsrfToken = getCsrfToken;
})();