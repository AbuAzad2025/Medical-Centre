export function deletePricing(priceId) {
    const cleanId = String(priceId == null ? '' : priceId).replace(/\D/g, '');
    if (!cleanId) {
        Swal.fire({ title: 'خطأ', text: 'معرف التسعيرة غير صالح', icon: 'error' });
        return;
    }
    Swal.fire({
        title: 'تأكيد',
        text: 'هل أنت متأكد من حذف هذه التسعيرة؟',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'نعم، احذف',
        cancelButtonText: 'إلغاء'
    }).then((result) => {
        if (!result.isConfirmed) return;
        const csrfToken = (document.querySelector('meta[name="csrf-token"]') || {}).content || '';
        fetch('/super-admin/service-pricing/delete/' + cleanId, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'X-CSRFToken': csrfToken, 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'text/html' },
        })
        .then((resp) => {
            if (resp.ok || resp.redirected) {
                location.reload();
                return;
            }
            Swal.fire({ title: 'خطأ', text: 'تعذر حذف التسعيرة (' + resp.status + ')', icon: 'error' });
        })
        .catch(() => Swal.fire({ title: 'خطأ', text: 'فشل الاتصال بالخادم', icon: 'error' }));
    });
}


// Backward compatibility
if (typeof deletePricing !== "undefined") window.deletePricing = deletePricing;

export {};
