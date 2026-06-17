var __M = window.__M || [];
function saveAppointment() {
    const form = document.getElementById('appointmentForm');
    const formData = new FormData(form);
    
    // التحقق من صحة البيانات
    if (!formData.get('patient_id') || !formData.get('doctor_id') || !formData.get('appointment_date') || !formData.get('appointment_time')) {
        Swal.fire({ title: 'حقول مطلوبة', text: 'يرجى ملء جميع الحقول المطلوبة', icon: 'warning' });
        return;
    }
    
    // التحقق من تاريخ الموعد
    const appointmentDate = new Date(formData.get('appointment_date'));
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    
    if (appointmentDate < today) {
        Swal.fire({ title: 'تاريخ غير صالح', text: 'لا يمكن حجز موعد في تاريخ ماضي', icon: 'error' });
        return;
    }
    
    form.submit();
}

function resetForm() {
    // إعادة تعيين النموذج
    Swal.fire({
        title: 'إعادة تعيين',
        text: 'هل تريد إعادة تعيين النموذج؟',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'تأكيد',
        cancelButtonText: 'إلغاء'
    }).then((res) => {
        if (res.isConfirmed) {
            document.getElementById('appointmentForm').reset();
        }
    });
}

// البحث عن المريض
document.getElementById('patient_search').addEventListener('input', function() {
    const searchTerm = this.value.toLowerCase();
    const suggestions = document.getElementById('patient_suggestions');
    
    if (searchTerm.length < 2) {
        suggestions.style.display = 'none';
        return;
    }
    
    // البحث في قائمة المرضى
    const patients = document.querySelectorAll('#patient_id option');
    let matches = [];
    
    patients.forEach(option => {
        if (option.value && (
            option.textContent.toLowerCase().includes(searchTerm) ||
            option.dataset.name.toLowerCase().includes(searchTerm) ||
            option.dataset.phone.includes(searchTerm) ||
            option.dataset.nationalId.includes(searchTerm)
        )) {
            matches.push(option);
        }
    });
    
    if (matches.length > 0) {
        suggestions.innerHTML = matches.map(option => 
            `<div class="list-group-item" onclick="selectPatient('${option.value}', '${option.textContent}')">
                ${option.textContent}
            </div>`
        ).join('');
        suggestions.style.display = 'block';
    } else {
        suggestions.style.display = 'none';
    }
});

// ضبط اختيار المريض مسبقاً إن وُجد
(function preselectPatient(){
    const sel = document.getElementById('patient_id');
    if (sel && sel.value) {
        const opt = sel.selectedOptions[0];
        if (opt) {
            document.getElementById('patient_search').value = opt.dataset.name;
        }
    }
})();

function selectPatient(patientId, patientName) {
    document.getElementById('patient_id').value = patientId;
    document.getElementById('patient_search').value = patientName;
    document.getElementById('patient_suggestions').style.display = 'none';
}

// إخفاء اقتراحات البحث عند النقر خارجها
document.addEventListener('click', function(e) {
    if (!e.target.closest('#patient_search') && !e.target.closest('#patient_suggestions')) {
        document.getElementById('patient_suggestions').style.display = 'none';
    }
});

function loadDoctors() {
    const appointmentType = document.getElementById('appointment_type').value;
    const departmentId = document.getElementById('department_id').value;
    const doctorSelect = document.getElementById('doctor_id');
    doctorSelect.innerHTML = '<option value="">اختر الطبيب</option>';
    const params = new URLSearchParams();
    if (appointmentType) params.append('appointment_type', appointmentType);
    if (departmentId) params.append('department_id', departmentId);
    fetch(`/booking/api/available-doctors?${params.toString()}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                data.doctors.forEach(doctor => {
                    const option = document.createElement('option');
                    option.value = doctor.id;
                    option.textContent = doctor.full_name;
                    doctorSelect.appendChild(option);
                });
            }
        })
        .catch(error => {
            console.error('Error loading doctors:', error);
        });
}

// حدّث الأطباء عند تغيير نوع الموعد أو القسم
document.getElementById('appointment_type').addEventListener('change', loadDoctors);
document.getElementById('department_id').addEventListener('change', loadDoctors);

// تحديث وقت الموعد بناءً على الطبيب المحدد
document.getElementById('doctor_id').addEventListener('change', function() {
    const doctorId = this.value;
    const appointmentDate = document.getElementById('appointment_date').value;
    
    if (doctorId && appointmentDate) {
        // جلب الأوقات المتاحة للطبيب في التاريخ المحدد
        fetch(`/booking/api/available-times?doctor_id=${doctorId}&date=${appointmentDate}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const timeSelect = document.getElementById('appointment_time');
                timeSelect.innerHTML = '';
                
                data.available_times.forEach(time => {
                    const option = document.createElement('option');
                    option.value = time;
                    option.textContent = time;
                    timeSelect.appendChild(option);
                });
            }
        })
        .catch(error => {
            console.error('Error loading available times:', error);
        });
    }
});

// تحديث الأوقات المتاحة عند تغيير التاريخ
document.getElementById('appointment_date').addEventListener('change', function() {
    const doctorId = document.getElementById('doctor_id').value;
    const appointmentDate = this.value;
    
    if (doctorId && appointmentDate) {
        // جلب الأوقات المتاحة للطبيب في التاريخ المحدد
        fetch(`/booking/api/available-times?doctor_id=${doctorId}&date=${appointmentDate}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const timeSelect = document.getElementById('appointment_time');
                timeSelect.innerHTML = '';
                
                data.available_times.forEach(time => {
                    const option = document.createElement('option');
                    option.value = time;
                    option.textContent = time;
                    timeSelect.appendChild(option);
                });
            }
        })
        .catch(error => {
            console.error('Error loading available times:', error);
        });
    }
});

// إضافة تأثيرات تفاعلية
document.addEventListener('DOMContentLoaded', function() {
    // إضافة تأثير focus للحقول
    const inputs = document.querySelectorAll('.form-control');
    inputs.forEach(input => {
        input.addEventListener('focus', function() {
            this.parentElement.classList.add('focused');
        });
        input.addEventListener('blur', function() {
            this.parentElement.classList.remove('focused');
        });
    });
    
    const isEdit = __M0__;
    if (!isEdit) {
        const today = new Date().toISOString().split('T')[0];
        document.getElementById('appointment_date').min = today;
    }
});
