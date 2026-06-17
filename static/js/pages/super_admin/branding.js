var __M = window.__M || [];
function saveBranding() {
    // حفظ إعدادات العلامة التجارية
    const form = document.getElementById('brandingForm');
    const formData = new FormData(form);
    
    fetch(__M0__, {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            Swal.fire({ title: 'تم', text: 'تم حفظ إعدادات العلامة التجارية بنجاح', icon: 'success' }).then(() => location.reload());
        } else {
            Swal.fire({ title: 'خطأ', text: 'حدث خطأ في حفظ الإعدادات', icon: 'error' });
        }
    })
    .catch(error => {
        console.error('Error:', error);
        Swal.fire({ title: 'خطأ', text: 'حدث خطأ في حفظ الإعدادات', icon: 'error' });
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
    Swal.fire({ title: 'تم', text: 'تم اختيار الثيم: ' + themeId, icon: 'success' });
}

// تحديث معاينة الألوان عند تغييرها
document.getElementById('primary_color').addEventListener('change', function() {
    document.getElementById('primary-preview').style.backgroundColor = this.value;
});

document.getElementById('secondary_color').addEventListener('change', function() {
    document.getElementById('secondary-preview').style.backgroundColor = this.value;
});

document.getElementById('accent_color').addEventListener('change', function() {
    document.getElementById('accent-preview').style.backgroundColor = this.value;
});

// معاينة الشعار عند اختيار ملف جديد
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

// إضافة تأثيرات تفاعلية
document.addEventListener('DOMContentLoaded', function() {
    // إضافة تأثير hover للثيمات
    const themeCards = document.querySelectorAll('.theme-card');
    themeCards.forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-2px)';
        });
        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
        });
    });
});
