(function() {
    function confirmAction(message, onConfirm) {
        var msg = message || 'هل أنت متأكد؟';
        if (window.Swal && typeof window.Swal.fire === 'function') {
            window.Swal.fire({
                title: 'تأكيد',
                text: msg,
                icon: 'warning',
                showCancelButton: true,
                confirmButtonText: 'نعم',
                cancelButtonText: 'إلغاء',
            }).then(function(res) { if (res.isConfirmed) onConfirm(); });
            return;
        }
        if (window.confirm(msg)) onConfirm();
    }

    document.addEventListener('click', function(e) {
        var el = e.target.closest('[data-action]');
        if (!el) return;
        var action = el.dataset.action;
        switch (action) {
            case 'print': window.print(); return;
            case 'go-back': history.back(); return;
            case 'reload': location.reload(); return;
            case 'close-modal':
                var m = el.closest('.modal');
                if (m) { var bs = bootstrap.Modal.getInstance(m); if (bs) bs.hide(); }
                return;
            case 'submit-form':
                var f = el.closest('form');
                if (f) f.submit();
                return;
            case 'confirm':
                e.preventDefault();
                confirmAction(el.dataset.message, function() {
                    var f = el.closest('form');
                    if (f) f.submit(); else if (el.href) location.href = el.href;
                });
                return;
            case 'confirm-submit':
                e.preventDefault();
                confirmAction(el.dataset.message, function() {
                    var f = el.closest('form');
                    if (f) f.submit();
                });
                return;
            case 'confirm-navigate':
                e.preventDefault();
                confirmAction(el.dataset.message, function() {
                    if (el.href) location.href = el.href;
                });
                return;
            case 'toggle-password':
                var t = document.getElementById(el.dataset.target);
                if (t) {
                    var isPwd = t.getAttribute('type') === 'password';
                    t.setAttribute('type', isPwd ? 'text' : 'password');
                }
                return;
        }
        if (action.indexOf('filter-') === 0) {
            var fnName = action.charAt(7).toUpperCase() + action.slice(8);
            fnName = fnName.replace(/-([a-z])/g, function(_, c) { return c.toUpperCase(); });
            fnName = 'filter' + fnName.charAt(0).toUpperCase() + fnName.slice(1);
            var fn = window[fnName];
            if (typeof fn === 'function') { fn(el.dataset.value); return; }
            fnName = action.replace(/-([a-z])/g, function(_, c) { return c.toUpperCase(); });
            fn = window[fnName];
            if (typeof fn === 'function') { fn(el.dataset.value); return; }
        }
        var fn = window[action];
        if (typeof fn === 'function') {
            var idKeys = [];
            for (var k in el.dataset) {
                if (k !== 'action' && k !== 'value' && k !== 'message' && k !== 'target' && k !== 'text') {
                    idKeys.push(k);
                }
            }
            if (idKeys.length === 1) {
                fn(el.dataset[idKeys[0]]);
            } else if (el.dataset.value !== undefined && el.dataset.text !== undefined) {
                fn(el.dataset.value, el.dataset.text);
            } else if (el.dataset.value !== undefined) {
                fn(el.dataset.value);
            } else if (el.dataset.message !== undefined) {
                fn(el.dataset.message);
            } else {
                fn();
            }
            return;
        }
        var camelName = action.replace(/-([a-z])/g, function(_, c) { return c.toUpperCase(); });
        var fn2 = window[camelName];
        if (typeof fn2 === 'function') {
            if (el.dataset.value !== undefined) fn2(el.dataset.value);
            else if (el.dataset.id !== undefined) fn2(el.dataset.id);
            else fn2();
        }
    });
})();
