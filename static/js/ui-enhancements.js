/**
 * UI Enhancements JavaScript
 * Medical System User Interface Improvements
 */

class UIEnhancements {
    constructor() {
        this.theme = localStorage.getItem('theme') || 'light';
        this.language = localStorage.getItem('language') || 'ar';
        this.animations = localStorage.getItem('animations') === 'true';
        this.init();
    }

    init() {
        this.setupThemeSwitcher();
        this.setupLanguageSwitcher();
        this.setupAnimations();
        this.setupAccessibility();
        this.setupResponsiveDesign();
        this.setupSmartNotifications();
        this.setupKeyboardShortcuts();
        this.setupDragAndDrop();
        this.setupAutoSave();
    }

    // Theme switcher
    setupThemeSwitcher() {
        const themeToggle = document.getElementById('theme-toggle');
        if (themeToggle) {
            themeToggle.addEventListener('click', () => {
                this.toggleTheme();
            });
        }

        this.applyTheme(this.theme);
    }

    toggleTheme() {
        this.theme = this.theme === 'light' ? 'dark' : 'light';
        localStorage.setItem('theme', this.theme);
        this.applyTheme(this.theme);
    }

    applyTheme(theme) {
        document.body.className = theme;
        
        // Update theme-specific styles
        const root = document.documentElement;
        if (theme === 'dark') {
            root.style.setProperty('--bg-color', '#1a1a1a');
            root.style.setProperty('--text-color', '#ffffff');
            root.style.setProperty('--card-bg', '#2d2d2d');
        } else {
            root.style.setProperty('--bg-color', '#ffffff');
            root.style.setProperty('--text-color', '#333333');
            root.style.setProperty('--card-bg', '#ffffff');
        }
    }

    // Language switcher
    setupLanguageSwitcher() {
        const languageSelect = document.getElementById('language-select');
        if (languageSelect) {
            languageSelect.addEventListener('change', (e) => {
                this.changeLanguage(e.target.value);
            });
        }
    }

    changeLanguage(lang) {
        this.language = lang;
        localStorage.setItem('language', lang);
        
        // Update RTL/LTR
        document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr';
        document.documentElement.lang = lang;
        
        // Update text content (you would implement actual translation here)
        this.updateTextContent(lang);
    }

    updateTextContent(lang) {
        // This would typically involve loading translation files
        const elements = document.querySelectorAll('[data-translate]');
        elements.forEach(element => {
            const key = element.getAttribute('data-translate');
            element.textContent = this.getTranslation(key, lang);
        });
    }

    getTranslation(key, lang) {
        // Mock translation function
        const translations = {
            'ar': {
                'dashboard': 'لوحة التحكم',
                'patients': 'المرضى',
                'visits': 'الزيارات'
            },
            'en': {
                'dashboard': 'Dashboard',
                'patients': 'Patients',
                'visits': 'Visits'
            }
        };
        return translations[lang]?.[key] || key;
    }

    // Animations
    setupAnimations() {
        if (this.animations) {
            this.setupScrollAnimations();
            this.setupHoverEffects();
            this.setupLoadingAnimations();
        }
    }

    setupScrollAnimations() {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('animate-in');
                }
            });
        });

        document.querySelectorAll('.animate-on-scroll').forEach(el => {
            observer.observe(el);
        });
    }

    setupHoverEffects() {
        document.querySelectorAll('.hover-effect').forEach(el => {
            el.addEventListener('mouseenter', () => {
                el.classList.add('hovered');
            });
            
            el.addEventListener('mouseleave', () => {
                el.classList.remove('hovered');
            });
        });
    }

    setupLoadingAnimations() {
        const loadingElements = document.querySelectorAll('.loading');
        loadingElements.forEach(el => {
            el.classList.add('loading-animation');
        });
    }

    // Accessibility
    setupAccessibility() {
        this.setupKeyboardNavigation();
        this.setupScreenReaderSupport();
        this.setupHighContrast();
        this.setupFocusManagement();
    }

    setupKeyboardNavigation() {
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Tab') {
                document.body.classList.add('keyboard-navigation');
            }
        });

        document.addEventListener('mousedown', () => {
            document.body.classList.remove('keyboard-navigation');
        });
    }

    setupScreenReaderSupport() {
        // Add ARIA labels to interactive elements
        document.querySelectorAll('button, a, input').forEach(el => {
            if (!el.getAttribute('aria-label')) {
                el.setAttribute('aria-label', el.textContent || el.value);
            }
        });
    }

    setupHighContrast() {
        const highContrastToggle = document.getElementById('high-contrast-toggle');
        if (highContrastToggle) {
            highContrastToggle.addEventListener('click', () => {
                document.body.classList.toggle('high-contrast');
            });
        }
    }

    setupFocusManagement() {
        // Trap focus in modals
        document.querySelectorAll('.modal').forEach(modal => {
            modal.addEventListener('keydown', (e) => {
                if (e.key === 'Escape') {
                    modal.classList.remove('show');
                }
            });
        });
    }

    // Responsive design
    setupResponsiveDesign() {
        this.setupMobileOptimizations();
        // this.setupTabletOptimizations(); // معطل مؤقتاً
        // this.setupDesktopOptimizations(); // معطل مؤقتاً
    }

    setupMobileOptimizations() {
        if (window.innerWidth < 768) {
            document.body.classList.add('mobile');
            this.setupTouchGestures();
            this.setupMobileNavigation();
        }
    }

    setupTouchGestures() {
        let startY = 0;
        let startX = 0;

        document.addEventListener('touchstart', (e) => {
            startY = e.touches[0].clientY;
            startX = e.touches[0].clientX;
        });

        document.addEventListener('touchmove', (e) => {
            const currentY = e.touches[0].clientY;
            const currentX = e.touches[0].clientX;
            const diffY = startY - currentY;
            const diffX = startX - currentX;

            if (Math.abs(diffY) > Math.abs(diffX)) {
                if (diffY > 0) {
                    // Swipe up
                    this.handleSwipeUp();
                } else {
                    // Swipe down
                    this.handleSwipeDown();
                }
            }
        });
    }

    handleSwipeUp() {
        // Handle swipe up gesture
        console.log('Swipe up detected');
    }

    handleSwipeDown() {
        // Handle swipe down gesture
        console.log('Swipe down detected');
    }

    setupMobileNavigation() {
        const mobileMenu = document.getElementById('mobile-menu');
        const menuToggle = document.getElementById('menu-toggle');
        
        if (menuToggle && mobileMenu) {
            menuToggle.addEventListener('click', () => {
                mobileMenu.classList.toggle('active');
            });
        }
    }

    // Smart notifications
    setupSmartNotifications() {
        this.setupPushNotifications();
        this.setupToastNotifications();
        this.setupBannerNotifications();
    }

    setupPushNotifications() {
        if ('Notification' in window) {
            Notification.requestPermission().then(permission => {
                if (permission === 'granted') {
                    this.showNotification('تم تفعيل الإشعارات', 'body');
                }
            });
        }
    }

    showNotification(title, body) {
        if (Notification.permission === 'granted') {
            new Notification(title, { body });
        }
    }

    setupToastNotifications() {
        this.showToast = (message, type = 'info') => {
            const toast = document.createElement('div');
            toast.className = `toast toast-${type}`;
            toast.textContent = message;
            
            document.body.appendChild(toast);
            
            setTimeout(() => {
                toast.classList.add('show');
            }, 100);
            
            setTimeout(() => {
                toast.classList.remove('show');
                setTimeout(() => {
                    document.body.removeChild(toast);
                }, 300);
            }, 3000);
        };
    }

    setupBannerNotifications() {
        // System-wide banner notifications
        this.showBanner = (message, type = 'info') => {
            const banner = document.createElement('div');
            banner.className = `banner banner-${type}`;
            banner.innerHTML = `
                <span>${message}</span>
                <button class="banner-close">&times;</button>
            `;
            
            document.body.appendChild(banner);
            
            banner.querySelector('.banner-close').addEventListener('click', () => {
                banner.remove();
            });
        };
    }

    // Keyboard shortcuts
    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey || e.metaKey) {
                switch (e.key) {
                    case 's':
                        e.preventDefault();
                        this.saveCurrentForm();
                        break;
                    case 'n':
                        e.preventDefault();
                        this.createNew();
                        break;
                    case 'f':
                        e.preventDefault();
                        this.focusSearch();
                        break;
                }
            }
        });
    }

    saveCurrentForm() {
        const form = document.querySelector('form');
        if (form) {
            form.dispatchEvent(new Event('submit'));
        }
    }

    createNew() {
        const newButton = document.querySelector('[data-action="create"]');
        if (newButton) {
            newButton.click();
        }
    }

    focusSearch() {
        const searchInput = document.querySelector('input[type="search"]');
        if (searchInput) {
            searchInput.focus();
        }
    }

    // Drag and drop
    setupDragAndDrop() {
        document.querySelectorAll('.drag-drop-zone').forEach(zone => {
            zone.addEventListener('dragover', (e) => {
                e.preventDefault();
                zone.classList.add('drag-over');
            });
            
            zone.addEventListener('dragleave', () => {
                zone.classList.remove('drag-over');
            });
            
            zone.addEventListener('drop', (e) => {
                e.preventDefault();
                zone.classList.remove('drag-over');
                this.handleFileDrop(e.dataTransfer.files);
            });
        });
    }

    handleFileDrop(files) {
        Array.from(files).forEach(file => {
            if (file.type.startsWith('image/')) {
                this.handleImageUpload(file);
            } else if (file.type === 'application/pdf') {
                this.handlePDFUpload(file);
            }
        });
    }

    handleImageUpload(file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            const img = document.createElement('img');
            img.src = e.target.result;
            img.className = 'uploaded-image';
            document.querySelector('.image-preview').appendChild(img);
        };
        reader.readAsDataURL(file);
    }

    handlePDFUpload(file) {
        console.log('PDF uploaded:', file.name);
    }

    // Auto-save functionality
    setupAutoSave() {
        document.querySelectorAll('form[data-autosave]').forEach(form => {
            const inputs = form.querySelectorAll('input, textarea, select');
            inputs.forEach(input => {
                input.addEventListener('input', this.debounce(() => {
                    this.autoSave(form);
                }, 2000));
            });
        });
    }

    autoSave(form) {
        const formData = new FormData(form);
        const data = Object.fromEntries(formData);
        
        localStorage.setItem(`autosave_${form.id}`, JSON.stringify({
            data: data,
            timestamp: Date.now()
        }));
        
        this.showToast('تم الحفظ التلقائي', 'success');
    }

    debounce(func, wait) {
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
}

// Initialize UI enhancements
const uiEnhancements = new UIEnhancements();

// Export for use in other modules
window.UIEnhancements = UIEnhancements;
window.uiEnhancements = uiEnhancements;
