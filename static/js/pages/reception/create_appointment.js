var __M = window.__M || [];
function saveAppointment() {
    const form = document.getElementById('appointmentForm');
    const formData = new FormData(form);
    
    if (!formData.get('patient_id') || !formData.get('doctor_id') || !formData.get('appointment_date') || !formData.get('appointment_time')) {
        Swal.fire({ title: 'حقول مطلوبة', text: 'يرجى ملء جميع الحقول المطلوبة', icon: 'warning' });
        return;
    }
    
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

const patientSearchEl = document.getElementById('patient_search');
if (patientSearchEl) {
    patientSearchEl.addEventListener('input', function() {
        const searchTerm = this.value.toLowerCase();
        const suggestions = document.getElementById('patient_suggestions');
        
        if (searchTerm.length < 2) {
            suggestions.style.display = 'none';
            return;
        }
        
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
            suggestions.innerHTML = '';
            matches.forEach(function(option) {
                var btn = document.createElement('div');
                btn.className = 'list-group-item';
                btn.dataset.patientId = option.value;
                btn.dataset.patientName = option.textContent;
                btn.textContent = option.textContent;
                btn.addEventListener('click', function() {
                    selectPatient(this.dataset.patientId, this.dataset.patientName);
                });
                suggestions.appendChild(btn);
            });
            suggestions.style.display = 'block';
        } else {
            suggestions.style.display = 'none';
        }
    });
}

(function preselectPatient(){
    const sel = document.getElementById('patient_id');
    if (sel && sel.value) {
        const opt = sel.selectedOptions[0];
        if (opt) {
            const ps = document.getElementById('patient_search');
            if (ps) ps.value = opt.dataset.name;
        }
    }
})();

function selectPatient(patientId, patientName) {
    document.getElementById('patient_id').value = patientId;
    document.getElementById('patient_search').value = patientName;
    document.getElementById('patient_suggestions').style.display = 'none';
}

document.addEventListener('click', function(e) {
    if (!e.target.closest('#patient_search') && !e.target.closest('#patient_suggestions')) {
        const suggestions = document.getElementById('patient_suggestions');
        if (suggestions) suggestions.style.display = 'none';
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
    fetch(((window.API_ROUTES && window.API_ROUTES.booking_available_doctors) || '/booking/api/available-doctors') + `?${params.toString()}`, { credentials: 'same-origin' })
        .then(response => {
            if (!response.ok) throw new Error(response.status);
            return response.json();
        })
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
            if (window.showToast) window.showToast('حدث خطأ أثناء تحميل البيانات');
            else alert('حدث خطأ أثناء تحميل البيانات');
        });
}

const appointmentTypeEl = document.getElementById('appointment_type');
if (appointmentTypeEl) appointmentTypeEl.addEventListener('change', loadDoctors);
const departmentIdEl = document.getElementById('department_id');
if (departmentIdEl) departmentIdEl.addEventListener('change', loadDoctors);

const doctorIdEl = document.getElementById('doctor_id');
if (doctorIdEl) {
    doctorIdEl.addEventListener('change', function() {
        const doctorId = this.value;
        const appointmentDate = document.getElementById('appointment_date').value;
        
        if (doctorId && appointmentDate) {
            fetch(((window.API_ROUTES && window.API_ROUTES.booking_available_times) || '/booking/api/available-times') + `?doctor_id=${doctorId}&date=${appointmentDate}`, { credentials: 'same-origin' })
            .then(response => {
                if (!response.ok) throw new Error(response.status);
                return response.json();
            })
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
                if (window.showToast) window.showToast('حدث خطأ أثناء تحميل البيانات');
                else alert('حدث خطأ أثناء تحميل البيانات');
            });
        }
    });
}

const appointmentDateEl = document.getElementById('appointment_date');
if (appointmentDateEl) {
    appointmentDateEl.addEventListener('change', function() {
        const doctorId = document.getElementById('doctor_id').value;
        const appointmentDate = this.value;
        
        if (doctorId && appointmentDate) {
            fetch(((window.API_ROUTES && window.API_ROUTES.booking_available_times) || '/booking/api/available-times') + `?doctor_id=${doctorId}&date=${appointmentDate}`, { credentials: 'same-origin' })
            .then(response => {
                if (!response.ok) throw new Error(response.status);
                return response.json();
            })
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
                if (window.showToast) window.showToast('حدث خطأ أثناء تحميل البيانات');
                else alert('حدث خطأ أثناء تحميل البيانات');
            });
        }
    });
}

document.addEventListener('DOMContentLoaded', function() {
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
        const aptDate = document.getElementById('appointment_date');
        if (aptDate) aptDate.min = today;
    }
});
