var __M = window.__M || [];

function saveBranding() {
    const form = document.getElementById('brandingForm');
    const formData = new FormData(form);

    fetch(__M0__, {
        method: 'POST',
        body: formData,
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'same-origin',
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            Swal.fire({ title: 'تم', text: 'تم حفظ إعدادات العلامة التجارية بنجاح', icon: 'success' }).then(() => {
                reloadPrintPreview();
            });
        } else {
            Swal.fire({ title: 'خطأ', text: data.error || 'حدث خطأ في حفظ الإعدادات', icon: 'error' });
        }
    })
    .catch(() => {
        form.submit();
    });
}

function resetBranding() {
    Swal.fire({
        title: 'تأكيد',
        text: 'هل تريد إعادة تعيين جميع إعدادات العلامة التجارية إلى القيم الافتراضية؟',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'نعم، إعادة',
        cancelButtonText: 'إلغاء'
    }).then((res) => { if (res.isConfirmed) { location.reload(); } });
}

function selectTheme(themeId) {
    const body = new FormData();
    body.append('csrf_token', typeof __CSRF__ !== 'undefined' ? __CSRF__ : '');

    fetch(`${__M2__}/${themeId}`, {
        method: 'POST',
        body: body,
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'same-origin',
    })
    .then(r => r.json())
    .then(data => {
        if (!data.success) {
            Swal.fire({ title: 'خطأ', text: data.error || 'تعذر تطبيق الثيم', icon: 'error' });
            return;
        }
        const colors = data.colors || {};
        ['primary_color', 'secondary_color', 'accent_color'].forEach(key => {
            const input = document.getElementById(key);
            const preview = document.getElementById(key.replace('_color', '-preview'));
            if (input && colors[key]) input.value = colors[key];
            if (preview && colors[key]) preview.style.backgroundColor = colors[key];
        });
        Swal.fire({ title: 'تم', text: 'تم تطبيق ألوان الثيم — احفظ لإبقاء التغييرات', icon: 'success' });
    })
    .catch(err => {
        console.error(err);
        Swal.fire({ title: 'خطأ', text: 'تعذر تطبيق الثيم', icon: 'error' });
    });
}

function reloadPrintPreview() {
    const frame = document.getElementById('printPreviewFrame');
    if (!frame) return;
    const active = document.querySelector('#docTypeTabs .nav-link.active');
    const docType = active ? active.getAttribute('data-doc-type') : 'invoice';
    frame.src = `${__M1__}?doc_type=${docType}&_=${Date.now()}`;
}

function showDocFields(docType) {
    document.querySelectorAll('.doc-fields').forEach(el => {
        el.classList.toggle('d-none', el.getAttribute('data-doc') !== docType);
    });
}

document.getElementById('primary_color').addEventListener('change', function() {
    document.getElementById('primary-preview').style.backgroundColor = this.value;
});

document.getElementById('secondary_color').addEventListener('change', function() {
    document.getElementById('secondary-preview').style.backgroundColor = this.value;
});

document.getElementById('accent_color').addEventListener('change', function() {
    document.getElementById('accent-preview').style.backgroundColor = this.value;
});

document.getElementById('logo_file').addEventListener('change', function() {
    const file = this.files[0];
    if (file) {
        const reader = new FileReader();
        reader.onload = function(e) {
            const logoPreview = document.querySelector('.logo-preview');
            logoPreview.innerHTML = `<img src="${e.target.result}" alt="الشعار" class="img-thumbnail" style="max-height: 100px;">`;
        };
        reader.readAsDataURL(file);
    }
});

document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.theme-card').forEach(card => {
        card.addEventListener('mouseenter', function() { this.style.transform = 'translateY(-2px)'; });
        card.addEventListener('mouseleave', function() { this.style.transform = 'translateY(0)'; });
    });

    document.querySelectorAll('#docTypeTabs .nav-link').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('#docTypeTabs .nav-link').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            const docType = this.getAttribute('data-doc-type');
            showDocFields(docType);
            const frame = document.getElementById('printPreviewFrame');
            if (frame) frame.src = `${__M1__}?doc_type=${docType}&_=${Date.now()}`;
        });
    });

    const firstDoc = document.querySelector('#docTypeTabs .nav-link.active');
    if (firstDoc) showDocFields(firstDoc.getAttribute('data-doc-type'));
});
