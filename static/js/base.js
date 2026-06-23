(function() {
    const token = (document.querySelector('meta[name="csrf-token"]') || {}).content;
    if (!token || !window.fetch) return;
    const originalFetch = window.fetch.bind(window);
    window.__apiMetrics = { calls: 0, time: 0 };
    window.fetch = function(input, init) {
        const start = performance.now();
        init = init || {};
        const method = (init.method || 'GET').toUpperCase();
        if (method !== 'GET' && method !== 'HEAD') {
            const headers = new Headers(init.headers || {});
            if (!headers.has('X-CSRFToken') && !headers.has('X-CSRF-Token')) {
                headers.set('X-CSRFToken', token);
            }
            init.headers = headers;
        }
        return originalFetch(input, init).then(response => {
            const elapsed = performance.now() - start;
            window.__apiMetrics.calls += 1;
            window.__apiMetrics.time += elapsed;
            return response;
        });
    };
})();

document.addEventListener('DOMContentLoaded', function() {
    try {
        var envEl = document.querySelector('meta[name="app-env"]');
        window.__ENV = (envEl && envEl.getAttribute('content')) || 'development';
        if (window.__ENV === 'production') {
            console.debug = function(){};
            console.log = function(){};
        }
    } catch (e) {}

    const sidebar = document.getElementById('appSidebar');
    const toggleBtn = document.getElementById('sidebarToggle');
    if (sidebar && toggleBtn) {
        try {
            const saved = localStorage.getItem('sidebarCollapsed');
            if (saved === '1') {
                sidebar.classList.add('collapsed');
                toggleBtn.setAttribute('aria-expanded', 'false');
            }
            toggleBtn.addEventListener('click', function() {
                const isCollapsed = sidebar.classList.toggle('collapsed');
                this.setAttribute('aria-expanded', isCollapsed ? 'false' : 'true');
                try { localStorage.setItem('sidebarCollapsed', isCollapsed ? '1' : '0'); } catch (e) {}
            });
        } catch (e) {
            console.warn('Sidebar toggle init failed:', e);
        }
    }

    // Mobile sidebar overlay toggle (Clinical Clean shell)
    const mobileToggle = document.getElementById('mobileSidebarToggle');
    const closeSidebarBtn = document.getElementById('closeSidebarBtn');
    const sidebarOverlay = document.getElementById('sidebarOverlay');
    function openSidebar() {
        if (sidebar) sidebar.classList.add('show');
        if (sidebarOverlay) sidebarOverlay.classList.add('active');
        document.body.classList.add('sidebar-open');
    }
    function closeSidebar() {
        if (sidebar) sidebar.classList.remove('show');
        if (sidebarOverlay) sidebarOverlay.classList.remove('active');
        document.body.classList.remove('sidebar-open');
    }
    if (mobileToggle) mobileToggle.addEventListener('click', openSidebar);
    if (closeSidebarBtn) closeSidebarBtn.addEventListener('click', closeSidebar);
    if (sidebarOverlay) sidebarOverlay.addEventListener('click', closeSidebar);

    // Form submit: disable button + show loading
    document.querySelectorAll('form').forEach(function(form) {
        var handled = form.hasAttribute('data-submit-handled');
        if (handled) return;
        form.setAttribute('data-submit-handled', '1');
        form.addEventListener('submit', function(e) {
            var btn = this.querySelector('button[type="submit"], input[type="submit"]');
            if (btn && !btn.disabled) {
                btn.disabled = true;
                btn.setAttribute('data-loading', '');
                // Re-enable after 30s in case of timeout
                setTimeout(function() {
                    if (btn) { btn.disabled = false; btn.removeAttribute('data-loading'); }
                }, 30000);
            }
        });
    });

    // Auto-focus first visible input in modals
    document.querySelectorAll('.modal').forEach(function(modal) {
        modal.addEventListener('shown.bs.modal', function() {
            var input = this.querySelector('input:not([type="hidden"]):not([type="search"]), textarea, select');
            if (input) setTimeout(function() { input.focus(); }, 100);
        });
        modal.addEventListener('hidden.bs.modal', function() {
            var btn = this.querySelector('button[type="submit"]');
            if (btn) { btn.disabled = false; btn.removeAttribute('data-loading'); }
        });
    });

    // Auto-attach confirmation to [data-confirm] buttons/links
    document.querySelectorAll('[data-confirm]').forEach(function(el) {
        var msg = el.getAttribute('data-confirm');
        if (!msg) return;
        el.addEventListener('click', function(e) {
            e.preventDefault();
            var target = this;
            var type = this.tagName === 'A' ? 'link' : 'button';
            if (typeof Swal !== 'undefined') {
                Swal.fire({
                    title: 'تأكيد',
                    text: msg,
                    icon: 'question',
                    showCancelButton: true,
                    confirmButtonText: 'نعم',
                    cancelButtonText: 'إلغاء'
                }).then(function(result) {
                    if (result.isConfirmed) {
                        if (type === 'link') {
                            var href = target.getAttribute('href');
                            if (href && href !== '#') window.location.href = href;
                        } else {
                            var form = target.form || target.closest('form');
                            if (form) form.submit();
                        }
                    }
                });
            }
        });
    });
});

if (typeof gsap !== 'undefined' && typeof ScrollTrigger !== 'undefined') {
    try {
        gsap.registerPlugin(ScrollTrigger);
    } catch (e) {
        console.warn('GSAP initialization failed:', e);
    }
}

document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
            target.scrollIntoView({
                behavior: reduced ? 'auto' : 'smooth',
                block: 'start'
            });
        }
    });
});

try {
    var theme = localStorage.getItem('theme');
    if (theme === 'dark') document.documentElement.setAttribute('data-theme', 'dark');
    var density = localStorage.getItem('ui_density');
    if (density) document.documentElement.setAttribute('data-density', density);
    var radius = localStorage.getItem('ui_radius');
    if (radius) document.documentElement.setAttribute('data-radius', radius);
} catch (e) {}

window.addEventListener('load', function() {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    if (typeof gsap === 'undefined') return;
    gsap.from('.card-modern', {
        duration: 0.8,
        y: 50,
        opacity: 0,
        stagger: 0.1,
        ease: "power2.out"
    });
});

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function validateForm(form) {
    const inputs = form.querySelectorAll('input[required], select[required], textarea[required]');
    let isValid = true;
    inputs.forEach(input => {
        if (!input.value.trim()) {
            input.classList.add('is-invalid');
            isValid = false;
        } else {
            input.classList.remove('is-invalid');
            input.classList.add('is-valid');
        }
    });
    return isValid;
}

function confirmNavigate(e, message) {
    e.preventDefault();
    const url = e.currentTarget.href;
    Swal.fire({
        title: 'تأكيد',
        text: message,
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: 'نعم',
        cancelButtonText: 'إلغاء'
    }).then((result) => {
        if (result.isConfirmed) {
            window.location.href = url;
        }
    });
    return false;
}

function confirmSubmit(e, message) {
    e.preventDefault();
    const form = e.currentTarget.form || e.currentTarget.closest('form');
    if (!form) return false;
    Swal.fire({
        title: 'تأكيد',
        text: message,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'نعم',
        cancelButtonText: 'إلغاء'
    }).then((result) => {
        if (result.isConfirmed) {
            form.submit();
        }
    });
    return false;
}

function initAdvancedTable(tableId) {
    const table = document.getElementById(tableId);
    if (!table) return;
    const searchInput = document.createElement('input');
    searchInput.type = 'text';
    searchInput.className = 'form-control mb-3';
    searchInput.placeholder = 'البحث...';
    searchInput.style.borderRadius = '15px';
    table.parentNode.insertBefore(searchInput, table);
    searchInput.addEventListener('input', debounce(function() {
        const filter = this.value.toLowerCase();
        const rows = table.querySelectorAll('tbody tr');
        rows.forEach(row => {
            const text = row.textContent.toLowerCase();
            row.style.display = text.includes(filter) ? '' : 'none';
        });
    }, 300));
    const headers = table.querySelectorAll('th[data-sort]');
    headers.forEach(header => {
        header.style.cursor = 'pointer';
        header.innerHTML += ' <i class="fas fa-sort ms-1"></i>';
        header.addEventListener('click', function() {
            const column = this.dataset.sort;
            const tbody = table.querySelector('tbody');
            const rows = Array.from(tbody.querySelectorAll('tr'));
            const isAsc = this.classList.contains('sort-asc');
            rows.sort((a, b) => {
                const aVal = a.querySelector(`[data-${column}]`)?.textContent || '';
                const bVal = b.querySelector(`[data-${column}]`)?.textContent || '';
                return isAsc ? bVal.localeCompare(aVal) : aVal.localeCompare(bVal);
            });
            headers.forEach(h => h.classList.remove('sort-asc', 'sort-desc'));
            this.classList.add(isAsc ? 'sort-desc' : 'sort-asc');
            rows.forEach(row => tbody.appendChild(row));
        });
    });
}

function updateClock() {
    const now = new Date();
    const timeString = now.toLocaleTimeString('ar-SA', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
    const dateString = now.toLocaleDateString('ar-SA', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
    const clockElements = document.querySelectorAll('.live-clock');
    clockElements.forEach(element => {
        element.innerHTML = `${timeString} - ${dateString}`;
    });
}

setInterval(updateClock, 1000);
updateClock();

function initAutoSave(formId, interval = 30000) {
    const form = document.getElementById(formId);
    if (!form) return;
    const inputs = form.querySelectorAll('input, select, textarea');
    let hasChanges = false;
    inputs.forEach(input => {
        input.addEventListener('input', () => {
            hasChanges = true;
        });
    });
    setInterval(() => {
        if (hasChanges) {
            console.log('Auto-saving form...');
            hasChanges = false;
        }
    }, interval);
}

function initPerformanceMonitoring() {
    window.addEventListener('load', () => {
        const loadTime = performance.now();
        console.log(`Page loaded in ${loadTime.toFixed(2)}ms`);
    });
}

document.addEventListener('DOMContentLoaded', function() {
    initPerformanceMonitoring();
    document.querySelectorAll('table[id]').forEach(table => {
        initAdvancedTable(table.id);
    });
    document.querySelectorAll('.card').forEach(card => {
        card.classList.add('card-modern');
    });
    document.querySelectorAll('.btn').forEach(btn => {
        btn.classList.add('btn-modern');
    });
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
    function enforceSafeLinks(){
        document.querySelectorAll('a').forEach(function(a){
            var href = a.getAttribute('href') || '';
            var isPlaceholder = href === '#' || href.trim() === '';
            var isToggle = a.hasAttribute('data-bs-toggle');
            if (isPlaceholder) {
                a.setAttribute('href','javascript:void(0)');
                a.setAttribute('role','button');
                a.setAttribute('tabindex','0');
            }
            if (isPlaceholder || isToggle) {
                a.addEventListener('click', function(e){ e.preventDefault(); });
            }
            if (window.__ENV !== 'production' && isPlaceholder && !isToggle && !a.getAttribute('onclick')){
                try {
                    var label = (a.textContent || a.getAttribute('aria-label') || '').trim();
                    if (label) console.warn('Placeholder link detected:', label);
                } catch (e) {}
            }
        });
    }
    enforceSafeLinks();
    const tabSelectors = ['a[data-bs-toggle="tab"]', '.nav-link[data-bs-toggle="tab"]', 'button[data-bs-toggle="tab"]'];
    document.querySelectorAll(tabSelectors.join(',')).forEach(function(tabLink){
        tabLink.addEventListener('shown.bs.tab', function(ev){
            const targetSel = ev.target.getAttribute('href') || ev.target.getAttribute('data-bs-target');
            const pane = targetSel && document.querySelector(targetSel);
            if (pane) {
                try {
                    if (window.$ && window.$.fn && window.$.fn.DataTable) {
                        pane.querySelectorAll('table[data-dt="1"]').forEach(function(tbl){
                            const dt = window.$(tbl).DataTable();
                            if (dt) dt.columns.adjust();
                        });
                    }
                } catch (e) {}
                const url = pane.getAttribute('data-load-url');
                if (url && !pane.getAttribute('data-loaded')) {
                    fetch(url, { method: 'GET', headers: { 'Accept': 'text/html' } })
                        .then(r => r.text())
                        .then(html => { pane.innerHTML = html; pane.setAttribute('data-loaded','1'); })
                        .catch(()=>{});
                }
            }
        });
    });
});

window.addEventListener('error', function(e) {
    if (e.filename && (e.filename.includes('.map') || e.filename.includes('favicon'))) {
        return;
    }
    console.error('Global error:', e.error);
});

if ('serviceWorker' in navigator) {
    window.addEventListener('load', function() {
        navigator.serviceWorker.register('/static/pwa/sw.js', { scope: '/' })
            .then(function(registration) {
                console.log('ServiceWorker registration successful');
            })
            .catch(function(err) {
                console.log('ServiceWorker registration failed:', err);
            });
    });
}

// Top loading bar for page navigation
(function() {
  var bar = document.createElement('div');
  bar.className = 'top-loading-bar';
  bar.id = 'topLoadingBar';
  bar.style.display = 'none';
  document.body.appendChild(bar);
  var timeoutId = null;
  function showBar() {
    bar.style.display = 'block';
    bar.style.width = '30%';
    if (timeoutId) clearTimeout(timeoutId);
  }
  function completeBar() {
    bar.style.width = '100%';
    timeoutId = setTimeout(function() {
      bar.style.width = '0';
      bar.style.display = 'none';
    }, 400);
  }
  // Hook into link clicks for same-origin navigation
  document.addEventListener('click', function(e) {
    var link = e.target.closest('a');
    if (!link) return;
    var href = link.getAttribute('href');
    if (!href || href === '#' || href.startsWith('javascript:') || href.startsWith('#')) return;
    if (link.target === '_blank' || link.hasAttribute('download')) return;
    try {
      var linkUrl = new URL(href, window.location.origin);
      if (linkUrl.origin !== window.location.origin) return;
      if (linkUrl.pathname === window.location.pathname) return;
    } catch(_) { return; }
    showBar();
  });
  window.addEventListener('beforeunload', function() { showBar(); });
  window.addEventListener('load', function() { completeBar(); });
})();

// Clickable table rows
document.addEventListener('click', function(e) {
  var tr = e.target.closest('tr[data-href]');
  if (tr) {
    var href = tr.getAttribute('data-href');
    if (href && href !== '#') {
      window.location.href = href;
    }
  }
});

// Keyboard shortcuts
document.addEventListener('keydown', function(e) {
    // Escape: close all toasts + modals
    if (e.key === 'Escape' && !e.target.closest('.tox')) {
        document.querySelectorAll('.toast:not(.removing)').forEach(function(toast) {
            var btn = toast.querySelector('.toast-close');
            if (btn) btn.click();
        });
    }

    // Ctrl+Enter / Cmd+Enter: submit current form
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        var active = document.activeElement;
        if (active) {
            var form = active.form || active.closest('form');
            if (form) {
                e.preventDefault();
                var btn = form.querySelector('button[type="submit"]');
                if (btn) btn.click();
                else form.submit();
            }
        }
    }
});

// Extra safety: prevent double-submit via capture phase
document.addEventListener('submit', function(e) {
    if (e.defaultPrevented) return;
    var btn = e.target.querySelector('button[type="submit"]');
    if (btn && btn.disabled) {
        e.preventDefault();
    }
}, true);
