// النظام الإداري - ملف JavaScript متخصص
// Admin System - Specialized JavaScript File

// تهيئة النظام الإداري
document.addEventListener('DOMContentLoaded', function() {
    initializeAdminSystem();
});

// تهيئة النظام الإداري
function initializeAdminSystem() {
    setupUserManagement();
    setupDepartmentManagement();
    setupRoleManagement();
    setupPermissionManagement();
    setupSystemSettings();
    setupReportManagement();
}

// إدارة المستخدمين
function setupUserManagement() {
    // إعداد البحث عن المستخدمين
    const userSearchInput = document.getElementById('userSearch');
    if (userSearchInput) {
        userSearchInput.addEventListener('input', function() {
            const query = this.value.toLowerCase();
            const userRows = document.querySelectorAll('.user-row');
            
            userRows.forEach(row => {
                const text = row.textContent.toLowerCase();
                if (text.includes(query)) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        });
    }
    
    // إعداد فلترة المستخدمين
    const userFilters = document.querySelectorAll('.user-filter');
    userFilters.forEach(filter => {
        filter.addEventListener('change', function() {
            filterUsers();
        });
    });
}

// فلترة المستخدمين
function filterUsers() {
    const roleFilter = document.getElementById('roleFilter');
    const statusFilter = document.getElementById('statusFilter');
    const departmentFilter = document.getElementById('departmentFilter');
    
    const userRows = document.querySelectorAll('.user-row');
    
    userRows.forEach(row => {
        let showRow = true;
        
        // فلترة حسب الدور
        if (roleFilter && roleFilter.value !== '') {
            const userRole = row.dataset.role;
            if (userRole !== roleFilter.value) {
                showRow = false;
            }
        }
        
        // فلترة حسب الحالة
        if (statusFilter && statusFilter.value !== '') {
            const userStatus = row.dataset.status;
            if (userStatus !== statusFilter.value) {
                showRow = false;
            }
        }
        
        // فلترة حسب القسم
        if (departmentFilter && departmentFilter.value !== '') {
            const userDepartment = row.dataset.department;
            if (userDepartment !== departmentFilter.value) {
                showRow = false;
            }
        }
        
        row.style.display = showRow ? '' : 'none';
    });
}

// إدارة الأقسام
function setupDepartmentManagement() {
    // إعداد البحث عن الأقسام
    const departmentSearchInput = document.getElementById('departmentSearch');
    if (departmentSearchInput) {
        departmentSearchInput.addEventListener('input', function() {
            const query = this.value.toLowerCase();
            const departmentRows = document.querySelectorAll('.department-row');
            
            departmentRows.forEach(row => {
                const text = row.textContent.toLowerCase();
                if (text.includes(query)) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        });
    }
    
    // إعداد فلترة الأقسام
    const departmentFilters = document.querySelectorAll('.department-filter');
    departmentFilters.forEach(filter => {
        filter.addEventListener('change', function() {
            filterDepartments();
        });
    });
}

// فلترة الأقسام
function filterDepartments() {
    const statusFilter = document.getElementById('departmentStatusFilter');
    const typeFilter = document.getElementById('departmentTypeFilter');
    const locationFilter = document.getElementById('locationFilter');
    
    const departmentRows = document.querySelectorAll('.department-row');
    
    departmentRows.forEach(row => {
        let showRow = true;
        
        // فلترة حسب الحالة
        if (statusFilter && statusFilter.value !== '') {
            const departmentStatus = row.dataset.status;
            if (departmentStatus !== statusFilter.value) {
                showRow = false;
            }
        }
        
        // فلترة حسب النوع
        if (typeFilter && typeFilter.value !== '') {
            const departmentType = row.dataset.type;
            if (departmentType !== typeFilter.value) {
                showRow = false;
            }
        }
        
        // فلترة حسب الموقع
        if (locationFilter && locationFilter.value !== '') {
            const departmentLocation = row.dataset.location;
            if (departmentLocation !== locationFilter.value) {
                showRow = false;
            }
        }
        
        row.style.display = showRow ? '' : 'none';
    });
}

// إدارة الأدوار
function setupRoleManagement() {
    // إعداد البحث عن الأدوار
    const roleSearchInput = document.getElementById('roleSearch');
    if (roleSearchInput) {
        roleSearchInput.addEventListener('input', function() {
            const query = this.value.toLowerCase();
            const roleRows = document.querySelectorAll('.role-row');
            
            roleRows.forEach(row => {
                const text = row.textContent.toLowerCase();
                if (text.includes(query)) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        });
    }
    
    // إعداد فلترة الأدوار
    const roleFilters = document.querySelectorAll('.role-filter');
    roleFilters.forEach(filter => {
        filter.addEventListener('change', function() {
            filterRoles();
        });
    });
}

// فلترة الأدوار
function filterRoles() {
    const statusFilter = document.getElementById('roleStatusFilter');
    const typeFilter = document.getElementById('roleTypeFilter');
    const levelFilter = document.getElementById('roleLevelFilter');
    
    const roleRows = document.querySelectorAll('.role-row');
    
    roleRows.forEach(row => {
        let showRow = true;
        
        // فلترة حسب الحالة
        if (statusFilter && statusFilter.value !== '') {
            const roleStatus = row.dataset.status;
            if (roleStatus !== statusFilter.value) {
                showRow = false;
            }
        }
        
        // فلترة حسب النوع
        if (typeFilter && typeFilter.value !== '') {
            const roleType = row.dataset.type;
            if (roleType !== typeFilter.value) {
                showRow = false;
            }
        }
        
        // فلترة حسب المستوى
        if (levelFilter && levelFilter.value !== '') {
            const roleLevel = row.dataset.level;
            if (roleLevel !== levelFilter.value) {
                showRow = false;
            }
        }
        
        row.style.display = showRow ? '' : 'none';
    });
}

// إدارة الصلاحيات
function setupPermissionManagement() {
    // إعداد البحث عن الصلاحيات
    const permissionSearchInput = document.getElementById('permissionSearch');
    if (permissionSearchInput) {
        permissionSearchInput.addEventListener('input', function() {
            const query = this.value.toLowerCase();
            const permissionRows = document.querySelectorAll('.permission-row');
            
            permissionRows.forEach(row => {
                const text = row.textContent.toLowerCase();
                if (text.includes(query)) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        });
    }
    
    // إعداد فلترة الصلاحيات
    const permissionFilters = document.querySelectorAll('.permission-filter');
    permissionFilters.forEach(filter => {
        filter.addEventListener('change', function() {
            filterPermissions();
        });
    });
}

// فلترة الصلاحيات
function filterPermissions() {
    const statusFilter = document.getElementById('permissionStatusFilter');
    const typeFilter = document.getElementById('permissionTypeFilter');
    const categoryFilter = document.getElementById('permissionCategoryFilter');
    
    const permissionRows = document.querySelectorAll('.permission-row');
    
    permissionRows.forEach(row => {
        let showRow = true;
        
        // فلترة حسب الحالة
        if (statusFilter && statusFilter.value !== '') {
            const permissionStatus = row.dataset.status;
            if (permissionStatus !== statusFilter.value) {
                showRow = false;
            }
        }
        
        // فلترة حسب النوع
        if (typeFilter && typeFilter.value !== '') {
            const permissionType = row.dataset.type;
            if (permissionType !== typeFilter.value) {
                showRow = false;
            }
        }
        
        // فلترة حسب الفئة
        if (categoryFilter && categoryFilter.value !== '') {
            const permissionCategory = row.dataset.category;
            if (permissionCategory !== categoryFilter.value) {
                showRow = false;
            }
        }
        
        row.style.display = showRow ? '' : 'none';
    });
}

// إعدادات النظام
function setupSystemSettings() {
    // إعداد البحث عن الإعدادات
    const settingsSearchInput = document.getElementById('settingsSearch');
    if (settingsSearchInput) {
        settingsSearchInput.addEventListener('input', function() {
            const query = this.value.toLowerCase();
            const settingsRows = document.querySelectorAll('.settings-row');
            
            settingsRows.forEach(row => {
                const text = row.textContent.toLowerCase();
                if (text.includes(query)) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        });
    }
    
    // إعداد فلترة الإعدادات
    const settingsFilters = document.querySelectorAll('.settings-filter');
    settingsFilters.forEach(filter => {
        filter.addEventListener('change', function() {
            filterSettings();
        });
    });
}

// فلترة الإعدادات
function filterSettings() {
    const categoryFilter = document.getElementById('settingsCategoryFilter');
    const typeFilter = document.getElementById('settingsTypeFilter');
    const statusFilter = document.getElementById('settingsStatusFilter');
    
    const settingsRows = document.querySelectorAll('.settings-row');
    
    settingsRows.forEach(row => {
        let showRow = true;
        
        // فلترة حسب الفئة
        if (categoryFilter && categoryFilter.value !== '') {
            const settingsCategory = row.dataset.category;
            if (settingsCategory !== categoryFilter.value) {
                showRow = false;
            }
        }
        
        // فلترة حسب النوع
        if (typeFilter && typeFilter.value !== '') {
            const settingsType = row.dataset.type;
            if (settingsType !== typeFilter.value) {
                showRow = false;
            }
        }
        
        // فلترة حسب الحالة
        if (statusFilter && statusFilter.value !== '') {
            const settingsStatus = row.dataset.status;
            if (settingsStatus !== statusFilter.value) {
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

// وظائف خاصة بالتحقق من صحة البيانات الإدارية
function validateAdminData(form) {
    let isValid = true;
    
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
    
    // التحقق من صحة البيانات الإدارية
    if (!validateAdminData(form)) {
        isValid = false;
    }
    
    return isValid;
}

// وظائف خاصة بالتحقق من صحة النماذج الإدارية
function validateUserForm(form) {
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

// وظائف خاصة بالتحقق من صحة النماذج الإدارية
function validateDepartmentForm(form) {
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

// وظائف خاصة بالتحقق من صحة النماذج الإدارية
function validateRoleForm(form) {
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
    
    return isValid;
}

// وظائف خاصة بالتحقق من صحة النماذج الإدارية
function validatePermissionForm(form) {
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
    
    return isValid;
}

// وظائف خاصة بالتحقق من صحة النماذج الإدارية
function validateSystemSettingsForm(form) {
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

// وظائف خاصة بالتحقق من صحة النماذج الإدارية
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

// وظائف خاصة بالتحقق من صحة النماذج الإدارية
function validateAdminDataForm(form) {
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
    
    // التحقق من صحة البيانات الإدارية
    if (!validateAdminData(form)) {
        isValid = false;
    }
    
    return isValid;
}
