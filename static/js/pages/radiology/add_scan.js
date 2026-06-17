// تعيين التاريخ الحالي كقيمة افتراضية
document.addEventListener('DOMContentLoaded', function() {
    const today = new Date().toISOString().split('T')[0];
    document.querySelector('input[name="scan_date"]').value = today;
});
