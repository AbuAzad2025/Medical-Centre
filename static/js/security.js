/**
 * Security Enhancement JavaScript
 * Medical System - Advanced Security Scripts
 */

// Security utilities
class SecurityManager {
    constructor() {
        this.csrfToken = null;
        this.sessionTimeout = 30 * 60 * 1000; // 30 minutes
        this.lastActivity = Date.now();
        this.init();
    }

    init() {
        this.getCSRFToken();
        this.setupSessionTimeout();
        this.setupInputSanitization();
        this.setupXSSProtection();
        this.setupCSRFProtection();
        this.setupClickjackingProtection();
        this.setupContentSecurityPolicy();
    }

    getCSRFToken() {
        const tokenElement = document.querySelector('meta[name="csrf-token"]');
        if (tokenElement) {
            this.csrfToken = tokenElement.getAttribute('content');
        }
    }

    setupSessionTimeout() {
        // Reset timeout on user activity
        ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart'].forEach(event => {
            document.addEventListener(event, () => {
                this.lastActivity = Date.now();
            }, true);
        });

        // Check for timeout every minute
        setInterval(() => {
            if (Date.now() - this.lastActivity > this.sessionTimeout) {
                this.handleSessionTimeout();
            }
        }, 60000);
    }

    handleSessionTimeout() {
        if (window.notifications) {
            window.notifications.show('انتهت جلسة العمل. يرجى تسجيل الدخول مرة أخرى.', 'warning');
        }
        
        setTimeout(() => {
            window.location.href = '/auth/login';
        }, 3000);
    }

    setupInputSanitization() {
        // Sanitize all text inputs
        document.addEventListener('input', (e) => {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                this.sanitizeInput(e.target);
            }
        });
    }

    sanitizeInput(input) {
        // Remove potentially dangerous characters
        let value = input.value;
        
        // Remove script tags
        value = value.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '');
        
        // Remove javascript: protocols
        value = value.replace(/javascript:/gi, '');
        
        // Remove data: protocols (except safe image types)
        value = value.replace(/data:(?!image\/(png|jpg|jpeg|gif|svg))/gi, '');
        
        // Remove on* event handlers
        value = value.replace(/\bon\w+\s*=/gi, '');
        
        input.value = value;
    }

    setupXSSProtection() {
        const desc = Object.getOwnPropertyDescriptor(Element.prototype, 'innerHTML');
        const originalSetter = desc && desc.set;
        if (!originalSetter) return;
        Object.defineProperty(Element.prototype, 'innerHTML', {
            set: function(html) {
                try {
                    if (this.tagName === 'SCRIPT' || this.tagName === 'STYLE') {
                        originalSetter.call(this, html);
                        return;
                    }
                    if (typeof html === 'string') {
                        const cleaned = html
                            .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
                            .replace(/\bon\w+\s*=/gi, '');
                        originalSetter.call(this, cleaned);
                    } else {
                        originalSetter.call(this, html);
                    }
                } catch (_) {
                    originalSetter.call(this, html);
                }
            }
        });
    }

    setupCSRFProtection() {
        // Add CSRF token to all forms
        document.addEventListener('submit', (e) => {
            if (e.target.tagName === 'FORM' && this.csrfToken) {
                const existingToken = e.target.querySelector('input[name="csrf_token"]');
                if (!existingToken) {
                    const tokenInput = document.createElement('input');
                    tokenInput.type = 'hidden';
                    tokenInput.name = 'csrf_token';
                    tokenInput.value = this.csrfToken;
                    e.target.appendChild(tokenInput);
                }
            }
        });
    }

    setupClickjackingProtection() {
        // Prevent clickjacking
        if (window.top !== window.self) {
            window.top.location = window.self.location;
        }
    }

    setupContentSecurityPolicy() {
        // Note: frame-ancestors directive is ignored in meta tags and should be set via HTTP headers
        // CSP is better configured at the server level (Flask app) for full security
        // This is just a client-side fallback for basic protection
        if (!document.querySelector('meta[http-equiv="Content-Security-Policy"]')) {
            const csp = document.createElement('meta');
            csp.httpEquiv = 'Content-Security-Policy';
            // Note: frame-ancestors removed as it's not supported in meta tags
            csp.content = "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://unpkg.com; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com https://unpkg.com; font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; img-src 'self' data: https:; connect-src 'self' https://cdn.jsdelivr.net; frame-src 'none';";
            document.head.appendChild(csp);
        }
    }

    // Password strength checker
    checkPasswordStrength(password) {
        const strength = {
            score: 0,
            feedback: []
        };

        // Length check
        if (password.length >= 8) {
            strength.score += 1;
        } else {
            strength.feedback.push('يجب أن تكون كلمة المرور 8 أحرف على الأقل');
        }

        // Uppercase check
        if (/[A-Z]/.test(password)) {
            strength.score += 1;
        } else {
            strength.feedback.push('يجب أن تحتوي على حرف كبير واحد على الأقل');
        }

        // Lowercase check
        if (/[a-z]/.test(password)) {
            strength.score += 1;
        } else {
            strength.feedback.push('يجب أن تحتوي على حرف صغير واحد على الأقل');
        }

        // Number check
        if (/\d/.test(password)) {
            strength.score += 1;
        } else {
            strength.feedback.push('يجب أن تحتوي على رقم واحد على الأقل');
        }

        // Special character check
        if (/[!@#$%^&*(),.?":{}|<>]/.test(password)) {
            strength.score += 1;
        } else {
            strength.feedback.push('يجب أن تحتوي على رمز خاص واحد على الأقل');
        }

        return strength;
    }

    // Rate limiting for API calls
    setupRateLimiting() {
        const rateLimits = new Map();
        const maxRequests = 100; // per minute
        const windowMs = 60000; // 1 minute

        const originalFetch = window.fetch;
        window.fetch = (url, options = {}) => {
            const now = Date.now();
            const key = `${url}_${options.method || 'GET'}`;
            
            if (!rateLimits.has(key)) {
                rateLimits.set(key, []);
            }
            
            const requests = rateLimits.get(key);
            
            // Remove old requests
            while (requests.length > 0 && requests[0] < now - windowMs) {
                requests.shift();
            }
            
            if (requests.length >= maxRequests) {
                throw new Error('Rate limit exceeded. Please try again later.');
            }
            
            requests.push(now);
            
            return originalFetch(url, options);
        };
    }
}

// Input validation
class InputValidator {
    constructor() {
        this.patterns = {
            email: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
            phone: /^[\+]?[1-9][\d]{0,15}$/,
            arabicName: /^[\u0600-\u06FF\s]+$/,
            englishName: /^[a-zA-Z\s]+$/,
            idNumber: /^[0-9]{9}$/,
            date: /^\d{4}-\d{2}-\d{2}$/,
            time: /^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$/
        };
    }

    validateEmail(email) {
        return this.patterns.email.test(email);
    }

    validatePhone(phone) {
        return this.patterns.phone.test(phone);
    }

    validateArabicName(name) {
        return this.patterns.arabicName.test(name);
    }

    validateEnglishName(name) {
        return this.patterns.englishName.test(name);
    }

    validateIdNumber(id) {
        return this.patterns.idNumber.test(id);
    }

    validateDate(date) {
        return this.patterns.date.test(date) && !isNaN(Date.parse(date));
    }

    validateTime(time) {
        return this.patterns.time.test(time);
    }

    sanitizeString(str) {
        return str.replace(/[<>\"'&]/g, (match) => {
            const escape = {
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#x27;',
                '&': '&amp;'
            };
            return escape[match];
        });
    }
}

// File upload security
class SecureFileUpload {
    constructor() {
        this.allowedTypes = [
            'image/jpeg',
            'image/png',
            'image/gif',
            'image/svg+xml',
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        ];
        this.maxSize = 10 * 1024 * 1024; // 10MB
    }

    validateFile(file) {
        const errors = [];

        // Check file type
        if (!this.allowedTypes.includes(file.type)) {
            errors.push('نوع الملف غير مسموح');
        }

        // Check file size
        if (file.size > this.maxSize) {
            errors.push('حجم الملف كبير جداً');
        }

        // Check file name
        if (!/^[a-zA-Z0-9\u0600-\u06FF\s\-_\.]+$/.test(file.name)) {
            errors.push('اسم الملف يحتوي على أحرف غير مسموحة');
        }

        return {
            isValid: errors.length === 0,
            errors
        };
    }

    scanFile(file) {
        return new Promise((resolve) => {
            const reader = new FileReader();
            reader.onload = (e) => {
                const content = e.target.result;
                
                // Check for malicious content
                const maliciousPatterns = [
                    /<script/i,
                    /javascript:/i,
                    /vbscript:/i,
                    /onload=/i,
                    /onerror=/i
                ];

                const isMalicious = maliciousPatterns.some(pattern => 
                    pattern.test(content)
                );

                resolve({
                    isSafe: !isMalicious,
                    content
                });
            };
            reader.readAsText(file);
        });
    }
}

// Session management
class SessionManager {
    constructor() {
        this.sessionData = new Map();
        this.init();
    }

    init() {
        this.loadSessionData();
        this.setupStorageListener();
    }

    loadSessionData() {
        try {
            const data = sessionStorage.getItem('medical_session');
            if (data) {
                this.sessionData = new Map(JSON.parse(data));
            }
        } catch (error) {
            console.error('Error loading session data:', error);
        }
    }

    saveSessionData() {
        try {
            const data = JSON.stringify(Array.from(this.sessionData.entries()));
            sessionStorage.setItem('medical_session', data);
        } catch (error) {
            console.error('Error saving session data:', error);
        }
    }

    set(key, value) {
        this.sessionData.set(key, value);
        this.saveSessionData();
    }

    get(key) {
        return this.sessionData.get(key);
    }

    remove(key) {
        this.sessionData.delete(key);
        this.saveSessionData();
    }

    clear() {
        this.sessionData.clear();
        sessionStorage.removeItem('medical_session');
    }

    setupStorageListener() {
        window.addEventListener('storage', (e) => {
            if (e.key === 'medical_session') {
                this.loadSessionData();
            }
        });
    }
}

// Audit logging
class AuditLogger {
    constructor() {
        this.logs = [];
        this.maxLogs = 1000;
    }

    log(action, details = {}) {
        const logEntry = {
            timestamp: new Date().toISOString(),
            action,
            details,
            userAgent: navigator.userAgent,
            url: window.location.href,
            userId: this.getCurrentUserId()
        };

        this.logs.push(logEntry);

        // Keep only recent logs
        if (this.logs.length > this.maxLogs) {
            this.logs.shift();
        }

        // Send to server
        this.sendLog(logEntry);
    }

    getCurrentUserId() {
        // Get user ID from session or token
        return sessionStorage.getItem('user_id') || 'anonymous';
    }

    sendLog(logEntry) {
        const headers = {
            'Content-Type': 'application/json',
        };
        if (this.csrfToken) {
            headers['X-CSRFToken'] = this.csrfToken;
        }
        fetch('/super-admin/api/audit-log', {
            method: 'POST',
            headers,
            body: JSON.stringify(logEntry)
        }).catch(error => {
            console.error('Failed to send audit log:', error);
        });
    }
}

// Initialize security features
document.addEventListener('DOMContentLoaded', () => {
    // Initialize security manager
    const securityManager = new SecurityManager();
    
    // Initialize input validator
    const inputValidator = new InputValidator();
    
    // Initialize secure file upload
    const secureFileUpload = new SecureFileUpload();
    
    // Initialize session manager
    const sessionManager = new SessionManager();
    
    // Initialize audit logger
    const auditLogger = new AuditLogger();
    
    // Setup file upload validation
    document.addEventListener('change', (e) => {
        if (e.target.type === 'file') {
            const files = Array.from(e.target.files);
            files.forEach(file => {
                const validation = secureFileUpload.validateFile(file);
                if (!validation.isValid) {
                    if (window.notifications) {
                        window.notifications.show(validation.errors.join(', '), 'error');
                    }
                    e.target.value = '';
                }
            });
        }
    });
    
    // Setup form validation
    document.addEventListener('submit', (e) => {
        if (e.target.tagName === 'FORM') {
            const formData = new FormData(e.target);
            const data = Object.fromEntries(formData.entries());
            
            // Log form submission
            auditLogger.log('form_submission', {
                formId: e.target.id,
                formAction: e.target.action,
                fields: Object.keys(data)
            });
        }
    });
    
    // Setup input validation
    document.addEventListener('blur', (e) => {
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
            const field = e.target;
            const value = field.value.trim();
            
            // Validate based on field type
            if (field.type === 'email' && value) {
                if (!inputValidator.validateEmail(value)) {
                    field.classList.add('is-invalid');
                } else {
                    field.classList.remove('is-invalid');
                    field.classList.add('is-valid');
                }
            }
            
            if (field.type === 'tel' && value) {
                if (!inputValidator.validatePhone(value)) {
                    field.classList.add('is-invalid');
                } else {
                    field.classList.remove('is-invalid');
                    field.classList.add('is-valid');
                }
            }
        }
    }, true);
    
    // Make utilities globally available
    window.securityManager = securityManager;
    window.inputValidator = inputValidator;
    window.secureFileUpload = secureFileUpload;
    window.sessionManager = sessionManager;
    window.auditLogger = auditLogger;
});

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        SecurityManager,
        InputValidator,
        SecureFileUpload,
        SessionManager,
        AuditLogger
    };
}
