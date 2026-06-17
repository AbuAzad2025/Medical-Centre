var __M = window.__M || [];
const __csrfToken = (document.querySelector('meta[name="csrf-token"]') || {}).content || '';

// بدء العلاج
function startTreatment(visitId) {
    Swal.fire({
        title: 'بدء العلاج',
        text: 'هل تريد بدء علاج هذه الحالة؟',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'بدء',
        cancelButtonText: 'إلغاء'
    }).then((res) => {
        if (res.isConfirmed) {
            fetch(`__M0__`.replace('0', visitId), {
                method: 'POST',
                headers: __csrfToken ? { 'X-CSRFToken': __csrfToken } : {},
                body: new FormData()
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    Swal.fire({ title: 'تم البدء', text: 'تم بدء العلاج بنجاح', icon: 'success' }).then(() => { location.reload(); });
                } else {
                    Swal.fire({ title: 'خطأ', text: (data.message || 'حدث خطأ في بدء العلاج'), icon: 'error' });
                }
            })
            .catch(error => {
                Swal.fire({ title: 'خطأ', text: 'حدث خطأ في بدء العلاج', icon: 'error' });
            });
        }
    });
}

// إنهاء الزيارة
function completeVisit(visitId) {
    Swal.fire({
        title: 'إنهاء الحالة',
        text: 'هل تريد إنهاء هذه الحالة وإرجاعها للاستقبال؟',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'إنهاء',
        cancelButtonText: 'إلغاء',
        input: 'textarea',
        inputPlaceholder: 'ملاحظات الطوارئ (اختياري)'
    }).then((res) => {
        if (res.isConfirmed) {
            const notes = res.value || '';
            fetch(`__M1__`.replace('0', visitId), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...( __csrfToken ? { 'X-CSRFToken': __csrfToken } : {} )
                },
                body: JSON.stringify({ notes })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    Swal.fire({ title: 'تم الإنهاء', text: 'تم إنهاء الحالة وإرجاعها للاستقبال', icon: 'success' }).then(() => { location.reload(); });
                } else {
                    Swal.fire({ title: 'خطأ', text: (data.message || 'حدث خطأ في إنهاء الحالة'), icon: 'error' });
                }
            })
            .catch(error => {
                Swal.fire({ title: 'خطأ', text: 'حدث خطأ في إنهاء الحالة', icon: 'error' });
            });
        }
    });
}
