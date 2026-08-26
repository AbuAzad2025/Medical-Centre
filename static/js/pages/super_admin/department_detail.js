const csrfToken = (document.querySelector('meta[name="csrf-token"]') || {}).content;

function activateDepartment(deptId) {
    Swal.fire({
        title: 'تأكيد',
        text: 'هل أنت متأكد من تفعيل هذا القسم؟',
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: 'نعم',
        cancelButtonText: 'إلغاء'
    }).then((result) => {
        if (result.isConfirmed) {
            fetch(((window.API_ROUTES && window.API_ROUTES.activate_department) || '/super-admin/activate-department/0').replace('/0', '/' + deptId), {
                method: 'POST',
                headers: Object.assign({ 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' }, csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
                credentials: 'same-origin'
            })
            .then(response => {
                if (!response.ok) throw new Error('http_' + response.status);
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    location.reload();
                }
            })
            .catch(() => Swal.fire({ title: 'خطأ', text: 'فشل الاتصال بالخادم', icon: 'error' }));
        }
    });
}

function deactivateDepartment(deptId) {
    Swal.fire({
        title: 'تأكيد',
        text: 'هل أنت متأكد من إلغاء تفعيل هذا القسم؟',
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: 'نعم',
        cancelButtonText: 'إلغاء'
    }).then((result) => {
        if (result.isConfirmed) {
            fetch(((window.API_ROUTES && window.API_ROUTES.deactivate_department) || '/super-admin/deactivate-department/0').replace('/0', '/' + deptId), {
                method: 'POST',
                headers: Object.assign({ 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' }, csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
                credentials: 'same-origin'
            })
            .then(response => {
                if (!response.ok) throw new Error('http_' + response.status);
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    location.reload();
                }
            })
            .catch(() => Swal.fire({ title: 'خطأ', text: 'فشل الاتصال بالخادم', icon: 'error' }));
        }
    });
}
