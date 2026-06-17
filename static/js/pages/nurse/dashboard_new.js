var __M = window.__M || [];
__M0__


const d = JSON.parse(document.getElementById('nurse-chart-data').textContent);
  function spark(id, data, color) {
    new Chart(document.getElementById(id).getContext('2d'), {
      type: 'line',
      data: { labels: data.map(function(_, i){ return i; }), datasets: [{ data: data, borderColor: color, borderWidth: 2, pointRadius: 0, fill: false, tension: 0.4 }] },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { enabled: false } }, scales: { x: { display: false }, y: { display: false } } }
    });
  }
  spark('sparkToday', d.spark, '#0d6efd');
  spark('sparkActive', [d.spark[1], d.spark[1]+1, d.spark[1]-1, d.spark[1]+2], '#198754');
  spark('sparkTasks', [d.spark[2], d.spark[2]-1, d.spark[2]+1, d.spark[2]], '#ffc107');
  spark('sparkEff', [d.spark[3], d.spark[3]+1, d.spark[3], d.spark[3]+2], '#0dcaf0');

  new Chart(document.getElementById('nurseMainChart'), {
    type: 'bar',
    data: { labels: ['مرضى اليوم', 'زيارات نشطة', 'مهام معلقة', 'أدوية ناقصة', 'مهام مكتملة'], datasets: [{ label: 'العدد', data: d.mainData, backgroundColor: ['#0d6efd', '#198754', '#ffc107', '#dc3545', '#0dcaf0'] }] },
    options: { responsive: true, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }
  });
  document.querySelectorAll('.progress-dynamic').forEach(function(el){ el.style.width = (parseFloat(el.dataset.width) || 0) + '%'; });
