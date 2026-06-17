function createBackup() {
    Swal.fire({
        title: 'تأكيد',
        text: 'هل تريد إنشاء نسخة احتياطية للنظام؟',
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: 'نعم',
        cancelButtonText: 'إلغاء'
    }).then((result) => {
        if (result.isConfirmed) {
            const btn = event && event.target ? event.target.closest('button') : null;
            if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> جاري الإنشاء...'; }
            fetch('/super-admin/backup/create', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            })
            .then(r => r.json())
            .then(data => {
                if (data && data.success) {
                    Swal.fire({ title: 'تم', text: 'تم إنشاء النسخة الاحتياطية بنجاح', icon: 'success' }).then(() => { location.reload(); });
                } else {
                    Swal.fire({ title: 'خطأ', text: (data && data.message) || 'حدث خطأ في إنشاء النسخة الاحتياطية', icon: 'error' });
                }
                if (btn) { btn.disabled = false; }
            })
            .catch(() => {
                Swal.fire({ title: 'خطأ', text: 'حدث خطأ في الاتصال', icon: 'error' });
                if (btn) { btn.disabled = false; }
            });
        }
    });
}

function scheduleBackup() {
    Swal.showLoading();
    fetch('/super-admin/backup/schedule')
        .then(r => r.json())
        .then(data => {
            if (!data.success) throw new Error(data.message);
            
            Swal.fire({
                title: 'جدولة النسخ الاحتياطي',
                html: `
                    <div class="text-right text-start">
                        <div class="form-check mb-3">
                            <input class="form-check-input" type="checkbox" id="scheduleEnabled" ${data.enabled ? 'checked' : ''}>
                            <label class="form-check-label" for="scheduleEnabled">تفعيل الجدولة التلقائية</label>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">تكرار النسخ</label>
                            <select class="form-control" id="scheduleType">
                                <option value="daily" ${data.type === 'daily' ? 'selected' : ''}>يومي</option>
                                <option value="weekly" ${data.type === 'weekly' ? 'selected' : ''}>أسبوعي</option>
                                <option value="monthly" ${data.type === 'monthly' ? 'selected' : ''}>شهري</option>
                            </select>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">وقت التنفيذ</label>
                            <input type="time" class="form-control" id="scheduleTime" value="${data.time}">
                        </div>
                        <div class="alert alert-info small">
                            <i class="fas fa-info-circle"></i> ملاحظة: تتطلب الجدولة أن يكون الخادم قيد التشغيل في الوقت المحدد.
                        </div>
                    </div>
                `,
                showCancelButton: true,
                confirmButtonText: 'حفظ الإعدادات',
                cancelButtonText: 'إلغاء',
                preConfirm: () => {
                    return {
                        enabled: document.getElementById('scheduleEnabled').checked,
                        type: document.getElementById('scheduleType').value,
                        time: document.getElementById('scheduleTime').value
                    }
                }
            }).then((result) => {
                if (result.isConfirmed) {
                    Swal.showLoading();
                    fetch('/super-admin/backup/schedule', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(result.value)
                    })
                    .then(r => r.json())
                    .then(res => {
                        if (res.success) {
                            Swal.fire('تم', res.message, 'success');
                        } else {
                            Swal.fire('خطأ', res.message, 'error');
                        }
                    })
                    .catch(() => Swal.fire('خطأ', 'حدث خطأ في الاتصال', 'error'));
                }
            });
        })
        .catch(err => {
            Swal.fire('خطأ', 'فشل تحميل الإعدادات: ' + err.message, 'error');
        });
}

function createFullBackup() {
    Swal.fire({
        title: 'تأكيد',
        text: 'هل تريد إنشاء نسخة احتياطية كاملة؟ قد يستغرق هذا بعض الوقت.',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'بدء',
        cancelButtonText: 'إلغاء'
    }).then((result) => {
        if (result.isConfirmed) {
            const btn = event && event.target ? event.target.closest('button') : null;
            if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> جاري النسخ...'; }
            fetch('/super-admin/backup/create', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ type: 'full' })
            })
            .then(r => r.json())
            .then(data => {
                if (data && data.success) {
                    Swal.fire({ title: 'تم', text: 'تم إنشاء النسخة الكاملة بنجاح', icon: 'success' }).then(() => { location.reload(); });
                } else {
                    Swal.fire({ title: 'خطأ', text: (data && data.message) || 'حدث خطأ في إنشاء النسخة الاحتياطية', icon: 'error' });
                }
                if (btn) { btn.disabled = false; }
            })
            .catch(() => {
                Swal.fire({ title: 'خطأ', text: 'حدث خطأ في الاتصال', icon: 'error' });
                if (btn) { btn.disabled = false; }
            });
        }
    });
}

function createIncrementalBackup() {
    Swal.fire({
        title: 'تأكيد',
        text: 'هل تريد إنشاء نسخة احتياطية تدريجية (قاعدة البيانات فقط)؟',
        icon: 'info',
        showCancelButton: true,
        confirmButtonText: 'بدء',
        cancelButtonText: 'إلغاء'
    }).then((result) => {
        if (result.isConfirmed) {
            const btn = event && event.target ? event.target.closest('button') : null;
            if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> جاري النسخ...'; }
            fetch('/super-admin/backup/create', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ type: 'incremental' })
            })
            .then(r => r.json())
            .then(data => {
                if (data && data.success) {
                    Swal.fire({ title: 'تم', text: 'تم إنشاء النسخة التدريجية بنجاح', icon: 'success' }).then(() => { location.reload(); });
                } else {
                    Swal.fire({ title: 'خطأ', text: (data && data.message) || 'حدث خطأ في إنشاء النسخة', icon: 'error' });
                }
                if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fas fa-plus-circle me-2"></i> نسخة احتياطية تدريجية'; }
            })
            .catch(() => {
                Swal.fire({ title: 'خطأ', text: 'حدث خطأ في الاتصال', icon: 'error' });
                if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fas fa-plus-circle me-2"></i> نسخة احتياطية تدريجية'; }
            });
        }
    });
}

function createDatabaseBackup() {
    Swal.fire({
        title: 'تأكيد',
        text: 'هل تريد إنشاء نسخة احتياطية لقاعدة البيانات فقط؟',
        icon: 'info',
        showCancelButton: true,
        confirmButtonText: 'بدء',
        cancelButtonText: 'إلغاء'
    }).then((result) => {
        if (result.isConfirmed) {
            const btn = event && event.target ? event.target.closest('button') : null;
            if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> جاري النسخ...'; }
            fetch('/super-admin/backup/create', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ type: 'database' })
            })
            .then(r => r.json())
            .then(data => {
                if (data && data.success) {
                    Swal.fire({ title: 'تم', text: 'تم إنشاء نسخة قاعدة البيانات بنجاح', icon: 'success' }).then(() => { location.reload(); });
                } else {
                    Swal.fire({ title: 'خطأ', text: (data && data.message) || 'حدث خطأ في إنشاء النسخة', icon: 'error' });
                }
                if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fas fa-table me-2"></i> نسخة احتياطية لقاعدة البيانات'; }
            })
            .catch(() => {
                Swal.fire({ title: 'خطأ', text: 'حدث خطأ في الاتصال', icon: 'error' });
                if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fas fa-table me-2"></i> نسخة احتياطية لقاعدة البيانات'; }
            });
        }
    });
}

function createFilesBackup() {
    Swal.fire({
        title: 'تأكيد',
        text: 'هل تريد إنشاء نسخة احتياطية للملفات فقط؟',
        icon: 'info',
        showCancelButton: true,
        confirmButtonText: 'بدء',
        cancelButtonText: 'إلغاء'
    }).then((result) => {
        if (result.isConfirmed) {
            const btn = event && event.target ? event.target.closest('button') : null;
            if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> جاري النسخ...'; }
            fetch('/super-admin/backup/create', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ type: 'files' })
            })
            .then(r => r.json())
            .then(data => {
                if (data && data.success) {
                    Swal.fire({ title: 'تم', text: 'تم إنشاء نسخة الملفات بنجاح', icon: 'success' }).then(() => { location.reload(); });
                } else {
                    Swal.fire({ title: 'خطأ', text: (data && data.message) || 'حدث خطأ في إنشاء النسخة', icon: 'error' });
                }
                if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fas fa-folder me-2"></i> نسخة احتياطية للملفات'; }
            })
            .catch(() => {
                Swal.fire({ title: 'خطأ', text: 'حدث خطأ في الاتصال', icon: 'error' });
                if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fas fa-folder me-2"></i> نسخة احتياطية للملفات'; }
            });
        }
    });
}

function filterBackups(status) {
    const rows = document.querySelectorAll('#backupsTable tbody tr');
    
    rows.forEach(row => {
        if (status === 'all' || row.dataset.status === status) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
    
    // تحديث أزرار التصفية
    document.querySelectorAll('.btn-outline-primary, .btn-outline-success, .btn-outline-warning, .btn-outline-danger').forEach(btn => {
        btn.classList.remove('active');
    });
    
    event.target.classList.add('active');
}

function restoreBackup(backupId) {
    Swal.fire({
        title: 'تأكيد الاستعادة',
        text: 'سيتم استبدال البيانات الحالية. هل تريد المتابعة؟',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'نعم، استعادة',
        cancelButtonText: 'إلغاء'
    }).then((result) => {
        if (result.isConfirmed) {
            Swal.showLoading();
            fetch('/super-admin/backup/restore/' + backupId, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    Swal.fire('تم', data.message, 'success').then(() => location.reload());
                } else {
                    Swal.fire('خطأ', data.message, 'error');
                }
            })
            .catch(() => {
                Swal.fire('خطأ', 'حدث خطأ في الاتصال', 'error');
            });
        }
    });
}

function deleteBackup(backupId) {
    Swal.fire({
        title: 'حذف النسخة',
        text: 'هل تريد حذف هذه النسخة نهائياً؟',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'نعم، حذف',
        cancelButtonText: 'إلغاء'
    }).then((result) => {
        if (result.isConfirmed) {
            Swal.showLoading();
            fetch('/super-admin/backup/delete/' + backupId, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    Swal.fire('تم', data.message, 'success').then(() => location.reload());
                } else {
                    Swal.fire('خطأ', data.message, 'error');
                }
            })
            .catch(() => {
                Swal.fire('خطأ', 'حدث خطأ في الاتصال', 'error');
            });
        }
    });
}

function cancelBackup(backupId) {
    Swal.fire({
        title: 'إلغاء النسخ',
        text: 'هل تريد إلغاء عملية النسخ الاحتياطي؟ (سيتم وضع علامة "ملغى")',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'نعم، إلغاء',
        cancelButtonText: 'تراجع'
    }).then((result) => {
        if (result.isConfirmed) {
            Swal.showLoading();
            fetch('/super-admin/backup/cancel/' + backupId, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    Swal.fire('تم', data.message, 'success').then(() => location.reload());
                } else {
                    Swal.fire('خطأ', data.message, 'error');
                }
            })
            .catch(() => {
                Swal.fire('خطأ', 'حدث خطأ في الاتصال', 'error');
            });
        }
    });
}

function retryBackup(type) {
    let reqType = 'full';
    if (type === 'incremental' || type === 'INCREMENTAL') reqType = 'incremental';
    else if (type === 'differential' || type === 'DIFFERENTIAL') reqType = 'database'; // Defaulting to database

    Swal.fire({
        title: 'تأكيد إعادة المحاولة',
        text: 'هل تريد إعادة محاولة إنشاء النسخة الاحتياطية؟',
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: 'نعم، إعادة المحاولة',
        cancelButtonText: 'إلغاء'
    }).then((result) => {
        if (result.isConfirmed) {
            Swal.fire({
                title: 'جاري النسخ...',
                html: 'يرجى الانتظار بينما يتم إنشاء النسخة الاحتياطية.',
                allowOutsideClick: false,
                didOpen: () => {
                    Swal.showLoading();
                }
            });
            
            fetch('/super-admin/backup/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ type: reqType })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    Swal.fire('تم', 'تم إنشاء النسخة الاحتياطية بنجاح', 'success').then(() => location.reload());
                } else {
                    Swal.fire('خطأ', data.message || 'حدث خطأ غير معروف', 'error');
                }
            })
            .catch(() => Swal.fire('خطأ', 'حدث خطأ في الاتصال', 'error'));
        }
    });
}

function saveBackupSettings() {
    Swal.fire({
        title: 'حفظ الإعدادات',
        text: 'هل تريد حفظ إعدادات النسخ الاحتياطي؟',
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: 'حفظ',
        cancelButtonText: 'إلغاء'
    }).then((result) => {
        if (result.isConfirmed) {
            const form = document.getElementById('backupSettingsForm');
            const formData = new FormData(form);
            const data = {};
            formData.forEach((value, key) => data[key] = value);
            // Handle checkbox manually because unchecked checkboxes are not included in FormData
            data['auto_backup'] = document.getElementById('auto_backup').checked;

            Swal.showLoading();
            fetch('/super-admin/backup/settings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            })
            .then(r => r.json())
            .then(response => {
                if (response.success) {
                    Swal.fire('تم', response.message, 'success');
                } else {
                    Swal.fire('خطأ', response.message, 'error');
                }
            })
            .catch(() => {
                Swal.fire('خطأ', 'حدث خطأ في الاتصال', 'error');
            });
        }
    });
}

function generateBackupReport() {
    window.location.href = '/super-admin/backup/report';
}

function exportBackupLogs() {
    window.location.href = '/super-admin/backup/export-logs';
}

function viewBackupHistory() {
    Swal.showLoading();
    fetch('/super-admin/backup/history')
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            let html = '<div class="text-start" class="scrollable-400"><ul class="list-group">';
            if (data.history.length === 0) {
                html += '<li class="list-group-item text-center text-muted">لا توجد سجلات</li>';
            } else {
                data.history.forEach(item => {
                    let badgeClass = 'secondary';
                    if (item.status === 'COMPLETED') badgeClass = 'success';
                    else if (item.status === 'FAILED') badgeClass = 'danger';
                    else if (item.status === 'IN_PROGRESS') badgeClass = 'warning';
                    
                    html += `
                        <li class="list-group-item d-flex justify-content-between align-items-center">
                            <div>
                                <span class="badge bg-${badgeClass} me-2">${item.status}</span>
                                <span>${item.type}</span>
                            </div>
                            <small class="text-muted" dir="ltr">${item.created_at}</small>
                        </li>
                    `;
                });
            }
            html += '</ul></div>';
            
            Swal.fire({
                title: 'تاريخ النسخ الاحتياطي',
                html: html,
                width: '600px',
                confirmButtonText: 'إغلاق'
            });
        } else {
            Swal.fire('خطأ', data.message, 'error');
        }
    })
    .catch(() => Swal.fire('خطأ', 'حدث خطأ في الاتصال', 'error'));
}

// إضافة تأثيرات تفاعلية
document.addEventListener('DOMContentLoaded', function() {
    // إضافة تأثير hover للصفوف
    const rows = document.querySelectorAll('#backupsTable tbody tr');
    rows.forEach(row => {
        row.addEventListener('mouseenter', function() {
            this.style.backgroundColor = '#f8f9fa';
        });
        row.addEventListener('mouseleave', function() {
            this.style.backgroundColor = '';
        });
    });
});
