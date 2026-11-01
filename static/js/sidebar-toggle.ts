/* Sidebar toggle - TypeScript */
(function(): void {
  'use strict';

  const STORAGE_KEY = 'azad-sidebar';
  const SIDEBAR = 'sidebar';
  const TOGGLE_BTN = 'sidebarToggle';

  function getSidebarState(): { collapsed: boolean; position: 'left' | 'right' } {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return stored ? JSON.parse(stored) : { collapsed: false, position: 'left' };
    } catch {
      return { collapsed: false, position: 'left' };
    }
  }

  function setSidebarState(state: { collapsed: boolean; position: 'left' | 'right' }): void {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }

  function toggleSidebar(): void {
    const sidebar = document.getElementById(SIDEBAR);
    const state = getSidebarState();
    state.collapsed = !state.collapsed;
    if (sidebar) {
      sidebar.classList.toggle('collapsed', state.collapsed);
    }
    setSidebarState(state);
  }

  function togglePosition(): void {
    const sidebar = document.getElementById(SIDEBAR);
    const state = getSidebarState();
    state.position = state.position === 'left' ? 'right' : 'left';
    if (sidebar) {
      sidebar.classList.toggle('sidebar-right', state.position === 'right');
    }
    setSidebarState(state);
  }

  // Initialize
  document.addEventListener('DOMContentLoaded', () => {
    const sidebar = document.getElementById(SIDEBAR);
    const state = getSidebarState();
    if (sidebar) {
      sidebar.classList.toggle('collapsed', state.collapsed);
      sidebar.classList.toggle('sidebar-right', state.position === 'right');
    }
    const toggleBtn = document.getElementById(TOGGLE_BTN);
    if (toggleBtn) {
      toggleBtn.addEventListener('click', toggleSidebar);
    }
  });

  (window as any).toggleSidebar = toggleSidebar;
  (window as any).toggleSidebarPosition = togglePosition;
})();