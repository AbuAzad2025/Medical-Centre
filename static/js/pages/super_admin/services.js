// Search functionality
document.getElementById('searchInput').addEventListener('input', function() {
    const searchTerm = this.value.toLowerCase();
    const table = document.getElementById('servicesTable');
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

// Service management functions
function viewService(serviceId) {
    // عرض تفاصيل الخدمة
    window.location.href = `/super-admin/service/${serviceId}`;
}

function editService(serviceId) {
    // تعديل الخدمة
    window.location.href = `/super-admin/edit-service/${serviceId}`;
}

function managePricing(serviceId) {
    // إدارة تسعير الخدمة
    window.location.href = `/super-admin/service-pricing/${serviceId}`;
}

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
            fetch(`/super-admin/activate-service/${serviceId}`, {
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
            fetch(`/super-admin/deactivate-service/${serviceId}`, {
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

function exportServices() {
    // تصدير الخدمات
    window.open('/super-admin/export-services', '_blank');
}

// Add service form
document.getElementById('addServiceForm').addEventListener('submit', function(e) {
    e.preventDefault();
    
    const formData = new FormData(this);
    
    fetch('/super-admin/services/create', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            location.reload();
        } else {
            Swal.fire({ title: 'خطأ', text: 'حدث خطأ في إضافة الخدمة: ' + (data.message || ''), icon: 'error' });
        }
    })
    .catch(() => Swal.fire({ title: 'خطأ', text: 'فشل الاتصال بالخادم', icon: 'error' }));
});
