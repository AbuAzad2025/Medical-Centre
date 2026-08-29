if (typeof Chart !== 'undefined') {
  Chart.defaults.plugins.tooltip.rtl = true;
  Chart.defaults.plugins.tooltip.textDirection = 'rtl';
  Chart.defaults.plugins.legend.rtl = true;
  Chart.defaults.plugins.legend.labels.font = Chart.defaults.plugins.legend.labels.font || {};
  Chart.defaults.font.family = "'Cairo', 'Tajawal', sans-serif";
}

function refreshAnalytics() {
    location.reload();
}

function exportAnalytics() {
    const csvContent = "data:text/csv;charset=utf-8,"
        + "المؤشر,القيمة,التغيير\n"
        + "إجمالي المستخدمين,1234,+12%\n"
        + "النشاط اليومي,89%,+5%\n"
        + "الأداء,95%,+2%\n"
        + "الأخطاء,23,-15%\n";

    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", "analytics_" + new Date().toISOString().split('T')[0] + ".csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

document.addEventListener('DOMContentLoaded', function() {
    const usageEl = document.getElementById('usageChart');
    if (usageEl) {
        const usageCtx = usageEl.getContext('2d');
        new Chart(usageCtx, {
            type: 'line',
            data: {
                labels: ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو'],
                datasets: [{
                    label: 'المستخدمين النشطين',
                    data: [120, 150, 180, 200, 220, 250],
                    borderColor: 'rgb(75, 192, 192)',
                    tension: 0.1
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'اتجاهات الاستخدام الشهرية'
                    }
                }
            }
        });
    }

    const userDistEl = document.getElementById('userDistributionChart');
    if (userDistEl) {
        const userDistCtx = userDistEl.getContext('2d');
        new Chart(userDistCtx, {
            type: 'doughnut',
            data: {
                labels: ['الأطباء', 'الاستقبال', 'المختبر', 'الأشعة', 'المحاسبة'],
                datasets: [{
                    data: [30, 25, 20, 15, 10],
                    backgroundColor: [
                        'rgb(255, 99, 132)',
                        'rgb(54, 162, 235)',
                        'rgb(255, 205, 86)',
                        'rgb(75, 192, 192)',
                        'rgb(153, 102, 255)'
                    ]
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'توزيع المستخدمين حسب الدور'
                    }
                }
            }
        });
    }
});
