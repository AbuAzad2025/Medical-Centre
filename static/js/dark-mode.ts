/* Dark mode toggle - TypeScript */
const STORAGE_KEY = 'azad-theme';
const DARK = 'dark';
const LIGHT = 'light';

type Theme = 'dark' | 'light';

function getPreferredTheme(): Theme {
  const stored = localStorage.getItem(STORAGE_KEY) as Theme | null;
  if (stored) return stored;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? DARK : LIGHT;
}

function applyTheme(theme: Theme): void {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem(STORAGE_KEY, theme);
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) {
    meta.setAttribute('content', theme === DARK ? '#0f172a' : '#ffffff');
  }
}

function toggleTheme(): void {
  const current = (document.documentElement.getAttribute('data-theme') || LIGHT) as Theme;
  applyTheme(current === DARK ? LIGHT : DARK);
}

// Apply on load
applyTheme(getPreferredTheme());

// Listen for system preference changes
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e: MediaQueryListEvent) => {
  if (!localStorage.getItem(STORAGE_KEY)) {
    applyTheme(e.matches ? DARK : LIGHT);
  }
});

// Export for use in navbar
(window as any).toggleTheme = toggleTheme;
(window as any).getTheme = (): Theme => (document.documentElement.getAttribute('data-theme') || LIGHT) as Theme;