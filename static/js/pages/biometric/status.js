var __M = window.__M || [];
document.getElementById('registerBtn').addEventListener('click', async function() {
  try {
    const resp = await fetch(__M0__, {method: 'POST'});
    const data = await resp.json();
    // Simplified: in production, use fido2 library
    document.getElementById('registerResult').innerHTML = '<div class="alert alert-success">تم إرسال التحدي. أكمل التسجيل عبر المتصفح.</div>';
  } catch(e) {
    document.getElementById('registerResult').innerHTML = '<div class="alert alert-danger">خطأ: ' + e.message + '</div>';
  }
});
