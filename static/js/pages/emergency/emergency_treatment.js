var __M = window.__M || [];
document.getElementById('emergencyTreatmentForm').addEventListener('submit', function(e) {
    e.preventDefault();
    
    const formData = new FormData(this);
    const csrfToken = formData.get('csrf_token') || '';
    
    fetch(__M0__, {
        method: 'POST',
        credentials: 'same-origin',
        headers: Object.assign({ 'X-Requested-With': 'XMLHttpRequest' }, csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
        body: formData
    })
    .then(response => {
        if (!response.ok) throw new Error(response.status);
        return response.json();
    })
    .then(data => {
        if (data.success) {
            Swal.fire({ title: 'تم', text: 'تم حفظ العلاج الإسعافي بنجاح', icon: 'success' });
            // إعادة توجيه للطوارئ
            window.location.href = __M1__;
        } else {
            Swal.fire({ title: 'خطأ', text: 'خطأ: ' + (data.error || ''), icon: 'error' });
        }
    })
    .catch(error => {
        /* خطأ: */
        Swal.fire({ title: 'خطأ', text: 'حدث خطأ في حفظ العلاج الإسعافي', icon: 'error' });
    });
});
