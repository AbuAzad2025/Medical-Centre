function refreshUnits() {
    location.reload();
}

function exportUnitsReport() {
    const csvContent = "data:text/csv;charset=utf-8," 
        + "اسم الوحدة,النوع,المستخدمين,الحالة,آخر نشاط,الإنتاجية\n"
        + "الاستقبال,استقبال,5,نشط,منذ 5 دقائق,85%\n"
        + "الطبيب,طبي,8,نشط,منذ 3 دقائق,92%\n"
        + "الطوارئ,طوارئ,3,نشط,منذ دقيقة,78%\n"
        + "المختبر,مختبر,4,نشط,منذ 7 دقائق,88%\n"
        + "الأشعة,أشعة,2,نشط,منذ 4 دقائق,75%\n"
        + "المحاسب,مالي,3,نشط,منذ 2 دقيقة,90%\n";
    
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", "units_report_" + new Date().toISOString().split('T')[0] + ".csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

function viewUnitDetails(unitName) {
    Swal.fire({ title: 'تفاصيل الوحدة', text: 'عرض تفاصيل الوحدة: ' + unitName, icon: 'info' });
}

function toggleUnit(unitName) {
    Swal.fire({
        title: 'تأكيد',
        text: 'هل تريد تغيير حالة هذه الوحدة؟',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'نعم',
        cancelButtonText: 'إلغاء'
    }).then((r) => { if (r.isConfirmed) { Swal.fire({ title: 'تم', text: 'تم تغيير حالة الوحدة: ' + unitName, icon: 'success' }).then(() => { location.reload(); }); } });
}

function configureUnit(unitName) {
    Swal.fire({ title: 'إعدادات', text: 'إعدادات الوحدة: ' + unitName, icon: 'info' });
}

function restartUnit(unitName) {
    Swal.fire({
        title: 'تأكيد',
        text: 'هل تريد إعادة تشغيل هذه الوحدة؟',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'نعم',
        cancelButtonText: 'إلغاء'
    }).then((r) => { if (r.isConfirmed) { Swal.fire({ title: 'تم', text: 'تم إعادة تشغيل الوحدة: ' + unitName, icon: 'success' }); } });
}

function filterUnits(status) {
    const rows = document.querySelectorAll('#unitsTable tbody tr');
    
    rows.forEach(row => {
        if (status === 'all' || row.dataset.status === status) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
    
    // تحديث أزرار التصفية
    document.querySelectorAll('.btn-outline-primary, .btn-outline-success, .btn-outline-danger').forEach(btn => {
        btn.classList.remove('active');
    });
    
    event.target.classList.add('active');
}

function bulkActivate() {
    Swal.fire({
        title: 'تأكيد',
        text: 'هل تريد تفعيل جميع الوحدات؟',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'نعم',
        cancelButtonText: 'إلغاء'
    }).then((r) => { if (r.isConfirmed) { Swal.fire({ title: 'تم', text: 'تم تفعيل جميع الوحدات', icon: 'success' }).then(() => { location.reload(); }); } });
}

function bulkDeactivate() {
    Swal.fire({
        title: 'تأكيد',
        text: 'هل تريد تعطيل جميع الوحدات؟',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'نعم',
        cancelButtonText: 'إلغاء'
    }).then((r) => { if (r.isConfirmed) { Swal.fire({ title: 'تم', text: 'تم تعطيل جميع الوحدات', icon: 'success' }).then(() => { location.reload(); }); } });
}

function bulkRestart() {
    Swal.fire({
        title: 'تأكيد',
        text: 'هل تريد إعادة تشغيل جميع الوحدات؟',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'نعم',
        cancelButtonText: 'إلغاء'
    }).then((r) => { if (r.isConfirmed) { Swal.fire({ title: 'تم', text: 'تم إعادة تشغيل جميع الوحدات', icon: 'success' }).then(() => { location.reload(); }); } });
}

function bulkExport() {
    // تصدير تقرير الوحدات
    exportUnitsReport();
}

// إضافة تأثيرات تفاعلية
document.addEventListener('DOMContentLoaded', function() {
    // إضافة تأثير hover للصفوف
    const rows = document.querySelectorAll('#unitsTable tbody tr');
    rows.forEach(row => {
        row.addEventListener('mouseenter', function() {
            this.style.backgroundColor = '#f8f9fa';
        });
        row.addEventListener('mouseleave', function() {
            this.style.backgroundColor = '';
        });
    });
});
