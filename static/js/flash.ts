/* Flash messages - TypeScript */
interface FlashMessage {
  type: 'success' | 'error' | 'warning' | 'info';
  message: string;
  duration?: number;
}

function showFlash(msg: FlashMessage): void {
  const container = document.getElementById('flash-container') || document.body;
  const alert = document.createElement('div');
  alert.className = `alert alert-${msg.type} alert-dismissible fade show`;
  alert.setAttribute('role', 'alert');
  alert.innerHTML = `
    <span class="flash-text">${msg.message}</span>
    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
  `;
  container.appendChild(alert);
  setTimeout(() => {
    alert.classList.remove('show');
    setTimeout(() => alert.remove(), 300);
  }, msg.duration || 5000);
}

(window as any).showFlash = showFlash;