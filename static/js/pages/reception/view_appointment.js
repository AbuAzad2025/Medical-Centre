function getCsrfToken() {
    const el = document.querySelector('input[name="csrf_token"]') || document.querySelector('meta[name="csrf-token"]');
    return el ? (el.value || el.content || '') : '';
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
        if (!res.isConfirmed) return;
        fetch(((window.API_ROUTES && window.API_ROUTES.reception_confirm_appointment) || '/reception/appointments/0/confirm').replace('/0', '/' + appointmentId), { method: 'POST', headers: Object.assign({ 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' }, getCsrfToken() ? { 'X-CSRFToken': getCsrfToken() } : {}), credentials: 'same-origin' })
            .then(r => r.json().then(j => ({ ok: r.ok, j })))
            .then(({ ok, j }) => {
                if (!ok || !j.success) throw new Error(j.message || 'حدث خطأ');
                location.reload();
            })
            .catch(err => Swal.fire({ title: 'خطأ', text: err.message || 'حدث خطأ', icon: 'error' }));
    });
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
        if (!res.isConfirmed) return;
        fetch(((window.API_ROUTES && window.API_ROUTES.reception_cancel_appointment) || '/reception/appointments/0/cancel').replace('/0', '/' + appointmentId), { method: 'POST', headers: Object.assign({ 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' }, getCsrfToken() ? { 'X-CSRFToken': getCsrfToken() } : {}), credentials: 'same-origin' })
            .then(r => r.json().then(j => ({ ok: r.ok, j })))
            .then(({ ok, j }) => {
                if (!ok || !j.success) throw new Error(j.message || 'حدث خطأ');
                location.reload();
            })
            .catch(err => Swal.fire({ title: 'خطأ', text: err.message || 'حدث خطأ', icon: 'error' }));
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
        fetch(((window.API_ROUTES && window.API_ROUTES.reception_no_show_appointment) || '/reception/appointments/0/no-show').replace('/0', '/' + appointmentId), { method: 'POST', headers: Object.assign({ 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' }, getCsrfToken() ? { 'X-CSRFToken': getCsrfToken() } : {}), credentials: 'same-origin' })
            .then(r => r.json().then(j => ({ ok: r.ok, j })))
            .then(({ ok, j }) => {
                if (!ok || !j.success) throw new Error(j.message || 'حدث خطأ');
                location.reload();
            })
            .catch(err => Swal.fire({ title: 'خطأ', text: err.message || 'حدث خطأ', icon: 'error' }));
    });
}
