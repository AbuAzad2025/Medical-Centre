var __M = window.__M || [];
// طباعة بيانات الحالة
    function printEmergency() {
        window.print();
    }
    
    // تصدير بيانات الحالة
    function exportEmergency() {
        // يمكن إضافة وظيفة التصدير هنا
        console.log('تصدير بيانات حالة الطوارئ');
    }
    
    // مشاركة بيانات الحالة
    function shareEmergency() {
        // يمكن إضافة وظيفة المشاركة هنا
        console.log('مشاركة بيانات حالة الطوارئ');
    }

    document.addEventListener('DOMContentLoaded', function() {
        var form = document.getElementById('convertForm');
        if (form) {
            form.addEventListener('submit', function(e) {
                e.preventDefault();
                var data = new FormData(form);
                fetch(form.action, { 
                        method: 'POST', 
                        body: data 
                    })
                    .then(function(r){ return r.json(); })
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
