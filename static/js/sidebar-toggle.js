/**
 * Sidebar Toggle System - Works for both clinical and owner layouts
 * Features: Left/Right toggle, Collapse/Expand, Mobile support, Persistence
 */
(function() {
  'use strict';

  const STORAGE_KEY = 'sidebar-config';
  const DEFAULT_CONFIG = {
    position: 'right',  // 'left' or 'right'
    collapsed: false
  };

  // ============================================================
  // DOM Elements
  // ============================================================
  const html = document.documentElement;
  const body = document.body;

  // Clinical elements
  const clinicalSidebar = document.getElementById('appSidebar');
  const clinicalOverlay = document.getElementById('sidebarOverlay');
  const clinicalCloseBtn = document.getElementById('closeSidebarBtn');
  const clinicalToggleBtn = document.getElementById('mobileSidebarToggle');

  // Owner elements
  const ownerSidebar = document.getElementById('ownerSidebar');
  const ownerOverlay = document.getElementById('ownerSidebarOverlay');
  const ownerCloseBtn = document.getElementById('closeSidebarBtn'); // Same ID in owner
  const ownerMobileToggle = document.getElementById('ownerMobileToggle');

  // Toggle buttons
  const sidebarPositionToggle = document.getElementById('sidebarPositionToggle');
  const sidebarCollapseToggle = document.getElementById('sidebarCollapseToggle');

  // ============================================================
  // State Management
  // ============================================================
  function getConfig() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY)) || DEFAULT_CONFIG;
    } catch {
      return DEFAULT_CONFIG;
    }
  }

  function saveConfig(config) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
  }

  function applyConfig(config) {
    // Position
    html.classList.remove('sidebar-left', 'sidebar-right');
    html.classList.add('sidebar-' + config.position);

    // Collapse
    if (config.collapsed) {
      html.classList.add('sidebar-collapsed');
    } else {
      html.classList.remove('sidebar-collapsed');
    }

    // Update toggle button icons
    updateToggleButtons(config);
  }

  function updateToggleButtons(config) {
    const posBtn = sidebarPositionToggle;
    const collapseBtn = sidebarCollapseToggle;

    if (posBtn) {
      // Update icon and tooltip
      const isLeft = config.position === 'left';
      posBtn.setAttribute('aria-label', isLeft ? 'نقل القائمة لليمين' : 'نقل القائمة لليسار');
      posBtn.setAttribute('title', isLeft ? 'نقل القائمة لليمين' : 'نقل القائمة لليسار');
      
      // Update icon
      const icon = posBtn.querySelector('svg');
      if (icon) {
        icon.innerHTML = isLeft 
          ? '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>'
          : '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>';
      }
    }

    if (collapseBtn) {
      const isCollapsed = config.collapsed;
      collapseBtn.setAttribute('aria-label', isCollapsed ? 'توسيع القائمة' : 'طي القائمة');
      collapseBtn.setAttribute('title', isCollapsed ? 'توسيع القائمة' : 'طي القائمة');
      
      const icon = collapseBtn.querySelector('svg');
      if (icon) {
        icon.innerHTML = isCollapsed
          ? '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>'
          : '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>';
      }
    }
  }

  // ============================================================
  // Toggle Functions
  // ============================================================
  function togglePosition() {
    const config = getConfig();
    config.position = config.position === 'left' ? 'right' : 'left';
    saveConfig(config);
    applyConfig(config);
  }

  function toggleCollapse() {
    const config = getConfig();
    config.collapsed = !config.collapsed;
    saveConfig(config);
    applyConfig(config);
  }

  function toggleMobileSidebar() {
    const sidebar = clinicalSidebar || ownerSidebar;
    const overlay = clinicalOverlay || ownerOverlay;
    
    if (sidebar) {
      const isOpen = sidebar.classList.toggle('open');
      if (overlay) overlay.classList.toggle('active', isOpen);
      
      // Focus management
      if (isOpen) {
        sidebar.setAttribute('aria-hidden', 'false');
        // Trap focus
        const focusable = sidebar.querySelectorAll('a[href], button, input, select, textarea');
        if (focusable.length) focusable[0].focus();
      } else {
        sidebar.setAttribute('aria-hidden', 'true');
      }
    }
  }

  function closeMobileSidebar() {
    if (clinicalSidebar) clinicalSidebar.classList.remove('open');
    if (ownerSidebar) ownerSidebar.classList.remove('open');
    if (clinicalOverlay) clinicalOverlay.classList.remove('active');
    if (ownerOverlay) ownerOverlay.classList.remove('active');
  }

  // ============================================================
  // Event Listeners
  // ============================================================
  function initEventListeners() {
    // Position toggle
    if (sidebarPositionToggle) {
      sidebarPositionToggle.addEventListener('click', togglePosition);
    }

    // Collapse toggle
    if (sidebarCollapseToggle) {
      sidebarCollapseToggle.addEventListener('click', toggleCollapse);
    }

    // Mobile sidebar toggles
    if (clinicalToggleBtn) {
      clinicalToggleBtn.addEventListener('click', toggleMobileSidebar);
    }
    if (ownerMobileToggle) {
      ownerMobileToggle.addEventListener('click', toggleMobileSidebar);
    }

    // Close buttons
    if (clinicalCloseBtn) {
      clinicalCloseBtn.addEventListener('click', closeMobileSidebar);
    }
    if (ownerCloseBtn) {
      ownerCloseBtn.addEventListener('click', closeMobileSidebar);
    }

    // Overlay clicks
    if (clinicalOverlay) {
      clinicalOverlay.addEventListener('click', closeMobileSidebar);
    }
    if (ownerOverlay) {
      ownerOverlay.addEventListener('click', closeMobileSidebar);
    }

    // Close on Escape
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        closeMobileSidebar();
      }
    });

    // Close on navigation (mobile)
    document.addEventListener('click', (e) => {
      if (window.innerWidth <= 1199) {
        const link = e.target.closest('a[href]');
        if (link && !link.closest('.sidebar-toggle-btn')) {
          closeMobileSidebar();
        }
      }
    });
  }

  // ============================================================
  // Initialization
  // ============================================================
  function init() {
    const config = getConfig();
    applyConfig(config);
    initEventListeners();
    
    // Handle window resize
    let resizeTimer;
    window.addEventListener('resize', () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        if (window.innerWidth > 1199) {
          closeMobileSidebar();
        }
      }, 100);
    });

    console.log('[Sidebar] Initialized:', config);
  }

  // Auto-init when DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Expose for manual control
  window.SidebarToggle = {
    togglePosition,
    toggleCollapse,
    toggleMobile: toggleMobileSidebar,
    closeMobile: closeMobileSidebar,
    getConfig,
    applyConfig
  };
})();

export {};
