var __M = window.__M || [];

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
                const csrfEl = document.querySelector('input[name="csrf_token"]') || document.querySelector('meta[name="csrf-token"]');
                const csrfToken = csrfEl ? (csrfEl.value || csrfEl.content || '') : '';
                fetch(__M0__, {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: Object.assign({ 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' }, csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
                    body: JSON.stringify({})
                })
                .then(r => {
                    if (!r.ok) throw new Error(r.status);
                    return r.json();
                })
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
                const csrfEl = document.querySelector('input[name="csrf_token"]') || document.querySelector('meta[name="csrf-token"]');
                const csrfToken = csrfEl ? (csrfEl.value || csrfEl.content || '') : '';
                fetch(__M1__, {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: Object.assign({ 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' }, csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
                    body: JSON.stringify({ transfer_notes: transferNotes })
                })
                .then(r => {
                    if (!r.ok) throw new Error(r.status);
                    return r.json();
                })
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

    var originalData = {};
    var form = document.getElementById('emergencyForm');

    document.addEventListener('DOMContentLoaded', function() {
        var inputs = form.querySelectorAll('input, select, textarea');
        inputs.forEach(function(input) {
            originalData[input.name] = input.value;
        });
    });

    form.addEventListener('submit', function(e) {
        var requiredFields = ['patient_id', 'doctor_id', 'emergency_date', 'emergency_time', 'chief_complaint'];
        var isValid = true;

        requiredFields.forEach(function(field) {
            var input = document.querySelector('[name="' + field + '"]');
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
            return;
        }

        var hasChanges = false;
        var inputs = form.querySelectorAll('input, select, textarea');

        inputs.forEach(function(input) {
            if (originalData[input.name] !== input.value) {
                hasChanges = true;
            }
        });

        if (!hasChanges) {
            e.preventDefault();
            Swal.fire({ title: 'لا تغييرات', text: 'لم يتم إجراء أي تغييرات', icon: 'info' });
        }
    });
