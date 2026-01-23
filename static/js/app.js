document.addEventListener('DOMContentLoaded', async () => {
  try {
    const m = await import('./csrf.js');
    const fn = m.initCsrf || (m.default && m.default.initCsrf);
    if (typeof fn === 'function') fn();
  } catch (e) {
    try {
      const meta = document.querySelector('meta[name="csrf-token"]');
      const token = meta ? meta.getAttribute('content') : '';
      window.csrfToken = token || window.csrfToken || '';
      document.querySelectorAll('form').forEach(form => {
        if (!form.querySelector('input[name="csrf_token"]')) {
          const csrfInput = document.createElement('input');
          csrfInput.type = 'hidden';
          csrfInput.name = 'csrf_token';
          csrfInput.value = window.csrfToken;
          form.appendChild(csrfInput);
        }
      });
      window.__csrfInitialized = true;
    } catch (_) {}
  }
  try {
    const m = await import('./flash.js');
    const fn = m.initFlashAutoHide || (m.default && m.default.initFlashAutoHide);
    if (typeof fn === 'function') fn();
  } catch (_) {}
  try {
    const m = await import('./digits-ar.js');
    const fn = m.normalizeArabicDigits || (m.default && m.default.normalizeArabicDigits);
    if (typeof fn === 'function') fn(document.body);
  } catch (_) {}
  try {
    const m = await import('./datatables-init.js');
    const fn = m.initDataTables || (m.default && m.default.initDataTables);
    if (typeof fn === 'function') fn();
  } catch (_) {}
});
