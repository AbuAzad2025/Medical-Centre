/* Focus trap for modals - TypeScript */
function trapFocus(element: HTMLElement): () => void {
  const focusableSelectors = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
  const focusable = Array.from(element.querySelectorAll(focusableSelectors)) as HTMLElement[];
  if (focusable.length === 0) return () => {};

  const first = focusable[0];
  const last = focusable[focusable.length - 1];

  function handleKeyDown(e: KeyboardEvent): void {
    if (e.key !== 'Tab') return;
    if (e.shiftKey) {
      if (document.activeElement === first) {
        e.preventDefault();
        last.focus();
      }
    } else {
      if (document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  }

  element.addEventListener('keydown', handleKeyDown);
  first.focus();

  return () => element.removeEventListener('keydown', handleKeyDown);
}

(window as any).trapFocus = trapFocus;