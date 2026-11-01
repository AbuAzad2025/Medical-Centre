/* Login page - TypeScript */
document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('loginForm') as HTMLFormElement | null;
  if (!form) return;

  form.addEventListener('submit', (e: Event) => {
    const username = (document.getElementById('username') as HTMLInputElement)?.value?.trim();
    const password = (document.getElementById('password') as HTMLInputElement)?.value;

    if (!username || !password) {
      e.preventDefault();
      if (typeof (window as any).showFlash === 'function') {
        (window as any).showFlash({ type: 'error', message: 'يرجى إدخال اسم المستخدم وكلمة المرور' });
      }
    }
  });

  // Caps Lock warning
  const passwordField = document.getElementById('password') as HTMLInputElement | null;
  if (passwordField) {
    passwordField.addEventListener('keyup', (e: KeyboardEvent) => {
      const warning = document.getElementById('capsLockWarning');
      if (warning) {
        warning.style.display = e.getModifierState('CapsLock') ? 'block' : 'none';
      }
    });
  }
});