document.addEventListener('DOMContentLoaded', function() {
    const form = document.querySelector('form');
    if (!form) return;
    const inputs = form.querySelectorAll('input, textarea');

    setInterval(function() {
  function notifyErr(msg) {
    if (window.showToast) window.showToast(msg || 'حدث خطأ', 'error');
    else console.warn('[doctor-page]', msg);
  }

        const formData = new FormData(form);
        const csrfEl = form.querySelector('input[name="csrf_token"]') || document.querySelector('meta[name="csrf-token"]');
        const csrfToken = csrfEl ? (csrfEl.value || csrfEl.content || '') : '';
        fetch(form.action, {
            method: 'POST',
            body: formData,
            credentials: 'same-origin',
            headers: Object.assign({ 'X-Requested-With': 'XMLHttpRequest' }, csrfToken ? { 'X-CSRFToken': csrfToken } : {})
        }).then(response => {
            if (!response.ok) throw new Error(response.status);
        }).catch(error => {
            if (window.showToast) window.showToast('حدث خطأ أثناء تحميل البيانات');
            else notifyErr('حدث خطأ أثناء تحميل البيانات');
        });
    }, 30000);

    inputs.forEach(input => {
        input.addEventListener('input', function() {
            form.classList.add('dirty');
        });
    });

    window.addEventListener('beforeunload', function(e) {
        if (form.classList.contains('dirty')) {
            e.preventDefault();
            e.returnValue = '';
        }
    });
});
