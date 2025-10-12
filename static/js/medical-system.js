// النظام الصحي المتكامل - ملف JavaScript متخصص
// Medical System - Specialized JavaScript File

// تهيئة النظام الطبي
document.addEventListener('DOMContentLoaded', function() {
    initializeMedicalSystem();
});

// تهيئة النظام الطبي
function initializeMedicalSystem() {
    setupPatientManagement();
    setupVisitManagement();
    setupEmergencyManagement();
    setupAppointmentManagement();
    setupMedicationManagement();
    setupPricingManagement();
    setupReportManagement();
}

// إدارة المرضى
function setupPatientManagement() {
    // إعداد البحث عن المرضى
    const patientSearchInput = document.getElementById('patientSearch');
    if (patientSearchInput) {
        patientSearchInput.addEventListener('input', function() {
            const query = this.value.toLowerCase();
            const patientCards = document.querySelectorAll('.patient-card');
            
            patientCards.forEach(card => {
                const text = card.textContent.toLowerCase();
                if (text.includes(query)) {
                    card.style.display = 'block';
                } else {
                    card.style.display = 'none';
                }
            });
        });
    }
    
    // إعداد فلترة المرضى
    const patientFilters = document.querySelectorAll('.patient-filter');
    patientFilters.forEach(filter => {
        filter.addEventListener('change', function() {
            filterPatients();
        });
    });
}

// فلترة المرضى
function filterPatients() {
    const genderFilter = document.getElementById('genderFilter');
    const ageFilter = document.getElementById('ageFilter');
    const statusFilter = document.getElementById('statusFilter');
    
    const patientCards = document.querySelectorAll('.patient-card');
    
    patientCards.forEach(card => {
        let showCard = true;
        
        // فلترة حسب الجنس
        if (genderFilter && genderFilter.value !== '') {
            const patientGender = card.dataset.gender;
            if (patientGender !== genderFilter.value) {
                showCard = false;
            }
        }
        
        // فلترة حسب العمر
        if (ageFilter && ageFilter.value !== '') {
            const patientAge = parseInt(card.dataset.age);
            const ageRange = ageFilter.value;
            
            if (ageRange === 'child' && patientAge > 12) showCard = false;
            if (ageRange === 'adult' && (patientAge < 13 || patientAge > 65)) showCard = false;
            if (ageRange === 'elderly' && patientAge < 66) showCard = false;
        }
        
        // فلترة حسب الحالة
        if (statusFilter && statusFilter.value !== '') {
            const patientStatus = card.dataset.status;
            if (patientStatus !== statusFilter.value) {
                showCard = false;
            }
        }
        
        card.style.display = showCard ? 'block' : 'none';
    });
}

// إدارة الزيارات
function setupVisitManagement() {
    // إعداد البحث عن الزيارات
    const visitSearchInput = document.getElementById('visitSearch');
    if (visitSearchInput) {
        visitSearchInput.addEventListener('input', function() {
            const query = this.value.toLowerCase();
            const visitRows = document.querySelectorAll('.visit-row');
            
            visitRows.forEach(row => {
                const text = row.textContent.toLowerCase();
                if (text.includes(query)) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        });
    }
    
    // إعداد فلترة الزيارات
    const visitFilters = document.querySelectorAll('.visit-filter');
    visitFilters.forEach(filter => {
        filter.addEventListener('change', function() {
            filterVisits();
        });
    });
}

// فلترة الزيارات
function filterVisits() {
    const typeFilter = document.getElementById('visitTypeFilter');
    const statusFilter = document.getElementById('visitStatusFilter');
    const dateFilter = document.getElementById('visitDateFilter');
    
    const visitRows = document.querySelectorAll('.visit-row');
    
    visitRows.forEach(row => {
        let showRow = true;
        
        // فلترة حسب النوع
        if (typeFilter && typeFilter.value !== '') {
            const visitType = row.dataset.type;
            if (visitType !== typeFilter.value) {
                showRow = false;
            }
        }
        
        // فلترة حسب الحالة
        if (statusFilter && statusFilter.value !== '') {
            const visitStatus = row.dataset.status;
            if (visitStatus !== statusFilter.value) {
                showRow = false;
            }
        }
        
        // فلترة حسب التاريخ
        if (dateFilter && dateFilter.value !== '') {
            const visitDate = row.dataset.date;
            if (visitDate !== dateFilter.value) {
                showRow = false;
            }
        }
        
        row.style.display = showRow ? '' : 'none';
    });
}

// إدارة الطوارئ
function setupEmergencyManagement() {
    // إعداد البحث عن حالات الطوارئ
    const emergencySearchInput = document.getElementById('emergencySearch');
    if (emergencySearchInput) {
        emergencySearchInput.addEventListener('input', function() {
            const query = this.value.toLowerCase();
            const emergencyCards = document.querySelectorAll('.emergency-card');
            
            emergencyCards.forEach(card => {
                const text = card.textContent.toLowerCase();
                if (text.includes(query)) {
                    card.style.display = 'block';
                } else {
                    card.style.display = 'none';
                }
            });
        });
    }
    
    // إعداد فلترة حالات الطوارئ
    const emergencyFilters = document.querySelectorAll('.emergency-filter');
    emergencyFilters.forEach(filter => {
        filter.addEventListener('change', function() {
            filterEmergencies();
        });
    });
}

// فلترة حالات الطوارئ
function filterEmergencies() {
    const typeFilter = document.getElementById('emergencyTypeFilter');
    const severityFilter = document.getElementById('severityFilter');
    const statusFilter = document.getElementById('emergencyStatusFilter');
    
    const emergencyCards = document.querySelectorAll('.emergency-card');
    
    emergencyCards.forEach(card => {
        let showCard = true;
        
        // فلترة حسب النوع
        if (typeFilter && typeFilter.value !== '') {
            const emergencyType = card.dataset.type;
            if (emergencyType !== typeFilter.value) {
                showCard = false;
            }
        }
        
        // فلترة حسب الخطورة
        if (severityFilter && severityFilter.value !== '') {
            const emergencySeverity = card.dataset.severity;
            if (emergencySeverity !== severityFilter.value) {
                showCard = false;
            }
        }
        
        // فلترة حسب الحالة
        if (statusFilter && statusFilter.value !== '') {
            const emergencyStatus = card.dataset.status;
            if (emergencyStatus !== statusFilter.value) {
                showCard = false;
            }
        }
        
        card.style.display = showCard ? 'block' : 'none';
    });
}

// إدارة المواعيد
function setupAppointmentManagement() {
    // إعداد البحث عن المواعيد
    const appointmentSearchInput = document.getElementById('appointmentSearch');
    if (appointmentSearchInput) {
        appointmentSearchInput.addEventListener('input', function() {
            const query = this.value.toLowerCase();
            const appointmentRows = document.querySelectorAll('.appointment-row');
            
            appointmentRows.forEach(row => {
                const text = row.textContent.toLowerCase();
                if (text.includes(query)) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        });
    }
    
    // إعداد فلترة المواعيد
    const appointmentFilters = document.querySelectorAll('.appointment-filter');
    appointmentFilters.forEach(filter => {
        filter.addEventListener('change', function() {
            filterAppointments();
        });
    });
}

// فلترة المواعيد
function filterAppointments() {
    const typeFilter = document.getElementById('appointmentTypeFilter');
    const statusFilter = document.getElementById('appointmentStatusFilter');
    const dateFilter = document.getElementById('appointmentDateFilter');
    
    const appointmentRows = document.querySelectorAll('.appointment-row');
    
    appointmentRows.forEach(row => {
        let showRow = true;
        
        // فلترة حسب النوع
        if (typeFilter && typeFilter.value !== '') {
            const appointmentType = row.dataset.type;
            if (appointmentType !== typeFilter.value) {
                showRow = false;
            }
        }
        
        // فلترة حسب الحالة
        if (statusFilter && statusFilter.value !== '') {
            const appointmentStatus = row.dataset.status;
            if (appointmentStatus !== statusFilter.value) {
                showRow = false;
            }
        }
        
        // فلترة حسب التاريخ
        if (dateFilter && dateFilter.value !== '') {
            const appointmentDate = row.dataset.date;
            if (appointmentDate !== dateFilter.value) {
                showRow = false;
            }
        }
        
        row.style.display = showRow ? '' : 'none';
    });
}

// إدارة الأدوية
function setupMedicationManagement() {
    // إعداد البحث عن الأدوية
    const medicationSearchInput = document.getElementById('medicationSearch');
    if (medicationSearchInput) {
        medicationSearchInput.addEventListener('input', function() {
            const query = this.value.toLowerCase();
            const medicationRows = document.querySelectorAll('.medication-row');
            
            medicationRows.forEach(row => {
                const text = row.textContent.toLowerCase();
                if (text.includes(query)) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        });
    }
    
    // إعداد فلترة الأدوية
    const medicationFilters = document.querySelectorAll('.medication-filter');
    medicationFilters.forEach(filter => {
        filter.addEventListener('change', function() {
            filterMedications();
        });
    });
}

// فلترة الأدوية
function filterMedications() {
    const categoryFilter = document.getElementById('medicationCategoryFilter');
    const formFilter = document.getElementById('medicationFormFilter');
    const statusFilter = document.getElementById('medicationStatusFilter');
    
    const medicationRows = document.querySelectorAll('.medication-row');
    
    medicationRows.forEach(row => {
        let showRow = true;
        
        // فلترة حسب الفئة
        if (categoryFilter && categoryFilter.value !== '') {
            const medicationCategory = row.dataset.category;
            if (medicationCategory !== categoryFilter.value) {
                showRow = false;
            }
        }
        
        // فلترة حسب الشكل
        if (formFilter && formFilter.value !== '') {
            const medicationForm = row.dataset.form;
            if (medicationForm !== formFilter.value) {
                showRow = false;
            }
        }
        
        // فلترة حسب الحالة
        if (statusFilter && statusFilter.value !== '') {
            const medicationStatus = row.dataset.status;
            if (medicationStatus !== statusFilter.value) {
                showRow = false;
            }
        }
        
        row.style.display = showRow ? '' : 'none';
    });
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

// إدارة التقارير
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

// وظائف خاصة بالتحقق من صحة البيانات الطبية
function validateMedicalData(form) {
    let isValid = true;
    
    // التحقق من صحة العلامات الحيوية
    const vitalSigns = form.querySelectorAll('input[name^="vital_signs_"]');
    vitalSigns.forEach(input => {
        const value = parseFloat(input.value);
        const fieldName = input.name;
        
        if (value && !isValidVitalSign(fieldName, value)) {
            showFieldError(input, 'القيمة غير معقولة');
            isValid = false;
        }
    });
    
    // التحقق من صحة التاريخ
    const dateInputs = form.querySelectorAll('input[type="date"]');
    dateInputs.forEach(input => {
        if (input.value && !isValidDate(input.value)) {
            showFieldError(input, 'التاريخ غير صحيح');
            isValid = false;
        }
    });
    
    // التحقق من صحة الوقت
    const timeInputs = form.querySelectorAll('input[type="time"]');
    timeInputs.forEach(input => {
        if (input.value && !isValidTime(input.value)) {
            showFieldError(input, 'الوقت غير صحيح');
            isValid = false;
        }
    });
    
    return isValid;
}

// التحقق من صحة العلامات الحيوية
function isValidVitalSign(fieldName, value) {
    if (fieldName.includes('bp_systolic')) return value >= 50 && value <= 300;
    if (fieldName.includes('bp_diastolic')) return value >= 30 && value <= 200;
    if (fieldName.includes('heart_rate')) return value >= 30 && value <= 200;
    if (fieldName.includes('temperature')) return value >= 30 && value <= 45;
    if (fieldName.includes('oxygen_saturation')) return value >= 50 && value <= 100;
    return true;
}

// التحقق من صحة التاريخ
function isValidDate(dateString) {
    const date = new Date(dateString);
    return date instanceof Date && !isNaN(date);
}

// التحقق من صحة الوقت
function isValidTime(timeString) {
    const timeRegex = /^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$/;
    return timeRegex.test(timeString);
}

// وظائف خاصة بالطباعة
function printMedicalReport(reportId) {
    const reportElement = document.getElementById(`report-${reportId}`);
    if (reportElement) {
        const printWindow = window.open('', '_blank');
        printWindow.document.write(`
            <html>
                <head>
                    <title>تقرير طبي</title>
                    <style>
                        body { font-family: Arial, sans-serif; direction: rtl; }
                        .header { text-align: center; margin-bottom: 20px; }
                        .content { margin: 20px 0; }
                        .footer { text-align: center; margin-top: 20px; }
                    </style>
                </head>
                <body>
                    ${reportElement.innerHTML}
                </body>
            </html>
        `);
        printWindow.document.close();
        printWindow.print();
    }
}

// وظائف خاصة بالتصدير
function exportMedicalData(type, data) {
    switch (type) {
        case 'patients':
            exportPatientsToExcel();
            break;
        case 'visits':
            exportVisitsToExcel();
            break;
        case 'emergencies':
            exportEmergenciesToExcel();
            break;
        case 'appointments':
            exportAppointmentsToExcel();
            break;
        case 'medications':
            exportMedicationsToExcel();
            break;
        case 'pricing':
            exportPricingToExcel();
            break;
        default:
            console.log('نوع التصدير غير مدعوم');
    }
}

// وظائف خاصة بالبحث المتقدم
function advancedSearch() {
    const searchForm = document.getElementById('advancedSearchForm');
    if (searchForm) {
        const formData = new FormData(searchForm);
        const searchParams = new URLSearchParams();
        
        for (let [key, value] of formData.entries()) {
            if (value) {
                searchParams.append(key, value);
            }
        }
        
        const currentUrl = new URL(window.location);
        currentUrl.search = searchParams.toString();
        window.location.href = currentUrl.toString();
    }
}

// وظائف خاصة بالفلترة المتقدمة
function advancedFilter() {
    const filterForm = document.getElementById('advancedFilterForm');
    if (filterForm) {
        const formData = new FormData(filterForm);
        const filterParams = new URLSearchParams();
        
        for (let [key, value] of formData.entries()) {
            if (value) {
                filterParams.append(key, value);
            }
        }
        
        const currentUrl = new URL(window.location);
        currentUrl.search = filterParams.toString();
        window.location.href = currentUrl.toString();
    }
}

// وظائف خاصة بالتحقق من صحة النماذج الطبية
function validateMedicalForm(form) {
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
    
    // التحقق من صحة البيانات الطبية
    if (!validateMedicalData(form)) {
        isValid = false;
    }
    
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
    
    // التحقق من صحة المبالغ المالية
    const amountFields = form.querySelectorAll('input[name*="price"], input[name*="amount"], input[name*="cost"]');
    amountFields.forEach(field => {
        const value = parseFloat(field.value);
        if (value && (value < 0 || isNaN(value))) {
            showFieldError(field, 'المبلغ غير صحيح');
            isValid = false;
        }
    });
    
    return isValid;
}

// وظائف خاصة بالتحقق من صحة النماذج الإدارية
function validateAdminForm(form) {
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
    
    return isValid;
}
