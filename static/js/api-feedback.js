/**
 * Arabic API / UI feedback — global notify.* (G-126, §36.2)
 */
(function (global) {
  'use strict';

  function swal() {
    return global.Swal && typeof global.Swal.fire === 'function' ? global.Swal : null;
  }

  function toast(message, type, title) {
    const S = swal();
    const icons = { success: 'success', error: 'error', warning: 'warning', info: 'info' };
    const titles = {
      success: title || 'تم',
      error: title || 'تنبيه',
      warning: title || 'تنبيه',
      info: title || 'معلومة',
    };
    if (S) {
      S.fire({
        title: titles[type] || 'تنبيه',
        text: message,
        icon: icons[type] || 'info',
        timer: type === 'success' ? 2200 : undefined,
        showConfirmButton: type !== 'success',
        confirmButtonText: 'حسناً',
      });
      return;
    }
    global.alert(message);
  }

  function confirmDialog(message, onConfirm) {
    const S = swal();
    const msg = message || 'هل أنت متأكد؟';
    if (S) {
      S.fire({
        title: 'تأكيد',
        text: msg,
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: 'نعم',
        cancelButtonText: 'إلغاء',
      }).then(function (res) {
        if (res.isConfirmed && typeof onConfirm === 'function') onConfirm();
      });
      return;
    }
    if (global.confirm(msg) && typeof onConfirm === 'function') onConfirm();
  }

  const notify = {
    success: function (msg) { toast(msg, 'success'); },
    error: function (msg) { toast(msg, 'error'); },
    warning: function (msg) { toast(msg, 'warning'); },
    info: function (msg) { toast(msg, 'info'); },
    confirm: confirmDialog,
  };

  function showApiSuccess(title, text) {
    notify.success(text || title || 'تم');
  }

  function showApiError(title, text) {
    notify.error(text || title || 'حدث خطأ');
  }

  function showApiWarning(title, text) {
    notify.warning(text || title || 'تنبيه');
  }

  global.notify = notify;
  global.showApiSuccess = showApiSuccess;
  global.showApiError = showApiError;
  global.showApiWarning = showApiWarning;
})(window);
