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
        fetch(`/reception/appointments/${appointmentId}/confirm`, { method: 'POST', headers: { 'Accept': 'application/json' } })
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
        fetch(`/reception/appointments/${appointmentId}/cancel`, { method: 'POST', headers: { 'Accept': 'application/json' } })
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
        fetch(`/reception/appointments/${appointmentId}/no-show`, { method: 'POST', headers: { 'Accept': 'application/json' } })
            .then(r => r.json().then(j => ({ ok: r.ok, j })))
            .then(({ ok, j }) => {
                if (!ok || !j.success) throw new Error(j.message || 'حدث خطأ');
                location.reload();
            })
            .catch(err => Swal.fire({ title: 'خطأ', text: err.message || 'حدث خطأ', icon: 'error' }));
    });
}
