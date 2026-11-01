/* Theme toggle (legacy) - TypeScript */
function toggleThemeLegacy(): void {
  const body = document.body;
  body.classList.toggle('dark-theme');
  const isDark = body.classList.contains('dark-theme');
  localStorage.setItem('theme', isDark ? 'dark' : 'light');
}

function initTheme(): void {
  const stored = localStorage.getItem('theme');
  if (stored === 'dark') {
    document.body.classList.add('dark-theme');
  }
}

document.addEventListener('DOMContentLoaded', initTheme);
(window as any).toggleThemeLegacy = toggleThemeLegacy;