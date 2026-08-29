var __M = window.__M || [];

    function printEmergency() {
        window.print();
    }

    function exportEmergency() {

    }

    function shareEmergency() {

    }

    document.addEventListener('DOMContentLoaded', function() {
        var form = document.getElementById('convertForm');
        if (form) {
            form.addEventListener('submit', function(e) {
                e.preventDefault();
                var data = new FormData(form);
                var csrfEl = form.querySelector('input[name="csrf_token"]') || document.querySelector('meta[name="csrf-token"]');
                var csrfToken = csrfEl ? (csrfEl.value || csrfEl.content || '') : '';
                fetch(form.action, {
                        method: 'POST',
                        credentials: 'same-origin',
                        headers: Object.assign({ 'X-Requested-With': 'XMLHttpRequest' }, csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
                        body: data
                    })
                    .then(function(r){
                        if (!r.ok) throw new Error(r.status);
                        return r.json();
                    })
                    .then(function(j){
                        if (j && j.success) {
                            Swal.fire({ title: 'تم', text: 'تم نقل الحالة بنجاح', icon: 'success' }).then(() => {
                                window.location.href = __M0__;
                            });
                        } else {
                            Swal.fire({ title: 'خطأ', text: (j && j.message) ? j.message : 'فشل نقل الحالة', icon: 'error' });
                        }
                    })
                    .catch(function(){ Swal.fire({ title: 'خطأ', text: 'حدث خطأ أثناء النقل', icon: 'error' }); });
            });
        }
    });
