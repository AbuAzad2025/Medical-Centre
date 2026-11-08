export function optimizeDatabase() {
    Swal.fire({
        title: 'تأكيد',
        text: 'سيتم تنفيذ VACUUM ANALYZE على الجداول النشطة لتحسين الأداء. قد تستغرق العملية وقتاً وقد تُبطئ القاعدة مؤقتاً.',
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: 'نعم',
        cancelButtonText: 'إلغاء'
    }).then((result) => {
        if (!result.isConfirmed) return;
        const csrfToken = (document.querySelector('meta[name="csrf-token"]') || {}).content || '';
        const url = (window.API_ROUTES && window.API_ROUTES.optimize_database) || '/super-admin/system/optimize-database';
        fetch(url, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrfToken, 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin'
        })
        .then(r => r.json().then(d => ({ ok: r.ok, d })))
        .then(({ ok, d }) => {
            if (ok && d && d.success) {
                Swal.fire({ title: 'تم', text: d.message || 'تم تحسين قاعدة البيانات', icon: 'success' });
            } else {
                Swal.fire({ title: 'خطأ', text: (d && d.message) || 'حدث خطأ أثناء تحسين قاعدة البيانات', icon: 'error' });
            }
        })
        .catch(() => Swal.fire({ title: 'خطأ', text: 'فشل الاتصال بالخادم', icon: 'error' }));
    });
}

export function forceLogoutAll() {
    Swal.fire({
        title: 'تأكيد',
        text: 'سيتم إجبار جميع المستخدمين على تسجيل الخروج من جميع الجلسات. قد تؤدي العملية إلى فقدان بيانات غير محفوظة لدى الآخرين.',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'نعم',
        cancelButtonText: 'إلغاء'
    }).then((result) => {
        if (!result.isConfirmed) return;
        const csrfToken = (document.querySelector('meta[name="csrf-token"]') || {}).content || '';
        const url = (window.API_ROUTES && window.API_ROUTES.force_logout_all) || '/super-admin/system/force-logout-all';
        fetch(url, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrfToken, 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin'
        })
        .then(r => r.json().then(d => ({ ok: r.ok, d })))
        .then(({ ok, d }) => {
            if (ok && d && d.success) {
                Swal.fire({ title: 'تم', text: d.message || 'تم إجبار الجميع على تسجيل الخروج', icon: 'success' }).then(() => location.reload());
            } else {
                Swal.fire({ title: 'خطأ', text: (d && d.message) || 'حدث خطأ في تنفيذ العملية', icon: 'error' });
            }
        })
        .catch(() => Swal.fire({ title: 'خطأ', text: 'فشل الاتصال بالخادم', icon: 'error' }));
    });
}

export function refreshLogs() {
    location.reload();
}

export function clearLogs() {
    Swal.fire({
        title: 'تأكيد',
        text: 'سيتم حذف سجلات التدقيق القديمة وفق سياسة الاحتفاظ. لن يمكن التراجع عن هذا الإجراء.',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'نعم، مسح',
        cancelButtonText: 'إلغاء'
    }).then((result) => {
        if (!result.isConfirmed) return;
        const csrfToken = (document.querySelector('meta[name="csrf-token"]') || {}).content || '';
        const url = (window.API_ROUTES && window.API_ROUTES.system_cleanup) || '/super-admin/system/cleanup';
        const body = new FormData();
        body.append('cleanup_type', 'logs');
        fetch(url, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrfToken, 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin',
            body
        })
        .then(r => {
            if (!r.ok) throw new Error('http_' + r.status);
            return r;
        })
        .then(() => {
            Swal.fire({ title: 'تم', text: 'تم مسح السجلات القديمة', icon: 'success' }).then(() => refreshLogs());
        })
        .catch(() => Swal.fire({ title: 'خطأ', text: 'حدث خطأ في مسح السجلات', icon: 'error' }));
    });
}

export function loadSystemStatus() {
    const el = document.getElementById('systemStatusIndicator');
    fetch((window.API_ROUTES && window.API_ROUTES.health) || '/health', { headers: { 'X-Requested-With': 'XMLHttpRequest' }, credentials: 'same-origin' })
        .then(r => r.json())
        .then(data => {
            if (!el) return;
            const dbOk = data.database === 'connected';
            const redisOk = data.redis === 'connected' || data.redis === 'unavailable';
            const overallOk = data.status === 'healthy';
            el.className = 'badge ' + (overallOk ? 'bg-success' : 'bg-danger');
            el.textContent = overallOk ? 'النظام سليم' : 'النظام يعاني من خلل';
            el.title = `DB: ${data.database} | Redis: ${data.redis} | v${data.version || '?'}`;
        })
        .catch(() => { console.warn('فشل في تحميل حالة النظام'); });
}

setInterval(function() {
    loadSystemStatus();
}, 30000);

document.addEventListener('DOMContentLoaded', function() {
    loadSystemStatus();
});

// Backward compatibility
if (typeof clearLogs !== "undefined") window.clearLogs = clearLogs;
if (typeof forceLogoutAll !== "undefined") window.forceLogoutAll = forceLogoutAll;
if (typeof loadSystemStatus !== "undefined") window.loadSystemStatus = loadSystemStatus;
if (typeof refreshLogs !== "undefined") window.refreshLogs = refreshLogs;
if (typeof optimizeDatabase !== "undefined") window.optimizeDatabase = optimizeDatabase;

export {};
