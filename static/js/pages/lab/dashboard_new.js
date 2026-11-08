if (typeof Chart !== 'undefined') {
  Chart.defaults.plugins.tooltip.rtl = true;
  Chart.defaults.plugins.tooltip.textDirection = 'rtl';
  Chart.defaults.plugins.legend.rtl = true;
  Chart.defaults.plugins.legend.labels.font = Chart.defaults.plugins.legend.labels.font || {};
  Chart.defaults.font.family = "'Cairo', 'Tajawal', sans-serif";
}

var __M = window.__M || [];

(function() {
  const el = document.getElementById('lab-chart-data');
  let d = null;
  if (window.__M0__ && window.__M0__.spark) {
    d = window.__M0__;
  } else if (el) {
    d = JSON.parse(el.textContent);
  }
  if (!d) return;
  function spark(id, data, color) {
    if (typeof Chart === 'undefined') return;
    const sCanvas = document.getElementById(id);
    if (!sCanvas) return;
    new Chart(sCanvas.getContext('2d'), {
      type: 'line',
      data: { labels: data.map(function(_, i){ return i; }), datasets: [{ data: data, borderColor: color, borderWidth: 2, pointRadius: 0, fill: false, tension: 0.4 }] },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { enabled: false } }, scales: { x: { display: false }, y: { display: false } } }
    });
  }
  spark('sparkToday', d.spark, '#0d6efd');
  spark('sparkCompleted', [d.spark[1], d.spark[1]+1, d.spark[1]-1, d.spark[1]+2], '#198754');
  spark('sparkTime', [d.spark[2], d.spark[2]-1, d.spark[2]+1, d.spark[2]], '#0dcaf0');
  spark('sparkQuality', [d.spark[3], d.spark[3]+1, d.spark[3], d.spark[3]+2], '#ffc107');

  if (typeof Chart !== 'undefined' && document.getElementById('labMainChart')) {
  new Chart(document.getElementById('labMainChart'), {
      type: 'bar',
      data: { labels: ['مطلوبة', 'قيد العمل', 'مكتملة', 'أسبوعي', 'شهري'], datasets: [{ label: 'الطلبات', data: d.mainData, backgroundColor: ['#0d6efd', '#ffc107', '#198754', '#6f42c1', '#0dcaf0'] }] },
      options: { responsive: true, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }
    });
  }

  if (typeof Chart !== 'undefined' && document.getElementById('equipmentChart')) {
  new Chart(document.getElementById('equipmentChart'), {
      type: 'doughnut',
      data: { labels: ['تعمل', 'صيانة'], datasets: [{ data: d.equipment, backgroundColor: ['#198754', '#ffc107'] }] },
      options: { responsive: true, plugins: { legend: { position: 'bottom', labels: { boxWidth: 12 } } }, cutout: '65%' }
    });
  }
  document.querySelectorAll('.progress-dynamic').forEach(function(el){ el.style.width = (parseFloat(el.dataset.width) || 0) + '%'; });
})();

export {};
