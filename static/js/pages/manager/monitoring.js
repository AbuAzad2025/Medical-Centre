var __M = window.__M || [];
function refreshMonitoring() {
    location.reload();
}

function exportMonitoringReport() {
    const reportData = {
        timestamp: new Date().toISOString(),
        units: __M0__,
        performance: {
            response_rate: 95,
            uptime: 99.9,
            memory_usage: 75,
            disk_usage: 60
        }
    };
    
    const csvContent = "data:text/csv;charset=utf-8," 
        + "الوحدة,الحالة,الإحصائيات\n"
        + "الاستقبال,نشط,' + (' + __M1__ + ' || 0) + '\n"
        + "الطبيب,نشط,' + (' + __M2__ + ' || 0) + '\n"
        + "الطوارئ,نشط,' + (' + __M3__ + ' || 0) + '\n"
        + "المختبر,نشط,' + (' + __M4__ + ' || 0) + '\n"
        + "الأشعة,نشط,' + (' + __M5__ + ' || 0) + '\n"
        + "المحاسبة,نشط,' + (' + __M6__ + ' || 0) + '\n";
    
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", "monitoring_report_" + new Date().toISOString().split('T')[0] + ".csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

function viewUnitDetails(unitKey) {
    Swal.fire({ title: 'تفاصيل الوحدة', text: 'عرض تفاصيل الوحدة: ' + unitKey, icon: 'info' });
}

function refreshUnit(unitKey) {
    Swal.fire({ title: 'تحديث', text: 'تحديث الوحدة: ' + unitKey, icon: 'info' });
}

function clearLogs() {
    Swal.fire({
        title: 'تأكيد',
        text: 'هل تريد مسح جميع السجلات؟',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'نعم',
        cancelButtonText: 'إلغاء'
    }).then((r) => { if (r.isConfirmed) { Swal.fire({ title: 'تم', text: 'تم مسح السجلات', icon: 'success' }); } });
}

function exportLogs() {
    Swal.fire({ title: 'تم', text: 'تم تصدير السجلات', icon: 'success' });
}

// تحديث تلقائي كل دقيقة
setInterval(function() {
    // تحديث حالة الوحدات
    fetch(__M7__ + '?ajax=true')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // تحديث البيانات في الصفحة
                updateUnitStatus(data.units_status);
            }
        })
        .catch(error => {
            console.error('Error updating monitoring data:', error);
        });
}, 60000); // دقيقة واحدة

function updateUnitStatus(unitsStatus) {
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
