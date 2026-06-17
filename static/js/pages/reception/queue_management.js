var __M = window.__M || [];
let currentTicketId = null;
const currentUserRole = __M0__;
const currentDoctorId = __M1__;

function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
}

// تحديث حالة الطابور الموحد
function updateQueueStatus() {
    const params = new URLSearchParams();
    const dep = document.getElementById('filterDepartment');
    const st = document.getElementById('filterStatus');
    const pr = document.getElementById('filterPriority');
    const dr = document.getElementById('filterDoctor');
    const sr = document.getElementById('filterSearch');
    const em = document.getElementById('filterEmergency');
    const fo = document.getElementById('filterForce');
    if (dep && dep.value) params.set('department_id', dep.value);
    if (st && st.value) params.set('status', st.value);
    if (pr && pr.value) params.set('priority', pr.value);
    if (dr && dr.value) params.set('doctor_id', dr.value);
    if (sr && sr.value) params.set('search', sr.value);
    if (em && em.checked) params.set('is_emergency', '1');
    if (fo && fo.checked) params.set('force_entry', '1');
    if (currentUserRole === 'doctor' && currentDoctorId) params.set('doctor_id', currentDoctorId);
    const url = `/reception/api/queue-status-all?${params.toString()}`;
    fetch(url)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                displayQueueStatusAll(data.data);
                updateWaitMetrics(dep && dep.value ? dep.value : '');
            } else {
                const tbody = document.querySelector('#queue-status-all tbody');
                tbody.innerHTML = '<tr><td colspan="10" class="text-center text-danger">خطأ في تحميل الطابور</td></tr>';
            }
        })
        .catch(error => {
            console.error('Error:', error);
            const tbody = document.querySelector('#queue-status-all tbody');
            tbody.innerHTML = '<tr><td colspan="10" class="text-center text-danger">خطأ في الاتصال</td></tr>';
        });
}

function updateWaitMetrics(departmentId) {
    const params = new URLSearchParams();
    if (departmentId) params.set('department_id', departmentId);
    fetch(`/reception/api/queue-wait-metrics?${params.toString()}`)
        .then(r => r.json())
        .then(data => {
            const overallEl = document.getElementById('avg-wait-today');
            const deptEl = document.getElementById('avg-wait-dept');
            if (!data || !data.success) {
                if (overallEl) overallEl.textContent = '--';
                if (deptEl) deptEl.textContent = '--';
                return;
            }
            const overall = data.data && data.data.overall_avg_wait_minutes;
            if (overallEl) overallEl.textContent = (typeof overall === 'number') ? `${overall} د` : '--';
            if (deptEl) {
                const items = (data.data && data.data.by_department) ? data.data.by_department : [];
                const depIdInt = departmentId ? parseInt(departmentId) : null;
                if (!depIdInt) {
                    deptEl.textContent = '--';
                } else {
                    const it = items.find(x => x.department_id === depIdInt);
                    const v = it ? it.avg_wait_minutes : null;
                    deptEl.textContent = (typeof v === 'number') ? `${v} د` : '--';
                }
            }
        })
        .catch(() => {
            const overallEl = document.getElementById('avg-wait-today');
            const deptEl = document.getElementById('avg-wait-dept');
            if (overallEl) overallEl.textContent = '--';
            if (deptEl) deptEl.textContent = '--';
        });
}

// عرض حالة الطابور الموحد
function displayQueueStatusAll(status) {
    const tbody = document.querySelector('#queue-status-all tbody');
    const rows = [];
    const addRow = (t) => {
        const waitMinutes = (typeof t.wait_minutes === 'number') ? t.wait_minutes : null;
        const waitTxt = waitMinutes === null ? '-' : (waitMinutes < 60 ? `${waitMinutes} د` : `${Math.floor(waitMinutes / 60)} س ${waitMinutes % 60} د`);
        let rowClass = '';
        if (t.status === 'waiting') rowClass = '';
        else if (t.status === 'called') rowClass = 'table-warning';
        else if (t.status === 'in_progress') rowClass = 'table-success';
        rows.push(`
            <tr class="${rowClass}">
                <td>${t.ticket_number || '-'}</td>
                <td>${t.patient_name || '-'}</td>
                <td>${t.department_name || '-'}</td>
                <td>${t.doctor_name || '-'}</td>
                <td>${t.status_display || t.status || '-'}${t.is_emergency ? ' <span class=\"badge bg-danger\">طوارئ</span>' : ''}${t.force_entry ? ' <span class=\"badge bg-warning\">دخول قوي</span>' : ''}</td>
                <td>${t.priority_display || t.priority_level || '-'}</td>
                <td>${t.queued_at_display || '-'}</td>
                <td>${waitTxt}</td>
                <td>${t.called_at_display || '-'}</td>
                <td>
                    <div class="btn-group btn-group-sm" role="group">
                        ${t.status === 'waiting' ? `<button class="btn btn-outline-warning" onclick="skipPatient(${t.ticket_id})" title="تخطي" aria-label="تخطي المريض"><i class='fas fa-forward'></i> <span class='btn-label'>تخطي</span></button>` : ''}
                        ${t.status === 'called' || t.status === 'in_progress' || t.status === 'skipped' ? `<button class="btn btn-outline-secondary" onclick="returnToQueue(${t.ticket_id})" title="إرجاع للطابور" aria-label="إرجاع للطابور"><i class='fas fa-rotate-left'></i> <span class='btn-label'>إرجاع</span></button>` : ''}
                        ${t.status === 'called' ? `<button class="btn btn-outline-primary" onclick="startTreatment(${t.ticket_id})" title="بدء العلاج" aria-label="بدء العلاج"><i class='fas fa-play'></i> <span class='btn-label'>بدء</span></button>` : ''}
                        ${t.status === 'in_progress' ? `<button class="btn btn-outline-success" onclick="completeTreatment(${t.ticket_id})" title="إكمال العلاج" aria-label="إكمال العلاج"><i class='fas fa-check'></i> <span class='btn-label'>إكمال</span></button>` : ''}
                        <button class="btn btn-outline-danger" onclick="cancelTicket(${t.ticket_id})" title="إلغاء" aria-label="إلغاء التذكرة"><i class='fas fa-times'></i> <span class='btn-label'>إلغاء</span></button>
                        ${t.visit_id ? `<a class="btn btn-outline-secondary" href="/reception/view_visit/${t.visit_id}" title="عرض الزيارة" aria-label="عرض الزيارة"><i class='fas fa-eye'></i> <span class='btn-label'>عرض</span></a>` : ''}
                        ${t.visit_id ? `<a class="btn btn-outline-secondary" href="/reception/print_receipt/${t.visit_id}" title="طباعة السند" aria-label="طباعة السند"><i class='fas fa-print'></i> <span class='btn-label'>طباعة</span></a>` : ''}
                        ${t.visit_id && t.status === 'waiting' ? `<button class="btn btn-outline-info" onclick="transferVisit(${t.visit_id})" title="تحويل لقسم آخر" aria-label="تحويل الزيارة"><i class='fas fa-exchange-alt'></i> <span class='btn-label'>تحويل</span></button>` : ''}
                    </div>
                </td>
            </tr>
        `);
    };
    if (status.tickets && status.tickets.length) status.tickets.forEach(addRow);
    const tbodyHtml = rows.length ? rows.join('') : `<tr><td colspan="10" class="text-center text-muted">لا يوجد مرضى في الطابور</td></tr>`;
    tbody.innerHTML = tbodyHtml;
}

// استدعاء المريض التالي
function callNextPatient(departmentId) {
    const url = currentUserRole === 'doctor'
        ? `/reception/queue/call-next/${departmentId}?doctor_id=${currentDoctorId}`
        : `/reception/queue/call-next/${departmentId}`;
    fetch(url)
        .then(response => response.text())
        .then(() => {
            updateQueueStatus();
        })
        .catch(error => {
            console.error('Error:', error);
            Swal.fire({ title: 'خطأ', text: 'حدث خطأ في استدعاء المريض', icon: 'error' });
        });
}

function callNextForSelectedDepartment() {
    const dep = document.getElementById('filterDepartment');
    if (!dep || !dep.value) {
        Swal.fire({ title: 'تنبيه', text: 'يرجى اختيار قسم أولاً لنداء المريض التالي', icon: 'info' });
        return;
    }
    callNextPatient(dep.value);
}

// استدعاء مريض محدد
function callPatient(ticketId) {
    currentTicketId = ticketId;
    const modal = new bootstrap.Modal(document.getElementById('callPatientModal'));
    modal.show();
}

// بدء العلاج
function startTreatment(ticketId) {
    fetch(`/reception/queue/start-treatment/${ticketId}`)
        .then(response => response.text())
        .then(() => {
            updateQueueStatus();
            const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('callPatientModal'));
            modal.hide();
        })
        .catch(error => {
            console.error('Error:', error);
            Swal.fire({ title: 'خطأ', text: 'حدث خطأ في بدء العلاج', icon: 'error' });
        });
}

// إكمال العلاج
function completeTreatment(ticketId) {
    fetch(`/reception/queue/complete-treatment/${ticketId}`)
        .then(response => response.text())
        .then(() => {
            updateQueueStatus();
        })
        .catch(error => {
            console.error('Error:', error);
            Swal.fire({ title: 'خطأ', text: 'حدث خطأ في إكمال العلاج', icon: 'error' });
        });
}

// تخطي المريض
function skipPatient(ticketId) {
    currentTicketId = ticketId;
    const modal = new bootstrap.Modal(document.getElementById('skipPatientModal'));
    modal.show();
}

// إلغاء التذكرة
function cancelTicket(ticketId) {
    currentTicketId = ticketId;
    const modal = new bootstrap.Modal(document.getElementById('cancelTicketModal'));
    modal.show();
}

function transferVisit(visitId) {
    document.getElementById('transfer_visit_id').value = visitId;
    const deptSelect = document.getElementById('transfer_department_id');
    const docSelect = document.getElementById('transfer_doctor_id');
    deptSelect.addEventListener('change', function() {
        const deptId = this.value;
        if (!deptId) { docSelect.innerHTML = '<option value="">اختر بعد القسم...</option>'; return; }
        fetch(`/reception/api/department-staff?department_id=${deptId}`)
            .then(r => r.json())
            .then(data => {
                docSelect.innerHTML = '<option value="">بدون تحديد موظف</option>';
                (data.staff || []).forEach(s => {
                    const roleAr = {'doctor':'طبيب','nurse':'ممرض','lab':'فني مختبر','radiology':'فني أشعة','emergency':'طوارئ'}[s.role] || s.role;
                    docSelect.innerHTML += `<option value="${s.id}">${s.full_name} - ${roleAr}</option>`;
                });
            });
    }, {once: false});
    const modal = new bootstrap.Modal(document.getElementById('transferVisitModal'));
    modal.show();
}

document.getElementById('transferVisitForm') && document.getElementById('transferVisitForm').addEventListener('submit', function(e) {
    e.preventDefault();
    const visitId = document.getElementById('transfer_visit_id').value;
    const deptId = document.getElementById('transfer_department_id').value;
    const docId = document.getElementById('transfer_doctor_id').value;
    if (!deptId) { Swal.fire({title:'تنبيه', text:'يجب اختيار القسم', icon:'warning'}); return; }
    const fd = new FormData();
    fd.append('csrf_token', getCsrfToken());
    fd.append('department_id', deptId);
    if (docId) fd.append('doctor_id', docId);
    fetch(`/reception/visits/${visitId}/transfer`, {method:'POST', body:fd})
        .then(r => r.json())
        .then(data => {
            const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('transferVisitModal'));
            modal.hide();
            if (data.success) {
                Swal.fire({title:'تم', text:'تم تحويل الزيارة بنجاح', icon:'success', timer:2000, showConfirmButton:false});
                updateQueueStatus();
            } else {
                Swal.fire({title:'خطأ', text: data.message || 'فشل التحويل', icon:'error'});
            }
        })
        .catch(() => Swal.fire({title:'خطأ', text:'حدث خطأ في التحويل', icon:'error'}));
});

function returnToQueue(ticketId) {
    Swal.fire({
        title: 'إرجاع للطابور',
        input: 'text',
        inputPlaceholder: 'سبب الإرجاع (اختياري)',
        showCancelButton: true,
        confirmButtonText: 'إرجاع',
        cancelButtonText: 'إلغاء'
    }).then((res) => {
        if (!res.isConfirmed) return;
        const fd = new FormData();
        fd.append('reason', res.value || '');
        const csrf = getCsrfToken();
        if (csrf) fd.append('csrf_token', csrf);
        fetch(`/reception/queue/return-to-queue/${ticketId}`, { method: 'POST', body: fd })
            .then(() => updateQueueStatus())
            .catch(() => Swal.fire({ title: 'خطأ', text: 'حدث خطأ في إرجاع المريض للطابور', icon: 'error' }));
    });
}

// الموافقة على دين الطوارئ
function approveEmergencyDebt(ticketId) {
    currentTicketId = ticketId;
    const modal = new bootstrap.Modal(document.getElementById('approveEmergencyDebtModal'));
    modal.show();
}

// الموافقة على الدخول القوي
function approveForceEntry(ticketId) {
    currentTicketId = ticketId;
    const modal = new bootstrap.Modal(document.getElementById('approveForceEntryModal'));
    modal.show();
}

// معالجة النماذج
document.getElementById('skipPatientForm').addEventListener('submit', function(e) {
    e.preventDefault();
    const formData = new FormData(this);
    const csrf = getCsrfToken();
    if (csrf && !formData.get('csrf_token')) formData.append('csrf_token', csrf);
    
    fetch(`/reception/queue/skip-patient/${currentTicketId}`, {
        method: 'POST',
        body: formData
    })
    .then(response => response.text())
    .then(() => {
        updateQueueStatus();
        const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('skipPatientModal'));
        modal.hide();
        this.reset();
    })
    .catch(error => {
        console.error('Error:', error);
        Swal.fire({ title: 'خطأ', text: 'حدث خطأ في تخطي المريض', icon: 'error' });
    });
});

document.getElementById('cancelTicketForm').addEventListener('submit', function(e) {
    e.preventDefault();
    const formData = new FormData(this);
    const csrf = getCsrfToken();
    if (csrf && !formData.get('csrf_token')) formData.append('csrf_token', csrf);
    
    fetch(`/reception/queue/cancel-ticket/${currentTicketId}`, {
        method: 'POST',
        body: formData
    })
    .then(response => response.text())
    .then(() => {
        updateQueueStatus();
        const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('cancelTicketModal'));
        modal.hide();
        this.reset();
    })
    .catch(error => {
        console.error('Error:', error);
        Swal.fire({ title: 'خطأ', text: 'حدث خطأ في إلغاء التذكرة', icon: 'error' });
    });
});

document.getElementById('approveEmergencyDebtForm').addEventListener('submit', function(e) {
    e.preventDefault();
    const formData = new FormData(this);
    const csrf = getCsrfToken();
    if (csrf && !formData.get('csrf_token')) formData.append('csrf_token', csrf);
    
    fetch(`/reception/queue/approve-emergency-debt/${currentTicketId}`, {
        method: 'POST',
        body: formData
    })
    .then(response => response.text())
    .then(() => {
        updateQueueStatus();
        const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('approveEmergencyDebtModal'));
        modal.hide();
        this.reset();
    })
    .catch(error => {
        console.error('Error:', error);
        Swal.fire({ title: 'خطأ', text: 'حدث خطأ في الموافقة على دين الطوارئ', icon: 'error' });
    });
});

document.getElementById('approveForceEntryForm').addEventListener('submit', function(e) {
    e.preventDefault();
    const formData = new FormData(this);
    const csrf = getCsrfToken();
    if (csrf && !formData.get('csrf_token')) formData.append('csrf_token', csrf);
    
    fetch(`/reception/queue/approve-force-entry/${currentTicketId}`, {
        method: 'POST',
        body: formData
    })
    .then(response => response.text())
    .then(() => {
        updateQueueStatus();
        const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('approveForceEntryModal'));
        modal.hide();
        this.reset();
    })
    .catch(error => {
        console.error('Error:', error);
        Swal.fire({ title: 'خطأ', text: 'حدث خطأ في الموافقة على الدخول القوي', icon: 'error' });
    });
});

// تحديث دوري
setInterval(updateQueueStatus, 30000); // كل 30 ثانية

// تحميل أولي
document.addEventListener('DOMContentLoaded', function() {
    updateQueueStatus();
});
