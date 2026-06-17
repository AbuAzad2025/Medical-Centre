var __M = window.__M || [];
// حل حالة الطوارئ
    function resolveEmergency() {
        Swal.fire({
            title: 'حل الحالة',
            text: 'هل أنت متأكد من حل هذه الحالة؟',
            icon: 'warning',
            showCancelButton: true,
            confirmButtonText: 'تأكيد',
            cancelButtonText: 'إلغاء'
        }).then((res) => {
            if (res.isConfirmed) {
                fetch(__M0__, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({})
                })
                .then(r => r.json())
                .then(d => {
                    if (d.success) {
                        Swal.fire({ title: 'تم', text: 'تم حل الحالة بنجاح', icon: 'success' }).then(() => { location.reload(); });
                    } else {
                        Swal.fire({ title: 'خطأ', text: (d.message || 'حدث خطأ أثناء الحل'), icon: 'error' });
                    }
                })
                .catch(() => Swal.fire({ title: 'خطأ', text: 'تعذر الاتصال بالخادم', icon: 'error' }));
            }
        });
    }
    
    // نقل حالة الطوارئ
    function transferEmergency() {
        Swal.fire({
            title: 'نقل الحالة',
            text: 'أدخل ملاحظات النقل (اختياري)',
            icon: 'question',
            input: 'textarea',
            inputPlaceholder: 'ملاحظات النقل',
            showCancelButton: true,
            confirmButtonText: 'نقل',
            cancelButtonText: 'إلغاء'
        }).then((res) => {
            if (res.isConfirmed) {
                const transferNotes = res.value || '';
                fetch(__M1__, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ transfer_notes: transferNotes })
                })
                .then(r => r.json())
                .then(d => {
                    if (d.success) {
                        Swal.fire({ title: 'تم النقل', text: 'تم نقل الحالة بنجاح', icon: 'success' }).then(() => { location.reload(); });
                    } else {
                        Swal.fire({ title: 'خطأ', text: (d.message || 'حدث خطأ أثناء النقل'), icon: 'error' });
                    }
                })
                .catch(() => Swal.fire({ title: 'خطأ', text: 'تعذر الاتصال بالخادم', icon: 'error' }));
            }
        });
    }
    
    // التحقق من صحة البيانات
    document.getElementById('emergencyForm').addEventListener('submit', function(e) {
        const requiredFields = ['patient_id', 'doctor_id', 'emergency_date', 'emergency_time', 'chief_complaint'];
        let isValid = true;
        
        requiredFields.forEach(field => {
            const input = document.querySelector(`[name="${field}"]`);
            if (!input.value.trim()) {
                input.classList.add('is-invalid');
                isValid = false;
            } else {
                input.classList.remove('is-invalid');
            }
        });
        
        if (!isValid) {
            e.preventDefault();
            Swal.fire({ title: 'حقول مطلوبة', text: 'يرجى ملء جميع الحقول المطلوبة', icon: 'warning' });
        }
    });
    
    // تتبع التغييرات
    let originalData = {};
    const form = document.getElementById('emergencyForm');
    
    // حفظ البيانات الأصلية
    document.addEventListener('DOMContentLoaded', function() {
        const inputs = form.querySelectorAll('input, select, textarea');
        inputs.forEach(input => {
            originalData[input.name] = input.value;
        });
    });
    
    // التحقق من التغييرات
    form.addEventListener('submit', function(e) {
        let hasChanges = false;
        const inputs = form.querySelectorAll('input, select, textarea');
        
        inputs.forEach(input => {
            if (originalData[input.name] !== input.value) {
                hasChanges = true;
            }
        });
        
        if (!hasChanges) {
            e.preventDefault();
            Swal.fire({ title: 'لا تغييرات', text: 'لم يتم إجراء أي تغييرات', icon: 'info' });
            return false;
        }
    });
