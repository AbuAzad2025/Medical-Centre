var __M = window.__M || [];
export function refreshMonitoring() {
    location.reload();
}

export function exportMonitoringReport() {
    // Export the real payload the page rendered — never invented figures.
    const units = window.__M0__ || {};
    const perf = window.__M7__ || {};

    const rows = [
        ['الوحدة', 'الحجم'],
    ];
    const countColumn = {
        reception: 'pending_visits',
        doctor: 'in_progress_visits',
        emergency: 'emergency_visits',
        lab: 'lab_requests',
        radiology: 'radiology_requests',
        accountant: 'open_invoices',
    };
    Object.keys(units).forEach(key => {
        const col = countColumn[key];
        const val = col && units[key] ? units[key][col] : '';
        rows.push([(units[key] && units[key].name) || key, val]);
    });
    if (perf.cpu_percent !== undefined) rows.push(['استهلاك المعالج %', Math.round(perf.cpu_percent)]);
    if (perf.memory_percent !== undefined) rows.push(['استهلاك الذاكرة %', Math.round(perf.memory_percent)]);
    if (perf.disk_percent !== undefined) rows.push(['استهلاك القرص %', Math.round(perf.disk_percent)]);
    if (perf.uptime_hours !== undefined) rows.push(['وقت التشغيل (ساعة)', perf.uptime_hours]);

    const csv = rows
        .map(r => r.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(','))
        .join('\r\n');
    const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', 'monitoring_report_' + new Date().toISOString().split('T')[0] + '.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}

export function viewUnitDetails(unitKey) {
    const units = window.__M0__ || {};
    const unit = units[unitKey];
    if (!unit) {
        Swal.fire({ title: 'تفاصيل الوحدة', text: 'لا توجد بيانات لهذه الوحدة', icon: 'info' });
        return;
    }
    const countColumn = {
        reception: 'pending_visits',
        doctor: 'in_progress_visits',
        emergency: 'emergency_visits',
        lab: 'lab_requests',
        radiology: 'radiology_requests',
        accountant: 'open_invoices',
    };
    const col = countColumn[unitKey];
    const val = col ? unit[col] : '-';
    Swal.fire({
        title: unit.name || unitKey,
        html: '<p class="text-start mb-1">الحالة: ' + (unit.status === 'active' ? 'نشطة' : 'معطّلة') + '</p>'
            + '<p class="text-start mb-0">القيمة الحالية: <strong>' + val + '</strong></p>',
        icon: 'info',
    });
}

export function refreshUnit() {
    location.reload();
}

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
if (typeof refreshMonitoring !== "undefined") window.refreshMonitoring = refreshMonitoring;
if (typeof exportMonitoringReport !== "undefined") window.exportMonitoringReport = exportMonitoringReport;
if (typeof viewUnitDetails !== "undefined") window.viewUnitDetails = viewUnitDetails;
if (typeof updateUnitStatus !== "undefined") window.updateUnitStatus = updateUnitStatus;
if (typeof refreshUnit !== "undefined") window.refreshUnit = refreshUnit;
