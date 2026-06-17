var __M = window.__M || [];
document.getElementById('visitSummaryForm').addEventListener('submit', function(e) {
    e.preventDefault();
    
    const formData = new FormData(this);
    
    fetch(__M0__, {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            Swal.fire({
                title: 'تم',
                text: 'تم حفظ ملخص الزيارة بنجاح',
                icon: 'success'
            }).then(() => {
                window.location.href = __M1__;
            });
        } else {
            Swal.fire({
                title: 'خطأ',
                text: 'خطأ: ' + (data.message || ''),
                icon: 'error'
            });
        }
    })
    .catch(error => {
        console.error('Error:', error);
        Swal.fire({
            title: 'خطأ',
            text: 'حدث خطأ في حفظ ملخص الزيارة',
            icon: 'error'
        });
    });
});
