/* Dark mode toggle */
(function() {
  'use strict';

  const STORAGE_KEY = 'azad-theme';
  const DARK = 'dark';
  const LIGHT = 'light';

  function getPreferredTheme() {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) return stored;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? DARK : LIGHT;
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(STORAGE_KEY, theme);
    // Update meta theme-color
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) {
      meta.setAttribute('content', theme === DARK ? '#0f172a' : '#ffffff');
    }
  }

  function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || LIGHT;
    applyTheme(current === DARK ? LIGHT : DARK);
  }

  // Apply on load
  applyTheme(getPreferredTheme());

  // Listen for system preference changes
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    if (!localStorage.getItem(STORAGE_KEY)) {
      applyTheme(e.matches ? DARK : LIGHT);
    }
  });

  // Export for use in navbar
  window.toggleTheme = toggleTheme;
  window.getTheme = () => document.documentElement.getAttribute('data-theme') || LIGHT;
})();

export {};
