function refreshPage() {
    location.reload();
}

// تحديث تلقائي كل 60 ثانية
setInterval(function() {
    // يمكن إضافة AJAX لتحديث الصفحة بدون إعادة تحميل
}, 60000);
