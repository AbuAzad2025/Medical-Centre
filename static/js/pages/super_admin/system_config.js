var __M = window.__M || [];
function saveSettings() {
    const forms = ['generalSettingsForm', 'securitySettingsForm', 'databaseSettingsForm', 'notificationsSettingsForm', 'backupSettingsForm'];
    const settings = {};
    forms.forEach(formId => {
        const form = document.getElementById(formId);
        if (form) {
            const elements = form.querySelectorAll('input, select, textarea');
            elements.forEach(el => {
                const key = el.name || el.id;
                if (!key) return;
                if (el.type === 'checkbox') {
                    settings[key] = el.checked;
                } else {
                    settings[key] = el.value;
                }
            });
        }
    });
    fetch(__M0__, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(settings)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            Swal.fire({ title: 'تم', text: 'تم حفظ الإعدادات بنجاح', icon: 'success' });
        } else {
            Swal.fire({ title: 'خطأ', text: 'حدث خطأ في حفظ الإعدادات', icon: 'error' });
        }
    })
    .catch(error => {
        console.error('Error:', error);
        Swal.fire({ title: 'خطأ', text: 'حدث خطأ في حفظ الإعدادات', icon: 'error' });
    });
}

function resetSettings() {
    // إعادة تعيين الإعدادات
    Swal.fire({
        title: 'تأكيد',
        text: 'هل تريد إعادة تعيين جميع الإعدادات إلى القيم الافتراضية؟',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'نعم، إعادة',
        cancelButtonText: 'إلغاء'
    }).then((result) => { if (result.isConfirmed) { location.reload(); } });
}

function testConnection() {
    // اختبار اتصال قاعدة البيانات
    const dbSettings = {
        host: document.getElementById('db_host').value,
        port: document.getElementById('db_port').value,
        name: document.getElementById('db_name').value,
        username: document.getElementById('db_username').value,
        password: document.getElementById('db_password').value
    };
    
    fetch(__M1__ + '?action=test_db', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(dbSettings)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            Swal.fire({ title: 'تم', text: 'تم الاتصال بقاعدة البيانات بنجاح', icon: 'success' });
        } else {
            Swal.fire({ title: 'فشل', text: 'فشل الاتصال بقاعدة البيانات: ' + (data.message || ''), icon: 'error' });
        }
    })
    .catch(error => {
        console.error('Error:', error);
        Swal.fire({ title: 'خطأ', text: 'حدث خطأ في اختبار الاتصال', icon: 'error' });
    });
}

// تحميل الإعدادات عند فتح الصفحة
document.addEventListener('DOMContentLoaded', function() {
    // تحميل الإعدادات الحالية
    fetch(__M2__ + '?action=load')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // تطبيق الإعدادات على النماذج
                Object.keys(data.settings).forEach(key => {
                    const element = document.getElementById(key);
                    if (element) {
                        const val = data.settings[key];
                        if (element.type === 'checkbox') {
                            const s = String(val).toLowerCase();
                            element.checked = (s === 'true' || s === '1' || s === 'yes' || s === 'on');
                        } else {
                            element.value = val;
                        }
                    }
                });
            }
        })
        .catch(error => {
            console.error('Error loading settings:', error);
        });

    fetch(__M3__ + '?action=load')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const tbody = document.querySelector('#deptQueueTable tbody');
                tbody.innerHTML = '';
                data.items.forEach(item => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td data-id="${item.department_id}">${item.department_name}</td>
                        <td><input type="number" class="dept-max" value="${item.max_queue_size}" min="1" style="width:100px"></td>
                        <td><input type="checkbox" class="dept-required" ${item.payment_required ? 'checked' : ''}></td>
                        <td><input type="checkbox" class="dept-emergency-waived" ${item.emergency_payment_waived ? 'checked' : ''}></td>
                        <td><input type="checkbox" class="dept-force" ${item.force_entry_allowed ? 'checked' : ''}></td>
                        <td><input type="number" class="dept-avg" value="${item.average_wait_time}" min="5" max="240" style="width:120px"></td>
                        <td><input type="checkbox" class="dept-partial" ${item.allow_partial_payment ? 'checked' : ''}></td>
                        <td><input type="checkbox" class="dept-debt" ${item.allow_debt ? 'checked' : ''}></td>
                    `;
                    tbody.appendChild(tr);
                });
            }
        })
        .catch(function(err) { console.error('خطأ:', err); });

    document.getElementById('saveDeptQueueSettings').addEventListener('click', function() {
        const rows = document.querySelectorAll('#deptQueueTable tbody tr');
        const items = [];
        rows.forEach(row => {
            const deptId = parseInt(row.querySelector('td[data-id]').getAttribute('data-id'));
            const maxSize = parseInt(row.querySelector('.dept-max').value || '0');
            const paymentRequired = row.querySelector('.dept-required').checked;
            const emergencyWaived = row.querySelector('.dept-emergency-waived').checked;
            const forceAllowed = row.querySelector('.dept-force').checked;
            const avgWait = parseInt(row.querySelector('.dept-avg').value || '0');
            const allowPartial = row.querySelector('.dept-partial').checked;
            const allowDebt = row.querySelector('.dept-debt').checked;
            items.push({ department_id: deptId, max_queue_size: maxSize, payment_required: paymentRequired, emergency_payment_waived: emergencyWaived, force_entry_allowed: forceAllowed, average_wait_time: avgWait, allow_partial_payment: allowPartial, allow_debt: allowDebt });
        });
        fetch(__M4__, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ items })
        })
        .then(r => r.json())
        .then(d => { if (d.success) { Swal.fire({ title: 'تم', text: 'تم حفظ إعدادات الأقسام بنجاح', icon: 'success' }); } else { Swal.fire({ title: 'خطأ', text: 'فشل حفظ إعدادات الأقسام', icon: 'error' }); } })
        .catch(function(err) { console.error('خطأ:', err); });
    });
});
