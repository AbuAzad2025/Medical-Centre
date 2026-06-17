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
    const r = await fetch(__M0__, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items })
    });
    const data = await r.json().catch(() => ({}));
    if (data.success) {
      alert('تم حفظ القوالب');
    } else {
      alert('تعذر الحفظ');
    }
  });
}
