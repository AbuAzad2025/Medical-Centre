var __M = window.__M || [];
__M0__


const d = JSON.parse(document.getElementById('emg-chart-data').textContent);
  function spark(id, data, color) {
    new Chart(document.getElementById(id).getContext('2d'), {
      type: 'line',
      data: { labels: data.map(function(_, i){ return i; }), datasets: [{ data: data, borderColor: color, borderWidth: 2, pointRadius: 0, fill: false, tension: 0.4 }] },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { enabled: false } }, scales: { x: { display: false }, y: { display: false } } }
    });
  }
  spark('sparkToday', d.spark, '#dc3545');
  spark('sparkCompleted', [d.spark[1], d.spark[1]+1, d.spark[1]-1, d.spark[1]+2], '#198754');
  spark('sparkCritical', [d.spark[2], d.spark[2]-1, d.spark[2]+1, d.spark[2]], '#ffc107');
  spark('sparkRx', [d.spark[3], d.spark[3]+1, d.spark[3], d.spark[3]+2], '#0dcaf0');

  new Chart(document.getElementById('emgMainChart'), {
    type: 'bar',
    data: { labels: ['اليوم', 'نشطة', 'مكتملة', 'عاجلة', 'حرجة'], datasets: [{ label: 'الحالات', data: d.mainData, backgroundColor: ['#dc3545', '#0d6efd', '#198754', '#ffc107', '#a52a2a'] }] },
    options: { responsive: true, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }
  });
