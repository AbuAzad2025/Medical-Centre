var __M = window.__M || [];
fetch(__M0__)
    .then(r => r.json())
    .then(d => {
      new Chart(document.getElementById('qcMainChart'), {
        type: 'line',
        data: {
          labels: d.labels,
          datasets: [
            { label: 'المختبر', data: d.lab, borderColor: '#198754', tension: 0.4, fill: false },
            { label: 'الأشعة', data: d.radiology, borderColor: '#0d6efd', tension: 0.4, fill: false },
            { label: 'الزيارات', data: d.visits, borderColor: '#ffc107', tension: 0.4, fill: false }
          ]
        },
        options: { responsive: true, plugins: { legend: { position: 'bottom', labels: { boxWidth: 12 } } }, scales: { y: { beginAtZero: true } } }
      });
    })
    .catch(() => { document.getElementById('qcMainChart').parentNode.innerHTML = '<p class="text-muted text-center">تعذر تحميل البيانات</p>'; });
  document.querySelectorAll('.progress-dynamic').forEach(function(el){ el.style.width = (parseFloat(el.dataset.width) || 0) + '%'; });
