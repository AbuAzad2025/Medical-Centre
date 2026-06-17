var __M = window.__M || [];
__M0__


Chart.defaults.font.family = "'Segoe UI', 'Tahoma', sans-serif";
    Chart.defaults.color = '#6c757d';

    const chartData = JSON.parse(document.getElementById('chart-data').textContent);
    const months = chartData.months;
    const tenantGrowth = chartData.tenantGrowth;
    const mrrTrend = chartData.mrrTrend;

    // Main chart: Tenant growth + MRR
    new Chart(document.getElementById('mainChart'), {
        type: 'line',
        data: {
            labels: months,
            datasets: [
                {
                    label: 'العملاء',
                    data: tenantGrowth,
                    borderColor: '#0d6efd',
                    backgroundColor: 'rgba(13, 110, 253, 0.1)',
                    fill: true,
                    tension: 0.4,
                    yAxisID: 'y'
                },
                {
                    label: 'MRR',
                    data: mrrTrend,
                    borderColor: '#198754',
                    backgroundColor: 'rgba(25, 135, 84, 0.05)',
                    fill: false,
                    tension: 0.4,
                    yAxisID: 'y1'
                }
            ]
        },
        options: {
            responsive: true,
            interaction: { mode: 'index', intersect: false },
            plugins: { legend: { position: 'top' } },
            scales: {
                y: { type: 'linear', display: true, position: 'left', title: { display: true, text: 'العملاء' } },
                y1: { type: 'linear', display: true, position: 'right', title: { display: true, text: 'MRR' }, grid: { drawOnChartArea: false } }
            }
        }
    });

    // Status distribution
    new Chart(document.getElementById('statusChart'), {
        type: 'doughnut',
        data: {
            labels: chartData.statusLabels,
            datasets: [{
                data: chartData.statusData,
                backgroundColor: ['#198754', '#ffc107', '#dc3545', '#6c757d', '#0dcaf0']
            }]
        },
        options: {
            responsive: true,
            plugins: { legend: { position: 'bottom', labels: { boxWidth: 12 } } },
            cutout: '65%'
        }
    });

    // Tickets chart
    new Chart(document.getElementById('ticketChart'), {
        type: 'bar',
        data: {
            labels: chartData.ticketLabels,
            datasets: [{
                label: 'التذاكر',
                data: chartData.ticketData,
                backgroundColor: ['#dc3545', '#0d6efd', '#ffc107', '#198754']
            }]
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: { y: { beginAtZero: true } }
        }
    });

    // Sparklines
    function sparkline(id, data, color) {
        const ctx = document.getElementById(id).getContext('2d');
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.map(function(_, i) { return i; }),
                datasets: [{ data: data, borderColor: color, borderWidth: 2, pointRadius: 0, fill: false, tension: 0.4 }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false }, tooltip: { enabled: false } },
                scales: { x: { display: false }, y: { display: false } }
            }
        });
    }
    sparkline('sparkTenants', tenantGrowth, '#0d6efd');
    sparkline('sparkMRR', mrrTrend, '#198754');
    sparkline('sparkChurn', chartData.churnSpark, '#dc3545');
    sparkline('sparkUsers', chartData.userSpark, '#0dcaf0');
