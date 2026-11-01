/* UX enhancements - TypeScript */
function enhanceForms(): void {
  const forms = document.querySelectorAll('form');
  forms.forEach((form) => {
    const inputs = form.querySelectorAll('input, select, textarea');
    inputs.forEach((input) => {
      const el = input as HTMLElement;
      el.addEventListener('focus', () => {
        el.parentElement?.classList.add('focused');
      });
      el.addEventListener('blur', () => {
        el.parentElement?.classList.remove('focused');
      });
    });
  });
}

function enhanceButtons(): void {
  const buttons = document.querySelectorAll('.btn');
  buttons.forEach((btn) => {
    const el = btn as HTMLElement;
    el.addEventListener('click', (e: Event) => {
      const me = e as MouseEvent;
      const target = me.currentTarget as HTMLElement;
      const ripple = document.createElement('span');
      ripple.className = 'ripple';
      const rect = target.getBoundingClientRect();
      ripple.style.left = `${me.clientX - rect.left}px`;
      ripple.style.top = `${me.clientY - rect.top}px`;
      target.appendChild(ripple);
      setTimeout(() => ripple.remove(), 600);
    });
  });
}

document.addEventListener('DOMContentLoaded', () => {
  enhanceForms();
  enhanceButtons();
});