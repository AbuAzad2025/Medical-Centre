function createPermission() {
    document.getElementById('modalTitle').textContent = 'إضافة صلاحية جديدة';
    document.getElementById('permissionForm').reset();
    document.getElementById('permissionModal').style.display = 'block';
}

function editPermission(id) {
    document.getElementById('modalTitle').textContent = 'تعديل الصلاحية';
    // هنا يمكن تحميل بيانات الصلاحية وتعبئة النموذج
    document.getElementById('permissionModal').style.display = 'block';
}

function deletePermission(id) {
    Swal.fire({
        title: 'تأكيد',
        text: 'هل أنت متأكد من حذف هذه الصلاحية؟',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'نعم، حذف',
        cancelButtonText: 'إلغاء'
    }).then((res) => {
        if (res.isConfirmed) {
            const form = document.createElement('form');
            form.method = 'POST';
            form.action = `/super-admin/permissions/${id}/delete`;
            const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
            const csrfInput = document.createElement('input');
            csrfInput.type = 'hidden';
            csrfInput.name = 'csrf_token';
            csrfInput.value = csrfToken;
            form.appendChild(csrfInput);
            document.body.appendChild(form);
            form.submit();
        }
    });
}

function closeModal() {
    document.getElementById('permissionModal').style.display = 'none';
}

// إغلاق النافذة المنبثقة عند النقر خارجها
window.onclick = function(event) {
    const modal = document.getElementById('permissionModal');
    if (event.target == modal) {
        closeModal();
    }
}
