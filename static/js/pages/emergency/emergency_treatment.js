var __M = window.__M || [];
document.getElementById('emergencyTreatmentForm').addEventListener('submit', function(e) {
    e.preventDefault();
    
    const formData = new FormData(this);
    
    fetch(__M0__, {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
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
        console.error('Error:', error);
        Swal.fire({ title: 'خطأ', text: 'حدث خطأ في حفظ العلاج الإسعافي', icon: 'error' });
    });
});
