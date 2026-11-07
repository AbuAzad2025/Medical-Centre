export function generateReport() {
    Swal.fire({ title: 'تقرير', text: 'إنشاء تقرير جديد', icon: 'info' });
}

export function exportAllReports() {
    Swal.fire({ title: 'تصدير', text: 'تصدير جميع التقارير', icon: 'info' });
}

export function viewPatientReports() {
    Swal.fire({ title: 'عرض', text: 'عرض تقارير المرضى', icon: 'info' });
}

export function viewFinancialReports() {
    Swal.fire({ title: 'عرض', text: 'عرض التقارير المالية', icon: 'info' });
}

export function viewDoctorReports() {
    Swal.fire({ title: 'عرض', text: 'عرض تقارير الأطباء', icon: 'info' });
}

export function viewAnalyticalReports() {
    Swal.fire({ title: 'عرض', text: 'عرض التقارير التحليلية', icon: 'info' });
}

export function generateDailyReport() {
    Swal.fire({ title: 'تقرير', text: 'إنشاء تقرير يومي', icon: 'info' });
}

export function generateWeeklyReport() {
    Swal.fire({ title: 'تقرير', text: 'إنشاء تقرير أسبوعي', icon: 'info' });
}

export function generateMonthlyReport() {
    Swal.fire({ title: 'تقرير', text: 'إنشاء تقرير شهري', icon: 'info' });
}

export function generateCustomReport() {

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

export function filterReports(filter, e) {
    const rows = document.querySelectorAll('#reportsTable tbody tr');

    rows.forEach(row => {
        if (filter === 'all') {
            row.style.display = '';
        } else if (filter === 'recent') {

            row.style.display = '';
        } else if (filter === 'favorite') {

            row.style.display = '';
        }
    });

    document.querySelectorAll('.btn-outline-primary, .btn-outline-success, .btn-outline-warning').forEach(btn => {
        btn.classList.remove('active');
    });

    if (e) e.target.classList.add('active');
}

export function viewReport(reportId) {
    Swal.fire({ title: 'عرض تقرير', text: 'عرض التقرير: ' + reportId, icon: 'info' });
}

export function downloadReport(reportId) {
    Swal.fire({ title: 'تحميل', text: 'تحميل التقرير: ' + reportId, icon: 'info' });
}

export function shareReport(reportId) {
    Swal.fire({ title: 'مشاركة', text: 'مشاركة التقرير: ' + reportId, icon: 'info' });
}

export function deleteReport(reportId) {
    Swal.fire({
        title: 'تأكيد',
        text: 'هل تريد حذف هذا التقرير؟',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'نعم',
        cancelButtonText: 'إلغاء'
    }).then((r) => { if (r.isConfirmed) { Swal.fire({ title: 'تم', text: 'تم حذف التقرير: ' + reportId, icon: 'success' }); } });
}

document.addEventListener('DOMContentLoaded', function() {

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


// Backward compatibility
if (typeof downloadReport !== "undefined") window.downloadReport = downloadReport;
if (typeof filterReports !== "undefined") window.filterReports = filterReports;
if (typeof generateCustomReport !== "undefined") window.generateCustomReport = generateCustomReport;
if (typeof shareReport !== "undefined") window.shareReport = shareReport;
if (typeof deleteReport !== "undefined") window.deleteReport = deleteReport;
if (typeof exportAllReports !== "undefined") window.exportAllReports = exportAllReports;
if (typeof generateReport !== "undefined") window.generateReport = generateReport;
if (typeof generateDailyReport !== "undefined") window.generateDailyReport = generateDailyReport;
if (typeof viewReport !== "undefined") window.viewReport = viewReport;
if (typeof generateMonthlyReport !== "undefined") window.generateMonthlyReport = generateMonthlyReport;
if (typeof viewDoctorReports !== "undefined") window.viewDoctorReports = viewDoctorReports;
if (typeof viewPatientReports !== "undefined") window.viewPatientReports = viewPatientReports;
if (typeof viewAnalyticalReports !== "undefined") window.viewAnalyticalReports = viewAnalyticalReports;
if (typeof viewFinancialReports !== "undefined") window.viewFinancialReports = viewFinancialReports;
if (typeof generateWeeklyReport !== "undefined") window.generateWeeklyReport = generateWeeklyReport;
