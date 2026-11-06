// api-feedback.js - API feedback utilities
// Converted to ES module

function swal() {
  return window.Swal && typeof window.Swal.fire === 'function' ? window.Swal : null;
}

export function toast(message, type, title) {
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
  window.alert(message);
}

export function confirmDialog(message, onConfirm) {
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
  if (window.confirm(msg) && typeof onConfirm === 'function') onConfirm();
}

export const notify = {
  success: function (msg) { toast(msg, 'success'); },
  error: function (msg) { toast(msg, 'error'); },
  warning: function (msg) { toast(msg, 'warning'); },
  info: function (msg) { toast(msg, 'info'); },
  confirm: confirmDialog,
};

export function showApiSuccess(title, text) {
  notify.success(text || title || 'تم');
}

export function showApiError(title, text) {
  notify.error(text || title || 'حدث خطأ');
}

export function showApiWarning(title, text) {
  notify.warning(text || title || 'تنبيه');
}

export function showApiInfo(title, text) {
  notify.info(text || title || 'معلومة');
}

// Expose globally for backward compatibility
if (typeof window !== 'undefined') {
  window.notify = notify;
  window.showApiSuccess = showApiSuccess;
  window.showApiError = showApiError;
  window.showApiWarning = showApiWarning;
  window.showApiInfo = showApiInfo;
}

export default {
  toast,
  confirmDialog,
  notify,
  showApiSuccess,
  showApiError,
  showApiWarning,
  showApiInfo,
};