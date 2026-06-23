var __M = window.__M || [];
document.getElementById('visitSummaryForm').addEventListener('submit', function(e) {
    e.preventDefault();

    const formData = new FormData(this);
    const notify = window.notify || {};

    fetch(__M0__, {
        method: 'POST',
        body: formData
    })
    .then(function (response) { return response.json(); })
    .then(function (data) {
        if (data.success) {
            if (typeof notify.success === 'function') {
                notify.success('تم حفظ ملخص الزيارة بنجاح');
            }
            window.location.href = __M1__;
            return;
        }
        const msg = (data && data.message) ? String(data.message) : 'تعذّر حفظ ملخص الزيارة. حاول مرة أخرى.';
        if (typeof notify.error === 'function') {
            notify.error(msg.indexOf('خطأ:') === 0 ? msg.replace(/^خطأ:\s*/, '') : msg);
        }
    })
    .catch(function () {
        if (typeof notify.error === 'function') {
            notify.error('انقطع الاتصال. تحقق من الشبكة وحاول مرة أخرى.');
        }
    });
});
