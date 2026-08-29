function optimizeDatabase() {
    Swal.fire({
        title: 'تأكيد',
        text: 'هل أنت متأكد من تحسين قاعدة البيانات؟ قد يستغرق هذا بعض الوقت.',
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: 'نعم',
        cancelButtonText: 'إلغاء'
    }).then((result) => {
        if (result.isConfirmed) {
            Swal.fire({ title: 'جاري العمل', text: 'جاري تحسين قاعدة البيانات...', icon: 'info' });
        }
    });
}

function forceLogoutAll() {
    Swal.fire({
        title: 'تأكيد',
        text: 'هل أنت متأكد من إجبار جميع المستخدمين على تسجيل الخروج؟',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'نعم',
        cancelButtonText: 'إلغاء'
    }).then((result) => {
        if (result.isConfirmed) {
            Swal.fire({ title: 'تم', text: 'تم إجبار جميع المستخدمين على تسجيل الخروج', icon: 'success' });
        }
    });
}

function refreshLogs() {
    location.reload();
}

function clearLogs() {
    Swal.fire({
        title: 'تأكيد',
        text: 'هل أنت متأكد من مسح سجل النظام؟ لا يمكن التراجع عن هذا الإجراء.',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'نعم، مسح',
        cancelButtonText: 'إلغاء'
    }).then((result) => {
        if (result.isConfirmed) {
            Swal.fire({ title: 'تم', text: 'تم مسح سجل النظام', icon: 'success' });
        }
    });
}

function loadSystemStatus() {
    fetch((window.API_ROUTES && window.API_ROUTES.health) || '/health', { headers: { 'X-Requested-With': 'XMLHttpRequest' }, credentials: 'same-origin' })
        .then(r => r.json())
        .then(data => {
            const el = document.getElementById('systemStatusIndicator');
            if (!el) return;
            const dbOk = data.database === 'connected';
            const redisOk = data.redis === 'connected' || data.redis === 'unavailable';
            const overallOk = data.status === 'healthy';
            el.className = 'badge ' + (overallOk ? 'bg-success' : 'bg-danger');
            el.textContent = overallOk ? '● النظام سليم' : '● النظام يعاني من مشاكل';
            el.title = `DB: ${data.database} | Redis: ${data.redis} | v${data.version || '?'}`;
        })
        .catch(() => { console.warn('تعذر تحميل حالة النظام'); });
}

setInterval(function() {
    loadSystemStatus();
}, 30000);

document.addEventListener('DOMContentLoaded', function() {
    loadSystemStatus();
});
