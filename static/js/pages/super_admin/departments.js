// Search functionality
document.getElementById('searchInput').addEventListener('input', function() {
    const searchTerm = this.value.toLowerCase();
    const table = document.getElementById('departmentsTable');
    const rows = table.getElementsByTagName('tr');
    
    for (let i = 1; i < rows.length; i++) {
        const row = rows[i];
        const text = row.textContent.toLowerCase();
        if (text.includes(searchTerm)) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    }
});

// Department management functions
function viewDepartment(departmentId) {
    // عرض تفاصيل القسم
    window.open((window.API_ROUTES && window.API_ROUTES.view_department) ? window.API_ROUTES.view_department.replace('/0', '/' + departmentId) : `/super-admin/department/${departmentId}`, '_blank');
}

function editDepartment(departmentId) {
    // تعديل القسم
    window.location.href = (window.API_ROUTES && window.API_ROUTES.edit_department) ? window.API_ROUTES.edit_department.replace('/0', '/' + departmentId) : `/super-admin/edit-department/${departmentId}`;
}

function manageStaff(departmentId) {
    // إدارة موظفي القسم
    window.location.href = (window.API_ROUTES && window.API_ROUTES.department_staff) ? window.API_ROUTES.department_staff.replace('/0', '/' + departmentId) : `/super-admin/department-staff/${departmentId}`;
}

function activateDepartment(departmentId) {
    Swal.fire({
        title: 'تأكيد',
        text: 'هل أنت متأكد من تفعيل هذا القسم؟',
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: 'نعم',
        cancelButtonText: 'إلغاء'
    }).then((result) => {
        if (result.isConfirmed) {
            fetch(((window.API_ROUTES && window.API_ROUTES.activate_department) || '/super-admin/activate-department/0').replace('/0', '/' + departmentId), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    location.reload();
                } else {
                    Swal.fire({ title: 'خطأ', text: 'حدث خطأ في تفعيل القسم', icon: 'error' });
                }
            })
            .catch(() => Swal.fire({ title: 'خطأ', text: 'فشل الاتصال بالخادم', icon: 'error' }));
        }
    });
}

function deactivateDepartment(departmentId) {
    Swal.fire({
        title: 'تأكيد',
        text: 'هل أنت متأكد من إلغاء تفعيل هذا القسم؟',
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: 'نعم',
        cancelButtonText: 'إلغاء'
    }).then((result) => {
        if (result.isConfirmed) {
            fetch(((window.API_ROUTES && window.API_ROUTES.deactivate_department) || '/super-admin/deactivate-department/0').replace('/0', '/' + departmentId), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    location.reload();
                } else {
                    Swal.fire({ title: 'خطأ', text: 'حدث خطأ في إلغاء تفعيل القسم', icon: 'error' });
                }
            })
            .catch(() => Swal.fire({ title: 'خطأ', text: 'فشل الاتصال بالخادم', icon: 'error' }));
        }
    });
}

function exportDepartments() {
    // تصدير الأقسام
    window.open((window.API_ROUTES && window.API_ROUTES.export_departments) || '/super-admin/export-departments', '_blank');
}

// Add department form
document.getElementById('addDepartmentForm').addEventListener('submit', function(e) {
    e.preventDefault();
    
    const formData = new FormData(this);
    
    const createUrl = (window.API_ROUTES && window.API_ROUTES.create_department) || '/super-admin/departments/create';
    fetch(createUrl, {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            location.reload();
        } else {
            Swal.fire({ title: 'خطأ', text: 'حدث خطأ في إضافة القسم: ' + (data.message || ''), icon: 'error' });
        }
    })
    .catch(() => Swal.fire({ title: 'خطأ', text: 'فشل الاتصال بالخادم', icon: 'error' }));
});
