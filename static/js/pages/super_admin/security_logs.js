function refreshLogs() {
    location.reload();
}

function exportLogs() {
    const csvContent = "data:text/csv;charset=utf-8," 
        + "الوقت,المستوى,المستخدم,العنوان IP,الحدث,التفاصيل\n"
        + "2024-01-15 10:30:25,CRITICAL,admin,192.168.1.100,محاولة دخول غير مصرح بها,محاولة الوصول إلى صفحة محظورة\n"
        + "2024-01-15 10:25:15,WARNING,user1,192.168.1.101,محاولة دخول فاشلة,كلمة مرور خاطئة\n"
        + "2024-01-15 10:20:05,INFO,doctor1,192.168.1.102,تسجيل دخول ناجح,تم تسجيل الدخول بنجاح\n"
        + "2024-01-15 10:15:30,CRITICAL,unknown,192.168.1.103,هجوم محتمل,محاولة SQL injection\n";
    
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", "security_logs_" + new Date().toISOString().split('T')[0] + ".csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

function filterLogs(level) {
    const rows = document.querySelectorAll('#securityLogsTable tbody tr');
    
    rows.forEach(row => {
        if (level === 'all' || row.dataset.level === level) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
    
    // تحديث أزرار التصفية
    document.querySelectorAll('.btn-outline-primary, .btn-outline-danger, .btn-outline-warning, .btn-outline-info').forEach(btn => {
        btn.classList.remove('active');
    });
    
    event.target.classList.add('active');
}

function viewLogDetails(logId) {
    Swal.fire({ title: 'تفاصيل السجل', text: 'عرض تفاصيل السجل: ' + logId, icon: 'info' });
}

function blockIP() {
    Swal.fire({
        title: 'حظر IP',
        input: 'text',
        inputLabel: 'أدخل عنوان IP للحظر',
        inputPlaceholder: 'مثال: 192.168.1.10',
        showCancelButton: true,
        confirmButtonText: 'حظر',
        cancelButtonText: 'إلغاء',
        inputValidator: (value) => {
            if (!value) return 'يجب إدخال عنوان IP';
        }
    }).then((res) => {
        if (res.isConfirmed) {
            const ip = res.value;
            Swal.fire({ title: 'تم', text: 'تم حظر العنوان IP: ' + ip, icon: 'success' });
        }
    });
}

function resetFailedLogins() {
    Swal.fire({
        title: 'تأكيد',
        text: 'هل تريد إعادة تعيين جميع محاولات الدخول الفاشلة؟',
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: 'نعم',
        cancelButtonText: 'إلغاء'
    }).then((r) => { if (r.isConfirmed) { Swal.fire({ title: 'تم', text: 'تم إعادة تعيين محاولات الدخول الفاشلة', icon: 'success' }); } });
}

function clearLogs() {
    Swal.fire({
        title: 'تأكيد',
        text: 'هل تريد مسح السجلات القديمة (أكثر من 30 يوم)؟',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'نعم، مسح',
        cancelButtonText: 'إلغاء'
    }).then((r) => { if (r.isConfirmed) { Swal.fire({ title: 'تم', text: 'تم مسح السجلات القديمة', icon: 'success' }); } });
}

function exportSecurityReport() {
    Swal.fire({ title: 'تم', text: 'تم تصدير تقرير الأمان', icon: 'success' });
}

// إضافة تأثيرات تفاعلية
document.addEventListener('DOMContentLoaded', function() {
    // إضافة تأثير hover للصفوف
    const rows = document.querySelectorAll('#securityLogsTable tbody tr');
    rows.forEach(row => {
        row.addEventListener('mouseenter', function() {
            this.style.backgroundColor = '#f8f9fa';
        });
        row.addEventListener('mouseleave', function() {
            this.style.backgroundColor = '';
        });
    });
});
