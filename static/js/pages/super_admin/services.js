const csrfToken = (document.querySelector('meta[name="csrf-token"]') || {}).content;
const searchInputEl = document.getElementById('searchInput');
if (searchInputEl) {
    searchInputEl.addEventListener('input', function() {
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
}

export function viewService(serviceId) {
    window.location.href = (window.API_ROUTES && window.API_ROUTES.view_service) ? window.API_ROUTES.view_service.replace('/0', '/' + serviceId) : `/super-admin/service/${serviceId}`;
}

export function editService(serviceId) {
    window.location.href = (window.API_ROUTES && window.API_ROUTES.edit_service) ? window.API_ROUTES.edit_service.replace('/0', '/' + serviceId) : `/super-admin/edit-service/${serviceId}`;
}

export function managePricing(serviceId) {
    window.location.href = (window.API_ROUTES && window.API_ROUTES.service_pricing) ? window.API_ROUTES.service_pricing.replace('/0', '/' + serviceId) : `/super-admin/service-pricing/${serviceId}`;
}

export function activateService(serviceId) {
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
                } else {
                    Swal.fire({ title: 'خطأ', text: 'حدث خطأ في تفعيل الخدمة', icon: 'error' });
                }
            })
            .catch(() => Swal.fire({ title: 'خطأ', text: 'فشل الاتصال بالخادم', icon: 'error' }));
        }
    });
}

export function deactivateService(serviceId) {
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
                } else {
                    Swal.fire({ title: 'خطأ', text: 'حدث خطأ في إلغاء تفعيل الخدمة', icon: 'error' });
                }
            })
            .catch(() => Swal.fire({ title: 'خطأ', text: 'فشل الاتصال بالخادم', icon: 'error' }));
        }
    });
}

export function exportServices() {
    window.open((window.API_ROUTES && window.API_ROUTES.export_services) || '/super-admin/export-services', '_blank');
}

const addServiceFormEl = document.getElementById('addServiceForm');
if (addServiceFormEl) {
    addServiceFormEl.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const formData = new FormData(this);
        
        const createUrl = (window.API_ROUTES && window.API_ROUTES.create_service) || '/super-admin/services/create';
        fetch(createUrl, {
            method: 'POST',
            body: formData,
            headers: Object.assign({ 'X-Requested-With': 'XMLHttpRequest' }, csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
            credentials: 'same-origin'
        })
        .then(response => {
            if (!response.ok) throw new Error('http_' + response.status);
            return response.json();
        })
        .then(data => {
            if (data.success) {
                location.reload();
            } else {
                Swal.fire({ title: 'خطأ', text: 'حدث خطأ في إضافة الخدمة: ' + (data.message || ''), icon: 'error' });
            }
        })
        .catch(() => Swal.fire({ title: 'خطأ', text: 'فشل الاتصال بالخادم', icon: 'error' }));
    });
}


// Backward compatibility
if (typeof viewService !== "undefined") window.viewService = viewService;
if (typeof exportServices !== "undefined") window.exportServices = exportServices;
if (typeof editService !== "undefined") window.editService = editService;
if (typeof deactivateService !== "undefined") window.deactivateService = deactivateService;
if (typeof managePricing !== "undefined") window.managePricing = managePricing;
if (typeof activateService !== "undefined") window.activateService = activateService;
