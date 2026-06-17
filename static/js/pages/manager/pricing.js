var __M = window.__M || [];
let serviceModal;

document.addEventListener('DOMContentLoaded', function() {
    serviceModal = new bootstrap.Modal(document.getElementById('serviceModal'));
    
    // Search functionality
    document.getElementById('searchInput').addEventListener('keyup', function() {
        const value = this.value.toLowerCase();
        const rows = document.querySelectorAll('#pricingTable tbody tr');
        
        rows.forEach(row => {
            const text = row.getAttribute('data-search').toLowerCase();
            if (text.includes(value)) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        });
    });
});

function filterServices(category) {
    const rows = document.querySelectorAll('#pricingTable tbody tr');
    rows.forEach(row => {
        if (category === 'all' || row.getAttribute('data-category') === category) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
}

function openAddModal() {
    document.getElementById('serviceForm').reset();
    document.getElementById('serviceId').value = '';
    document.getElementById('serviceModalLabel').innerText = 'إضافة خدمة جديدة';
    document.getElementById('isActive').checked = true;
    document.getElementById('serviceDepartment').value = '';
    document.getElementById('serviceDuration').value = '';
    document.getElementById('serviceMaxDaily').value = '';
    serviceModal.show();
}

function editService(id, data) {
    document.getElementById('serviceId').value = id;
    document.getElementById('serviceCode').value = data.code;
    document.getElementById('serviceName').value = data.name;
    document.getElementById('serviceNameAr').value = data.name_ar || '';
    document.getElementById('serviceCategory').value = data.category;
    document.getElementById('serviceDepartment').value = data.department_id || '';
    document.getElementById('basePrice').value = data.base_price;
    document.getElementById('emergencyPrice').value = data.emergency_price || '';
    document.getElementById('insurancePrice').value = data.insurance_price || '';
    document.getElementById('serviceDuration').value = data.duration || '';
    document.getElementById('serviceMaxDaily').value = data.max_daily || '';
    document.getElementById('serviceDescription').value = data.description || '';
    document.getElementById('isActive').checked = data.is_active;
    
    document.getElementById('serviceModalLabel').innerText = 'تعديل الخدمة';
    serviceModal.show();
}

async function saveService() {
    const id = document.getElementById('serviceId').value;
    const isEdit = !!id;
    
    const data = {
        code: document.getElementById('serviceCode').value,
        name: document.getElementById('serviceName').value,
        name_ar: document.getElementById('serviceNameAr').value,
        category: document.getElementById('serviceCategory').value,
        department_id: document.getElementById('serviceDepartment').value || null,
        base_price: parseFloat(document.getElementById('basePrice').value) || 0,
        emergency_price: parseFloat(document.getElementById('emergencyPrice').value) || null,
        insurance_price: parseFloat(document.getElementById('insurancePrice').value) || null,
        duration: parseInt(document.getElementById('serviceDuration').value) || null,
        max_daily: parseInt(document.getElementById('serviceMaxDaily').value) || null,
        description: document.getElementById('serviceDescription').value,
        is_active: document.getElementById('isActive').checked
    };
    
    if (!data.code || !data.name || !data.name_ar) {
        Swal.fire('خطأ', 'يرجى ملء الحقول المطلوبة', 'error');
        return;
    }
    
    const url = isEdit ? `/manager/api/pricing/services/${id}` : '/manager/api/pricing/services';
    const method = isEdit ? 'PUT' : 'POST';
    
    try {
        const response = await fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': __M0__
            },
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        
        if (result.success) {
            Swal.fire('نجاح', result.message, 'success').then(() => {
                location.reload();
            });
            serviceModal.hide();
        } else {
            Swal.fire('خطأ', result.message, 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        Swal.fire('خطأ', 'حدث خطأ أثناء حفظ البيانات', 'error');
    }
}

async function deleteService(id) {
    const result = await Swal.fire({
        title: 'هل أنت متأكد؟',
        text: "لن تتمكن من التراجع عن هذا الإجراء!",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#d33',
        cancelButtonColor: '#3085d6',
        confirmButtonText: 'نعم، احذفها!',
        cancelButtonText: 'إلغاء'
    });
    
    if (result.isConfirmed) {
        try {
            const response = await fetch(`/manager/api/pricing/services/${id}`, {
                method: 'DELETE',
                headers: {
                    'X-CSRFToken': __M1__
                }
            });
            
            const result = await response.json();
            
            if (result.success) {
                Swal.fire('تم الحذف!', result.message, 'success').then(() => {
                    location.reload();
                });
            } else {
                Swal.fire('خطأ', result.message, 'error');
            }
        } catch (error) {
            console.error('Error:', error);
            Swal.fire('خطأ', 'حدث خطأ أثناء الحذف', 'error');
        }
    }
}
