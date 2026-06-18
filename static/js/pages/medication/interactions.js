var __M = window.__M || [];
const csrfToken = __M0__;
async function toggleInteraction(id) {
  try {
    const res = await fetch(`/medication/interactions/${id}/toggle`, { method: 'POST', headers: { 'X-CSRFToken': csrfToken } });
    if (res.ok) location.reload();
  } catch (err) {
    console.error('فشل تبديل حالة التفاعل:', err);
  }
}
