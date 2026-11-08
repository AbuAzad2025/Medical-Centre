import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

const STORAGE_KEY = 'sidebar-config';

function ownerDom() {
  document.body.innerHTML = `
    <div id="ownerSidebar"><a href="/home">Home</a></div>
    <div id="ownerSidebarOverlay"></div>
    <button id="ownerMobileToggle">Toggle</button>
    <button id="closeSidebarBtn">Close</button>
  `;
}

function clinicalDom() {
  document.body.innerHTML = `
    <div id="appSidebar"></div>
    <div id="sidebarOverlay"></div>
    <button id="mobileSidebarToggle">Toggle</button>
    <button id="closeSidebarBtn">Close</button>
  `;
}

beforeEach(() => {
  document.body.innerHTML = '';
  document.documentElement.className = '';
  window.localStorage.clear();
  window.innerWidth = 1024;
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe('sidebar-toggle.js remaining arms', () => {
  it('owner layout toggles owner sidebar when clinical is absent', async () => {
    ownerDom();
    await loadModule('static/js/sidebar-toggle.js');
    document.getElementById('ownerMobileToggle').click();
    expect(document.getElementById('ownerSidebar').classList.contains('open')).toBe(true);
    expect(document.getElementById('ownerSidebarOverlay').classList.contains('active')).toBe(true);
  });

  it('toggleMobileSidebar with no sidebar elements does not crash', async () => {
    document.body.innerHTML = '<button id="mobileSidebarToggle">Toggle</button>';
    await loadModule('static/js/sidebar-toggle.js');
    expect(() => document.getElementById('mobileSidebarToggle').click()).not.toThrow();
  });

  it('open sidebar with no focusable children still toggles aria-hidden', async () => {
    document.body.innerHTML = `
      <div id="appSidebar"></div>
      <div id="sidebarOverlay"></div>
      <button id="mobileSidebarToggle">Toggle</button>
    `;
    await loadModule('static/js/sidebar-toggle.js');
    document.getElementById('mobileSidebarToggle').click();
    const sidebar = document.getElementById('appSidebar');
    expect(sidebar.classList.contains('open')).toBe(true);
    expect(sidebar.getAttribute('aria-hidden')).toBe('false');
  });

  it('clicking a link on desktop width does not close the mobile sidebar', async () => {
    window.innerWidth = 1400;
    clinicalDom();
    await loadModule('static/js/sidebar-toggle.js');
    document.getElementById('mobileSidebarToggle').click();
    const link = document.createElement('a');
    link.href = '/x';
    link.textContent = 'Go';
    document.body.appendChild(link);
    link.click();
    expect(document.getElementById('appSidebar').classList.contains('open')).toBe(true);
  });

  it('aria labels reflect collapsed state and left position', async () => {
    ownerDom();
    document.body.insertAdjacentHTML('beforeend', `
      <button id="sidebarPositionToggle"><svg viewBox="0 0 24 24"></svg></button>
      <button id="sidebarCollapseToggle"><svg viewBox="0 0 24 24"></svg></button>
    `);
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ position: 'left', collapsed: true }));
    await loadModule('static/js/sidebar-toggle.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const collapse = document.getElementById('sidebarCollapseToggle');
    expect(collapse.getAttribute('aria-label')).toBeTruthy();
    expect(document.documentElement.classList.contains('sidebar-left')).toBe(true);
    expect(document.documentElement.classList.contains('sidebar-collapsed')).toBe(true);
  });

  it('missing toggle buttons do not crash the initializer', async () => {
    document.body.innerHTML = '';
    await expect(loadModule('static/js/sidebar-toggle.js')).resolves.toBeDefined();
  });

  it('toggle button without svg child skips icon update without crashing', async () => {
    ownerDom();
    document.body.insertAdjacentHTML('beforeend', '<button id="sidebarPositionToggle"></button>');
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ position: 'right', collapsed: false }));
    await expect(loadModule('static/js/sidebar-toggle.js')).resolves.toBeDefined();
  });

  it('module registers init on DOMContentLoaded while document is still loading', async () => {
    Object.defineProperty(document, 'readyState', { value: 'loading', configurable: true });
    clinicalDom();
    await loadModule('static/js/sidebar-toggle.js');
    expect(document.documentElement.classList.contains('sidebar-right')).toBe(false);
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(document.documentElement.classList.contains('sidebar-right')).toBe(true);
    Object.defineProperty(document, 'readyState', { value: 'complete', configurable: true });
  });
});
