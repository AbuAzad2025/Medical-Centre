// CSRF Token Management (ES Module)
export function initCsrf() {
  if (window.__csrfInitialized) return;
  const meta = document.querySelector('meta[name="csrf-token"]');
  const token = meta ? meta.getAttribute('content') : '';
  window.csrfToken = token || window.csrfToken || '';

  const forms = document.querySelectorAll('form');
  forms.forEach(form => {
    if (!form.querySelector('input[name="csrf_token"]')) {
      const csrfInput = document.createElement('input');
      csrfInput.type = 'hidden';
      csrfInput.name = 'csrf_token';
      csrfInput.value = window.csrfToken;
      form.appendChild(csrfInput);
    }
  });

  window.__csrfInitialized = true;
}
export default { initCsrf }
