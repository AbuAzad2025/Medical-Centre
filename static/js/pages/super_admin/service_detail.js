function activateService(serviceId) {
    Swal.fire({
        title: 'تأكيد',
        text: 'هل أنت متأكد من تفعيل هذه الخدمة؟',
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: 'نعم',
        cancelButtonText: 'إلغاء'
    }).then((result) => {
        if (result.isConfirmed) {
            fetch(((window.API_ROUTES && window.API_ROUTES.activate_service) || '/super-admin/activate-service/0').replace('/0', '/' + serviceId), {
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
                    Swal.fire({ title: 'خطأ', text: 'حدث خطأ في تفعيل الخدمة', icon: 'error' });
                }
            })
            .catch(() => Swal.fire({ title: 'خطأ', text: 'فشل الاتصال بالخادم', icon: 'error' }));
        }
    });
}

function deactivateService(serviceId) {
    Swal.fire({
        title: 'تأكيد',
        text: 'هل أنت متأكد من إلغاء تفعيل هذه الخدمة؟',
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: 'نعم',
        cancelButtonText: 'إلغاء'
    }).then((result) => {
        if (result.isConfirmed) {
            fetch(((window.API_ROUTES && window.API_ROUTES.deactivate_service) || '/super-admin/deactivate-service/0').replace('/0', '/' + serviceId), {
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
                    Swal.fire({ title: 'خطأ', text: 'حدث خطأ في إلغاء تفعيل الخدمة', icon: 'error' });
                }
            })
            .catch(() => Swal.fire({ title: 'خطأ', text: 'فشل الاتصال بالخادم', icon: 'error' }));
        }
    });
}
