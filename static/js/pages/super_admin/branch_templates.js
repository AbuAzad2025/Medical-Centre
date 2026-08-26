var __M = window.__M || [];
const saveBtn = document.getElementById('saveTemplates');
if (saveBtn) {
  saveBtn.addEventListener('click', async () => {
    let items = [];
    try {
      items = JSON.parse(document.getElementById('templatesJson').value || '[]');
    } catch (e) {
      alert('صيغة JSON غير صحيحة');
      return;
    }
    const csrfToken = (document.querySelector('meta[name="csrf-token"]') || {}).content;
    try {
      const r = await fetch(__M0__, {
        method: 'POST',
        headers: Object.assign({ 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' }, csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
        credentials: 'same-origin',
        body: JSON.stringify({ items })
      });
      if (!r.ok) throw new Error('http_' + r.status);
      const data = await r.json().catch(() => ({}));
      if (data.success) {
        alert('تم حفظ القوالب');
      } else {
        alert('تعذر الحفظ');
      }
    } catch (e) {
      if (window.showToast) window.showToast('حدث خطأ أثناء حفظ القوالب'); else alert('حدث خطأ أثناء تحميل البيانات');
    }
  });
}
