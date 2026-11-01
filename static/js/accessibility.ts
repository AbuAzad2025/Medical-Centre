/* Accessibility enhancements - TypeScript */
(function(): void {
  'use strict';

  // Skip to main content link
  function addSkipLink(): void {
    const skipLink = document.createElement('a');
    skipLink.href = '#main-content';
    skipLink.className = 'skip-link';
    skipLink.textContent = 'Skip to main content';
    skipLink.style.cssText = 'position:absolute;top:-40px;left:0;background:#000;color:#fff;padding:8px;z-index:9999;transition:top 0.3s;';
    skipLink.addEventListener('focus', () => { skipLink.style.top = '0'; });
    skipLink.addEventListener('blur', () => { skipLink.style.top = '-40px'; });
    document.body.insertBefore(skipLink, document.body.firstChild);
  }

  // Keyboard navigation for dropdowns
  function initKeyboardNav(): void {
    document.querySelectorAll('[data-bs-toggle="dropdown"]').forEach((btn) => {
      btn.addEventListener('keydown', (e: Event) => {
        const ke = e as KeyboardEvent;
        if (ke.key === 'Enter' || ke.key === ' ') {
          ke.preventDefault();
          (btn as HTMLElement).click();
        }
        if (ke.key === 'Escape') {
          const dropdown = (btn as HTMLElement).closest('.dropdown');
          if (dropdown) {
            const menu = dropdown.querySelector('.dropdown-menu');
            if (menu) (menu as HTMLElement).classList.remove('show');
          }
        }
      });
    });
  }

  // Focus management for modals
  function initModalFocus(): void {
    document.querySelectorAll('.modal').forEach((modal) => {
      modal.addEventListener('shown.bs.modal', () => {
        const firstInput = modal.querySelector('input, select, textarea, button') as HTMLElement | null;
        if (firstInput) firstInput.focus();
      });
    });
  }

  // ARIA live regions for dynamic content
  function announceToScreenReader(message: string): void {
    const announcer = document.getElementById('sr-announcer') || (() => {
      const el = document.createElement('div');
      el.id = 'sr-announcer';
      el.setAttribute('aria-live', 'polite');
      el.setAttribute('aria-atomic', 'true');
      el.className = 'visually-hidden';
      document.body.appendChild(el);
      return el;
    })();
    announcer.textContent = message;
  }

  // Color contrast check (warning only)
  function checkContrast(): void {
    // Basic check - warn if text color too light
    const elements = document.querySelectorAll('p, span, a, li, td, th, label');
    elements.forEach((el) => {
      const style = window.getComputedStyle(el);
      const color = style.color;
      // Simple luminance check
      const rgb = color.match(/\d+/g);
      if (rgb) {
        const luminance = (0.299 * parseInt(rgb[0]) + 0.587 * parseInt(rgb[1]) + 0.114 * parseInt(rgb[2])) / 255;
        if (luminance > 0.85) {
          // Too light - might be accessibility issue
          // console.warn('Low contrast detected:', el);
        }
      }
    });
  }

  // Initialize
  document.addEventListener('DOMContentLoaded', () => {
    addSkipLink();
    initKeyboardNav();
    initModalFocus();
    // Create announcer
    if (!document.getElementById('sr-announcer')) {
      const announcer = document.createElement('div');
      announcer.id = 'sr-announcer';
      announcer.setAttribute('aria-live', 'polite');
      announcer.setAttribute('aria-atomic', 'true');
      announcer.className = 'visually-hidden';
      document.body.appendChild(announcer);
    }
  });

  (window as any).announceToScreenReader = announceToScreenReader;
})();