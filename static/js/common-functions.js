// الوظائف المشتركة - ملف JavaScript
// Common Functions - JavaScript File

// تهيئة الوظائف المشتركة
document.addEventListener('DOMContentLoaded', function() {
    initializeCommonFunctions();
});

// تهيئة الوظائف المشتركة
function initializeCommonFunctions() {
    setupCommonValidation();
    setupCommonUI();
    setupCommonEvents();
    setupCommonUtilities();
}

// إعداد التحقق المشترك
function setupCommonValidation() {
    // إعداد التحقق من النماذج
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!validateCommonForm(this)) {
                e.preventDefault();
            }
        });
    });
}

// التحقق من النماذج المشتركة
function validateCommonForm(form) {
    let isValid = true;
    
    // التحقق من الحقول المطلوبة
    const requiredFields = form.querySelectorAll('[required]');
    requiredFields.forEach(field => {
        if (!field.value.trim()) {
            showFieldError(field, 'هذا الحقل مطلوب');
            isValid = false;
        } else {
            clearFieldError(field);
        }
    });
    
    // التحقق من صحة البريد الإلكتروني
    const emailFields = form.querySelectorAll('input[type="email"]');
    emailFields.forEach(field => {
        if (field.value && !validateEmail(field.value)) {
            showFieldError(field, 'البريد الإلكتروني غير صحيح');
            isValid = false;
        }
    });
    
    // التحقق من صحة رقم الهاتف
    const phoneFields = form.querySelectorAll('input[name*="phone"]');
    phoneFields.forEach(field => {
        if (field.value && !validatePhone(field.value)) {
            showFieldError(field, 'رقم الهاتف غير صحيح');
            isValid = false;
        }
    });
    
    // التحقق من صحة التواريخ
    const dateFields = form.querySelectorAll('input[type="date"]');
    dateFields.forEach(field => {
        if (field.value && !isValidDate(field.value)) {
            showFieldError(field, 'التاريخ غير صحيح');
            isValid = false;
        }
    });
    
    // التحقق من صحة الوقت
    const timeFields = form.querySelectorAll('input[type="time"]');
    timeFields.forEach(field => {
        if (field.value && !isValidTime(field.value)) {
            showFieldError(field, 'الوقت غير صحيح');
            isValid = false;
        }
    });
    
    return isValid;
}

// إعداد واجهة المستخدم المشتركة
function setupCommonUI() {
    // إعداد الأزرار
    setupButtons();
    
    // إعداد النوافذ المنبثقة
    setupModals();
    
    // إعداد التنبيهات
    setupAlerts();
    
    // إعداد الجداول
    setupTables();
    
    // إعداد النماذج
    setupForms();
}

// إعداد الأزرار
function setupButtons() {
    // إعداد أزرار التحميل
    const loadingButtons = document.querySelectorAll('.btn-loading');
    loadingButtons.forEach(button => {
        button.addEventListener('click', function() {
            showButtonLoading(this);
        });
    });
    
    // إعداد أزرار التأكيد
    const confirmButtons = document.querySelectorAll('.btn-confirm');
    confirmButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            if (!confirm(this.dataset.message || 'هل أنت متأكد؟')) {
                e.preventDefault();
            }
        });
    });
}

// إظهار تحميل الزر
function showButtonLoading(button) {
    const originalText = button.textContent;
    button.textContent = 'جاري التحميل...';
    button.disabled = true;
    
    setTimeout(() => {
        button.textContent = originalText;
        button.disabled = false;
    }, 2000);
}

// إعداد النوافذ المنبثقة
function setupModals() {
    const modals = document.querySelectorAll('.modal');
    modals.forEach(modal => {
        // إعداد أزرار الإغلاق
        const closeButtons = modal.querySelectorAll('.modal-close, .btn-close');
        closeButtons.forEach(button => {
            button.addEventListener('click', function() {
                closeModal(modal);
            });
        });
        
        // إعداد النقر خارج النافذة
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                closeModal(modal);
            }
        });
    });
}

// فتح نافذة منبثقة
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'block';
        modal.classList.add('show');
        document.body.classList.add('modal-open');
    }
}

// إغلاق نافذة منبثقة
function closeModal(modal) {
    modal.style.display = 'none';
    modal.classList.remove('show');
    document.body.classList.remove('modal-open');
}

// إعداد التنبيهات
function setupAlerts() {
    // إعداد التنبيهات القابلة للإغلاق
    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(alert => {
        const closeButton = alert.querySelector('.btn-close');
        if (closeButton) {
            closeButton.addEventListener('click', function() {
                alert.remove();
            });
        }
    });
    
    // إعداد التنبيهات التلقائية
    const autoAlerts = document.querySelectorAll('.alert-auto');
    autoAlerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            setTimeout(() => {
                alert.remove();
            }, 300);
        }, 5000);
    });
}

// إظهار تنبيه
function showAlert(message, type = 'info', duration = 5000) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    const container = document.querySelector('.main-content') || document.body;
    container.insertBefore(alertDiv, container.firstChild);
    
    // إخفاء التنبيه تلقائياً
    if (duration > 0) {
        setTimeout(() => {
            alertDiv.remove();
        }, duration);
    }
}

// إعداد الجداول
function setupTables() {
    const tables = document.querySelectorAll('.table');
    tables.forEach(table => {
        // إضافة ترقيم للصفوف
        addRowNumbers(table);
        
        // إضافة ميزات البحث
        addTableSearch(table);
        
        // إضافة ميزات الفرز
        addTableSorting(table);
    });
}

// إضافة ترقيم للصفوف
function addRowNumbers(table) {
    const rows = table.querySelectorAll('tbody tr');
    rows.forEach((row, index) => {
        const cell = document.createElement('td');
        cell.textContent = index + 1;
        cell.className = 'text-center';
        row.insertBefore(cell, row.firstChild);
    });
}

// إضافة ميزات البحث
function addTableSearch(table) {
    const searchInput = table.querySelector('.table-search');
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            const query = this.value.toLowerCase();
            const rows = table.querySelectorAll('tbody tr');
            
            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                if (text.includes(query)) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        });
    }
}

// إضافة ميزات الفرز
function addTableSorting(table) {
    const headers = table.querySelectorAll('th[data-sort]');
    headers.forEach(header => {
        header.style.cursor = 'pointer';
        header.addEventListener('click', function() {
            sortTable(table, this.dataset.sort);
        });
    });
}

// فرز الجدول
function sortTable(table, column) {
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    
    rows.sort((a, b) => {
        const aValue = a.querySelector(`td[data-column="${column}"]`)?.textContent || '';
        const bValue = b.querySelector(`td[data-column="${column}"]`)?.textContent || '';
        
        return aValue.localeCompare(bValue, 'ar');
    });
    
    rows.forEach(row => tbody.appendChild(row));
}

// إعداد النماذج
function setupForms() {
    // إعداد النماذج الديناميكية
    const dynamicForms = document.querySelectorAll('.dynamic-form');
    dynamicForms.forEach(form => {
        setupDynamicForm(form);
    });
    
    // إعداد النماذج المتقدمة
    const advancedForms = document.querySelectorAll('.advanced-form');
    advancedForms.forEach(form => {
        setupAdvancedForm(form);
    });
}

// إعداد النماذج الديناميكية
function setupDynamicForm(form) {
    const addButton = form.querySelector('.add-field');
    const removeButton = form.querySelector('.remove-field');
    const fieldContainer = form.querySelector('.field-container');
    
    if (addButton && fieldContainer) {
        addButton.addEventListener('click', function() {
            addDynamicField(fieldContainer);
        });
    }
    
    if (removeButton && fieldContainer) {
        removeButton.addEventListener('click', function() {
            removeDynamicField(fieldContainer);
        });
    }
}

// إضافة حقل ديناميكي
function addDynamicField(container) {
    const fieldTemplate = container.querySelector('.field-template');
    if (fieldTemplate) {
        const newField = fieldTemplate.cloneNode(true);
        newField.classList.remove('field-template');
        newField.style.display = 'block';
        container.appendChild(newField);
    }
}

// إزالة حقل ديناميكي
function removeDynamicField(container) {
    const fields = container.querySelectorAll('.dynamic-field');
    if (fields.length > 1) {
        fields[fields.length - 1].remove();
    }
}

// إعداد النماذج المتقدمة
function setupAdvancedForm(form) {
    // إعداد التحقق المتقدم
    const fields = form.querySelectorAll('input, select, textarea');
    fields.forEach(field => {
        field.addEventListener('blur', function() {
            validateField(this);
        });
    });
}

// التحقق من الحقل
function validateField(field) {
    const value = field.value.trim();
    const type = field.type;
    const name = field.name;
    
    // التحقق من الحقول المطلوبة
    if (field.required && !value) {
        showFieldError(field, 'هذا الحقل مطلوب');
        return false;
    }
    
    // التحقق من صحة البريد الإلكتروني
    if (type === 'email' && value && !validateEmail(value)) {
        showFieldError(field, 'البريد الإلكتروني غير صحيح');
        return false;
    }
    
    // التحقق من صحة رقم الهاتف
    if (name.includes('phone') && value && !validatePhone(value)) {
        showFieldError(field, 'رقم الهاتف غير صحيح');
        return false;
    }
    
    // التحقق من صحة التاريخ
    if (type === 'date' && value && !isValidDate(value)) {
        showFieldError(field, 'التاريخ غير صحيح');
        return false;
    }
    
    // التحقق من صحة الوقت
    if (type === 'time' && value && !isValidTime(value)) {
        showFieldError(field, 'الوقت غير صحيح');
        return false;
    }
    
    clearFieldError(field);
    return true;
}

// إعداد الأحداث المشتركة
function setupCommonEvents() {
    // إعداد الأحداث العامة
    setupGlobalEvents();
    
    // إعداد الأحداث الخاصة
    setupSpecificEvents();
}

// إعداد الأحداث العامة
function setupGlobalEvents() {
    // إعداد الأحداث العامة
    document.addEventListener('click', function(e) {
        // إعداد النقر على الأزرار
        if (e.target.matches('.btn')) {
            handleButtonClick(e.target);
        }
        
        // إعداد النقر على الروابط
        if (e.target.matches('a')) {
            handleLinkClick(e.target);
        }
    });
}

// معالجة النقر على الأزرار
function handleButtonClick(button) {
    const action = button.dataset.action;
    if (action) {
        switch (action) {
            case 'refresh':
                location.reload();
                break;
            case 'back':
                history.back();
                break;
            case 'print':
                window.print();
                break;
            case 'export':
                exportData(button.dataset.format, button.dataset.data);
                break;
            default:
                console.log('إجراء غير معروف:', action);
        }
    }
}

// معالجة النقر على الروابط
function handleLinkClick(link) {
    const target = link.dataset.target;
    if (target) {
        switch (target) {
            case '_blank':
                window.open(link.href, '_blank');
                break;
            case '_self':
                window.location.href = link.href;
                break;
            default:
                console.log('هدف غير معروف:', target);
        }
    }
}

// إعداد الأحداث الخاصة
function setupSpecificEvents() {
    // إعداد الأحداث الخاصة
    setupKeyboardEvents();
    setupMouseEvents();
    setupTouchEvents();
}

// إعداد أحداث لوحة المفاتيح
function setupKeyboardEvents() {
    document.addEventListener('keydown', function(e) {
        // إعداد الاختصارات
        if (e.ctrlKey) {
            switch (e.key) {
                case 's':
                    e.preventDefault();
                    saveForm();
                    break;
                case 'r':
                    e.preventDefault();
                    refreshPage();
                    break;
                case 'p':
                    e.preventDefault();
                    printPage();
                    break;
                default:
                    console.log('اختصار غير معروف:', e.key);
            }
        }
    });
}

// إعداد أحداث الماوس
function setupMouseEvents() {
    // إعداد أحداث الماوس
    document.addEventListener('mousemove', function(e) {
        // إعداد تتبع الماوس
        trackMouse(e);
    });
}

// تتبع الماوس
function trackMouse(e) {
    // إعداد تتبع الماوس
    const mouseX = e.clientX;
    const mouseY = e.clientY;
    
    // إعداد تتبع الماوس
    console.log('موضع الماوس:', mouseX, mouseY);
}

// إعداد أحداث اللمس
function setupTouchEvents() {
    // إعداد أحداث اللمس
    document.addEventListener('touchstart', function(e) {
        // إعداد أحداث اللمس
        handleTouchStart(e);
    });
}

// معالجة بداية اللمس
function handleTouchStart(e) {
    // معالجة بداية اللمس
    console.log('بداية اللمس');
}

// إعداد المرافق المشتركة
function setupCommonUtilities() {
    // إعداد المرافق المشتركة
    setupDateUtilities();
    setupStringUtilities();
    setupNumberUtilities();
    setupArrayUtilities();
}

// إعداد مرافق التاريخ
function setupDateUtilities() {
    // إعداد مرافق التاريخ
    window.formatDate = formatDate;
    window.formatTime = formatTime;
    window.formatDateTime = formatDateTime;
}

// تنسيق التاريخ
function formatDate(date) {
    return new Date(date).toLocaleDateString('ar-SA');
}

// تنسيق الوقت
function formatTime(time) {
    return new Date(time).toLocaleTimeString('ar-SA');
}

// تنسيق التاريخ والوقت
function formatDateTime(dateTime) {
    return new Date(dateTime).toLocaleString('ar-SA');
}

// إعداد مرافق النصوص
function setupStringUtilities() {
    // إعداد مرافق النصوص
    window.capitalize = capitalize;
    window.truncate = truncate;
    window.sanitize = sanitize;
}

// تحويل الحرف الأول إلى كبير
function capitalize(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
}

// قطع النص
function truncate(str, length) {
    return str.length > length ? str.slice(0, length) + '...' : str;
}

// تنظيف النص
function sanitize(str) {
    return str.replace(/[<>]/g, '');
}

// إعداد مرافق الأرقام
function setupNumberUtilities() {
    // إعداد مرافق الأرقام
    window.formatNumber = formatNumber;
    window.formatCurrency = formatCurrency;
    window.formatPercentage = formatPercentage;
}

// تنسيق الأرقام
function formatNumber(number) {
    return new Intl.NumberFormat('ar-SA').format(number);
}

// تنسيق العملة
function formatCurrency(amount) {
    return new Intl.NumberFormat('ar-SA', {
        style: 'currency',
        currency: 'ILS'
    }).format(amount);
}

// تنسيق النسبة المئوية
function formatPercentage(value) {
    return new Intl.NumberFormat('ar-SA', {
        style: 'percent'
    }).format(value / 100);
}

// إعداد مرافق المصفوفات
function setupArrayUtilities() {
    // إعداد مرافق المصفوفات
    window.unique = unique;
    window.shuffle = shuffle;
    window.chunk = chunk;
}

// إزالة التكرار
function unique(array) {
    return [...new Set(array)];
}

// خلط المصفوفة
function shuffle(array) {
    return array.sort(() => Math.random() - 0.5);
}

// تقسيم المصفوفة
function chunk(array, size) {
    const chunks = [];
    for (let i = 0; i < array.length; i += size) {
        chunks.push(array.slice(i, i + size));
    }
    return chunks;
}
