/**
 * Performance Optimization JavaScript
 * Medical System - Advanced Performance Scripts
 */

// Performance monitoring
class PerformanceMonitor {
    constructor() {
        this.metrics = {};
        this.startTime = performance.now();
        this.init();
    }

    init() {
        this.monitorPageLoad();
        this.monitorAPI();
        this.monitorMemory();
        this.monitorFPS();
    }

    monitorPageLoad() {
        window.addEventListener('load', () => {
            const loadTime = performance.now() - this.startTime;
            this.metrics.pageLoad = loadTime;
            console.log(`Page loaded in ${loadTime.toFixed(2)}ms`);
        });
    }

    monitorAPI() {
        const originalFetch = window.fetch;
        window.fetch = async (...args) => {
            const start = performance.now();
            try {
                const response = await originalFetch(...args);
                const end = performance.now();
                const duration = end - start;
                this.metrics.apiCalls = (this.metrics.apiCalls || 0) + 1;
                this.metrics.apiTime = (this.metrics.apiTime || 0) + duration;
                console.log(`API call took ${duration.toFixed(2)}ms`);
                return response;
            } catch (error) {
                const end = performance.now();
                console.error(`API call failed after ${(end - start).toFixed(2)}ms:`, error);
                throw error;
            }
        };
    }

    monitorMemory() {
        if ('memory' in performance) {
            setInterval(() => {
                const memory = performance.memory;
                this.metrics.memory = {
                    used: memory.usedJSHeapSize,
                    total: memory.totalJSHeapSize,
                    limit: memory.jsHeapSizeLimit
                };
            }, 5000);
        }
    }

    monitorFPS() {
        let lastTime = performance.now();
        let frameCount = 0;
        let fps = 0;

        const measureFPS = () => {
            frameCount++;
            const currentTime = performance.now();
            
            if (currentTime - lastTime >= 1000) {
                fps = Math.round((frameCount * 1000) / (currentTime - lastTime));
                this.metrics.fps = fps;
                frameCount = 0;
                lastTime = currentTime;
            }
            
            requestAnimationFrame(measureFPS);
        };
        
        requestAnimationFrame(measureFPS);
    }

    getMetrics() {
        return this.metrics;
    }
}

// Lazy loading implementation
class LazyLoader {
    constructor() {
        this.observer = null;
        this.init();
    }

    init() {
        if ('IntersectionObserver' in window) {
            this.observer = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        this.loadElement(entry.target);
                        this.observer.unobserve(entry.target);
                    }
                });
            }, {
                rootMargin: '50px 0px',
                threshold: 0.1
            });

            this.observeElements();
        }
    }

    observeElements() {
        document.querySelectorAll('.lazy-load').forEach(el => {
            this.observer.observe(el);
        });
    }

    loadElement(element) {
        element.classList.add('loaded');
        
        // Load images
        if (element.tagName === 'IMG' && element.dataset.src) {
            element.src = element.dataset.src;
            element.removeAttribute('data-src');
        }
        
        // Load background images
        if (element.dataset.bg) {
            element.style.backgroundImage = `url(${element.dataset.bg})`;
            element.removeAttribute('data-bg');
        }
    }
}

// Debounce utility
function debounce(func, wait, immediate = false) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            timeout = null;
            if (!immediate) func(...args);
        };
        const callNow = immediate && !timeout;
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
        if (callNow) func(...args);
    };
}

// Throttle utility
function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// Optimized search
class OptimizedSearch {
    constructor(inputSelector, resultsSelector, searchFunction) {
        this.input = document.querySelector(inputSelector);
        this.results = document.querySelector(resultsSelector);
        this.searchFunction = searchFunction;
        this.cache = new Map();
        this.init();
    }

    init() {
        if (this.input) {
            this.input.addEventListener('input', debounce((e) => {
                this.performSearch(e.target.value);
            }, 300));
        }
    }

    async performSearch(query) {
        if (query.length < 2) {
            this.clearResults();
            return;
        }

        // Check cache first
        if (this.cache.has(query)) {
            this.displayResults(this.cache.get(query));
            return;
        }

        try {
            const results = await this.searchFunction(query);
            this.cache.set(query, results);
            this.displayResults(results);
        } catch (error) {
            console.error('Search error:', error);
        }
    }

    displayResults(results) {
        if (this.results) {
            this.results.innerHTML = results.map(result => 
                `<div class="search-result">${result}</div>`
            ).join('');
        }
    }

    clearResults() {
        if (this.results) {
            this.results.innerHTML = '';
        }
    }
}

// Optimized table
class OptimizedTable {
    constructor(tableSelector) {
        this.table = document.querySelector(tableSelector);
        this.data = [];
        this.filteredData = [];
        this.currentPage = 1;
        this.pageSize = 50;
        this.sortColumn = null;
        this.sortDirection = 'asc';
        this.init();
    }

    init() {
        if (this.table) {
            this.addSearch();
            this.addSorting();
            this.addPagination();
            this.addVirtualScrolling();
        }
    }

    addSearch() {
        const searchInput = document.createElement('input');
        searchInput.type = 'text';
        searchInput.className = 'form-control mb-3';
        searchInput.placeholder = 'البحث...';
        
        searchInput.addEventListener('input', debounce((e) => {
            this.filterData(e.target.value);
        }, 300));

        this.table.parentNode.insertBefore(searchInput, this.table);
    }

    addSorting() {
        const headers = this.table.querySelectorAll('th[data-sort]');
        headers.forEach(header => {
            header.style.cursor = 'pointer';
            header.addEventListener('click', () => {
                this.sortData(header.dataset.sort);
            });
        });
    }

    addPagination() {
        const pagination = document.createElement('div');
        pagination.className = 'pagination-container mt-3';
        this.table.parentNode.appendChild(pagination);
    }

    addVirtualScrolling() {
        // Implement virtual scrolling for large datasets
        const tbody = this.table.querySelector('tbody');
        if (tbody) {
            tbody.style.maxHeight = '400px';
            tbody.style.overflowY = 'auto';
        }
    }

    filterData(query) {
        this.filteredData = this.data.filter(row => 
            Object.values(row).some(value => 
                String(value).toLowerCase().includes(query.toLowerCase())
            )
        );
        this.render();
    }

    sortData(column) {
        if (this.sortColumn === column) {
            this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc';
        } else {
            this.sortColumn = column;
            this.sortDirection = 'asc';
        }

        this.filteredData.sort((a, b) => {
            const aVal = a[column];
            const bVal = b[column];
            
            if (aVal < bVal) return this.sortDirection === 'asc' ? -1 : 1;
            if (aVal > bVal) return this.sortDirection === 'asc' ? 1 : -1;
            return 0;
        });

        this.render();
    }

    render() {
        // Implement efficient rendering
        const tbody = this.table.querySelector('tbody');
        if (tbody) {
            tbody.innerHTML = this.filteredData
                .slice((this.currentPage - 1) * this.pageSize, this.currentPage * this.pageSize)
                .map(row => this.createRow(row))
                .join('');
        }
    }

    createRow(row) {
        return `<tr>${Object.values(row).map(cell => `<td>${cell}</td>`).join('')}</tr>`;
    }
}

// Optimized form validation
class OptimizedFormValidator {
    constructor(formSelector) {
        this.form = document.querySelector(formSelector);
        this.rules = {};
        this.init();
    }

    init() {
        if (this.form) {
            this.setupValidation();
            this.addRealTimeValidation();
        }
    }

    setupValidation() {
        this.form.addEventListener('submit', (e) => {
            if (!this.validateForm()) {
                e.preventDefault();
            }
        });
    }

    addRealTimeValidation() {
        const inputs = this.form.querySelectorAll('input, select, textarea');
        inputs.forEach(input => {
            input.addEventListener('blur', () => {
                this.validateField(input);
            });
        });
    }

    validateForm() {
        let isValid = true;
        const inputs = this.form.querySelectorAll('input, select, textarea');
        
        inputs.forEach(input => {
            if (!this.validateField(input)) {
                isValid = false;
            }
        });

        return isValid;
    }

    validateField(field) {
        const value = field.value.trim();
        const rules = this.rules[field.name] || [];
        let isValid = true;

        rules.forEach(rule => {
            if (!rule.test(value)) {
                this.showError(field, rule.message);
                isValid = false;
            }
        });

        if (isValid) {
            this.clearError(field);
        }

        return isValid;
    }

    showError(field, message) {
        field.classList.add('is-invalid');
        let errorElement = field.parentNode.querySelector('.invalid-feedback');
        if (!errorElement) {
            errorElement = document.createElement('div');
            errorElement.className = 'invalid-feedback';
            field.parentNode.appendChild(errorElement);
        }
        errorElement.textContent = message;
    }

    clearError(field) {
        field.classList.remove('is-invalid');
        field.classList.add('is-valid');
        const errorElement = field.parentNode.querySelector('.invalid-feedback');
        if (errorElement) {
            errorElement.remove();
        }
    }

    addRule(fieldName, rule) {
        if (!this.rules[fieldName]) {
            this.rules[fieldName] = [];
        }
        this.rules[fieldName].push(rule);
    }
}

// Optimized notifications
class OptimizedNotifications {
    constructor() {
        this.notifications = [];
        this.container = this.createContainer();
        this.init();
    }

    init() {
        document.body.appendChild(this.container);
    }

    createContainer() {
        const container = document.createElement('div');
        container.className = 'notifications-container';
        container.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
            max-width: 400px;
        `;
        return container;
    }

    show(message, type = 'info', duration = 5000) {
        const notification = this.createNotification(message, type);
        this.container.appendChild(notification);
        this.notifications.push(notification);

        // Animate in
        requestAnimationFrame(() => {
            notification.classList.add('show');
        });

        // Auto remove
        setTimeout(() => {
            this.remove(notification);
        }, duration);
    }

    createNotification(message, type) {
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.style.cssText = `
            background: white;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            padding: 16px;
            margin-bottom: 10px;
            transform: translateX(100%);
            transition: transform 0.3s ease;
            border-left: 4px solid ${this.getColor(type)};
        `;

        notification.innerHTML = `
            <div style="display: flex; align-items: center; justify-content: space-between;">
                <span>${message}</span>
                <button onclick="this.parentElement.parentElement.remove()" style="background: none; border: none; font-size: 18px; cursor: pointer;">&times;</button>
            </div>
        `;

        return notification;
    }

    getColor(type) {
        const colors = {
            success: '#28a745',
            error: '#dc3545',
            warning: '#ffc107',
            info: '#17a2b8'
        };
        return colors[type] || colors.info;
    }

    remove(notification) {
        notification.style.transform = 'translateX(100%)';
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
            const index = this.notifications.indexOf(notification);
            if (index > -1) {
                this.notifications.splice(index, 1);
            }
        }, 300);
    }
}

// Optimized caching
class OptimizedCache {
    constructor(maxSize = 100) {
        this.cache = new Map();
        this.maxSize = maxSize;
    }

    get(key) {
        if (this.cache.has(key)) {
            const item = this.cache.get(key);
            // Move to end (LRU)
            this.cache.delete(key);
            this.cache.set(key, item);
            return item.value;
        }
        return null;
    }

    set(key, value, ttl = 300000) { // 5 minutes default
        if (this.cache.size >= this.maxSize) {
            // Remove oldest item
            const firstKey = this.cache.keys().next().value;
            this.cache.delete(firstKey);
        }

        this.cache.set(key, {
            value,
            expiry: Date.now() + ttl
        });
    }

    clear() {
        this.cache.clear();
    }

    cleanup() {
        const now = Date.now();
        for (const [key, item] of this.cache.entries()) {
            if (item.expiry < now) {
                this.cache.delete(key);
            }
        }
    }
}

// Initialize performance optimizations
document.addEventListener('DOMContentLoaded', () => {
    // Initialize performance monitor
    const performanceMonitor = new PerformanceMonitor();
    
    // Initialize lazy loader
    const lazyLoader = new LazyLoader();
    
    // Initialize notifications
    const notifications = new OptimizedNotifications();
    
    // Initialize optimized tables
    document.querySelectorAll('table[id]').forEach(table => {
        new OptimizedTable(`#${table.id}`);
    });
    
    // Initialize optimized forms
    document.querySelectorAll('form[id]').forEach(form => {
        new OptimizedFormValidator(`#${form.id}`);
    });
    
    // Add performance CSS classes
    document.querySelectorAll('.card').forEach(card => {
        card.classList.add('card-optimized');
    });
    
    document.querySelectorAll('.btn').forEach(btn => {
        btn.classList.add('btn-optimized');
    });
    
    document.querySelectorAll('.form-control').forEach(input => {
        input.classList.add('form-control-optimized');
    });
    
    // Cleanup cache every 5 minutes
    setInterval(() => {
        if (window.optimizedCache) {
            window.optimizedCache.cleanup();
        }
    }, 300000);
    
    // Make utilities globally available
    window.performanceMonitor = performanceMonitor;
    window.notifications = notifications;
    window.optimizedCache = new OptimizedCache();
    window.debounce = debounce;
    window.throttle = throttle;
});

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        PerformanceMonitor,
        LazyLoader,
        OptimizedSearch,
        OptimizedTable,
        OptimizedFormValidator,
        OptimizedNotifications,
        OptimizedCache,
        debounce,
        throttle
    };
}