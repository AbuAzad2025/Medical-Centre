function togglePassword(fieldId) {
    const field = document.getElementById(fieldId);
    const button = field.nextElementSibling;
    const icon = button.querySelector('i');
    
    if (field.type === 'password') {
        field.type = 'text';
        icon.classList.remove('fa-eye');
        icon.classList.add('fa-eye-slash');
    } else {
        field.type = 'password';
        icon.classList.remove('fa-eye-slash');
        icon.classList.add('fa-eye');
    }
}

// التحقق من تطابق كلمات المرور
document.getElementById('confirm_password').addEventListener('input', function() {
    const password = document.getElementById('password').value;
    const confirmPassword = this.value;
    
    if (password !== confirmPassword) {
        this.setCustomValidity('كلمات المرور غير متطابقة');
    } else {
        this.setCustomValidity('');
    }
});

// التحقق من قوة كلمة المرور
document.getElementById('password').addEventListener('input', function() {
    const password = this.value;
    const strength = checkPasswordStrength(password);
    
    // إضافة مؤشر قوة كلمة المرور
    let strengthIndicator = document.getElementById('password-strength');
    if (!strengthIndicator) {
        strengthIndicator = document.createElement('div');
        strengthIndicator.id = 'password-strength';
        strengthIndicator.className = 'mt-2';
        this.parentNode.appendChild(strengthIndicator);
    }
    
    strengthIndicator.innerHTML = `
        <div class="progress h-5">
            <div class="progress-bar ${strength.color}" style="width: ${strength.percentage}%"></div>
        </div>
        <small class="text-${strength.color}">${strength.text}</small>
    `;
});

function checkPasswordStrength(password) {
    let score = 0;
    let feedback = [];
    
    if (password.length >= 8) score++;
    else feedback.push('8 أحرف على الأقل');
    
    if (/[a-z]/.test(password)) score++;
    else feedback.push('أحرف صغيرة');
    
    if (/[A-Z]/.test(password)) score++;
    else feedback.push('أحرف كبيرة');
    
    if (/[0-9]/.test(password)) score++;
    else feedback.push('أرقام');
    
    if (/[^A-Za-z0-9]/.test(password)) score++;
    else feedback.push('رموز خاصة');
    
    if (score >= 4) {
        return { percentage: 100, color: 'success', text: 'قوية جداً' };
    } else if (score >= 3) {
        return { percentage: 75, color: 'info', text: 'قوية' };
    } else if (score >= 2) {
        return { percentage: 50, color: 'warning', text: 'متوسطة' };
    } else {
        return { percentage: 25, color: 'danger', text: 'ضعيفة' };
    }
}

// منع إرسال النموذج إذا كانت كلمات المرور غير متطابقة
document.getElementById('createUserForm').addEventListener('submit', function(e) {
    const password = document.getElementById('password').value;
    const confirmPassword = document.getElementById('confirm_password').value;
    
    if (password !== confirmPassword) {
        e.preventDefault();
        Swal.fire({ title: 'تحذير', text: 'كلمات المرور غير متطابقة', icon: 'warning' });
        return false;
    }
});

const roleSelect = document.getElementById('role');
const doctorPricingSection = document.getElementById('doctorPricingSection');
function toggleDoctorPricing() {
    doctorPricingSection.style.display = roleSelect.value === 'doctor' ? '' : 'none';
}
roleSelect.addEventListener('change', toggleDoctorPricing);
toggleDoctorPricing();
