function generateReport() {
    Swal.fire({ title: 'تقرير', text: 'إنشاء تقرير جديد', icon: 'info' });
}

function exportAllReports() {
    Swal.fire({ title: 'تصدير', text: 'تصدير جميع التقارير', icon: 'info' });
}

function viewPatientReports() {
    Swal.fire({ title: 'عرض', text: 'عرض تقارير المرضى', icon: 'info' });
}

function viewFinancialReports() {
    Swal.fire({ title: 'عرض', text: 'عرض التقارير المالية', icon: 'info' });
}

function viewDoctorReports() {
    Swal.fire({ title: 'عرض', text: 'عرض تقارير الأطباء', icon: 'info' });
}

function viewAnalyticalReports() {
    Swal.fire({ title: 'عرض', text: 'عرض التقارير التحليلية', icon: 'info' });
}

function generateDailyReport() {
    Swal.fire({ title: 'تقرير', text: 'إنشاء تقرير يومي', icon: 'info' });
}

function generateWeeklyReport() {
    Swal.fire({ title: 'تقرير', text: 'إنشاء تقرير أسبوعي', icon: 'info' });
}

function generateMonthlyReport() {
    Swal.fire({ title: 'تقرير', text: 'إنشاء تقرير شهري', icon: 'info' });
}

function generateCustomReport() {
    // إنشاء تقرير مخصص
    const form = document.getElementById('customReportForm');
    const formData = new FormData(form);
    
    const reportData = {};
    for (let [key, value] of formData.entries()) {
        reportData[key] = value;
    }
    
    if (!reportData.report_type || !reportData.date_from || !reportData.date_to) {
        Swal.fire({ title: 'حقول مطلوبة', text: 'يرجى ملء جميع الحقول المطلوبة', icon: 'warning' });
        return;
    }
    
    Swal.fire({ title: 'تقرير', text: 'إنشاء تقرير مخصص: ' + JSON.stringify(reportData), icon: 'info' });
}

function filterReports(filter) {
    const rows = document.querySelectorAll('#reportsTable tbody tr');
    
    rows.forEach(row => {
        if (filter === 'all') {
            row.style.display = '';
        } else if (filter === 'recent') {
            // تصفية التقارير الحديثة
            row.style.display = '';
        } else if (filter === 'favorite') {
            // تصفية التقارير المفضلة
            row.style.display = '';
        }
    });
    
    // تحديث أزرار التصفية
    document.querySelectorAll('.btn-outline-primary, .btn-outline-success, .btn-outline-warning').forEach(btn => {
        btn.classList.remove('active');
    });
    
    event.target.classList.add('active');
}

function viewReport(reportId) {
    Swal.fire({ title: 'عرض تقرير', text: 'عرض التقرير: ' + reportId, icon: 'info' });
}

function downloadReport(reportId) {
    Swal.fire({ title: 'تحميل', text: 'تحميل التقرير: ' + reportId, icon: 'info' });
}

function shareReport(reportId) {
    Swal.fire({ title: 'مشاركة', text: 'مشاركة التقرير: ' + reportId, icon: 'info' });
}

function deleteReport(reportId) {
    Swal.fire({
        title: 'تأكيد',
        text: 'هل تريد حذف هذا التقرير؟',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'نعم',
        cancelButtonText: 'إلغاء'
    }).then((r) => { if (r.isConfirmed) { Swal.fire({ title: 'تم', text: 'تم حذف التقرير: ' + reportId, icon: 'success' }); } });
}

// إضافة تأثيرات تفاعلية
document.addEventListener('DOMContentLoaded', function() {
    // إضافة تأثير hover للصفوف
    const rows = document.querySelectorAll('#reportsTable tbody tr');
    rows.forEach(row => {
        row.addEventListener('mouseenter', function() {
            this.style.backgroundColor = '#f8f9fa';
        });
        row.addEventListener('mouseleave', function() {
            this.style.backgroundColor = '';
        });
    });
});
