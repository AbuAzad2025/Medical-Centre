// إظهار/إخفاء حقول الطوارئ
document.getElementById('is_emergency').addEventListener('change', function() {
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

// إظهار/إخفاء حقول الدخول القوي
document.getElementById('force_entry').addEventListener('change', function() {
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

// تحديث الأطباء عند تغيير القسم
document.getElementById('department_id').addEventListener('change', function() {
    const departmentId = this.value;
    const doctorSelect = document.getElementById('doctor_id');
    
    if (departmentId) {
        // جلب الأطباء للقسم المحدد
        fetch(`/reception/api/doctors?department_id=${departmentId}`)
            .then(response => response.json())
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
                console.error('Error:', error);
            });
    } else {
        doctorSelect.innerHTML = '<option value="">اختر الطبيب</option>';
    }
});

// معالجة النموذج
document.getElementById('addPatientForm').addEventListener('submit', function(e) {
    e.preventDefault();
    
    // جمع البيانات
    const formData = new FormData(this);
    const patientId = formData.get('patient_id');
    const departmentId = formData.get('department_id');
    const isEmergency = formData.get('is_emergency') === 'on';
    const forceEntry = formData.get('force_entry') === 'on';
    
    // التحقق من البيانات المطلوبة
    if (!patientId || !departmentId) {
        Swal.fire({ title: 'حقول مطلوبة', text: 'يرجى ملء جميع الحقول المطلوبة', icon: 'warning' });
        return;
    }
    
    // التحقق من الطوارئ
    if (isEmergency && !formData.get('emergency_reason')) {
        Swal.fire({ title: 'حقول مطلوبة', text: 'يرجى إدخال سبب الطوارئ', icon: 'warning' });
        return;
    }
    
    // التحقق من الدخول القوي
    if (forceEntry && !formData.get('force_entry_reason')) {
        Swal.fire({ title: 'حقول مطلوبة', text: 'يرجى إدخال سبب الدخول القوي', icon: 'warning' });
        return;
    }
    
    // عرض نافذة التأكيد
    showConfirmModal(formData);
});

// عرض نافذة التأكيد
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
            <p><strong>المريض:</strong> ${patientText}</p>
            <p><strong>القسم:</strong> ${departmentText}</p>
            <p><strong>الطبيب:</strong> ${doctorText}</p>
            <p><strong>نوع الطابور:</strong> ${queueTypeText}</p>
            <p><strong>حالة الدفع:</strong> ${paymentStatusText}</p>
    `;
    
    if (formData.get('is_emergency') === 'on') {
        confirmInfo += `<p><strong>حالة الطوارئ:</strong> نعم - ${formData.get('emergency_reason')}</p>`;
    }
    
    if (formData.get('force_entry') === 'on') {
        confirmInfo += `<p><strong>الدخول القوي:</strong> نعم - ${formData.get('force_entry_reason')}</p>`;
    }
    
    if (formData.get('notes')) {
        confirmInfo += `<p><strong>ملاحظات:</strong> ${formData.get('notes')}</p>`;
    }
    
    confirmInfo += '</div>';
    
    document.getElementById('confirmInfo').innerHTML = confirmInfo;
    $('#confirmAddModal').modal('show');
}

// إرسال النموذج
function submitForm() {
    const form = document.getElementById('addPatientForm');
    const formData = new FormData(form);
    
    fetch(form.action, {
        method: 'POST',
        body: formData
    })
    .then(response => {
        if (response.ok) {
            window.location.href = '/reception/queue';
        } else {
            throw new Error('Network response was not ok');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        Swal.fire({ title: 'خطأ', text: 'حدث خطأ في إضافة المريض للطابور', icon: 'error' });
    });
}

// تحميل أولي
$(document).ready(function() {
    // إضافة التحقق من صحة النموذج
    const form = document.getElementById('addPatientForm');
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
