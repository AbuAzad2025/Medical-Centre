var __M = window.__M || [];
document.addEventListener('DOMContentLoaded', function() {
  const input = document.getElementById('doctorPatientSearch');
  const list = document.getElementById('doctorPatientResults');
  let to;
  if (input) {
    input.addEventListener('input', function() {
      clearTimeout(to);
      const q = (this.value || '').trim();
      if (q.length < 2) { if (list) { list.style.display = 'none'; list.innerHTML=''; } return; }
      to = setTimeout(() => {
        fetch(__M0__ + '?q=' + encodeURIComponent(q), { credentials: 'same-origin' })
          .then(r => {
            if (!r.ok) throw new Error(r.status);
            return r.json();
          })
          .then(d => {
            const pts = d.patients || [];
            list.innerHTML = '';
            if (!pts.length) { list.innerHTML = '<div class="list-group-item text-muted">لا توجد نتائج</div>'; list.style.display='block'; return; }
            pts.forEach(p => {
              const item = document.createElement('a');
              item.href = (typeof __M1__ !== 'undefined' ? __M1__.replace('0', p.id) : '#');
              item.className = 'list-group-item list-group-item-action';
              const headerDiv = document.createElement('div');
              headerDiv.className = 'd-flex w-100 justify-content-between';
              const nameH6 = document.createElement('h6');
              nameH6.className = 'mb-1';
              nameH6.textContent = p.full_name;
              headerDiv.appendChild(nameH6);
              const visitSmall = document.createElement('small');
              visitSmall.className = 'text-muted';
              visitSmall.textContent = 'الزيارات: ' + (p.visit_count || 0);
              headerDiv.appendChild(visitSmall);
              item.appendChild(headerDiv);
              const infoSmall = document.createElement('small');
              infoSmall.className = 'text-muted';
              infoSmall.textContent = (p.national_id || '') + (p.phone ? ' | ' + p.phone : '');
              item.appendChild(infoSmall);
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
    const queueStatusUrl = (window.API_ROUTES && window.API_ROUTES.queue_status) || '/reception/api/queue-status/0';
    fetch(queueStatusUrl.replace('/0', '/' + dept) + '?doctor_id=' + __M2__, { credentials: 'same-origin' })
        .then(r => {
            if (!r.ok) throw new Error(r.status);
            return r.json();
        })
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
        .catch(() => {
            if (window.showToast) window.showToast('حدث خطأ أثناء تحميل البيانات');
            else notifyErr('حدث خطأ أثناء تحميل البيانات');
        });
}

setInterval(function() {
  function notifyErr(msg) {
    if (window.showToast) window.showToast(msg || 'حدث خطأ', 'error');
    else console.warn('[doctor-page]', msg);
  }

    refreshQueue();
}, 30000);

document.addEventListener('DOMContentLoaded', function() {
    const rows = document.querySelectorAll('table tbody tr');
    rows.forEach(row => {
        row.addEventListener('mouseenter', function() {
            this.style.backgroundColor = '#f8f9fa';
        });
        row.addEventListener('mouseleave', function() {
            this.style.backgroundColor = '';
        });
    });

    const buttons = document.querySelectorAll('button[type="submit"]');
    buttons.forEach(button => {
        button.addEventListener('click', function() {
            this.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>جاري المعالجة...';
            this.disabled = true;
        });
    });
});
