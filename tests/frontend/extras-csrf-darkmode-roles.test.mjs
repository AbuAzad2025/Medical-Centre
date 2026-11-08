import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function mockMatchMedia({ dark = false } = {}) {
  const listeners = [];
  window.matchMedia = vi.fn((query) => ({
    matches: query.includes('dark') ? dark : false,
    media: query,
    addEventListener: (_evt, cb) => listeners.push(cb),
    removeEventListener: vi.fn(),
  }));
  return {
    fireChange(matches) {
      for (const cb of listeners) cb({ matches });
    },
  };
}

beforeEach(() => {
  document.body.innerHTML = '';
  document.head.innerHTML = '';
  document.documentElement.removeAttribute('data-theme');
  window.localStorage.clear();
  delete window.csrfToken;
  delete window.__csrfInitialized;
  delete window.toggleTheme;
  delete window.getTheme;
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('csrf.js initCsrf branches', () => {
  it('no meta and no preset yields an empty token', async () => {
    const { initCsrf } = await loadModule('static/js/csrf.js');
    initCsrf();
    expect(window.csrfToken).toBe('');
    expect(window.__csrfInitialized).toBe(true);
  });

  it('no meta but preset token keeps the preset', async () => {
    window.csrfToken = 'preset';
    const { initCsrf } = await loadModule('static/js/csrf.js');
    initCsrf();
    expect(window.csrfToken).toBe('preset');
  });

  it('meta token wins over preset', async () => {
    window.csrfToken = 'preset';
    document.head.innerHTML = '<meta name="csrf-token" content="meta-tok">';
    const { initCsrf } = await loadModule('static/js/csrf.js');
    initCsrf();
    expect(window.csrfToken).toBe('meta-tok');
  });

  it('already initialized is a no-op', async () => {
    window.__csrfInitialized = true;
    window.csrfToken = 'keepme';
    const { initCsrf } = await loadModule('static/js/csrf.js');
    initCsrf();
    expect(window.csrfToken).toBe('keepme');
  });

  it('forms missing csrf input get one injected; existing inputs are kept', async () => {
    document.head.innerHTML = '<meta name="csrf-token" content="meta-tok">';
    document.body.innerHTML = `
      <form id="f1"></form>
      <form id="f2"><input type="hidden" name="csrf_token" value="existing"></form>
    `;
    const { initCsrf } = await loadModule('static/js/csrf.js');
    initCsrf();
    expect(document.querySelector('#f1 input[name="csrf_token"]').value).toBe('meta-tok');
    expect(document.querySelectorAll('#f2 input[name="csrf_token"]').length).toBe(1);
    expect(document.querySelector('#f2 input[name="csrf_token"]').value).toBe('existing');
  });
});

describe('dark-mode.js branches', () => {
  it('applies dark on load when stored theme is dark', async () => {
    window.localStorage.setItem('azad-theme', 'dark');
    mockMatchMedia({ dark: false });
    await loadModule('static/js/dark-mode.js');
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
  });

  it('falls back to prefers-color-scheme dark when nothing stored', async () => {
    mockMatchMedia({ dark: true });
    await loadModule('static/js/dark-mode.js');
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
  });

  it('falls back to light when nothing stored and scheme is light', async () => {
    mockMatchMedia({ dark: false });
    await loadModule('static/js/dark-mode.js');
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
  });

  it('stored light wins over dark scheme', async () => {
    window.localStorage.setItem('azad-theme', 'light');
    mockMatchMedia({ dark: true });
    await loadModule('static/js/dark-mode.js');
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
  });

  it('meta theme-color is updated when present', async () => {
    document.head.innerHTML = '<meta name="theme-color" content="#ffffff">';
    window.localStorage.setItem('azad-theme', 'dark');
    mockMatchMedia();
    await loadModule('static/js/dark-mode.js');
    expect(document.querySelector('meta[name="theme-color"]').getAttribute('content')).toBe('#0f172a');
  });

  it('meta theme-color light content for light theme', async () => {
    document.head.innerHTML = '<meta name="theme-color" content="#0f172a">';
    window.localStorage.setItem('azad-theme', 'light');
    mockMatchMedia();
    await loadModule('static/js/dark-mode.js');
    expect(document.querySelector('meta[name="theme-color"]').getAttribute('content')).toBe('#ffffff');
  });

  it('system preference change applies only without a stored theme', async () => {
    const media = mockMatchMedia({ dark: true });
    await loadModule('static/js/dark-mode.js');
    media.fireChange(false);
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
  });

  it('system preference change is ignored with a stored theme', async () => {
    window.localStorage.setItem('azad-theme', 'dark');
    const media = mockMatchMedia({ dark: true });
    await loadModule('static/js/dark-mode.js');
    media.fireChange(false);
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
  });

  it('toggleTheme flips and persists the theme', async () => {
    window.localStorage.setItem('azad-theme', 'light');
    mockMatchMedia();
    await loadModule('static/js/dark-mode.js');
    window.toggleTheme();
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    expect(window.localStorage.getItem('azad-theme')).toBe('dark');
    window.toggleTheme();
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
  });

  it('getTheme returns the current theme and the light fallback', async () => {
    mockMatchMedia();
    await loadModule('static/js/dark-mode.js');
    expect(window.getTheme()).toBe('light');
    window.localStorage.setItem('azad-theme', 'dark');
    await loadModule('static/js/dark-mode.js');
    expect(window.getTheme()).toBe('dark');
  });

  it('meta theme-color absent does not throw', async () => {
    window.localStorage.setItem('azad-theme', 'dark');
    mockMatchMedia();
    await expect(loadModule('static/js/dark-mode.js')).resolves.toBeDefined();
    expect(document.querySelector('meta[name="theme-color"]')).toBeNull();
  });
});

describe('roles.js URL branches', () => {
  it('editRole uses API_ROUTES when set', async () => {
    window.API_ROUTES = { edit_role: '/admin/edit/0' };
    window.location = { href: '' };
    const mod = await loadModule('static/js/pages/super_admin/roles.js');
    mod.editRole(5);
    expect(window.location.href).toBe('/admin/edit/5');
  });

  it('editRole falls back to the default route', async () => {
    window.API_ROUTES = {};
    window.location = { href: '' };
    const mod = await loadModule('static/js/pages/super_admin/roles.js');
    mod.editRole(5);
    expect(window.location.href).toBe('/super-admin/roles/5/edit');
  });

  it('managePermissions uses API_ROUTES when set', async () => {
    window.API_ROUTES = { manage_role_permissions: '/admin/perms/0' };
    window.location = { href: '' };
    const mod = await loadModule('static/js/pages/super_admin/roles.js');
    mod.managePermissions(7);
    expect(window.location.href).toBe('/admin/perms/7');
  });

  it('managePermissions falls back to the default route', async () => {
    window.API_ROUTES = {};
    window.location = { href: '' };
    const mod = await loadModule('static/js/pages/super_admin/roles.js');
    mod.managePermissions(7);
    expect(window.location.href).toBe('/super-admin/roles/7/permissions');
  });

  it('manageDepartmentPermissions uses API_ROUTES when set', async () => {
    window.API_ROUTES = { manage_role_department_permissions: '/admin/deptperms/0' };
    window.location = { href: '' };
    const mod = await loadModule('static/js/pages/super_admin/roles.js');
    mod.manageDepartmentPermissions(9);
    expect(window.location.href).toBe('/admin/deptperms/9');
  });

  it('manageDepartmentPermissions falls back to the default route', async () => {
    window.API_ROUTES = {};
    window.location = { href: '' };
    const mod = await loadModule('static/js/pages/super_admin/roles.js');
    mod.manageDepartmentPermissions(9);
    expect(window.location.href).toBe('/super-admin/roles/9/department-permissions');
  });

  it('window helpers are exposed for inline handlers', async () => {
    await loadModule('static/js/pages/super_admin/roles.js');
    expect(typeof window.editRole).toBe('function');
    expect(typeof window.managePermissions).toBe('function');
    expect(typeof window.manageDepartmentPermissions).toBe('function');
  });
});
