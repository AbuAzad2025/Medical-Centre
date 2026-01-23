// Flash Messages Management (ES Module)
export function initFlashAutoHide() {
  const flashMessages = document.querySelectorAll('.flash-message');
  flashMessages.forEach(message => {
    setTimeout(() => {
      message.style.opacity = '0';
      message.style.transform = 'translateX(100%)';
      setTimeout(() => { message.remove(); }, 300);
    }, 5000);
  });

  flashMessages.forEach(message => {
    const closeBtn = document.createElement('button');
    closeBtn.innerHTML = '×';
    closeBtn.style.cssText = `
      background: none;
      border: none;
      font-size: 1.5rem;
      cursor: pointer;
      margin-left: auto;
      color: #666;
    `;
    closeBtn.onclick = () => {
      message.style.opacity = '0';
      message.style.transform = 'translateX(100%)';
      setTimeout(() => { message.remove(); }, 300);
    };
    message.appendChild(closeBtn);
  });
}
