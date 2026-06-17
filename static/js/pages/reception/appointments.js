var __M = window.__M || [];

function createNewAppointment() {
    location.href = '/reception/create_appointment';
}

function createNewVisit() {
    location.href = '/reception/create_visit';
}

function exportAppointments() {
    var csvContent = "data:text/csv;charset=utf-8," 
        + __M0__.map(function(a) {
            var patient = a.patient ? a.patient.full_name : "\u063a\u064a\u0631 \u0645\u062d\u062f\u062f";
            var doctor = a.doctor ? a.doctor.full_name : "\u063a\u064a\u0631 \u0645\u062d\u062f\u062f";
            var date = a.starts_at ? a.starts_at.split("T")[0] : "\u063a\u064a\u0631 \u0645\u062d\u062f\u062f";
            var time = a.starts_at && a.starts_at.includes("T") ? a.starts_at.split("T")[1].substring(0, 5) : "\u063a\u064a\u0631 \u0645\u062d\u062f\u062f";
            return "#" + a.id + "," + patient + "," + doctor + "," + date + "," + time + "," + a.status + "," + (a.appointment_type || "\u0639\u0627\u0645") + "\n";
        }).join("");
    
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", "appointments_" + new Date().toISOString().split('T')[0] + ".csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

function applyFilters() {
    const searchTerm = (document.getElementById('searchInput').value || '').trim();
    const departmentFilter = document.getElementById('departmentFilter').value;
    const statusFilter = document.getElementById('statusFilter').value;
    const doctorFilter = document.getElementById('doctorFilter').value;
    const dateFilter = document.getElementById('dateFilter').value;
    const perPage = document.getElementById('perPageFilter').value;

    const params = new URLSearchParams();
    if (searchTerm) params.set('search', searchTerm);
    if (departmentFilter) params.set('department_id', departmentFilter);
    if (statusFilter) params.set('status', statusFilter);
    if (doctorFilter) params.set('doctor_id', doctorFilter);
    if (dateFilter) params.set('date', dateFilter);
    if (perPage) params.set('per_page', perPage);
    params.set('page', '1');

    const baseUrl = '/reception/appointments';
    location.href = baseUrl + '?' + params.toString();
}

function clearFilters() {
    document.getElementById('searchInput').value = '';
    document.getElementById('departmentFilter').value = '';
    document.getElementById('statusFilter').value = '';
    document.getElementById('doctorFilter').value = '';
    document.getElementById('dateFilter').value = '';
    const perPage = document.getElementById('perPageFilter').value || __M1__;
    const baseUrl = '/reception/appointments';
    location.href = baseUrl + '?per_page=' + encodeURIComponent(perPage);
}

function filterAppointments(filter, btnEl) {
    const rows = document.querySelectorAll('#appointmentsTable tbody tr');
    const today = new Date().toISOString().split('T')[0];
    
    rows.forEach(row => {
        if (filter === 'all') {
            row.style.display = '';
        } else if (filter === 'today') {
            row.style.display = row.dataset.date === today ? '' : 'none';
        } else if (filter === 'pending') {
            row.style.display = row.dataset.status === 'scheduled' ? '' : 'none';
        } else if (filter === 'confirmed') {
            row.style.display = row.dataset.status === 'confirmed' ? '' : 'none';
        }
    });
    
    // تحديث أزرار التصفية
    document.querySelectorAll('.btn-outline-primary, .btn-outline-success, .btn-outline-warning, .btn-outline-info').forEach(btn => {
        btn.classList.remove('active');
    });
    if (btnEl) btnEl.classList.add('active');
}

function viewAppointment(appointmentId) {
    var baseUrl = '/reception/appointments/0/view';
    location.href = baseUrl.replace(/0$/, appointmentId);
}

function confirmAppointment(appointmentId) {
    Swal.fire({
        title: 'تأكيد الموعد',
        text: 'هل تريد تأكيد هذا الموعد؟',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'تأكيد',
        cancelButtonText: 'إلغاء'
    }).then((res) => {
        if (res.isConfirmed) {
            fetch(`/reception/appointments/${appointmentId}/confirm`, { method: 'POST', headers: { 'Accept': 'application/json' } })
                .then(r => r.json().then(j => ({ ok: r.ok, j })))
                .then(({ ok, j }) => {
                    if (!ok || !j.success) throw new Error(j.message || 'حدث خطأ');
                    location.reload();
                })
                .catch(err => Swal.fire({ title: 'خطأ', text: err.message || 'حدث خطأ', icon: 'error' }));
        }
    });
}

function editAppointment(appointmentId) {
    var baseUrl = '/reception/appointments/0/edit';
    location.href = baseUrl.replace(/0$/, appointmentId);
}

function cancelAppointment(appointmentId) {
    Swal.fire({
        title: 'إلغاء الموعد',
        text: 'هل تريد إلغاء هذا الموعد؟',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'إلغاء',
        cancelButtonText: 'تراجع'
    }).then((res) => {
        if (res.isConfirmed) {
            fetch(`/reception/appointments/${appointmentId}/cancel`, { method: 'POST', headers: { 'Accept': 'application/json' } })
                .then(r => r.json().then(j => ({ ok: r.ok, j })))
                .then(({ ok, j }) => {
                    if (!ok || !j.success) throw new Error(j.message || 'حدث خطأ');
                    location.reload();
                })
                .catch(err => Swal.fire({ title: 'خطأ', text: err.message || 'حدث خطأ', icon: 'error' }));
        }
    });
}

function noShowAppointment(appointmentId) {
    Swal.fire({
        title: 'لم يحضر',
        text: 'تأكيد وضع الموعد كـ لم يحضر؟',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'تأكيد',
        cancelButtonText: 'إلغاء'
    }).then((res) => {
        if (!res.isConfirmed) return;
        fetch(`/reception/appointments/${appointmentId}/no-show`, { method: 'POST', headers: { 'Accept': 'application/json' } })
            .then(r => r.json().then(j => ({ ok: r.ok, j })))
            .then(({ ok, j }) => {
                if (!ok || !j.success) throw new Error(j.message || 'حدث خطأ');
                location.reload();
            })
            .catch(err => Swal.fire({ title: 'خطأ', text: err.message || 'حدث خطأ', icon: 'error' }));
    });
}

function generateReport() {
    Swal.fire({ title: 'تقرير', text: 'إنشاء تقرير المواعيد', icon: 'info' });
}

function bulkActions() {
    Swal.fire({ title: 'إجراءات', text: 'الإجراءات الجماعية', icon: 'info' });
}

// البحث المباشر
document.getElementById('searchInput').addEventListener('input', function() {
    applyFilters();
});

// إضافة تأثيرات تفاعلية
document.addEventListener('DOMContentLoaded', function() {
    // إضافة تأثير hover للصفوف
    const rows = document.querySelectorAll('#appointmentsTable tbody tr');
    rows.forEach(row => {
        row.addEventListener('mouseenter', function() {
            this.style.backgroundColor = '#f8f9fa';
        });
        row.addEventListener('mouseleave', function() {
            this.style.backgroundColor = '';
        });
    });
});