var __M = window.__M || [];
document.getElementById('addStaffForm').addEventListener('submit', function(e) {
    e.preventDefault();
    const userId = document.getElementById('user_id').value;
    
    fetch(`/super-admin/department-staff/__M0__/add`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ user_id: userId })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            location.reload();
        } else {
            Swal.fire({ title: 'خطأ', text: (data.message || 'حدث خطأ'), icon: 'error' });
        }
    })
    .catch(() => Swal.fire({ title: 'خطأ', text: 'فشل الاتصال بالخادم', icon: 'error' }));
});

function removeFromDepartment(userId) {
    Swal.fire({
        title: 'تأكيد',
        text: 'هل أنت متأكد من إزالة هذا الموظف من القسم؟',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'نعم، إزالة',
        cancelButtonText: 'إلغاء'
    }).then((result) => {
        if (result.isConfirmed) {
            fetch(`/super-admin/department-staff/__M1__/remove`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ user_id: userId })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    location.reload();
                } else {
                    Swal.fire({ title: 'خطأ', text: (data.message || 'حدث خطأ'), icon: 'error' });
                }
            })
            .catch(() => Swal.fire({ title: 'خطأ', text: 'فشل الاتصال بالخادم', icon: 'error' }));
        }
    });
}
