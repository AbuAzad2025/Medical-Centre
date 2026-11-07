import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <aside id="appSidebar"><a href="/x">Link A</a></aside>
    <div id="sidebarOverlay"></div>
    <button id="closeSidebarBtn">Close</button>
    <button id="mobileSidebarToggle">Toggle</button>
    <button id="sidebarPositionToggle" aria-label="x"><svg></svg></button>
    <button id="sidebarCollapseToggle" aria-label="x"><svg></svg></button>
  `;
}

beforeEach(() => {
  baseDom();
  localStorage.clear();
  document.documentElement.className = '';
});

afterEach(() => {
  vi.useRealTimers();
});

describe('sidebar-toggle.js', () => {
  it('auto-initializes and exposes window.SidebarToggle', async () => {
    await loadModule('static/js/sidebar-toggle.js');
    expect(window.SidebarToggle).toBeDefined();
    expect(window.SidebarToggle.getConfig).toBeInstanceOf(Function);
  });

  it('uses saved config from localStorage', async () => {
    localStorage.setItem('sidebar-config', JSON.stringify({ position: 'left', collapsed: true }));
    await loadModule('static/js/sidebar-toggle.js');
    const cfg = window.SidebarToggle.getConfig();
    expect(cfg.position).toBe('left');
    expect(cfg.collapsed).toBe(true);
    expect(document.documentElement.classList.contains('sidebar-left')).toBe(true);
    expect(document.documentElement.classList.contains('sidebar-collapsed')).toBe(true);
  });

  it('falls back to default config when localStorage is corrupted', async () => {
    localStorage.setItem('sidebar-config', 'not-json');
    await loadModule('static/js/sidebar-toggle.js');
    expect(window.SidebarToggle.getConfig()).toEqual({ position: 'right', collapsed: false });
  });

  it('togglePosition flips right to left and persists', async () => {
    await loadModule('static/js/sidebar-toggle.js');
    window.SidebarToggle.togglePosition();
    const cfg = window.SidebarToggle.getConfig();
    expect(cfg.position).toBe('left');
    expect(document.documentElement.classList.contains('sidebar-left')).toBe(true);
    window.SidebarToggle.togglePosition();
    expect(window.SidebarToggle.getConfig().position).toBe('right');
  });

  it('toggleCollapse toggles collapsed class', async () => {
    await loadModule('static/js/sidebar-toggle.js');
    window.SidebarToggle.toggleCollapse();
    expect(document.documentElement.classList.contains('sidebar-collapsed')).toBe(true);
    window.SidebarToggle.toggleCollapse();
    expect(document.documentElement.classList.contains('sidebar-collapsed')).toBe(false);
  });

  it('position toggle button click changes position', async () => {
    await loadModule('static/js/sidebar-toggle.js');
    document.getElementById('sidebarPositionToggle').click();
    expect(window.SidebarToggle.getConfig().position).toBe('left');
  });

  it('collapse toggle button click toggles collapsed', async () => {
    await loadModule('static/js/sidebar-toggle.js');
    document.getElementById('sidebarCollapseToggle').click();
    expect(window.SidebarToggle.getConfig().collapsed).toBe(true);
  });

  it('mobile toggle opens sidebar and overlay', async () => {
    await loadModule('static/js/sidebar-toggle.js');
    document.getElementById('mobileSidebarToggle').click();
    expect(document.getElementById('appSidebar').classList.contains('open')).toBe(true);
    expect(document.getElementById('sidebarOverlay').classList.contains('active')).toBe(true);
    expect(document.getElementById('appSidebar').getAttribute('aria-hidden')).toBe('false');
  });

  it('mobile toggle again closes sidebar and overlay', async () => {
    await loadModule('static/js/sidebar-toggle.js');
    document.getElementById('mobileSidebarToggle').click();
    document.getElementById('mobileSidebarToggle').click();
    expect(document.getElementById('appSidebar').classList.contains('open')).toBe(false);
    expect(document.getElementById('sidebarOverlay').classList.contains('active')).toBe(false);
  });

  it('close button closes sidebar and overlay', async () => {
    await loadModule('static/js/sidebar-toggle.js');
    document.getElementById('mobileSidebarToggle').click();
    document.getElementById('closeSidebarBtn').click();
    expect(document.getElementById('appSidebar').classList.contains('open')).toBe(false);
    expect(document.getElementById('sidebarOverlay').classList.contains('active')).toBe(false);
  });

  it('overlay click closes sidebar', async () => {
    await loadModule('static/js/sidebar-toggle.js');
    document.getElementById('mobileSidebarToggle').click();
    document.getElementById('sidebarOverlay').click();
    expect(document.getElementById('appSidebar').classList.contains('open')).toBe(false);
  });

  it('escape key closes mobile sidebar', async () => {
    await loadModule('static/js/sidebar-toggle.js');
    document.getElementById('mobileSidebarToggle').click();
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    expect(document.getElementById('appSidebar').classList.contains('open')).toBe(false);
  });

  it('clicking a link inside sidebar closes sidebar on mobile widths', async () => {
    await loadModule('static/js/sidebar-toggle.js');
    document.getElementById('mobileSidebarToggle').click();
    document.querySelector('#appSidebar a').click();
    expect(document.getElementById('appSidebar').classList.contains('open')).toBe(false);
  });

  it('window resize hides sidebar when viewport grows', async () => {
    vi.useFakeTimers();
    await loadModule('static/js/sidebar-toggle.js');
    document.getElementById('mobileSidebarToggle').click();
    Object.defineProperty(window, 'innerWidth', { value: 1280, configurable: true });
    window.dispatchEvent(new Event('resize'));
    vi.advanceTimersByTime(200);
    expect(document.getElementById('appSidebar').classList.contains('open')).toBe(false);
    vi.useRealTimers();
  });
});