if (typeof Chart !== 'undefined') {
  Chart.defaults.plugins.tooltip.rtl = true;
  Chart.defaults.plugins.tooltip.textDirection = 'rtl';
  Chart.defaults.plugins.legend.rtl = true;
  Chart.defaults.plugins.legend.labels.font = Chart.defaults.plugins.legend.labels.font || {};
  Chart.defaults.font.family = "'Cairo', 'Tajawal', sans-serif";
}

export function refreshAnalytics() {
    location.reload();
}

export function exportAnalytics() {
    // Export the real payload that was rendered on the page; never invent data.
    const totals = window.__M1__ || {};
    const visits = (window.__M0__ && window.__M0__.visits) || { labels: [], data: [] };
    const roles = (window.__M0__ && window.__M0__.roles) || { labels: [], data: [] };

    const rows = [
        ['المقياس', 'القيمة'],
        ['إجمالي المستخدمين', totals.total_users ?? ''],
        ['إجمالي المرضى', totals.total_patients ?? ''],
        ['إجمالي الزيارات', totals.total_visits ?? ''],
        ['زيارات اليوم', totals.visits_today ?? ''],
        ['مدفوعات اليوم', totals.payments_today ?? ''],
        ['إجمالي مدفوعات اليوم', totals.payment_amount_today ?? ''],
        ['وصفات طبية اليوم', totals.prescriptions_today ?? ''],
        ['أحداث الأمان اليوم', totals.audit_errors_today ?? ''],
    ];
    visits.labels.forEach((label, i) => rows.push(['زيارة ' + label, visits.data[i] ?? 0]));
    roles.labels.forEach((label, i) => rows.push(['دور ' + label, roles.data[i] ?? 0]));

    const csv = '﻿' + rows
        .map(row => row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(','))
        .join('\r\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', 'analytics_' + new Date().toISOString().split('T')[0] + '.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}

function renderCharts() {
    const payload = window.__M0__ || {};
    const visits = payload.visits || { labels: [], data: [] };
    const roles = payload.roles || { labels: [], data: [] };

    const usageEl = document.getElementById('usageChart');
    if (usageEl && typeof Chart !== 'undefined') {
        new Chart(usageEl.getContext('2d'), {
            type: 'line',
            data: {
                labels: visits.labels,
                datasets: [{
                    label: 'الزيارات',
                    data: visits.data,
                    borderColor: 'rgb(75, 192, 192)',
                    backgroundColor: 'rgba(75, 192, 192, 0.1)',
                    tension: 0.2,
                    fill: true,
                }],
            },
            options: {
                responsive: true,
                plugins: { title: { display: true, text: 'الزيارات خلال آخر 7 أيام' } },
                scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
            },
        });
    }

    const userDistEl = document.getElementById('userDistributionChart');
    if (userDistEl && typeof Chart !== 'undefined') {
        new Chart(userDistEl.getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: roles.labels,
                datasets: [{
                    data: roles.data,
                    backgroundColor: [
                        'rgb(255, 99, 132)',
                        'rgb(54, 162, 235)',
                        'rgb(255, 205, 86)',
                        'rgb(75, 192, 192)',
                        'rgb(153, 102, 255)',
                        'rgb(201, 203, 207)',
                    ],
                }],
            },
            options: {
                responsive: true,
                plugins: { legend: { position: 'bottom' } },
            },
        });
    }
}

document.addEventListener('DOMContentLoaded', renderCharts);

// Backward compatibility
if (typeof exportAnalytics !== "undefined") window.exportAnalytics = exportAnalytics;
if (typeof refreshAnalytics !== "undefined") window.refreshAnalytics = refreshAnalytics;

export {};
