function setText(id, value, suffix) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = value + (suffix || '');
}

export function updatePerformanceData() {
    fetch((window.API_ROUTES && window.API_ROUTES.performance_metrics) || '/super-admin/api/performance', {
        credentials: 'same-origin',
        headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
    })
        .then(r => r.ok ? r.json() : null)
        .then(data => {
            if (!data || data.success !== true) return;
            if (typeof data.cpu_percent === 'number') setText('cpu-usage', Math.round(data.cpu_percent), '%');
            if (typeof data.memory_percent === 'number') setText('memory-usage', Math.round(data.memory_percent), '%');
            if (typeof data.disk_percent === 'number') setText('disk-usage', Math.round(data.disk_percent), '%');
            if (typeof data.uptime_hours === 'number') setText('uptime', Math.round(data.uptime_hours), '');
            if (typeof data.active_db_connections === 'number') setText('active-db-connections', data.active_db_connections);
            if (typeof data.db_size_mb === 'number') setText('db-size-mb', data.db_size_mb);
            if (typeof data.visits_today === 'number') setText('visits-today', data.visits_today);
            if (typeof data.payments_today === 'number') setText('payments-today', data.payments_today);
            if (typeof data.payment_amount_today === 'number') setText('payment-amount-today', data.payment_amount_today.toFixed(2));
            if (typeof data.prescriptions_today === 'number') setText('prescriptions-today', data.prescriptions_today);
        })
        .catch(() => { /* keep last known values */ });
}

setInterval(updatePerformanceData, 5000);
updatePerformanceData();

// Backward compatibility
if (typeof updatePerformanceData !== "undefined") window.updatePerformanceData = updatePerformanceData;

export {};
