var __M = window.__M || [];

function addNewUser() {
    Swal.fire({ title: 'إضافة مستخدم', text: 'إضافة مستخدم جديد', icon: 'info' });
}

function exportUsers() {
    var csvContent = "data:text/csv;charset=utf-8," 
        + "\u0627\u0644\u0627\u0633\u0645,\u0627\u0633\u0645 \u0627\u0644\u0645\u0633\u062a\u062e\u062f\u0645,\u0627\u0644\u0628\u0631\u064a\u062f \u0627\u0644\u0625\u0644\u0643\u062a\u0631\u0648\u0646\u064a,\u0627\u0644\u062f\u0648\u0631,\u0627\u0644\u0642\u0633\u0645,\u0627\u0644\u062d\u0627\u0644\u0629,\u0622\u062e\u0631 \u062f\u062e\u0648\u0644\n"
        + __M0__.map(function(u) {
            var dept = u.department ? u.department.name : "\u063a\u064a\u0631 \u0645\u062d\u062f\u062f";
            var lastLogin = u.last_login ? u.last_login : "\u0644\u0645 \u064a\u0633\u062c\u0644 \u062f\u062e\u0648\u0644";
            return (u.full_name || "\u063a\u064a\u0631 \u0645\u062d\u062f\u062f") + "," + u.username + "," + (u.email || "\u063a\u064a\u0631 \u0645\u062d\u062f\u062f") + "," + u.role + "," + dept + "," + (u.is_active ? "\u0646\u0634\u0637" : "\u0645\u0639\u0637\u0644") + "," + lastLogin + "\n";
        }).join("");
    
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", "users_" + new Date().toISOString().split('T')[0] + ".csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

function viewUser(userId) {
    Swal.fire({ title: 'عرض المستخدم', text: 'عرض تفاصيل المستخدم: ' + userId, icon: 'info' });
}

function editUser(userId) {
    Swal.fire({ title: 'تعديل المستخدم', text: 'تعديل المستخدم: ' + userId, icon: 'info' });
}

function toggleUser(userId) {
    Swal.fire({
        title: 'تغيير الحالة',
        text: 'هل تريد تغيير حالة هذا المستخدم؟',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'تأكيد',
        cancelButtonText: 'إلغاء'
    }).then((res) => {
        if (res.isConfirmed) {
            Swal.fire({ title: 'تم', text: 'تم تغيير حالة المستخدم: ' + userId, icon: 'success' }).then(() => { location.reload(); });
        }
    });
}

function resetPassword(userId) {
    Swal.fire({
        title: 'إعادة تعيين كلمة المرور',
        text: 'هل تريد إعادة تعيين كلمة مرور هذا المستخدم؟',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'تأكيد',
        cancelButtonText: 'إلغاء'
    }).then((res) => {
        if (res.isConfirmed) {
            Swal.fire({ title: 'تم', text: 'تم إعادة تعيين كلمة المرور للمستخدم: ' + userId, icon: 'success' });
        }
    });
}

function deleteUser(userId) {
    Swal.fire({
        title: 'حذف المستخدم',
        text: 'هل تريد حذف هذا المستخدم نهائياً؟',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'حذف',
        cancelButtonText: 'إلغاء'
    }).then((res) => {
        if (res.isConfirmed) {
            Swal.fire({ title: 'تم', text: 'تم حذف المستخدم: ' + userId, icon: 'success' }).then(() => { location.reload(); });
        }
    });
}

function filterUsers(filter) {
    const rows = document.querySelectorAll('#usersTable tbody tr');
    
    rows.forEach(row => {
        if (filter === 'all') {
            row.style.display = '';
        } else if (filter === 'active') {
            row.style.display = row.dataset.status === 'active' ? '' : 'none';
        } else if (filter === 'inactive') {
            row.style.display = row.dataset.status === 'inactive' ? '' : 'none';
        } else if (filter === 'admin') {
            row.style.display = row.dataset.admin === 'admin' ? '' : 'none';
        }
    });
    
    // تحديث أزرار التصفية
    document.querySelectorAll('.btn-outline-primary, .btn-outline-success, .btn-outline-warning, .btn-outline-info').forEach(btn => {
        btn.classList.remove('active');
    });
    
    event.target.classList.add('active');
}

function bulkActivate() {
    Swal.fire({
        title: 'تفعيل المستخدمين',
        text: 'هل تريد تفعيل المستخدمين المحددين؟',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'تفعيل',
        cancelButtonText: 'إلغاء'
    }).then((res) => {
        if (res.isConfirmed) {
            Swal.fire({ title: 'تم', text: 'تم تفعيل المستخدمين', icon: 'success' }).then(() => { location.reload(); });
        }
    });
}

function bulkDeactivate() {
    Swal.fire({
        title: 'تعطيل المستخدمين',
        text: 'هل تريد تعطيل المستخدمين المحددين؟',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'تعطيل',
        cancelButtonText: 'إلغاء'
    }).then((res) => {
        if (res.isConfirmed) {
            Swal.fire({ title: 'تم', text: 'تم تعطيل المستخدمين', icon: 'success' }).then(() => { location.reload(); });
        }
    });
}

function bulkResetPassword() {
    Swal.fire({
        title: 'إعادة تعيين كلمات المرور',
        text: 'هل تريد إعادة تعيين كلمات مرور المستخدمين المحددين؟',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'تأكيد',
        cancelButtonText: 'إلغاء'
    }).then((res) => {
        if (res.isConfirmed) {
            Swal.fire({ title: 'تم', text: 'تم إعادة تعيين كلمات المرور', icon: 'success' });
        }
    });
}

function bulkExport() {
    // تصدير المستخدمين
    exportUsers();
}

// إضافة تأثيرات تفاعلية
document.addEventListener('DOMContentLoaded', function() {
    // إضافة تأثير hover للصفوف
    const rows = document.querySelectorAll('#usersTable tbody tr');
    rows.forEach(row => {
        row.addEventListener('mouseenter', function() {
            this.style.backgroundColor = '#f8f9fa';
        });
        row.addEventListener('mouseleave', function() {
            this.style.backgroundColor = '';
        });
    });
});