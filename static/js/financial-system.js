// النظام المالي - ملف JavaScript متخصص
// Financial System - Specialized JavaScript File

// تهيئة النظام المالي
document.addEventListener('DOMContentLoaded', function() {
    initializeFinancialSystem();
});

// تهيئة النظام المالي
function initializeFinancialSystem() {
    setupPricingManagement();
    setupPaymentManagement();
    setupInvoiceManagement();
    setupReportManagement();
    setupCurrencyManagement();
}

// إدارة التسعير
function setupPricingManagement() {
    // إعداد البحث عن التسعير
    const pricingSearchInput = document.getElementById('pricingSearch');
    if (pricingSearchInput) {
        pricingSearchInput.addEventListener('input', function() {
            const query = this.value.toLowerCase();
            const pricingRows = document.querySelectorAll('.pricing-row');
            
            pricingRows.forEach(row => {
                const text = row.textContent.toLowerCase();
                if (text.includes(query)) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        });
    }
    
    // إعداد فلترة التسعير
    const pricingFilters = document.querySelectorAll('.pricing-filter');
    pricingFilters.forEach(filter => {
        filter.addEventListener('change', function() {
            filterPricing();
        });
    });
}

// فلترة التسعير
function filterPricing() {
    const typeFilter = document.getElementById('pricingTypeFilter');
    const currencyFilter = document.getElementById('currencyFilter');
    const statusFilter = document.getElementById('pricingStatusFilter');
    
    const pricingRows = document.querySelectorAll('.pricing-row');
    
    pricingRows.forEach(row => {
        let showRow = true;
        
        // فلترة حسب النوع
        if (typeFilter && typeFilter.value !== '') {
            const pricingType = row.dataset.type;
            if (pricingType !== typeFilter.value) {
                showRow = false;
            }
        }
        
        // فلترة حسب العملة
        if (currencyFilter && currencyFilter.value !== '') {
            const pricingCurrency = row.dataset.currency;
            if (pricingCurrency !== currencyFilter.value) {
                showRow = false;
            }
        }
        
        // فلترة حسب الحالة
        if (statusFilter && statusFilter.value !== '') {
            const pricingStatus = row.dataset.status;
            if (pricingStatus !== statusFilter.value) {
                showRow = false;
            }
        }
        
        row.style.display = showRow ? '' : 'none';
    });
}

// إدارة المدفوعات
function setupPaymentManagement() {
    // إعداد البحث عن المدفوعات
    const paymentSearchInput = document.getElementById('paymentSearch');
    if (paymentSearchInput) {
        paymentSearchInput.addEventListener('input', function() {
            const query = this.value.toLowerCase();
            const paymentRows = document.querySelectorAll('.payment-row');
            
            paymentRows.forEach(row => {
                const text = row.textContent.toLowerCase();
                if (text.includes(query)) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        });
    }
    
    // إعداد فلترة المدفوعات
    const paymentFilters = document.querySelectorAll('.payment-filter');
    paymentFilters.forEach(filter => {
        filter.addEventListener('change', function() {
            filterPayments();
        });
    });
}

// فلترة المدفوعات
function filterPayments() {
    const statusFilter = document.getElementById('paymentStatusFilter');
    const methodFilter = document.getElementById('paymentMethodFilter');
    const dateFilter = document.getElementById('paymentDateFilter');
    
    const paymentRows = document.querySelectorAll('.payment-row');
    
    paymentRows.forEach(row => {
        let showRow = true;
        
        // فلترة حسب الحالة
        if (statusFilter && statusFilter.value !== '') {
            const paymentStatus = row.dataset.status;
            if (paymentStatus !== statusFilter.value) {
                showRow = false;
            }
        }
        
        // فلترة حسب الطريقة
        if (methodFilter && methodFilter.value !== '') {
            const paymentMethod = (row.dataset.method || '').toLowerCase();
            const filterValue = (methodFilter.value || '').toLowerCase();
            if (paymentMethod !== filterValue) {
                showRow = false;
            }
        }
        
        // فلترة حسب التاريخ
        if (dateFilter && dateFilter.value !== '') {
            const paymentDate = row.dataset.date;
            if (paymentDate !== dateFilter.value) {
                showRow = false;
            }
        }
        
        row.style.display = showRow ? '' : 'none';
    });
}

// إدارة الفواتير
function setupInvoiceManagement() {
    // إعداد البحث عن الفواتير
    const invoiceSearchInput = document.getElementById('invoiceSearch');
    if (invoiceSearchInput) {
        invoiceSearchInput.addEventListener('input', function() {
            const query = this.value.toLowerCase();
            const invoiceRows = document.querySelectorAll('.invoice-row');
            
            invoiceRows.forEach(row => {
                const text = row.textContent.toLowerCase();
                if (text.includes(query)) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        });
    }
    
    // إعداد فلترة الفواتير
    const invoiceFilters = document.querySelectorAll('.invoice-filter');
    invoiceFilters.forEach(filter => {
        filter.addEventListener('change', function() {
            filterInvoices();
        });
    });
}

// فلترة الفواتير
function filterInvoices() {
    const statusFilter = document.getElementById('invoiceStatusFilter');
    const typeFilter = document.getElementById('invoiceTypeFilter');
    const dateFilter = document.getElementById('invoiceDateFilter');
    
    const invoiceRows = document.querySelectorAll('.invoice-row');
    
    invoiceRows.forEach(row => {
        let showRow = true;
        
        // فلترة حسب الحالة
        if (statusFilter && statusFilter.value !== '') {
            const invoiceStatus = row.dataset.status;
            if (invoiceStatus !== statusFilter.value) {
                showRow = false;
            }
        }
        
        // فلترة حسب النوع
        if (typeFilter && typeFilter.value !== '') {
            const invoiceType = row.dataset.type;
            if (invoiceType !== typeFilter.value) {
                showRow = false;
            }
        }
        
        // فلترة حسب التاريخ
        if (dateFilter && dateFilter.value !== '') {
            const invoiceDate = row.dataset.date;
            if (invoiceDate !== dateFilter.value) {
                showRow = false;
            }
        }
        
        row.style.display = showRow ? '' : 'none';
    });
}

// إدارة التقارير المالية
function setupReportManagement() {
    // إعداد البحث عن التقارير
    const reportSearchInput = document.getElementById('reportSearch');
    if (reportSearchInput) {
        reportSearchInput.addEventListener('input', function() {
            const query = this.value.toLowerCase();
            const reportRows = document.querySelectorAll('.report-row');
            
            reportRows.forEach(row => {
                const text = row.textContent.toLowerCase();
                if (text.includes(query)) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        });
    }
    
    // إعداد فلترة التقارير
    const reportFilters = document.querySelectorAll('.report-filter');
    reportFilters.forEach(filter => {
        filter.addEventListener('change', function() {
            filterReports();
        });
    });
}

// فلترة التقارير
function filterReports() {
    const typeFilter = document.getElementById('reportTypeFilter');
    const dateFilter = document.getElementById('reportDateFilter');
    const statusFilter = document.getElementById('reportStatusFilter');
    
    const reportRows = document.querySelectorAll('.report-row');
    
    reportRows.forEach(row => {
        let showRow = true;
        
        // فلترة حسب النوع
        if (typeFilter && typeFilter.value !== '') {
            const reportType = row.dataset.type;
            if (reportType !== typeFilter.value) {
                showRow = false;
            }
        }
        
        // فلترة حسب التاريخ
        if (dateFilter && dateFilter.value !== '') {
            const reportDate = row.dataset.date;
            if (reportDate !== dateFilter.value) {
                showRow = false;
            }
        }
        
        // فلترة حسب الحالة
        if (statusFilter && statusFilter.value !== '') {
            const reportStatus = row.dataset.status;
            if (reportStatus !== statusFilter.value) {
                showRow = false;
            }
        }
        
        row.style.display = showRow ? '' : 'none';
    });
}

// إدارة العملات
function setupCurrencyManagement() {
    // إعداد تحويل العملات
    const currencyConverter = document.getElementById('currencyConverter');
    if (currencyConverter) {
        currencyConverter.addEventListener('change', function() {
            convertCurrency();
        });
    }
    
    // إعداد تحديث أسعار الصرف
    const exchangeRateUpdater = document.getElementById('exchangeRateUpdater');
    if (exchangeRateUpdater) {
        exchangeRateUpdater.addEventListener('click', function() {
            updateExchangeRates();
        });
    }
}

// تحويل العملات
function convertCurrency() {
    const amount = parseFloat(document.getElementById('amount').value);
    const fromCurrency = document.getElementById('fromCurrency').value;
    const toCurrency = document.getElementById('toCurrency').value;
    
    if (amount && fromCurrency && toCurrency) {
        const convertedAmount = convertCurrencyAmount(amount, fromCurrency, toCurrency);
        document.getElementById('convertedAmount').value = convertedAmount.toFixed(2);
    }
}

// تحويل مبلغ العملة
function convertCurrencyAmount(amount, fromCurrency, toCurrency) {
    // أسعار الصرف الافتراضية (يجب تحديثها من API)
    const exchangeRates = {
        'شيكل': 1,
        'دولار': 3.7,
        'يورو': 4.1
    };
    
    const fromRate = exchangeRates[fromCurrency] || 1;
    const toRate = exchangeRates[toCurrency] || 1;
    
    return (amount * fromRate) / toRate;
}

// تحديث أسعار الصرف
function updateExchangeRates() {
    // تنفيذ تحديث أسعار الصرف من API
    console.log('تحديث أسعار الصرف...');
    showAlert('تم تحديث أسعار الصرف', 'success');
}

// وظائف خاصة بالتحقق من صحة البيانات المالية
function validateFinancialData(form) {
    let isValid = true;
    
    // التحقق من صحة المبالغ المالية
    const amountFields = form.querySelectorAll('input[name*="price"], input[name*="amount"], input[name*="cost"]');
    amountFields.forEach(field => {
        const value = parseFloat(field.value);
        if (value && (value < 0 || isNaN(value))) {
            showFieldError(field, 'المبلغ غير صحيح');
            isValid = false;
        }
    });
    
    // التحقق من صحة النسب المئوية
    const percentageFields = form.querySelectorAll('input[name*="percentage"], input[name*="rate"]');
    percentageFields.forEach(field => {
        const value = parseFloat(field.value);
        if (value && (value < 0 || value > 100 || isNaN(value))) {
            showFieldError(field, 'النسبة المئوية غير صحيحة');
            isValid = false;
        }
    });
    
    // التحقق من صحة التواريخ المالية
    const dateFields = form.querySelectorAll('input[name*="date"]');
    dateFields.forEach(field => {
        if (field.value && !isValidDate(field.value)) {
            showFieldError(field, 'التاريخ غير صحيح');
            isValid = false;
        }
    });
    
    return isValid;
}

// وظائف خاصة بالتحقق من صحة النماذج المالية
function validateFinancialForm(form) {
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
    
    // التحقق من صحة البيانات المالية
    if (!validateFinancialData(form)) {
        isValid = false;
    }
    
    return isValid;
}

// وظائف خاصة بالتحقق من صحة النماذج المالية
function validatePricingForm(form) {
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
    
    // التحقق من صحة الأسعار
    const priceFields = form.querySelectorAll('input[name*="price"]');
    priceFields.forEach(field => {
        const value = parseFloat(field.value);
        if (value && (value < 0 || isNaN(value))) {
            showFieldError(field, 'السعر غير صحيح');
            isValid = false;
        }
    });
    
    // التحقق من صحة النسب المئوية
    const percentageFields = form.querySelectorAll('input[name*="percentage"]');
    percentageFields.forEach(field => {
        const value = parseFloat(field.value);
        if (value && (value < 0 || value > 100 || isNaN(value))) {
            showFieldError(field, 'النسبة المئوية غير صحيحة');
            isValid = false;
        }
    });
    
    return isValid;
}

// وظائف خاصة بالتحقق من صحة النماذج المالية
function validatePaymentForm(form) {
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
    
    // التحقق من صحة المبالغ المالية
    const amountFields = form.querySelectorAll('input[name*="amount"]');
    amountFields.forEach(field => {
        const value = parseFloat(field.value);
        if (value && (value < 0 || isNaN(value))) {
            showFieldError(field, 'المبلغ غير صحيح');
            isValid = false;
        }
    });
    
    return isValid;
}

// وظائف خاصة بالتحقق من صحة النماذج المالية
function validateInvoiceForm(form) {
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
    
    // التحقق من صحة المبالغ المالية
    const amountFields = form.querySelectorAll('input[name*="amount"]');
    amountFields.forEach(field => {
        const value = parseFloat(field.value);
        if (value && (value < 0 || isNaN(value))) {
            showFieldError(field, 'المبلغ غير صحيح');
            isValid = false;
        }
    });
    
    return isValid;
}

// وظائف خاصة بالتحقق من صحة النماذج المالية
function validateReportForm(form) {
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
    
    // التحقق من صحة التواريخ
    const dateFields = form.querySelectorAll('input[type="date"]');
    dateFields.forEach(field => {
        if (field.value && !isValidDate(field.value)) {
            showFieldError(field, 'التاريخ غير صحيح');
            isValid = false;
        }
    });
    
    return isValid;
}

// وظائف خاصة بالتحقق من صحة النماذج المالية
function validateCurrencyForm(form) {
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
    
    // التحقق من صحة أسعار الصرف
    const rateFields = form.querySelectorAll('input[name*="rate"]');
    rateFields.forEach(field => {
        const value = parseFloat(field.value);
        if (value && (value < 0 || isNaN(value))) {
            showFieldError(field, 'سعر الصرف غير صحيح');
            isValid = false;
        }
    });
    
    return isValid;
}

// وظائف خاصة بالتحقق من صحة النماذج المالية
function validateExchangeRateForm(form) {
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
    
    // التحقق من صحة أسعار الصرف
    const rateFields = form.querySelectorAll('input[name*="rate"]');
    rateFields.forEach(field => {
        const value = parseFloat(field.value);
        if (value && (value < 0 || isNaN(value))) {
            showFieldError(field, 'سعر الصرف غير صحيح');
            isValid = false;
        }
    });
    
    return isValid;
}

// وظائف خاصة بالتحقق من صحة النماذج المالية
function validateFinancialReportForm(form) {
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
    
    // التحقق من صحة التواريخ
    const dateFields = form.querySelectorAll('input[type="date"]');
    dateFields.forEach(field => {
        if (field.value && !isValidDate(field.value)) {
            showFieldError(field, 'التاريخ غير صحيح');
            isValid = false;
        }
    });
    
    return isValid;
}

// وظائف خاصة بالتحقق من صحة النماذج المالية
function validateFinancialDataForm(form) {
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
    
    // التحقق من صحة البيانات المالية
    if (!validateFinancialData(form)) {
        isValid = false;
    }
    
    return isValid;
}
