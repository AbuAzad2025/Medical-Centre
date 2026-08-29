var __M = window.__M || [];
const csrfToken = (document.querySelector('meta[name="csrf-token"]') || {}).content;
const addStaffFormEl = document.getElementById('addStaffForm');
if (addStaffFormEl) {
    addStaffFormEl.addEventListener('submit', function(e) {
        e.preventDefault();
        const userId = document.getElementById('user_id').value;
        
        fetch((window.API_ROUTES && window.API_ROUTES.add_department_staff) ? window.API_ROUTES.add_department_staff.replace('/0', '/' + __M0__) : `/super-admin/department-staff/${__M0__}/add`, {
            method: 'POST',
            headers: Object.assign({ 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' }, csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
            credentials: 'same-origin',
            body: JSON.stringify({ user_id: userId })
        })
        .then(response => {
            if (!response.ok) throw new Error('http_' + response.status);
            return response.json();
        })
        .then(data => {
            if (data.success) {
                location.reload();
            } else {
                Swal.fire({ title: 'خطأ', text: (data.message || 'حدث خطأ'), icon: 'error' });
            }
        })
        .catch(() => Swal.fire({ title: 'خطأ', text: 'فشل الاتصال بالخادم', icon: 'error' }));
    });
}

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
            fetch((window.API_ROUTES && window.API_ROUTES.remove_department_staff) ? window.API_ROUTES.remove_department_staff.replace('/0', '/' + __M1__) : `/super-admin/department-staff/${__M1__}/remove`, {
                method: 'POST',
                headers: Object.assign({ 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' }, csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
                credentials: 'same-origin',
                body: JSON.stringify({ user_id: userId })
            })
            .then(response => {
                if (!response.ok) throw new Error('http_' + response.status);
                return response.json();
            })
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
