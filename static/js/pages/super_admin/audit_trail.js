var __M = window.__M || [];

export function refreshAuditLogs() {
    location.reload();
}

export function exportAuditLogs() {
    var csvContent = "data:text/csv;charset=utf-8,"
        + window.__M0__.map(function(l) {
            var ts = l.timestamp ? l.timestamp : "\u063a\u064a\u0631 \u0645\u062d\u062f\u062f";
            var user = l.user ? l.user.full_name : "\u063a\u064a\u0631 \u0645\u062d\u062f\u062f";
            return ts + "," + user + "," + l.action + "," + (l.entity_type || "\u063a\u064a\u0631 \u0645\u062d\u062f\u062f") + "," + (l.description || "\u0644\u0627 \u064a\u0648\u062c\u062f \u062a\u0641\u0627\u0635\u064a\u0644") + "," + l.status + "\n";
        }).join("");

    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", "audit_logs_" + new Date().toISOString().split('T')[0] + ".csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

export function applyFilters() {

    const form = document.getElementById('auditFiltersForm');
    const formData = new FormData(form);

    const filters = {};
    for (let [key, value] of formData.entries()) {
        if (value) filters[key] = value;
    }

    Swal.fire({ title: 'تطبيق التصفية', text: 'تم تطبيق التصفية', icon: 'success' });
}

export function clearFilters() {

    document.getElementById('auditFiltersForm').reset();
    Swal.fire({ title: 'تم', text: 'تم مسح التصفية', icon: 'success' });
}

export function filterLogs(status, e) {
    const rows = document.querySelectorAll('#auditLogsTable tbody tr');

    rows.forEach(row => {
        if (status === 'all' || row.dataset.status === status) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });

    document.querySelectorAll('.btn-outline-primary, .btn-outline-success, .btn-outline-warning, .btn-outline-danger').forEach(btn => {
        btn.classList.remove('active');
    });

    if (e) e.target.classList.add('active');
}

export function viewLogDetails(logId) {
    Swal.fire({ title: 'تفاصيل السجل', text: 'عرض تفاصيل السجل: ' + logId, icon: 'info' });
}

export function exportLog(logId) {
    Swal.fire({ title: 'تصدير', text: 'تصدير السجل: ' + logId, icon: 'info' });
}

export function generateAuditReport() {
    Swal.fire({ title: 'إنشاء تقرير', text: 'إنشاء تقرير التدقيق', icon: 'info' });
}

export function exportAllLogs() {

    exportAuditLogs();
}

export function cleanOldLogs() {
    Swal.fire({
        title: 'تأكيد',
        text: 'هل تريد تنظيف السجلات القديمة (أكثر من 90 يوم)؟',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'نعم، تنظيف',
        cancelButtonText: 'إلغاء'
    }).then((r) => { if (r.isConfirmed) { Swal.fire({ title: 'تم', text: 'تم تنظيف السجلات القديمة', icon: 'success' }); } });
}

export function viewAuditSettings() {
    Swal.fire({ title: 'إعدادات التدقيق', text: 'عرض إعدادات التدقيق', icon: 'info' });
}

document.addEventListener('DOMContentLoaded', function() {

    const rows = document.querySelectorAll('#auditLogsTable tbody tr');
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
if (typeof exportLog !== "undefined") window.exportLog = exportLog;
if (typeof viewAuditSettings !== "undefined") window.viewAuditSettings = viewAuditSettings;
if (typeof refreshAuditLogs !== "undefined") window.refreshAuditLogs = refreshAuditLogs;
if (typeof exportAuditLogs !== "undefined") window.exportAuditLogs = exportAuditLogs;
if (typeof viewLogDetails !== "undefined") window.viewLogDetails = viewLogDetails;
if (typeof cleanOldLogs !== "undefined") window.cleanOldLogs = cleanOldLogs;
if (typeof generateAuditReport !== "undefined") window.generateAuditReport = generateAuditReport;
if (typeof clearFilters !== "undefined") window.clearFilters = clearFilters;
if (typeof exportAllLogs !== "undefined") window.exportAllLogs = exportAllLogs;
if (typeof filterLogs !== "undefined") window.filterLogs = filterLogs;
if (typeof applyFilters !== "undefined") window.applyFilters = applyFilters;
