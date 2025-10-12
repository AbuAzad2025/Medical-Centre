// CSRF Token Management
document.addEventListener('DOMContentLoaded', function() {
    // Get CSRF token from meta tag
    const csrfToken = document.querySelector('meta[name="csrf-token"]');
    if (csrfToken) {
        window.csrfToken = csrfToken.getAttribute('content');
    }
    
    // Add CSRF token to all forms
    const forms = document.querySelectorAll('form');
    forms.forEach(function(form) {
        if (!form.querySelector('input[name="csrf_token"]')) {
            const csrfInput = document.createElement('input');
            csrfInput.type = 'hidden';
            csrfInput.name = 'csrf_token';
            csrfInput.value = window.csrfToken;
            form.appendChild(csrfInput);
        }
    });
    
    // Add CSRF token to all AJAX requests
    const originalFetch = window.fetch;
    window.fetch = function(url, options = {}) {
        if (options.method && options.method !== 'GET') {
            options.headers = options.headers || {};
            options.headers['X-CSRFToken'] = window.csrfToken;
        }
        return originalFetch(url, options);
    };
});