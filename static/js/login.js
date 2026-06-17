document.getElementById('loginForm').addEventListener('submit', function(e) {
    const btn = document.getElementById('loginBtn');
    const text = btn.querySelector('.btn-text');
    const icon = btn.querySelector('.btn-icon');
    const loading = document.getElementById('loginLoading');
    text.style.display = 'none';
    if (icon) icon.style.display = 'none';
    loading.classList.add('show');
    btn.disabled = true;
});

const pwd = document.getElementById('password');
const toggle = document.getElementById('togglePassword');
const caps = document.getElementById('capsLock');
toggle.addEventListener('click', function() {
    const isPwd = pwd.getAttribute('type') === 'password';
    pwd.setAttribute('type', isPwd ? 'text' : 'password');
    this.setAttribute('aria-label', isPwd ? 'إخفاء كلمة المرور' : 'إظهار كلمة المرور');
    this.innerHTML = isPwd ? '<i class="fas fa-eye-slash"></i>' : '<i class="fas fa-eye"></i>';
});
pwd.addEventListener('keyup', function(e) {
    if (e.getModifierState && e.getModifierState('CapsLock')) {
        caps.style.display = 'block';
    } else {
        caps.style.display = 'none';
    }
});

document.querySelector('[data-action="forgot-password"]')?.addEventListener('click', function() {
    Swal.fire({
        title: '\u0627\u0633\u062A\u0639\u0627\u062F\u0629 \u0643\u0644\u0645\u0629 \u0627\u0644\u0645\u0631\u0648\u0631',
        text: '\u064A\u0631\u062C\u0649 \u0627\u0644\u062A\u0648\u0627\u0635\u0644 \u0645\u0639 \u0645\u062F\u064A\u0631 \u0627\u0644\u0646\u0638\u0627\u0645 \u0644\u0625\u0639\u0627\u062F\u0629 \u062A\u0639\u064A\u064A\u0646 \u0643\u0644\u0645\u0629 \u0627\u0644\u0645\u0631\u0648\u0631',
        icon: 'info'
    });
});
