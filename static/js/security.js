/**
 * Security Enhancement JavaScript
 * Medical System - Advanced Security Scripts
 */

class SecurityManager {
    constructor() {
        this.csrfToken = null;
        this.sessionTimeout = 30 * 60 * 1000;
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
        ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart'].forEach(event => {
            document.addEventListener(event, () => {
                this.lastActivity = Date.now();
            }, true);
        });

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
            window.location.href = (window.API_ROUTES && window.API_ROUTES.auth_login) || '/auth/login';
        }, 3000);
    }

    setupInputSanitization() {
        document.addEventListener('blur', (e) => {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                this.sanitizeInput(e.target);
            }
        }, true);
    }

    sanitizeInput(input) {
        let value = input.value;
        value = value.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '');
        value = value.replace(/javascript:/gi, '');
        value = value.replace(/data:(?!image\/(png|jpg|jpeg|gif|svg))/gi, '');
        value = value.replace(/\bon\w+\s*=/gi, '');
        input.value = value;
    }

    setupXSSProtection() {
        if (typeof DOMPurify !== 'undefined') return;
        console.warn('DOMPurify not loaded - XSS innerHTML protection is limited. Server-side sanitization + CSP headers required.');
    }

    setupCSRFProtection() {
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
        if (window.top !== window.self) {
            window.top.location = window.self.location;
        }
    }

    setupContentSecurityPolicy() {
        if (!document.querySelector('meta[http-equiv="Content-Security-Policy"]')) {
            const csp = document.createElement('meta');
            csp.httpEquiv = 'Content-Security-Policy';
            csp.content = "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; font-src 'self'; img-src 'self' data: https:; connect-src 'self'; frame-src 'none';";
            document.head.appendChild(csp);
        }
    }

    checkPasswordStrength(password) {
        const strength = {
            score: 0,
            feedback: []
        };

        if (password.length >= 8) {
            strength.score += 1;
        } else {
            strength.feedback.push('يجب أن تكون كلمة المرور 8 أحرف على الأقل');
        }
        if (/[A-Z]/.test(password)) {
            strength.score += 1;
        } else {
            strength.feedback.push('يجب أن تحتوي على حرف كبير واحد على الأقل');
        }
        if (/[a-z]/.test(password)) {
            strength.score += 1;
        } else {
            strength.feedback.push('يجب أن تحتوي على حرف صغير واحد على الأقل');
        }
        if (/\d/.test(password)) {
            strength.score += 1;
        } else {
            strength.feedback.push('يجب أن تحتوي على رقم واحد على الأقل');
        }
        if (/[!@#$%^&*(),.?":{}|<>]/.test(password)) {
            strength.score += 1;
        } else {
            strength.feedback.push('يجب أن تحتوي على رمز خاص واحد على الأقل');
        }

        return strength;
    }

    setupRateLimiting() {
        const rateLimits = new Map();
        const maxRequests = 100;
        const windowMs = 60000;
        const currentFetch = window.fetch.bind(window);

        window.fetch = (url, options = {}) => {
            const now = Date.now();
            const key = `${url}_${options.method || 'GET'}`;

            if (!rateLimits.has(key)) {
                rateLimits.set(key, []);
            }

            const requests = rateLimits.get(key);

            while (requests.length > 0 && requests[0] < now - windowMs) {
                requests.shift();
            }

            if (requests.length >= maxRequests) {
                throw new Error('Rate limit exceeded. Please try again later.');
            }

            requests.push(now);

            return currentFetch(url, options);
        };
    }
}

class InputValidator {
    constructor() {
        this.patterns = {
            email: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
            phone: /^[\+]?[1-9][\d]{0,15}$/,
            arabicName: /^[\u0600-\u06FF\s]+$/,
            englishName: /^[a-zA-Z\s]+$/,
            idNumber: /^[0-9]{1,20}$/,
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
        this.maxSize = 10 * 1024 * 1024;
    }

    validateFile(file) {
        const errors = [];
        if (!this.allowedTypes.includes(file.type)) {
            errors.push('نوع الملف غير مسموح');
        }
        if (file.size > this.maxSize) {
            errors.push('حجم الملف كبير جداً');
        }
        if (!/^[a-zA-Z0-9\u0600-\u06FF\s\-_\.]+$/.test(file.name)) {
            errors.push('اسم الملف يحتوي على أحرف غير مسموحة');
        }
        return { isValid: errors.length === 0, errors };
    }

    scanFile(file) {
        return new Promise((resolve) => {
            const reader = new FileReader();
            reader.onload = (e) => {
                const content = e.target.result;
                const maliciousPatterns = [
                    /<script/i,
                    /javascript:/i,
                    /vbscript:/i,
                    /onload=/i,
                    /onerror=/i
                ];
                const isMalicious = maliciousPatterns.some(pattern => pattern.test(content));
                resolve({ isSafe: !isMalicious, content });
            };
            reader.readAsText(file);
        });
    }
}

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
        } catch (error) {}
    }

    saveSessionData() {
        try {
            const data = JSON.stringify(Array.from(this.sessionData.entries()));
            sessionStorage.setItem('medical_session', data);
        } catch (error) {}
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
        if (this.logs.length > this.maxLogs) {
            this.logs.shift();
        }
        this.sendLog(logEntry);
    }

    getCurrentUserId() {
        return sessionStorage.getItem('user_id') || 'anonymous';
    }

    sendLog(logEntry) {
        const headers = { 'Content-Type': 'application/json' };
        if (this.csrfToken) {
            headers['X-CSRFToken'] = this.csrfToken;
        }
        const auditLogUrl = (window.API_ROUTES && window.API_ROUTES.audit_log) || '/super-admin/api/audit-log';
        fetch(auditLogUrl, {
            method: 'POST',
            headers,
            body: JSON.stringify(logEntry)
        }).catch(() => {});
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const securityManager = new SecurityManager();
    const inputValidator = new InputValidator();
    const secureFileUpload = new SecureFileUpload();
    const sessionManager = new SessionManager();
    const auditLogger = new AuditLogger();

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

    document.addEventListener('submit', (e) => {
        if (e.target.tagName === 'FORM') {
            const formData = new FormData(e.target);
            const data = Object.fromEntries(formData.entries());
            auditLogger.log('form_submission', {
                formId: e.target.id,
                formAction: e.target.action,
                fields: Object.keys(data)
            });
        }
    });

    document.addEventListener('blur', (e) => {
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
            const field = e.target;
            const value = field.value.trim();
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

    window.securityManager = securityManager;
    window.inputValidator = inputValidator;
    window.secureFileUpload = secureFileUpload;
    window.sessionManager = sessionManager;
    window.auditLogger = auditLogger;
});

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        SecurityManager,
        InputValidator,
        SecureFileUpload,
        SessionManager,
        AuditLogger
    };
}
