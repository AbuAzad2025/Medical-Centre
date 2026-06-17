function deletePricing(pricingId) {
    Swal.fire({
        title: 'تأكيد',
        text: 'هل أنت متأكد من حذف هذا التسعير؟',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'نعم، حذف',
        cancelButtonText: 'إلغاء'
    }).then((r) => { if (r.isConfirmed) { Swal.fire({ title: 'قريباً', text: 'سيتم تفعيل الحذف قريباً', icon: 'info' }); } });
}
