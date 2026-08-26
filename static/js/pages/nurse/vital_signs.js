document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('vitalSignsForm');
    if (!form) return;

    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        const formData = new FormData(form);
        const csrf = formData.get('csrf_token') || '';
        const submitBtn = form.querySelector('button[type="submit"]');
        if (submitBtn) submitBtn.disabled = true;
        try {
            const response = await fetch(form.action, {
                method: 'POST',
                body: formData,
                credentials: 'same-origin',
                headers: {
                    'X-CSRFToken': csrf,
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            if (!response.ok) throw new Error(response.status);
            const result = await response.json();
            if (result && result.success) {
                window.location.reload();
            } else {
                alert((result && result.message) ? result.message : 'حدث خطأ');
            }
        } catch (err) {
            alert('حدث خطأ');
        } finally {
            if (submitBtn) submitBtn.disabled = false;
        }
    });
});
