var __M = window.__M || [];
__M0__


const d = JSON.parse(document.getElementById('lab-chart-data').textContent);
  function spark(id, data, color) {
    new Chart(document.getElementById(id).getContext('2d'), {
      type: 'line',
      data: { labels: data.map(function(_, i){ return i; }), datasets: [{ data: data, borderColor: color, borderWidth: 2, pointRadius: 0, fill: false, tension: 0.4 }] },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { enabled: false } }, scales: { x: { display: false }, y: { display: false } } }
    });
  }
  spark('sparkToday', d.spark, '#0d6efd');
  spark('sparkCompleted', [d.spark[1], d.spark[1]+1, d.spark[1]-1, d.spark[1]+2], '#198754');
  spark('sparkTime', [d.spark[2], d.spark[2]-1, d.spark[2]+1, d.spark[2]], '#0dcaf0');
  spark('sparkQuality', [d.spark[3], d.spark[3]+1, d.spark[3], d.spark[3]+2], '#ffc107');

  new Chart(document.getElementById('labMainChart'), {
    type: 'bar',
    data: { labels: ['مطلوبة', 'قيد العمل', 'مكتملة', 'أسبوعي', 'شهري'], datasets: [{ label: 'الطلبات', data: d.mainData, backgroundColor: ['#0d6efd', '#ffc107', '#198754', '#6f42c1', '#0dcaf0'] }] },
    options: { responsive: true, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }
  });

  new Chart(document.getElementById('equipmentChart'), {
    type: 'doughnut',
    data: { labels: ['تعمل', 'صيانة'], datasets: [{ data: d.equipment, backgroundColor: ['#198754', '#ffc107'] }] },
    options: { responsive: true, plugins: { legend: { position: 'bottom', labels: { boxWidth: 12 } } }, cutout: '65%' }
  });
  document.querySelectorAll('.progress-dynamic').forEach(function(el){ el.style.width = (parseFloat(el.dataset.width) || 0) + '%'; });
