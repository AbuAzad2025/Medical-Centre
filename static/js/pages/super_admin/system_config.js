var __M = window.__M || [];
const csrfToken = (document.querySelector('meta[name="csrf-token"]') || {}).content;
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
        headers: Object.assign({ 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' }, csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
        credentials: 'same-origin',
        body: JSON.stringify(settings)
    })
    .then(response => {
        if (!response.ok) throw new Error('http_' + response.status);
        return response.json();
    })
    .then(data => {
        if (data.success) {
            Swal.fire({ title: 'تم', text: 'تم حفظ الإعدادات بنجاح', icon: 'success' });
        } else {
            Swal.fire({ title: 'خطأ', text: 'حدث خطأ في حفظ الإعدادات', icon: 'error' });
        }
    })
    .catch(error => {
        Swal.fire({ title: 'خطأ', text: 'حدث خطأ في حفظ الإعدادات', icon: 'error' });
    });
}

function resetSettings() {
    Swal.fire({
        title: 'تأكيد',
        text: 'هل تريد إعادة تعيين جميع الإعدادات إلى القيم الافتراضية؟',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'نعم، إعادة',
        cancelButtonText: 'إلغاء'
    }).then((result) => { if (result.isConfirmed) { location.reload(); } });
}

function testSmsConnection() {
    const testPhone = prompt('أدخل رقم الهاتف المرسل إليه (مثال: +970599123456):');
    if (!testPhone) return;
    fetch(__M5__, {
        method: 'POST',
        headers: Object.assign({ 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' }, csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
        credentials: 'same-origin',
        body: JSON.stringify({ phone_number: testPhone })
    })
    .then(r => {
        if (!r.ok) throw new Error('http_' + r.status);
        return r.json();
    })
    .then(d => {
        Swal.fire({ title: d.success ? 'تم' : 'فشل', text: d.message, icon: d.success ? 'success' : 'error' });
    })
    .catch(err => {
        Swal.fire({ title: 'خطأ', text: 'حدث خطأ في إرسال الرسالة', icon: 'error' });
    });
}

function processNotificationQueue() {
    fetch(__M6__, {
        method: 'POST',
        headers: Object.assign({ 'X-Requested-With': 'XMLHttpRequest' }, csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
        credentials: 'same-origin'
    })
    .then(r => {
        if (!r.ok) throw new Error('http_' + r.status);
        return r.json();
    })
    .then(d => {
        Swal.fire({ title: d.success ? 'تم' : 'خطأ', text: d.message, icon: d.success ? 'success' : 'error' });
    })
    .catch(err => {
        Swal.fire({ title: 'خطأ', text: 'حدث خطأ في معالجة الطابور', icon: 'error' });
    });
}

document.addEventListener('DOMContentLoaded', function() {
    const providerSelect = document.getElementById('sms_provider');
    if (providerSelect) {
        providerSelect.addEventListener('change', function() {
            const twilioSettings = document.getElementById('twilioSettings');
            if (this.value === 'twilio') {
                twilioSettings.style.display = 'block';
            } else {
                twilioSettings.style.display = 'none';
            }
        });
        if (providerSelect.value === 'twilio') {
            const twilioSettings = document.getElementById('twilioSettings');
            if (twilioSettings) twilioSettings.style.display = 'block';
        }
    }
});

function testConnection() {
    const dbSettings = {
        host: document.getElementById('db_host').value,
        port: document.getElementById('db_port').value,
        name: document.getElementById('db_name').value,
        username: document.getElementById('db_username').value,
        password: document.getElementById('db_password').value
    };
    
    fetch(__M1__ + '?action=test_db', {
        method: 'POST',
        headers: Object.assign({ 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' }, csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
        credentials: 'same-origin',
        body: JSON.stringify(dbSettings)
    })
    .then(response => {
        if (!response.ok) throw new Error('http_' + response.status);
        return response.json();
    })
    .then(data => {
        if (data.success) {
            Swal.fire({ title: 'تم', text: 'تم الاتصال بقاعدة البيانات بنجاح', icon: 'success' });
        } else {
            Swal.fire({ title: 'فشل', text: 'فشل الاتصال بقاعدة البيانات: ' + (data.message || ''), icon: 'error' });
        }
    })
    .catch(error => {
        Swal.fire({ title: 'خطأ', text: 'حدث خطأ في اختبار الاتصال', icon: 'error' });
    });
}

document.addEventListener('DOMContentLoaded', function() {
    fetch(__M2__ + '?action=load', { credentials: 'same-origin' })
        .then(response => {
            if (!response.ok) throw new Error('http_' + response.status);
            return response.json();
        })
        .then(data => {
            if (data.success) {
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
            if (window.showToast) window.showToast('حدث خطأ أثناء تحميل البيانات'); else alert('حدث خطأ أثناء تحميل البيانات');
        });

    fetch(__M3__ + '?action=load', { credentials: 'same-origin' })
        .then(response => {
            if (!response.ok) throw new Error('http_' + response.status);
            return response.json();
        })
        .then(data => {
            if (data.success) {
                const tbody = document.querySelector('#deptQueueTable tbody');
                tbody.innerHTML = '';
                data.items.forEach(item => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td data-id="${item.department_id}">${window.escHtml(String(item.department_name || ''))}</td>
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
        .catch(function(err) {
            if (window.showToast) window.showToast('حدث خطأ أثناء تحميل البيانات'); else alert('حدث خطأ أثناء تحميل البيانات');
        });

    const saveDeptQueueSettingsEl = document.getElementById('saveDeptQueueSettings');
    if (saveDeptQueueSettingsEl) {
        saveDeptQueueSettingsEl.addEventListener('click', function() {
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
                headers: Object.assign({ 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' }, csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
                credentials: 'same-origin',
                body: JSON.stringify({ items })
            })
            .then(r => {
                if (!r.ok) throw new Error('http_' + r.status);
                return r.json();
            })
            .then(d => { if (d.success) { Swal.fire({ title: 'تم', text: 'تم حفظ إعدادات الأقسام بنجاح', icon: 'success' }); } else { Swal.fire({ title: 'خطأ', text: 'فشل حفظ إعدادات الأقسام', icon: 'error' }); } })
            .catch(function(err) {
                if (window.showToast) window.showToast('حدث خطأ أثناء حفظ الإعدادات'); else alert('حدث خطأ أثناء تحميل البيانات');
            });
        });
    }
});
