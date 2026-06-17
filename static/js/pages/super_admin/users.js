function swalInfo(message) {
    Swal.fire({
        title: 'معلومة',
        text: message,
        icon: 'info'
    });
    return false;
}

function swalConfirmOnly(e, message) {
    e.preventDefault();
    Swal.fire({
        title: 'تأكيد',
        text: message,
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: 'نعم',
        cancelButtonText: 'إلغاء'
    });
    return false;
}

function deleteUser(userId) {
    Swal.fire({
        title: 'تأكيد',
        text: 'هل أنت متأكد من حذف هذا المستخدم نهائياً؟',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'نعم، حذف',
        cancelButtonText: 'إلغاء'
    }).then((result) => {
        if (result.isConfirmed) {
            fetch(`/super-admin/users/${userId}/delete`, {
                method: 'POST'
            }).then((resp) => {
                if (resp.ok) {
                    location.reload();
                } else {
                    Swal.fire({ title: 'خطأ', text: 'فشل حذف المستخدم', icon: 'error' });
                }
            }).catch(() => {
                Swal.fire({ title: 'خطأ', text: 'حدث خطأ في الاتصال', icon: 'error' });
            });
        }
    });
}

function resetPassword(userId) {
    Swal.fire({
        title: 'تأكيد',
        text: 'هل تريد إعادة تعيين كلمة مرور هذا المستخدم؟',
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: 'نعم',
        cancelButtonText: 'إلغاء'
    }).then((result) => {
        if (result.isConfirmed) {
            fetch(`/super-admin/users/${userId}/reset-password`, {
                method: 'POST'
            }).then(r => r.json()).then(data => {
                if (data.success) {
                    const el = document.getElementById(`temp-pass-${userId}`);
                    el.textContent = data.temp_password;
                    setTimeout(() => { el.textContent = ''; }, 60000);
                    Swal.fire({
                        title: 'تم',
                        text: `كلمة مرور مؤقتة: ${data.temp_password} ستختفي خلال دقيقة.`,
                        icon: 'success'
                    });
                } else {
                    Swal.fire({ title: 'خطأ', text: 'فشل إعادة تعيين كلمة المرور', icon: 'error' });
                }
            }).catch(() => {
                Swal.fire({ title: 'خطأ', text: 'حدث خطأ في الاتصال', icon: 'error' });
            });
        }
    });
}

function filterUsers(status) {
    const rows = document.querySelectorAll('#usersTable tbody tr');
    rows.forEach(row => {
        if (status === 'all' || row.dataset.status === status) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
    document.querySelectorAll('.btn-outline-primary, .btn-outline-success, .btn-outline-warning').forEach(btn => {
        btn.classList.remove('active');
    });
    event.target.classList.add('active');
}

document.addEventListener('DOMContentLoaded', function() {
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
