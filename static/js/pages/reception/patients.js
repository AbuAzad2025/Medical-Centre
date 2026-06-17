var __M = window.__M || [];
let smartSearchTimer = null;
(function() {
    const input = document.getElementById('search');
    const tbody = document.getElementById('patientsTableBody');
    if (!input || !tbody) return;

    const originalTbodyHtml = tbody.innerHTML;

    const genderLabel = (g) => {
        if (!g) return '-';
        const gg = String(g).toUpperCase();
        if (gg === 'M') return 'ذكر';
        if (gg === 'F') return 'أنثى';
        return 'آخر';
    };

    const buildActionsHtml = (id) => {
        const viewUrl = `/reception/view_patient/${id}`;
        const editUrl = `/reception/edit_patient/${id}`;
        const createVisitUrl = `/reception/visits/create?patient_id=${id}`;
        const apptUrl = `/reception/create_appointment?patient_id=${id}`;
        return `
            <a class="btn btn-sm btn-info me-1" href="${viewUrl}">عرض</a>
            <a class="btn btn-sm btn-warning me-1" href="${editUrl}">تعديل</a>
            <a class="btn btn-sm btn-success me-1" href="${createVisitUrl}">زيارة</a>
            <a class="btn btn-sm btn-primary mt-1" href="${apptUrl}">حجز مسبق</a>
        `;
    };

    const restore = () => {
        tbody.innerHTML = originalTbodyHtml;
    };

    const renderResults = (patients) => {
        if (!patients || !patients.length) {
            tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted">لا توجد نتائج</td></tr>`;
            return;
        }
        const rows = patients.map(p => {
            const id = p.id ?? '-';
            const name = p.full_name ?? '-';
            const phone = p.phone ?? '-';
            const nid = p.national_id ?? '-';
            const gender = genderLabel(p.gender);
            return `
                <tr>
                    <td>${id}</td>
                    <td>${name}</td>
                    <td>${phone}</td>
                    <td>${nid}</td>
                    <td>${gender}</td>
                    <td>-</td>
                    <td>-</td>
                    <td>${id !== '-' ? buildActionsHtml(id) : ''}</td>
                </tr>
            `;
        });
        tbody.innerHTML = rows.join('');
    };

    input.addEventListener('input', function() {
        const q = (this.value || '').trim();
        if (smartSearchTimer) window.clearTimeout(smartSearchTimer);

        if (q.length < 2) {
            restore();
            return;
        }

        smartSearchTimer = window.setTimeout(() => {
            fetch(`/reception/api/smart-patient-search?q=${encodeURIComponent(q)}`, {
                headers: { 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' }
            })
                .then(r => r.ok ? r.json() : Promise.reject(r))
                .then(d => renderResults(d.patients || []))
                .catch(() => {
                    tbody.innerHTML = `<tr><td colspan="8" class="text-center text-danger">خطأ في البحث</td></tr>`;
                });
        }, 250);
    });
})();

function calcAgeModal() {
    const v = document.getElementById('birth_date_modal').value;
    if (!v) { document.getElementById('age_modal').value = ''; return; }
    const b = new Date(v);
    const t = new Date();
    let age = t.getFullYear() - b.getFullYear();
    const m = t.getMonth() - b.getMonth();
    if (m < 0 || (m === 0 && t.getDate() < b.getDate())) age--;
    document.getElementById('age_modal').value = age;
}
function togglePregnancyModal() {
    const g = document.getElementById('gender_modal');
    const ms = document.getElementById('marital_status_modal');
    const s = document.getElementById('pregnancy_section_modal');
    
    if (!g || !ms || !s) return;

    const show = g.value === 'F' && ms.value === 'married';
    s.style.display = show ? '' : 'none';
    if (!show) {
        const chk = document.getElementById('is_pregnant_modal'); if (chk) chk.checked = false;
        const w = document.getElementById('pregnancy_weeks_modal'); if (w) w.value = '';
        const d = document.getElementById('last_menstruation_date_modal'); if (d) d.value = '';
        const n = document.getElementById('pregnancy_notes_modal'); if (n) n.value = '';
    }
}
function calcPregnancyWeeksModal() {
    const v = document.getElementById('last_menstruation_date_modal').value;
    if (!v) { document.getElementById('pregnancy_weeks_modal').value = ''; return; }
    const d = new Date(v);
    const t = new Date();
    const w = Math.floor((t - d) / (1000*60*60*24*7));
    if (w >= 0) document.getElementById('pregnancy_weeks_modal').value = w;
}
document.getElementById('birth_date_modal')?.addEventListener('change', calcAgeModal);
document.getElementById('gender_modal')?.addEventListener('change', togglePregnancyModal);
document.getElementById('marital_status_modal')?.addEventListener('change', togglePregnancyModal);
document.getElementById('last_menstruation_date_modal')?.addEventListener('change', calcPregnancyWeeksModal);
document.getElementById('savePatientModalBtn')?.addEventListener('click', function() {
    const form = document.getElementById('patientFormModal');
    const fd = new FormData(form);
    if (!fd.get('first_name') || !fd.get('last_name') || !fd.get('phone')) {
        Swal.fire({ title: 'حقول مطلوبة', text: 'يرجى ملء جميع الحقول المطلوبة', icon: 'warning' });
        return;
    }
    fetch(form.action, { method: 'POST', headers: { 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' }, body: fd })
        .then(r => r.json())
        .then(d => {
            if (d.success) {
                Swal.fire({ title: 'تم الحفظ', text: 'تم حفظ المريض بنجاح', icon: 'success' }).then(() => { location.reload(); });
            } else {
                Swal.fire({ title: 'خطأ', text: (d.message || 'تعذر حفظ المريض'), icon: 'error' });
            }
        })
        .catch(e => Swal.fire({ title: 'خطأ', text: 'حدث خطأ في حفظ المريض', icon: 'error' }));
});
togglePregnancyModal();

// فتح المودال تلقائياً إذا وُجد بارامتر show_add
(function() {
    const params = new URLSearchParams(window.location.search);
    if (params.get('show_add')) {
        if (window.bootstrap && document.getElementById('addPatientModal')) {
            const modal = new bootstrap.Modal(document.getElementById('addPatientModal'));
            modal.show();
        } else {
            // fallback: زر يملك data-bs-target، نحاول تشغيله برمجياً
            const btns = document.querySelectorAll('[data-bs-target="#addPatientModal"]');
            if (btns.length) btns[0].click();
        }
    }
    })();

function calcAgeEdit() {
    const v = document.getElementById('birth_date_edit')?.value;
    if (!v) { const a = document.getElementById('age_edit'); if (a) a.value = ''; return; }
    const b = new Date(v);
    const t = new Date();
    let age = t.getFullYear() - b.getFullYear();
    const m = t.getMonth() - b.getMonth();
    if (m < 0 || (m === 0 && t.getDate() < b.getDate())) age -= 1;
    const a = document.getElementById('age_edit');
    if (a) a.value = age;
}
function togglePregnancyEdit() {
    const g = document.getElementById('gender_edit')?.value;
    const ms = document.getElementById('marital_status_edit')?.value;
    const s = document.getElementById('pregnancy_section_edit');
    const show = g === 'F' && ms === 'married';
    if (s) s.style.display = show ? '' : 'none';
    if (!show) {
        const chk = document.getElementById('is_pregnant_edit'); if (chk) chk.checked = false;
        const w = document.getElementById('pregnancy_weeks_edit'); if (w) w.value = '';
        const d = document.getElementById('last_menstruation_date_edit'); if (d) d.value = '';
        const n = document.getElementById('pregnancy_notes_edit'); if (n) n.value = '';
    }
}
function calcPregnancyWeeksEdit() {
    const v = document.getElementById('last_menstruation_date_edit')?.value;
    if (!v) { const w = document.getElementById('pregnancy_weeks_edit'); if (w) w.value = ''; return; }
    const d = new Date(v);
    const t = new Date();
    const w = Math.floor((t - d) / (1000*60*60*24*7));
    if (w >= 0) { const ww = document.getElementById('pregnancy_weeks_edit'); if (ww) ww.value = w; }
}
document.getElementById('birth_date_edit')?.addEventListener('change', calcAgeEdit);
document.getElementById('gender_edit')?.addEventListener('change', togglePregnancyEdit);
document.getElementById('marital_status_edit')?.addEventListener('change', togglePregnancyEdit);
document.getElementById('last_menstruation_date_edit')?.addEventListener('change', calcPregnancyWeeksEdit);
document.getElementById('savePatientEditBtn')?.addEventListener('click', function() {
    const form = document.getElementById('patientFormEdit');
    if (!form) return;
    const fd = new FormData(form);
    if (!fd.get('first_name') || !fd.get('last_name') || !fd.get('phone')) {
        Swal.fire({ title: 'حقول مطلوبة', text: 'يرجى ملء جميع الحقول المطلوبة', icon: 'warning' });
        return;
    }
    fetch(form.action, { method: 'POST', headers: { 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' }, body: fd })
        .then(r => r.ok ? r.json() : r.text().then(t => ({ success: false, message: t })))
        .then(d => {
            if (d.success) {
                Swal.fire({ title: 'تم الحفظ', text: 'تم حفظ التعديلات بنجاح', icon: 'success' }).then(() => {
                    location.href = __M0__;
                });
            } else {
                Swal.fire({ title: 'خطأ', text: (d.message || 'تعذر حفظ التعديلات'), icon: 'error' });
            }
        })
        .catch(e => Swal.fire({ title: 'خطأ', text: 'حدث خطأ في حفظ التعديلات', icon: 'error' }));
});
if (__M1__) {
    if (window.bootstrap && document.getElementById('editPatientModal')) {
        const modal = new bootstrap.Modal(document.getElementById('editPatientModal'));
        modal.show();
    }
    togglePregnancyEdit();
    calcAgeEdit();
}


function confirmDeletePatient(btn) {
    const form = btn.closest('form');
    if (!form) return;
    Swal.fire({
        title: 'حذف المريض',
        text: 'هل أنت متأكد من حذف هذا المريض؟',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'حذف',
        cancelButtonText: 'إلغاء'
    }).then((res) => {
        if (res.isConfirmed) {
            form.submit();
        }
    });
}
