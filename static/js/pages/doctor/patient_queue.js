var __M = window.__M || [];
// Doctor patient search with visit count
document.addEventListener('DOMContentLoaded', function() {
  const input = document.getElementById('doctorPatientSearch');
  const list = document.getElementById('doctorPatientResults');
  let to;
  if (input) {
    input.addEventListener('input', function() {
      clearTimeout(to);
      const q = (this.value || '').trim();
      if (q.length < 2) { list.style.display = 'none'; list.innerHTML=''; return; }
      to = setTimeout(() => {
        fetch(__M0__ + '?q=' + encodeURIComponent(q))
          .then(r => r.json())
          .then(d => {
            const pts = d.patients || [];
            list.innerHTML = '';
            if (!pts.length) { list.innerHTML = '<div class="list-group-item text-muted">لا توجد نتائج</div>'; list.style.display='block'; return; }
            pts.forEach(p => {
              const item = document.createElement('a');
              item.href = __M1__.replace('0', p.id);
              item.className = 'list-group-item list-group-item-action';
              item.innerHTML = `
                <div class="d-flex w-100 justify-content-between">
                  <h6 class="mb-1">${p.full_name}</h6>
                  <small class="text-muted">الزيارات: ${p.visit_count || 0}</small>
                </div>
                <small class="text-muted">${p.national_id || ''} ${p.phone ? ' | ' + p.phone : ''}</small>
              `;
              list.appendChild(item);
            });
            list.style.display = 'block';
          })
          .catch(() => { list.innerHTML = '<div class="list-group-item text-danger">خطأ في البحث</div>'; list.style.display='block'; });
      }, 300);
    });
  }
});

function refreshQueue() {
    const container = document.querySelector('.container-fluid');
    const dept = parseInt((container && container.getAttribute('data-dept')) || '0');
    if (!dept) return;
    fetch('/reception/api/queue-status/' + dept + '?doctor_id=' + __M2__)
        .then(r => r.json())
        .then(d => {
            const s = d && d.data ? d.data : {};
            const waiting = Array.isArray(s.waiting_patients) ? s.waiting_patients.length : 0;
            const called = Array.isArray(s.called_patients) ? s.called_patients.length : 0;
            const inProgress = s.current_patient ? 1 : 0;
            const total = waiting + called + inProgress;
            const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = (val || 0); };
            set('stat-total', total);
            set('stat-ready', waiting);
            set('stat-in-progress', inProgress);
            set('stat-wait', s.estimated_wait_time || 15);
        })
        .catch(() => {});
}

// Auto-refresh every 30 seconds
setInterval(function() {
    refreshQueue();
}, 30000);

// Add click handlers for better UX
document.addEventListener('DOMContentLoaded', function() {
    // Add hover effects to table rows
    const rows = document.querySelectorAll('table tbody tr');
    rows.forEach(row => {
        row.addEventListener('mouseenter', function() {
            this.style.backgroundColor = '#f8f9fa';
        });
        row.addEventListener('mouseleave', function() {
            this.style.backgroundColor = '';
        });
    });
    
    // Add loading states to buttons
    const buttons = document.querySelectorAll('button[type="submit"]');
    buttons.forEach(button => {
        button.addEventListener('click', function() {
            this.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>جاري المعالجة...';
            this.disabled = true;
        });
    });
});
