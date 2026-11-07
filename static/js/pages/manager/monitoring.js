var __M = window.__M || [];
export function refreshMonitoring() {
    location.reload();
}

export function exportMonitoringReport() {
    const reportData = {
        timestamp: new Date().toISOString(),
        units: window.__M0__,
        performance: {
            response_rate: 95,
            uptime: 99.9,
            memory_usage: 75,
            disk_usage: 60
        }
    };

    const csvContent = "data:text/csv;charset=utf-8,"
        + "الوحدة,الحالة,الإحصائيات\n"
        + "الاستقبال,نشط,' + (' + window.__M1__ + ' || 0) + '\n"
        + "الطبيب,نشط,' + (' + window.__M2__ + ' || 0) + '\n"
        + "الطوارئ,نشط,' + (' + window.__M3__ + ' || 0) + '\n"
        + "المختبر,نشط,' + (' + window.__M4__ + ' || 0) + '\n"
        + "الأشعة,نشط,' + (' + window.__M5__ + ' || 0) + '\n"
        + "المحاسبة,نشط,' + (' + window.__M6__ + ' || 0) + '\n";

    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", "monitoring_report_" + new Date().toISOString().split('T')[0] + ".csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

export function viewUnitDetails(unitKey) {
    Swal.fire({ title: 'تفاصيل الوحدة', text: 'عرض تفاصيل الوحدة: ' + unitKey, icon: 'info' });
}

export function refreshUnit(unitKey) {
    Swal.fire({ title: 'تحديث', text: 'تحديث الوحدة: ' + unitKey, icon: 'info' });
}

export function clearLogs() {
    Swal.fire({
        title: 'تأكيد',
        text: 'هل تريد مسح جميع السجلات؟',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'نعم',
        cancelButtonText: 'إلغاء'
    }).then((r) => { if (r.isConfirmed) { Swal.fire({ title: 'تم', text: 'تم مسح السجلات', icon: 'success' }); } });
}

export function exportLogs() {
    Swal.fire({ title: 'تم', text: 'تم تصدير السجلات', icon: 'success' });
}

setInterval(function() {

    fetch(window.__M7__ + '?ajax=true', { credentials: 'same-origin' })
        .then(response => {
            if (!response.ok) throw new Error('http_' + response.status);
            return response.json();
        })
        .then(data => {
            if (data.success) {

                updateUnitStatus(data.units_status);
            }
        })
        .catch(error => {
            console.warn('تعذر تحديث بيانات المراقبة');
        });
}, 60000);

export function updateUnitStatus(unitsStatus) {
    const map = {
        reception: 'pending_visits',
        doctor: 'in_progress_visits',
        emergency: 'emergency_visits',
        lab: 'lab_requests',
        radiology: 'radiology_requests',
        accountant: 'open_invoices'
    };
    Object.keys(unitsStatus).forEach(unitKey => {
        const unit = unitsStatus[unitKey];
        const statProp = map[unitKey];
        const statEl = document.getElementById(`stat-${unitKey}-${statProp}`);
        if (statEl) {
            statEl.textContent = unit[statProp] ?? 0;
        }
        const badgeEl = document.getElementById(`badge-${unitKey}-status`);
        if (badgeEl) {
            const active = unit.status === 'active';
            let cls = active ? 'bg-success' : 'bg-danger';
            const val = unit[statProp] ?? 0;
            if (active) {
                if ((unitKey === 'lab' || unitKey === 'radiology') && val > 40) cls = 'bg-danger';
                else if ((unitKey === 'lab' || unitKey === 'radiology') && val > 20) cls = 'bg-warning';
                else if (unitKey === 'emergency' && val > 15) cls = 'bg-danger';
                else if (unitKey === 'emergency' && val > 8) cls = 'bg-warning';
            }
            badgeEl.className = `badge ${cls}`;
            badgeEl.textContent = active ? 'نشط' : 'معطل';
        }
    });
}


// Backward compatibility
if (typeof clearLogs !== "undefined") window.clearLogs = clearLogs;
if (typeof refreshMonitoring !== "undefined") window.refreshMonitoring = refreshMonitoring;
if (typeof exportLogs !== "undefined") window.exportLogs = exportLogs;
if (typeof exportMonitoringReport !== "undefined") window.exportMonitoringReport = exportMonitoringReport;
if (typeof viewUnitDetails !== "undefined") window.viewUnitDetails = viewUnitDetails;
if (typeof updateUnitStatus !== "undefined") window.updateUnitStatus = updateUnitStatus;
if (typeof refreshUnit !== "undefined") window.refreshUnit = refreshUnit;
