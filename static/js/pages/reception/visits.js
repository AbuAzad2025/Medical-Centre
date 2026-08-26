var __M = window.__M || [];

var ROLE = __M0__;
var billingActive = __M1__;
(function() {
    if (!["reception", "manager"].includes(ROLE)) return;
function viewVisit(visitId) {
    // عرض تفاصيل الزيارة
    window.location.href = (window.API_ROUTES && window.API_ROUTES.view_visit) ? window.API_ROUTES.view_visit.replace('/0', '/' + visitId) : `/reception/view_visit/${visitId}`;
}

function processPayment(visitId) {
    // معالجة الدفع
    window.location.href = (window.API_ROUTES && window.API_ROUTES.payment_process) ? window.API_ROUTES.payment_process.replace('/0', '/' + visitId) : `/payment/process/${visitId}`;
}

function printReceipt(visitId) {
    // طباعة الوصل
    if (typeof billingActive !== 'undefined' && !billingActive) return;
    window.open((window.API_ROUTES && window.API_ROUTES.print_receipt) ? window.API_ROUTES.print_receipt.replace('/0', '/' + visitId) : `/reception/print_receipt/${visitId}`, '_blank');
}

function editVisit(visitId) {
    // تعديل الزيارة
    window.location.href = (window.API_ROUTES && window.API_ROUTES.edit_visit) ? window.API_ROUTES.edit_visit.replace('/0', '/' + visitId) : `/reception/edit_visit/${visitId}`;
}

function exportVisits() {
    // تصدير الزيارات
    const params = new URLSearchParams(window.location.search);
    window.open(((window.API_ROUTES && window.API_ROUTES.export_visits) || '/reception/export/visits') + `?${params.toString()}`, '_blank');
}

// Auto-refresh every 30 seconds
setInterval(function() {
    if (document.visibilityState === 'visible') {
        location.reload();
    }
}, 30000);

function openTransfer(visitId) {
    document.getElementById('transferVisitId').value = visitId;
    document.getElementById('transferStatus').textContent = '';
    const modal = new bootstrap.Modal(document.getElementById('transferVisitModal'));
    modal.show();
}

document.getElementById('transferDepartment')?.addEventListener('change', function() {
    const deptId = this.value;
    const doctorSelect = document.getElementById('transferDoctor');
    doctorSelect.innerHTML = '<option value="">اختر الطبيب</option>';
    if (!deptId) return;
    fetch(((window.API_ROUTES && window.API_ROUTES.api_department_staff) || '/reception/api/department-staff') + `?department_id=${deptId}`, { credentials: 'same-origin' })
        .then(r => {
            if (!r.ok) throw new Error(r.status);
            return r.json();
        })
        .then(d => {
            const staff = d.staff || [];
            staff.forEach(s => {
                const opt = document.createElement('option');
                opt.value = s.id;
                opt.textContent = s.full_name;
                doctorSelect.appendChild(opt);
            });
        }).catch(() => {
            if (window.showToast) window.showToast('حدث خطأ أثناء تحميل البيانات');
            else alert('حدث خطأ أثناء تحميل البيانات');
        });
});

document.getElementById('confirmTransferBtn')?.addEventListener('click', function() {
    const visitId = document.getElementById('transferVisitId').value;
    const deptId = document.getElementById('transferDepartment').value;
    const doctorId = document.getElementById('transferDoctor').value;
    const statusEl = document.getElementById('transferStatus');
    if (!deptId) { Swal.fire({ title: 'حقول مطلوبة', text: 'يرجى اختيار القسم', icon: 'warning' }); return; }
    const csrfEl = document.querySelector('input[name="csrf_token"]') || document.querySelector('meta[name="csrf-token"]');
    const csrfToken = csrfEl ? (csrfEl.value || csrfEl.content || '') : '';
    fetch(((window.API_ROUTES && window.API_ROUTES.transfer_visit) || '/reception/visits/0/transfer').replace('/0', '/' + visitId), {
        method: 'POST',
        headers: Object.assign({ 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' }, csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
        credentials: 'same-origin',
        body: new URLSearchParams({ department_id: deptId, doctor_id: doctorId })
    }).then(r => {
        if (!r.ok) throw new Error(r.status);
        return r.json();
    }).then(d => {
        if (d.success) { Swal.fire({ title: 'تم', text: 'تم تحويل الزيارة بنجاح', icon: 'success' }).then(() => { location.reload(); }); }
        else { Swal.fire({ title: 'خطأ', text: (d.message || 'فشل التحويل'), icon: 'error' }); }
    }).catch(() => { Swal.fire({ title: 'خطأ', text: 'خطأ اتصال', icon: 'error' }); });
});

document.getElementById('visitsTable')?.addEventListener('contextmenu', function(e) {
    const row = e.target.closest('tr[data-visit-id]');
    if (!row) return;
    e.preventDefault();
    const id = row.getAttribute('data-visit-id');
    openTransfer(id);
});
})();