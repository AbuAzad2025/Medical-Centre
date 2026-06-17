// تحديث الصفحة كل 30 ثانية للحالات النشطة
    setInterval(function() {
        if (document.querySelector('.status-active')) {
            location.reload();
        }
    }, 30000);
    
    // فلترة سريعة
    document.querySelectorAll('select[name="priority"], select[name="status"], select[name="doctor_id"], select[name="today"]').forEach(function(select) {
        select.addEventListener('change', function() {
            this.form.submit();
        });
    });
