/**
 * SweetAlert2 helpers for API feedback (§35.5).
 */
(function (global) {
    function swal() {
        return global.Swal || null;
    }

    function showApiSuccess(title, text) {
        const S = swal();
        if (S) {
            S.fire({ title: title || 'تم', text: text || '', icon: 'success' });
            return;
        }
        alert(text || title || 'تم');
    }

    function showApiError(title, text) {
        const S = swal();
        if (S) {
            S.fire({ title: title || 'تنبيه', text: text || '', icon: 'error' });
            return;
        }
        alert(text || title || 'حدث خطأ');
    }

    function showApiWarning(title, text) {
        const S = swal();
        if (S) {
            S.fire({ title: title || 'تنبيه', text: text || '', icon: 'warning' });
            return;
        }
        alert(text || title || 'تنبيه');
    }

    global.showApiSuccess = showApiSuccess;
    global.showApiError = showApiError;
    global.showApiWarning = showApiWarning;
})(window);
