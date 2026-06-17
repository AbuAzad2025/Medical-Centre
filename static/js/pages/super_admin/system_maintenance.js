function optimizeDatabase() {
    Swal.fire({
        title: 'تأكيد',
        text: 'هل أنت متأكد من تحسين قاعدة البيانات؟ قد يستغرق هذا بعض الوقت.',
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: 'نعم',
        cancelButtonText: 'إلغاء'
    }).then((result) => {
        if (result.isConfirmed) {
            Swal.fire({ title: 'جاري العمل', text: 'جاري تحسين قاعدة البيانات...', icon: 'info' });
        }
    });
}

function forceLogoutAll() {
    Swal.fire({
        title: 'تأكيد',
        text: 'هل أنت متأكد من إجبار جميع المستخدمين على تسجيل الخروج؟',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'نعم',
        cancelButtonText: 'إلغاء'
    }).then((result) => {
        if (result.isConfirmed) {
            Swal.fire({ title: 'تم', text: 'تم إجبار جميع المستخدمين على تسجيل الخروج', icon: 'success' });
        }
    });
}

function refreshLogs() {
    location.reload();
}

function clearLogs() {
    Swal.fire({
        title: 'تأكيد',
        text: 'هل أنت متأكد من مسح سجل النظام؟ لا يمكن التراجع عن هذا الإجراء.',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'نعم، مسح',
        cancelButtonText: 'إلغاء'
    }).then((result) => {
        if (result.isConfirmed) {
            Swal.fire({ title: 'تم', text: 'تم مسح سجل النظام', icon: 'success' });
        }
    });
}

// تحديث الإحصائيات كل 30 ثانية
setInterval(function() {
    // هنا يمكن إضافة AJAX لتحديث الإحصائيات
}, 30000);
