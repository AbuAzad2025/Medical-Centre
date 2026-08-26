var __M = window.__M || [];
document.getElementById('registerBtn').addEventListener('click', async function() {
  var btn = this;
  if (btn.disabled) return;
  btn.disabled = true;
  var origText = btn.textContent;
  btn.textContent = 'جاري المعالجة...';
  try {
    var csrfEl = document.querySelector('meta[name="csrf-token"]');
    var csrfToken = csrfEl ? csrfEl.content : '';
    const resp = await fetch(__M0__, {method: 'POST', credentials: 'same-origin', headers: {'X-CSRFToken': csrfToken, 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'}});
    const data = await resp.json();
    document.getElementById('registerResult').innerHTML = '<div class="alert alert-success">تم إرسال التحدي. أكمل التسجيل عبر المتصفح.</div>';
    if(window.showToast) window.showToast('تم إرسال التحدي','success');
  } catch(e) {
    document.getElementById('registerResult').innerHTML = '<div class="alert alert-danger">خطأ: ' + window.escHtml(e.message || 'فشل التسجيل') + '</div>';
    if(window.showToast) window.showToast('فشل التسجيل: ' + window.escHtml(e.message || ''),'error');
  } finally {
    btn.disabled = false;
    btn.textContent = origText;
  }
});
