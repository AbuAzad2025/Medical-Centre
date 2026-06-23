/**
 * Arabic API / UI feedback — replaces raw alert() (G-116, phase 8)
 */
(function () {
  'use strict';

  function toast(message, type) {
    if (window.Swal && typeof window.Swal.fire === 'function') {
      const icons = { success: 'success', error: 'error', warning: 'warning', info: 'info' };
      window.Swal.fire({
        title: type === 'success' ? 'تم' : type === 'error' ? 'خطأ' : 'تنبيه',
        text: message,
        icon: icons[type] || 'info',
        timer: type === 'success' ? 2200 : undefined,
        showConfirmButton: type !== 'success',
        confirmButtonText: 'حسناً',
      });
      return;
    }
    window.alert(message);
  }

  window.notify = {
    success: (msg) => toast(msg, 'success'),
    error: (msg) => toast(msg, 'error'),
    warning: (msg) => toast(msg, 'warning'),
    info: (msg) => toast(msg, 'info'),
  };
})();
