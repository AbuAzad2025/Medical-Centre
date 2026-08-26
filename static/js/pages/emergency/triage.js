var __M = window.__M || [];
document.getElementById('triageForm').addEventListener('submit', function(e) {
    e.preventDefault();
    
    const formData = new FormData(this);
    
    // جمع العلامات الحيوية
    const vitalSigns = {
        blood_pressure: formData.get('blood_pressure'),
        heart_rate: formData.get('heart_rate'),
        temperature: formData.get('temperature'),
        oxygen_saturation: formData.get('oxygen_saturation'),
        respiratory_rate: formData.get('respiratory_rate'),
        pain_level: formData.get('pain_level')
    };
    
    formData.set('vital_signs', JSON.stringify(vitalSigns));
    
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
            Swal.fire({ title: 'تم', text: 'تم حفظ بيانات الفرز بنجاح', icon: 'success' });
            // إعادة توجيه للطوارئ
            window.location.href = __M1__;
        } else {
            Swal.fire({ title: 'خطأ', text: 'خطأ: ' + (data.error || ''), icon: 'error' });
        }
    })
    .catch(error => {
        /* خطأ: */
        Swal.fire({ title: 'خطأ', text: 'حدث خطأ في حفظ بيانات الفرز', icon: 'error' });
    });
});
