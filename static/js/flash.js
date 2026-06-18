// Toast Notification System (ES Module)
const toastContainer = (() => {
  let el = document.getElementById('toastContainer');
  if (!el) {
    el = document.createElement('div');
    el.id = 'toastContainer';
    el.className = 'toast-container';
    document.body.appendChild(el);
  }
  return el;
})();

export function showToast(message, type = 'info', duration = 5000) {
  const icons = { success: 'check-circle', error: 'exclamation-circle', warning: 'exclamation-triangle', info: 'info-circle' };
  const titles = { success: 'تم', error: 'خطأ', warning: 'تنبيه', info: 'ملاحظة' };
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `
    <div class="toast-header">
      <i class="fas fa-${icons[type] || icons.info}"></i>
      <span>${titles[type] || titles.info}</span>
      <button class="toast-close" aria-label="إغلاق">&times;</button>
    </div>
    <div class="toast-body">${message}</div>
    <div class="toast-progress" style="width: 100%"></div>
  `;
  toastContainer.appendChild(toast);
  const closeBtn = toast.querySelector('.toast-close');
  const progress = toast.querySelector('.toast-progress');
  closeBtn.addEventListener('click', () => removeToast(toast));
  let remaining = duration;
  let start = Date.now();
  let timer = setTimeout(() => removeToast(toast), duration);
  let progressTimer = setInterval(() => {
    const elapsed = Date.now() - start;
    const pct = Math.max(0, 100 - (elapsed / duration) * 100);
    if (progress) progress.style.width = pct + '%';
    if (pct <= 0) clearInterval(progressTimer);
  }, 50);
  toast.addEventListener('mouseenter', () => {
    clearTimeout(timer);
    clearInterval(progressTimer);
    remaining -= Date.now() - start;
  });
  toast.addEventListener('mouseleave', () => {
    start = Date.now();
    timer = setTimeout(() => removeToast(toast), remaining);
    progressTimer = setInterval(() => {
      const elapsed = Date.now() - start;
      const pct = Math.max(0, (remaining - elapsed) / remaining * 100);
      if (progress) progress.style.width = pct + '%';
      if (pct <= 0) clearInterval(progressTimer);
    }, 50);
  });
  return toast;
}

export function removeToast(toast) {
  if (!toast || toast.classList.contains('removing')) return;
  toast.classList.add('removing');
  setTimeout(() => { if (toast.parentNode) toast.parentNode.removeChild(toast); }, 300);
}

export function initFlashAutoHide() {
  const flashMessages = document.querySelectorAll('.flash-message');
  if (flashMessages.length > 0) {
    flashMessages.forEach(msg => {
      const text = msg.textContent.trim();
      const category = msg.classList.contains('success') ? 'success' :
                       msg.classList.contains('error') ? 'error' :
                       msg.classList.contains('warning') ? 'warning' : 'info';
      showToast(text, category);
      msg.style.display = 'none';
    });
  }
}

export function showError(message) { return showToast(message, 'error', 8000); }
export function showSuccess(message) { return showToast(message, 'success', 4000); }
export function showWarning(message) { return showToast(message, 'warning', 6000); }
export function showInfo(message) { return showToast(message, 'info', 4000); }
