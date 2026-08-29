const isEmergencyEl = document.getElementById('is_emergency');
if (isEmergencyEl) {
    isEmergencyEl.addEventListener('change', function() {
        const reasonGroup = document.getElementById('emergency_reason_group');
        if (this.checked) {
            reasonGroup.style.display = 'block';
            document.getElementById('emergency_reason').required = true;
        } else {
            reasonGroup.style.display = 'none';
            document.getElementById('emergency_reason').required = false;
            document.getElementById('emergency_reason').value = '';
        }
    });
}

const forceEntryEl = document.getElementById('force_entry');
if (forceEntryEl) {
    forceEntryEl.addEventListener('change', function() {
        const reasonGroup = document.getElementById('force_entry_reason_group');
        if (this.checked) {
            reasonGroup.style.display = 'block';
            document.getElementById('force_entry_reason').required = true;
        } else {
            reasonGroup.style.display = 'none';
            document.getElementById('force_entry_reason').required = false;
            document.getElementById('force_entry_reason').value = '';
        }
    });
}

const departmentIdEl = document.getElementById('department_id');
if (departmentIdEl) {
    departmentIdEl.addEventListener('change', function() {
        const departmentId = this.value;
        const doctorSelect = document.getElementById('doctor_id');

        if (departmentId) {
            fetch(((window.API_ROUTES && window.API_ROUTES.api_doctors) || '/reception/api/doctors') + `?department_id=${departmentId}`, { credentials: 'same-origin' })
                .then(response => {
                    if (!response.ok) throw new Error(response.status);
                    return response.json();
                })
                .then(data => {
                    if (data.success) {
                        doctorSelect.innerHTML = '<option value="">اختر الطبيب</option>';
                        data.doctors.forEach(doctor => {
                            const option = document.createElement('option');
                            option.value = doctor.id;
                            option.textContent = doctor.full_name;
                            doctorSelect.appendChild(option);
                        });
                    }
                })
                .catch(error => {
                    if (window.showToast) window.showToast('حدث خطأ أثناء تحميل البيانات');
                    else alert('حدث خطأ أثناء تحميل البيانات');
                });
        } else {
            doctorSelect.innerHTML = '<option value="">اختر الطبيب</option>';
        }
    });
}

const addPatientFormEl = document.getElementById('addPatientForm');
if (addPatientFormEl) {
    addPatientFormEl.addEventListener('submit', function(e) {
        e.preventDefault();

        const formData = new FormData(this);
        const patientId = formData.get('patient_id');
        const departmentId = formData.get('department_id');
        const isEmergency = formData.get('is_emergency') === 'on';
        const forceEntry = formData.get('force_entry') === 'on';

        if (!patientId || !departmentId) {
            Swal.fire({ title: 'حقول مطلوبة', text: 'يرجى ملء جميع الحقول المطلوبة', icon: 'warning' });
            return;
        }

        if (isEmergency && !formData.get('emergency_reason')) {
            Swal.fire({ title: 'حقول مطلوبة', text: 'يرجى إدخال سبب الطوارئ', icon: 'warning' });
            return;
        }

        if (forceEntry && !formData.get('force_entry_reason')) {
            Swal.fire({ title: 'حقول مطلوبة', text: 'يرجى إدخال سبب الدخول القوي', icon: 'warning' });
            return;
        }

        showConfirmModal(formData);
    });
}

function showConfirmModal(formData) {
    const patientSelect = document.getElementById('patient_id');
    const departmentSelect = document.getElementById('department_id');
    const doctorSelect = document.getElementById('doctor_id');
    const queueTypeSelect = document.getElementById('queue_type');
    const paymentStatusSelect = document.getElementById('payment_status');

    const patientText = patientSelect.options[patientSelect.selectedIndex].text;
    const departmentText = departmentSelect.options[departmentSelect.selectedIndex].text;
    const doctorText = doctorSelect.value ? doctorSelect.options[doctorSelect.selectedIndex].text : 'غير محدد';
    const queueTypeText = queueTypeSelect.options[queueTypeSelect.selectedIndex].text;
    const paymentStatusText = paymentStatusSelect.options[paymentStatusSelect.selectedIndex].text;

    let confirmInfo = `
        <div class="alert alert-info">
            <h6>تأكيد إضافة المريض للطابور</h6>
            <p><strong>المريض:</strong> ${window.escHtml(patientText)}</p>
            <p><strong>القسم:</strong> ${window.escHtml(departmentText)}</p>
            <p><strong>الطبيب:</strong> ${window.escHtml(doctorText)}</p>
            <p><strong>نوع الطابور:</strong> ${window.escHtml(queueTypeText)}</p>
            <p><strong>حالة الدفع:</strong> ${window.escHtml(paymentStatusText)}</p>
    `;

    if (formData.get('is_emergency') === 'on') {
        confirmInfo += `<p><strong>حالة الطوارئ:</strong> نعم - ${window.escHtml(formData.get('emergency_reason'))}</p>`;
    }

    if (formData.get('force_entry') === 'on') {
        confirmInfo += `<p><strong>الدخول القوي:</strong> نعم - ${window.escHtml(formData.get('force_entry_reason'))}</p>`;
    }

    if (formData.get('notes')) {
        confirmInfo += `<p><strong>ملاحظات:</strong> ${window.escHtml(formData.get('notes'))}</p>`;
    }

    confirmInfo += '</div>';

    document.getElementById('confirmInfo').innerHTML = confirmInfo;
    const modalEl = document.getElementById('confirmAddModal');
    if (modalEl && window.bootstrap) {
        bootstrap.Modal.getOrCreateInstance(modalEl).show();
    }
}

function submitForm() {
    const form = document.getElementById('addPatientForm');
    const formData = new FormData(form);

    const csrfEl = form.querySelector('input[name="csrf_token"]') || document.querySelector('meta[name="csrf-token"]');
    const csrfToken = csrfEl ? (csrfEl.value || csrfEl.content || '') : '';
    fetch(form.action, {
        method: 'POST',
        headers: Object.assign({ 'X-Requested-With': 'XMLHttpRequest' }, csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
        credentials: 'same-origin',
        body: formData
    })
    .then(response => {
        if (response.ok) {
            window.location.href = (window.API_ROUTES && window.API_ROUTES.reception_queue) || '/reception/queue';
        } else {
            throw new Error('Network response was not ok');
        }
    })
    .catch(error => {
        Swal.fire({ title: 'خطأ', text: 'حدث خطأ في إضافة المريض للطابور', icon: 'error' });
    });
}

document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('addPatientForm');
    if (!form) return;
    const inputs = form.querySelectorAll('input[required], select[required], textarea[required]');
    inputs.forEach(input => {
        input.addEventListener('blur', function() {
            if (!this.value) {
                this.classList.add('is-invalid');
            } else {
                this.classList.remove('is-invalid');
                this.classList.add('is-valid');
            }
        });
    });
});
