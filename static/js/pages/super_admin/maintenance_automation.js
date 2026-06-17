var __M = window.__M || [];
const saveBtn = document.getElementById('saveAutomation');
if (saveBtn) {
  saveBtn.addEventListener('click', async () => {
    const csrfToken = (document.querySelector('meta[name="csrf-token"]') || {}).content;
    const payload = {
      auto_cleanup: document.getElementById('auto_cleanup').value === 'true',
      cleanup_days: parseInt(document.getElementById('cleanup_days').value || '30', 10),
      log_retention_days: parseInt(document.getElementById('log_retention_days').value || '90', 10),
      auto_backup: document.getElementById('auto_backup').value === 'true'
    };
    const r = await fetch(__M0__, {
      method: 'POST',
      headers: Object.assign({ 'Content-Type': 'application/json' }, csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
      body: JSON.stringify(payload)
    });
    const data = await r.json().catch(() => ({}));
    if (r.ok && data.success) {
      alert('تم حفظ الإعدادات');
    } else {
      alert('تعذر الحفظ');
    }
  });
}
